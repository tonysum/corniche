#!/usr/bin/env python3
"""
黑马监控程序 - 多策略增强版
支持三种黑马监控策略：
1. 小时黑马：基于小时主动买量暴涨（相对昨日平均）
2. 5分钟黑马：基于5分钟主动买量暴涨（相对昨日平均）
3. 日黑马：基于日线主动买量暴涨（可选）

运行方式：
  python hmjk_enhanced.py                    # 运行一次检测（三种策略）
  python hmjk_enhanced.py --monitor          # 持续监控模式
  python hmjk_enhanced.py --strategy hour    # 只运行小时黑马
  python hmjk_enhanced.py --strategy 5m      # 只运行5分钟黑马
  python hmjk_enhanced.py --check-signals    # 检查待建仓信号

更新时间：2026-01-14
"""

import os
import sys
import time
import json
import logging
import psycopg2
import argparse
import requests
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from db import engine

# 加载 .env 配置文件
load_dotenv()

# PID 文件路径
PID_FILE = '/tmp/hmjk_enhanced.pid'

def check_and_create_pid():
    """
    检查是否已有实例运行，如果没有则创建PID文件
    防止程序重复启动
    """
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            old_pid = int(f.read().strip())
        
        # 检查进程是否还在运行
        try:
            os.kill(old_pid, 0)  # 不会真的杀进程，只是检查是否存在
            print(f"❌ hmjk_enhanced.py 已在运行 (PID: {old_pid})")
            print(f"   如需强制启动，请先执行: kill {old_pid}")
            sys.exit(1)
        except OSError:
            # 进程不存在，删除旧的PID文件
            print(f"⚠️  清理旧的PID文件 (进程 {old_pid} 已不存在)")
            os.remove(PID_FILE)
    
    # 创建新的PID文件
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    # 注册退出时删除PID文件
    atexit.register(lambda: os.remove(PID_FILE) if os.path.exists(PID_FILE) else None)
    print(f"✅ hmjk_enhanced.py 启动成功 (PID: {os.getpid()})")
    print(f"   PID文件: {PID_FILE}")

# 导入通知系统
try:
    from notifier import Notifier
    HAS_NOTIFIER = True
except ImportError:
    HAS_NOTIFIER = False
    logging.warning("未找到通知模块，将不发送通知")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hmjk_enhanced.log'),
        logging.StreamHandler()
    ]
)

# 信号文件路径
SIGNALS_FILE = "hm_signals_multi.json"  # 多策略信号文件

# Binance API配置
BINANCE_API_BASE = "https://fapi.binance.com"

# ==================== 小时黑马策略参数（hm1.py） ====================
HOUR_BUY_SURGE_THRESHOLD = 2.0          # 小时买量暴涨阈值（2倍昨日平均）
HOUR_BUY_SURGE_MAX = 3.0                # 小时买量暴涨上限（3倍，超过则不建仓）
HOUR_PRE_SIGNAL_SURGE_THRESHOLD = 48.5  # 信号前1小时价格暴涨阈值（%）
# 小时黑马等待回调规则版本（用于兼容/迁移历史信号）
HOUR_RULE_VERSION = 2
HOUR_WAIT_DROP_CONFIG = [
    (3, -0.15),     # 2-3倍：等待15%回调（与hm1.py一致）
    (5, -0.04),     # 3-5倍：等待4%回调（与hm1.py一致）
    (10, -0.03),    # 5-10倍：等待3%回调
]
HOUR_SIGNAL_TIMEOUT_HOURS = 48

# ==================== 5分钟黑马策略参数（hm500.py） ====================
MIN5_BUY_SURGE_MIN = 200                # 5分钟买量暴涨最小倍数
MIN5_BUY_SURGE_MAX = 10000              # 5分钟买量暴涨最大倍数
MIN5_WAIT_DROP_CONFIG = [
    (100, -0.01),   # <100倍：等待1%回调
    (300, -0.13),   # 100-300倍：等待13%回调
    (500, -0.10),   # 300-500倍：等待10%回调
    (10000, 0.00),  # 500倍以上：立即建仓
]
MIN5_SIGNAL_TIMEOUT_HOURS = 24

# ==================== 通用参数 ====================
BASE_TAKE_PROFIT = 0.10
STOP_LOSS_PCT = -0.28
ADD_POSITION_TRIGGER = -0.18
MAX_HOLD_HOURS = 72


class MultiStrategyMonitor:
    """多策略黑马监控器"""
    
    def __init__(self, strategies=['hour', '5m']):
        """
        初始化监控器
        Args:
            strategies: 启用的策略列表，可选 ['hour', '5m', 'day']
        """
        # 使用 db.py 中定义的 SQLAlchemy engine
        self.engine = engine
        logging.info(f"✅ 成功连接到 PostgreSQL 数据库 (via SQLAlchemy)")

        self.strategies = strategies
        self.signals = self.load_signals()
        
        # 初始化通知系统
        if HAS_NOTIFIER:
            self.notifier = Notifier()
        else:
            self.notifier = None
    
    def __del__(self):
        """析构函数"""
        pass
    
    def load_signals(self) -> List[Dict]:
        """加载待建仓信号"""
        if os.path.exists(SIGNALS_FILE):
            try:
                with open(SIGNALS_FILE, 'r', encoding='utf-8') as f:
                    signals = json.load(f)
                    # 兼容历史数据：将 >10倍 的小时黑马标记为高风险仅观察，避免继续走“等待回调/建仓”流程
                    for s in signals:
                        try:
                            if s.get('strategy') == 'hour':
                                ratio = float(s.get('buy_surge_ratio', 0) or 0)
                                if ratio > HOUR_BUY_SURGE_MAX:
                                    s['tradeable'] = False
                                    s['status'] = 'high_risk'
                                    s['note'] = f'超过{HOUR_BUY_SURGE_MAX}倍，风险过高，仅观察不建仓'
                                    s.pop('entry_price', None)
                                    s.pop('entry_time', None)
                                    continue

                                # 兼容历史信号：旧规则里 2-3倍可能是“立即建仓(0回调)”
                                # 现在按 hm1 规则改为等待回调，因此需要把旧信号的目标价/状态一并迁移
                                old_ver = int(s.get('rule_version', 0) or 0)
                                if old_ver < HOUR_RULE_VERSION and ratio >= HOUR_BUY_SURGE_THRESHOLD:
                                    new_drop = self.get_wait_drop_pct(ratio, HOUR_WAIT_DROP_CONFIG)
                                    s['target_drop_pct'] = new_drop
                                    # 历史信号中 signal_price 记录的是发现时的价格，用它回算迁移后的建仓价更合理
                                    sp = float(s.get('signal_price', 0) or 0)
                                    if sp > 0:
                                        s['target_price'] = sp * (1 + new_drop)
                                    s['rule_version'] = HOUR_RULE_VERSION

                                    # 如果旧信号已经被标成 ready（旧规则=立即建仓），在新规则下应回退为 waiting
                                    if s.get('status') == 'ready' and new_drop < 0:
                                        s['status'] = 'waiting'
                                        s.pop('entry_price', None)
                                        s.pop('entry_time', None)
                                        s['note'] = f'规则更新：{HOUR_BUY_SURGE_THRESHOLD:.0f}-{HOUR_BUY_SURGE_MAX:.0f}倍按hm1等待回调，新目标为{abs(new_drop)*100:.0f}%'
                        except Exception:
                            continue
                    return signals
            except:
                return []
        return []
    
    def save_signals(self):
        """保存待建仓信号"""
        with open(SIGNALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.signals, f, ensure_ascii=False, indent=2)
    
    def get_all_usdt_symbols(self) -> List[str]:
        """获取所有USDT交易对 (从数据库表列表中获取)"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE :prefix
                    ORDER BY table_name
                """), {"prefix": "K1h%"})
                tables = result.fetchall()
            
            symbols = [
                row[0].replace('K1h', '') 
                for row in tables 
                if row[0].replace('K1h', '').endswith('USDT')
            ]
            
            logging.info(f"从数据库获取到 {len(symbols)} 个USDT交易对")
            return symbols
        except Exception as e:
            logging.error(f"从数据库获取交易对列表失败: {e}")
            return []
    
    def download_latest_kline(self, symbol: str, interval: str, limit: int = 50) -> Optional[pd.DataFrame]:
        """从数据库读取最新的K线数据
        Args:
            symbol: 交易对
            interval: K线间隔（'1h', '5m'）
            limit: 获取条数
        """
        try:
            # 映射 interval 到表前缀
            prefix = 'K1h' if interval == '1h' else 'K5m'
            table_name = f"{prefix}{symbol}"
            safe_table_name = f'"{table_name}"'
            
            with self.engine.connect() as conn:
                query = f"""
                    SELECT * FROM {safe_table_name}
                    ORDER BY trade_date DESC
                    LIMIT :limit
                """
                result = conn.execute(text(query), {"limit": limit})
                data = result.fetchall()
                
                if not data:
                    return None
                
                # 获取列名
                columns = result.keys()
                df = pd.DataFrame(data, columns=columns)
                
                # 按时间正序排列
                df = df.sort_values('trade_date').reset_index(drop=True)
                
                # 转换数据类型以兼容原逻辑
                # 数据库中的 trade_date 可能是字符串，原逻辑期望 open_time 是 datetime
                if 'open_time' in df.columns:
                    # 如果 open_time 是 BIGINT (ms)，则转换
                    if df['open_time'].dtype == 'int64':
                        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
                    else:
                        df['open_time'] = pd.to_datetime(df['open_time'])
                else:
                    # 只有 trade_date 时
                    df['open_time'] = pd.to_datetime(df['trade_date'])
                
                # 确保 active_buy_volume 存在
                if 'active_buy_volume' not in df.columns and 'taker_buy_volume' in df.columns:
                    df['active_buy_volume'] = df['taker_buy_volume'].astype(float)
                elif 'active_buy_volume' in df.columns:
                    df['active_buy_volume'] = df['active_buy_volume'].astype(float)
                
                # 转换其他列为 float
                float_cols = ['open', 'high', 'low', 'close', 'volume']
                for col in float_cols:
                    if col in df.columns:
                        df[col] = df[col].astype(float)
                
                return df
                
        except Exception as e:
            logging.debug(f"从数据库读取 {symbol} {interval} K线失败: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前价格 (优先从数据库获取最新K线收盘价)"""
        try:
            # 优先尝试从5分钟K线获取最新价格
            table_name = f"K5m{symbol}"
            safe_table_name = f'"{table_name}"'
            
            with self.engine.connect() as conn:
                query = f"SELECT close FROM {safe_table_name} ORDER BY trade_date DESC LIMIT 1"
                result = conn.execute(text(query))
                row = result.fetchone()
                if row:
                    return float(row[0])
            
            # 如果没有5分钟K线，尝试从1小时K线获取
            table_name = f"K1h{symbol}"
            safe_table_name = f'"{table_name}"'
            with self.engine.connect() as conn:
                query = f"SELECT close FROM {safe_table_name} ORDER BY trade_date DESC LIMIT 1"
                result = conn.execute(text(query))
                row = result.fetchone()
                if row:
                    return float(row[0])
            
            # 如果数据库没有数据，作为保底尝试从 API 获取 (可选)
            url = f"{BINANCE_API_BASE}/fapi/v1/ticker/price"
            params = {'symbol': symbol}
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            return float(data['price'])
            
        except Exception as e:
            logging.debug(f"获取 {symbol} 当前价格失败: {e}")
            return None
    
    # ==================== 小时黑马检测 ====================
    
    def calculate_hour_buy_surge_ratio(self, symbol: str) -> Optional[Tuple[float, float, float, datetime]]:
        """计算1小时买量暴涨倍数（最新1小时 vs 昨日小时平均）"""
        try:
            df = self.download_latest_kline(symbol, '1h', limit=48)
            if df is None or len(df) < 25:
                return None
            
            # 获取当前时间
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            
            # 获取昨天的24小时数据
            yesterday_data = df[(df['open_time'] >= yesterday_start) & (df['open_time'] < today_start)]
            
            if len(yesterday_data) < 24:
                return None
            
            # 计算昨天的小时平均买量
            yesterday_avg_hourly_volume = yesterday_data['active_buy_volume'].sum() / 24
            
            if yesterday_avg_hourly_volume == 0:
                return None
            
            # 获取今天最新的1小时数据
            today_data = df[df['open_time'] >= today_start]
            
            if len(today_data) == 0:
                return None
            
            # 最新1小时的买量
            latest_hour = today_data.iloc[-1]
            latest_hour_volume = latest_hour['active_buy_volume']
            signal_datetime = latest_hour['open_time']
            
            # 计算暴涨倍数
            buy_surge_ratio = latest_hour_volume / yesterday_avg_hourly_volume
            
            return (buy_surge_ratio, latest_hour_volume, yesterday_avg_hourly_volume, signal_datetime)
        except Exception as e:
            logging.debug(f"计算 {symbol} 小时买量暴涨倍数失败: {e}")
            return None
    
    def detect_hour_buy_surge(self) -> List[Dict]:
        """检测小时买量暴涨的交易对"""
        logging.info("=" * 80)
        logging.info("🔍 开始检测【小时黑马】买量暴涨信号...")
        logging.info("=" * 80)
        
        symbols = self.get_all_usdt_symbols()
        if not symbols:
            logging.error("无法获取交易对列表")
            return []
        
        surge_signals = []
        
        for i, symbol in enumerate(symbols, 1):
            try:
                if i % 50 == 0:
                    logging.info(f"进度: {i}/{len(symbols)} ({i/len(symbols)*100:.1f}%)")
                
                result = self.calculate_hour_buy_surge_ratio(symbol)
                if result is None:
                    continue
                
                buy_surge_ratio, latest_hour_volume, yesterday_avg_volume, signal_datetime = result
                
                # 检测是否在有效范围内（2-10倍）
                if buy_surge_ratio >= HOUR_BUY_SURGE_THRESHOLD:
                    # 过滤超过上限的信号
                    if buy_surge_ratio > HOUR_BUY_SURGE_MAX:
                        logging.info(f"⚠️ 跳过: {symbol} 小时买量暴涨 {buy_surge_ratio:.1f}x（超过{HOUR_BUY_SURGE_MAX}倍上限，风险过高）")
                        continue
                    
                    # 检查是否已有信号
                    existing_signal = next((s for s in self.signals 
                                          if s['symbol'] == symbol and s['strategy'] == 'hour'), None)
                    if existing_signal and existing_signal.get('status') != 'timeout':
                        logging.info(f"⏭️ 跳过通知: {symbol} 小时买量暴涨 {buy_surge_ratio:.1f}x，已有信号")
                        continue
                    
                    # 获取当前价格
                    current_price = self.get_current_price(symbol)
                    if current_price is None:
                        continue
                    
                    # 计算目标等待跌幅和建仓价
                    target_drop_pct = self.get_wait_drop_pct(buy_surge_ratio, HOUR_WAIT_DROP_CONFIG)
                    target_price = current_price * (1 + target_drop_pct)
                    
                    signal = {
                        'strategy': 'hour',
                        'strategy_name': '小时黑马',
                        'symbol': symbol,
                        'buy_surge_ratio': buy_surge_ratio,
                        'latest_volume': latest_hour_volume,
                        'yesterday_avg_volume': yesterday_avg_volume,
                        'signal_time': signal_datetime.isoformat(),
                        'signal_price': current_price,
                        'target_drop_pct': target_drop_pct,
                        'target_price': target_price,
                        'rule_version': HOUR_RULE_VERSION,
                        'timeout_time': (datetime.now() + timedelta(hours=HOUR_SIGNAL_TIMEOUT_HOURS)).isoformat(),
                        'status': 'waiting',
                        'expected_tp': self.get_expected_tp(buy_surge_ratio),
                        'stop_loss_pct': STOP_LOSS_PCT,
                        'add_position_trigger': ADD_POSITION_TRIGGER,
                        'max_hold_hours': MAX_HOLD_HOURS
                    }
                    
                    surge_signals.append(signal)
                    self.log_signal(signal)
                
                time.sleep(0.1)
            
            except Exception as e:
                logging.debug(f"处理 {symbol} 失败: {e}")
                continue
        
        logging.info(f"✅ 检测完成！发现 {len(surge_signals)} 个【小时黑马】信号")
        return surge_signals
    
    # ==================== 5分钟黑马检测 ====================
    
    def calculate_5m_buy_surge_ratio(self, symbol: str) -> Optional[Tuple[float, float, float, datetime]]:
        """计算5分钟买量暴涨倍数（最新5分钟 vs 昨日5分钟平均）"""
        try:
            # 获取最近288个5分钟K线（24小时）
            df = self.download_latest_kline(symbol, '5m', limit=300)
            if df is None or len(df) < 289:
                return None
            
            # 获取当前时间
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            
            # 获取昨天的数据（288个5分钟）
            yesterday_data = df[(df['open_time'] >= yesterday_start) & (df['open_time'] < today_start)]
            
            if len(yesterday_data) < 288:
                return None
            
            # 计算昨天的5分钟平均买量
            yesterday_avg_5m_volume = yesterday_data['active_buy_volume'].sum() / 288
            
            if yesterday_avg_5m_volume == 0:
                return None
            
            # 获取最新的5分钟数据
            latest_5m = df.iloc[-1]
            latest_5m_volume = latest_5m['active_buy_volume']
            signal_datetime = latest_5m['open_time']
            
            # 计算暴涨倍数
            buy_surge_ratio = latest_5m_volume / yesterday_avg_5m_volume
            
            return (buy_surge_ratio, latest_5m_volume, yesterday_avg_5m_volume, signal_datetime)
        except Exception as e:
            logging.debug(f"计算 {symbol} 5分钟买量暴涨倍数失败: {e}")
            return None
    
    def detect_5m_buy_surge(self) -> List[Dict]:
        """检测5分钟买量暴涨的交易对"""
        logging.info("=" * 80)
        logging.info("🔍 开始检测【5分钟黑马】买量暴涨信号...")
        logging.info("=" * 80)
        
        symbols = self.get_all_usdt_symbols()
        if not symbols:
            logging.error("无法获取交易对列表")
            return []
        
        surge_signals = []
        
        for i, symbol in enumerate(symbols, 1):
            try:
                if i % 50 == 0:
                    logging.info(f"进度: {i}/{len(symbols)} ({i/len(symbols)*100:.1f}%)")
                
                result = self.calculate_5m_buy_surge_ratio(symbol)
                if result is None:
                    continue
                
                buy_surge_ratio, latest_5m_volume, yesterday_avg_volume, signal_datetime = result
                
                # 检测是否在范围内
                if MIN5_BUY_SURGE_MIN <= buy_surge_ratio <= MIN5_BUY_SURGE_MAX:
                    # 检查是否已有信号
                    existing_signal = next((s for s in self.signals 
                                          if s['symbol'] == symbol and s['strategy'] == '5m'), None)
                    if existing_signal and existing_signal.get('status') != 'timeout':
                        logging.info(f"⏭️ 跳过通知: {symbol} 5分钟买量暴涨 {buy_surge_ratio:.1f}x，已有信号")
                        continue
                    
                    # 获取当前价格
                    current_price = self.get_current_price(symbol)
                    if current_price is None:
                        continue
                    
                    # 计算目标等待跌幅和建仓价
                    target_drop_pct = self.get_wait_drop_pct(buy_surge_ratio, MIN5_WAIT_DROP_CONFIG)
                    target_price = current_price * (1 + target_drop_pct)
                    
                    signal = {
                        'strategy': '5m',
                        'strategy_name': '5分钟黑马',
                        'symbol': symbol,
                        'buy_surge_ratio': buy_surge_ratio,
                        'latest_volume': latest_5m_volume,
                        'yesterday_avg_volume': yesterday_avg_volume,
                        'signal_time': signal_datetime.isoformat(),
                        'signal_price': current_price,
                        'target_drop_pct': target_drop_pct,
                        'target_price': target_price,
                        'timeout_time': (datetime.now() + timedelta(hours=MIN5_SIGNAL_TIMEOUT_HOURS)).isoformat(),
                        'status': 'waiting',
                        'expected_tp': self.get_expected_tp(buy_surge_ratio),
                        'stop_loss_pct': STOP_LOSS_PCT,
                        'add_position_trigger': ADD_POSITION_TRIGGER,
                        'max_hold_hours': MAX_HOLD_HOURS
                    }
                    
                    surge_signals.append(signal)
                    self.log_signal(signal)
                
                time.sleep(0.1)
            
            except Exception as e:
                logging.debug(f"处理 {symbol} 失败: {e}")
                continue
        
        logging.info(f"✅ 检测完成！发现 {len(surge_signals)} 个【5分钟黑马】信号")
        return surge_signals
    
    # ==================== 辅助函数 ====================
    
    def get_wait_drop_pct(self, buy_surge_ratio: float, config: List[Tuple]) -> float:
        """根据买量暴涨倍数获取等待跌幅"""
        for max_ratio, drop_pct in config:
            if buy_surge_ratio < max_ratio:
                return drop_pct
        return config[-1][1]
    
    def get_expected_tp(self, buy_surge_ratio: float) -> str:
        """根据买量倍数推荐止盈策略"""
        if buy_surge_ratio >= 10:
            return "预期强势，建议20%止盈"
        elif buy_surge_ratio >= 5:
            return "预期稳健，建议15%止盈"
        else:
            return "预期基础，建议10%止盈"
    
    def log_signal(self, signal: Dict):
        """输出信号详细信息"""
        logging.info(f"\n{'='*80}")
        logging.info(f"🔥 发现【{signal['strategy_name']}】信号: {signal['symbol']}")
        logging.info(f"{'='*80}")
        logging.info(f"📊 买量数据:")
        logging.info(f"   最新买量: {signal['latest_volume']:,.0f}")
        logging.info(f"   昨日平均: {signal['yesterday_avg_volume']:,.0f}")
        logging.info(f"   暴涨倍数: {signal['buy_surge_ratio']:.1f}x")
        logging.info(f"")
        logging.info(f"💰 建仓建议:")
        logging.info(f"   当前价: {signal['signal_price']:.8f}")
        if signal['target_drop_pct'] == 0:
            logging.info(f"   建仓价: {signal['target_price']:.8f} (立即建仓)")
        else:
            logging.info(f"   建仓价: {signal['target_price']:.8f} (等待{abs(signal['target_drop_pct'])*100:.1f}%回调)")
        logging.info(f"")
        logging.info(f"🎯 策略参数:")
        logging.info(f"   {signal['expected_tp']}")
        logging.info(f"   补仓触发: {signal['add_position_trigger']*100:.0f}%")
        logging.info(f"   止损: {signal['stop_loss_pct']*100:.0f}%")
        logging.info(f"   最大持仓: {signal['max_hold_hours']}小时")
        logging.info(f"{'='*80}\n")
        
        # 发送通知
        if self.notifier:
            try:
                # 注意：原版notifier不支持strategy参数，这里移除该参数
                self.notifier.notify_new_signal(
                    symbol=signal['symbol'],
                    ratio=signal['buy_surge_ratio'],
                    current_price=signal['signal_price'],
                    target_price=signal['target_price'],
                    target_drop_pct=signal['target_drop_pct']
                )
            except Exception as e:
                logging.error(f"发送通知失败: {e}")
    
    def check_signals(self) -> List[Dict]:
        """检查待建仓信号"""
        logging.info("=" * 80)
        logging.info("🔔 检查待建仓信号...")
        logging.info("=" * 80)
        
        if not self.signals:
            logging.info("当前没有待建仓信号")
            return []
        
        ready_signals = []
        now = datetime.now()
        
        for signal in self.signals[:]:
            symbol = signal['symbol']
            strategy = signal.get('strategy', 'unknown')
            status = signal.get('status', 'waiting')

            # 高风险仅观察：不参与建仓检查
            if signal.get('tradeable') is False or status == 'high_risk':
                continue
            
            if status != 'waiting':
                continue
            
            # 检查是否超时
            timeout_time = datetime.fromisoformat(signal['timeout_time'])
            if now > timeout_time:
                signal['status'] = 'timeout'
                logging.info(f"⏰ {symbol} [{strategy}] 信号超时")
                continue
            
            # 获取当前价格
            current_price = self.get_current_price(symbol)
            if current_price is None:
                continue
            
            target_price = signal['target_price']
            
            # 检查是否达到目标价格
            if current_price <= target_price:
                signal['status'] = 'ready'
                signal['entry_price'] = target_price
                signal['entry_time'] = now.isoformat()
                ready_signals.append(signal)
                
                logging.info(f"\n{'='*80}")
                logging.info(f"✅ {symbol} [{signal.get('strategy_name', strategy)}] 达到建仓条件！")
                logging.info(f"{'='*80}")
                logging.info(f"   买量暴涨: {signal['buy_surge_ratio']:.1f}x")
                logging.info(f"   当前价格: {current_price:.8f}")
                logging.info(f"   建议建仓价: {target_price:.8f}")
                logging.info(f"{'='*80}\n")
            else:
                drop_pct = (current_price - signal['signal_price']) / signal['signal_price'] * 100
                target_drop = signal['target_drop_pct'] * 100
                logging.info(f"⏳ {symbol} [{strategy}] 等待中... "
                           f"当前跌幅 {drop_pct:.1f}%，目标跌幅 {target_drop:.0f}%")
        
        self.save_signals()
        
        if ready_signals:
            logging.info(f"🎯 {len(ready_signals)} 个信号达到建仓条件！")
        
        return ready_signals
    
    def add_signals(self, new_signals: List[Dict]):
        """添加新信号到待建仓列表"""
        for signal in new_signals:
            symbol = signal['symbol']
            strategy = signal['strategy']
            
            # 查找是否已存在该交易对的该策略信号
            existing_signal = next((s for s in self.signals 
                                  if s['symbol'] == symbol and s['strategy'] == strategy), None)
            
            if not existing_signal:
                self.signals.append(signal)
                logging.info(f"➕ 新增信号: {symbol} [{signal['strategy_name']}] "
                           f"买量{signal['buy_surge_ratio']:.1f}倍")
            else:
                old_status = existing_signal.get('status', 'waiting')
                if old_status == 'timeout':
                    # 移除旧信号，添加新信号
                    self.signals = [s for s in self.signals 
                                  if not (s['symbol'] == symbol and s['strategy'] == strategy)]
                    self.signals.append(signal)
                    logging.info(f"🔄 更新信号: {symbol} [{signal['strategy_name']}] "
                               f"新买量{signal['buy_surge_ratio']:.1f}倍")
        
        self.save_signals()
    
    def show_signals_summary(self):
        """显示信号摘要"""
        waiting = [s for s in self.signals if s.get('status') == 'waiting']
        ready = [s for s in self.signals if s.get('status') == 'ready']
        timeout = [s for s in self.signals if s.get('status') == 'timeout']
        
        # 按策略分组
        hour_waiting = [s for s in waiting if s.get('strategy') == 'hour']
        min5_waiting = [s for s in waiting if s.get('strategy') == '5m']
        
        print("\n" + "=" * 80)
        print("📊 信号摘要")
        print("=" * 80)
        print(f"【小时黑马】等待中: {len(hour_waiting)} 个")
        print(f"【5分钟黑马】等待中: {len(min5_waiting)} 个")
        print(f"可建仓: {len(ready)} 个")
        print(f"已超时: {len(timeout)} 个")
        print("=" * 80)
    
    def run_detection(self):
        """运行一次检测（根据启用的策略）"""
        all_signals = []
        
        if 'hour' in self.strategies:
            hour_signals = self.detect_hour_buy_surge()
            all_signals.extend(hour_signals)
        
        if '5m' in self.strategies:
            min5_signals = self.detect_5m_buy_surge()
            all_signals.extend(min5_signals)
        
        return all_signals


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='黑马监控程序 - 多策略增强版')
    parser.add_argument('--monitor', action='store_true', help='持续监控模式')
    parser.add_argument('--check-signals', action='store_true', help='检查待建仓信号')
    parser.add_argument('--strategy', choices=['hour', '5m', 'all'], default='all',
                       help='选择策略：hour=小时黑马, 5m=5分钟黑马, all=全部')
    parser.add_argument('--interval', type=int, default=300,
                       help='监控间隔（秒），默认300秒（5分钟）')
    
    args = parser.parse_args()
    
    # 确定启用的策略
    if args.strategy == 'all':
        strategies = ['hour', '5m']
    else:
        strategies = [args.strategy]
    
    monitor = MultiStrategyMonitor(strategies=strategies)
    
    try:
        if args.check_signals:
            # 只检查现有信号
            ready_signals = monitor.check_signals()
            monitor.show_signals_summary()
            
        elif args.monitor:
            # 持续监控模式
            logging.info("🚀 启动持续监控模式...")
            logging.info(f"启用策略: {', '.join([s + '黑马' for s in strategies])}")
            logging.info(f"检测间隔: {args.interval}秒")
            
            while True:
                try:
                    # 检测新的买量暴涨信号
                    new_signals = monitor.run_detection()
                    if new_signals:
                        monitor.add_signals(new_signals)
                    
                    # 检查待建仓信号
                    ready_signals = monitor.check_signals()
                    
                    # 显示摘要
                    monitor.show_signals_summary()
                    
                    # 等待下一次检测
                    logging.info(f"\n⏰ 等待 {args.interval}秒 后进行下一次检测...")
                    time.sleep(args.interval)
                
                except KeyboardInterrupt:
                    logging.info("\n用户中断监控")
                    break
                except Exception as e:
                    logging.error(f"监控过程出错: {e}")
                    time.sleep(60)
        
        else:
            # 运行一次检测
            new_signals = monitor.run_detection()
            if new_signals:
                monitor.add_signals(new_signals)
            
            # 检查待建仓信号
            ready_signals = monitor.check_signals()
            
            # 显示摘要
            monitor.show_signals_summary()
    
    except KeyboardInterrupt:
        logging.info("\n程序被用户中断")
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logging.info("黑马监控程序结束")


if __name__ == "__main__":
    # 检查并创建PID文件，防止重复启动
    check_and_create_pid()
    
    # 运行主程序
    main()
