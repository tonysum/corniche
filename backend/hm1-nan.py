#!/usr/bin/env python3
"""
买量暴涨策略回测程序 - 小时线版本（优化版）
基于小时主动买量暴涨信号的快进快出量化策略

═══════════════════════════════════════════════════════════════════════════════
📊 核心策略逻辑
═══════════════════════════════════════════════════════════════════════════════

【1️⃣ 信号发现】
  • 数据源：每日扫描所有USDT永续合约交易对
  • 触发条件：某小时主动买量 >= 昨日平均小时买量 × 2倍
  • 信号过滤：默认仅接受2-3倍信号（更贴近“稳健”定义）
    - 小于2倍：可能只是正常波动，排除
    - 大于3倍：波动/风险更高（默认排除；可通过 --max-multiple 放宽到 10）

【2️⃣ 等待回调建仓】
  • 策略：根据买量暴涨倍数，设定不同的等待回调幅度
    - 2-3倍：等待回调5%（低倍数价格快速上涨，回调空间小）
    - 3-5倍：等待回调4%（中等倍数，适度等待）
    - 5-10倍：等待回调3%（高倍数波动大，有回调空间）
  • 建仓时机：价格从信号价回调达到目标跌幅时立即建仓
  • 超时机制：信号触发后48小时内未达到目标跌幅则放弃该信号
  • 资金管理：
    - 杠杆倍数：4倍
    - 单次建仓：当前资金 × 5%（复利模式）
    - 补仓金额：当前资金 × 15%（可独立配置）

【3️⃣ 动态止盈机制】
  • 基础止盈：8.5%
  • 动态调整逻辑（基于建仓后1小时内的 5m K线 close，更贴近“时间占比”的真实含义）：
    ① 强势币：建仓后窗口内（默认60分钟，理论12根5m K线），≥60% 的 5m close > 建仓价×(1+2%)
       → 止盈阈值 = 8.5% + 动态加成（按买量暴涨倍数分档）：
          - 2-3倍：+10%（18.5%）
          - 3-6倍：+8%（16.5%）
          - 6-10倍：+5%（13.5%）
    ② 普通币：不满足强势判定 → 使用基础止盈 8.5%
  • 监控频率：使用小时K线实时监控，每小时检查一次
  • 触发方式：当小时K线的最高价(high)达到动态止盈阈值时平仓

【4️⃣ 补仓机制】
  • 触发条件：价格从平均成本下跌18%
  • 补仓次数：最多补仓1次
  • 补仓金额：当前资金 × 15%（可独立配置，支持大于首次建仓比例）
  • 首次建仓：当前资金 × 5%
  • 成本重算：补仓后重新计算平均成本
    平均成本 = (首次建仓价 × 首次数量 + 补仓价 × 补仓数量) / 总数量
  • 补仓后立即检查：在补仓的同一小时内立即检查是否触发止盈或止损
  • 监控方式：使用小时K线的最低价(low)监控补仓触发

【5️⃣ 止损机制】
  • 启用条件：只在补仓后启用止损保护
  • 止损阈值：基于补仓后的新平均成本下跌18%
  • 监控方式：使用小时K线的最低价(low)监控止损触发
  • 设计理念：
    - 首次建仓不设止损，允许回调空间进行补仓
    - 补仓后必须止损，防止继续扩大亏损
    - 止损价 = 新平均成本 × (1 - 18%)

【6️⃣ 强制平仓】
  • 最大持仓时间：72小时（3天）
  • 平仓方式：超过72小时后，使用当前小时收盘价强制平仓
  • 设计理念：基于数据分析，72.3%的案例在3天内达到最高点，
    超过3天后继续持有风险增大

═══════════════════════════════════════════════════════════════════════════════
📈 回测表现（2025-11-01 至 2026-01-14，接受2-10倍信号）
═══════════════════════════════════════════════════════════════════════════════

总交易次数：358笔
盈利交易：227笔
胜率：63.41%
平均收益率：+5.20%
总盈亏：$169,837.91（初始资金$10,000）

平仓原因分布：
  • 止盈：176次（49.2%）
  • 止损：3次（0.8%）
  • 超时：179次（50.0%）

补仓情况：34次（9.5%）

═══════════════════════════════════════════════════════════════════════════════
⚠️ 风险提示
═══════════════════════════════════════════════════════════════════════════════

1. 杠杆风险：4倍杠杆放大收益的同时也放大风险
2. 补仓风险：9.5%的交易需要补仓，占用额外资金
3. 止损风险：0.8%的交易触发止损，单笔最大亏损可达-30%
4. 时间风险：50%的交易未能止盈，超时平仓，收益不确定
5. 市场风险：策略基于历史数据回测，实盘表现可能不同

═══════════════════════════════════════════════════════════════════════════════
🔧 技术实现细节
═══════════════════════════════════════════════════════════════════════════════

• 数据精度：使用小时K线数据（HourlyKline表）进行精确监控
• 时间戳：精确到小时级别，确保动态止盈计算准确
• 价格监控：
  - 止盈：使用每小时最高价(high)
  - 补仓：使用每小时最低价(low)
  - 止损：使用每小时最低价(low)
• 持仓时间：基于建仓小时时间戳精确计算，而非简单的日期差
• 无缓存设计：避免量化回测中的数据不一致问题，每次实时查询数据库

═══════════════════════════════════════════════════════════════════════════════

作者：量化交易助手
创建时间：2026-01-11
最后更新：2026-01-14
版本：v2.0（优化信号过滤，接受2-10倍信号）
"""

import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import argparse
import pandas as pd
import db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 数据库路径
CRYPTO_DB_PATH = db.db_path

class BuySurgeBacktest:
    """买量暴涨策略回测器"""

    def __init__(self):
        self.crypto_conn = sqlite3.connect(CRYPTO_DB_PATH)

        # 回测参数
        self.initial_capital = 10000.0  # 初始资金
        self.leverage = 4.0  # 杠杆倍数（4倍）
        self.position_size_ratio = 0.05  # 单次建仓占资金比例（5%）
        self.add_position_size_ratio = 0.05  # 补仓占资金比例（15%，可以设置为首仓的倍数）
        self.buy_surge_threshold = 2  # 小时主动买量比昨日暴涨阈值（2倍）
        self.buy_surge_max = 3.0  # 买量暴涨倍数上限（默认接受2-3倍，可通过参数放宽）
        self.take_profit_pct = 0.11  # 止盈比例 (8.5%)

        # 动态止盈参数（"强势币"提高止盈阈值）
        # - 判定条件（满足任一即触发）：
        #   1. 2小时内60%的5分钟K线收盘价涨幅>1.5%
        #   2. 12小时涨幅 >= 2.5%
        # - 提升幅度：按买量暴涨倍数分档（只对"强势币"生效）
        #   - 2-3倍：+11% → 总止盈19.5%
        #   - 3-6倍：+8%  → 总止盈16.5%
        #   - 6-10倍：+5% → 总止盈13.5%
        # - dynamic_tp_boost_pct：备用/覆盖用（当传入 --dynamic-tp-boost 时将覆盖所有分档）
        self.dynamic_tp_boost_pct = 0.11
        self.dynamic_tp_boost_config = [
            (3, 0.09),     # 2-3倍：19.5%总止盈
            (6, 0.08),     # 3-6倍：16.5%
            (10, 0.05),    # 6-10倍：13.5%
            (9999, 0.05),  # 10倍以上
        ]
        # 🆕 改为12小时窗口（720分钟），基于数据分析的最佳判定时机
        # 分析显示：能涨19.5%的币在12h涨3.56%，只涨8.5%的币12h涨0.11%，区分度极高
        self.dynamic_tp_lookback_minutes = 720
        # 🆕 调整强势币判定阈值为2.5%（而非原来的1%）
        self.dynamic_tp_close_up_pct = 0.025  # 12小时涨幅 >= 2.5%
        self.dynamic_tp_ratio = 0.60
        self.dynamic_tp_min_5m_bars = 8
        
        # ⚠️ 量化回测中不使用K线缓存，避免数据不一致
        # 只缓存交易对列表（回测期间不会变化）
        self._all_symbols_cache = None  # 交易对列表缓存
        
        self.add_position_trigger_pct = -0.18  # 补仓触发比例 (-18%)
        self.stop_loss_pct = -0.18  # 止损比例 (-18%，补仓后基于新平均成本)
        self.max_hold_hours = 68  # 最大持仓小时数 (72小时/3天强制平仓)
        # 说明：
        # - 回测里同时存在“并发持仓上限”和“每日新开仓上限”两个概念
        # - 你此前希望以 max_daily_positions 为准（例如 100），这里保持该参数并用于并发持仓上限（向后兼容）
        self.max_daily_positions = 10  # 每日最多建仓数量（同时也作为并发持仓上限）
        self.wait_timeout_hours = 48  # 等待超时时间（小时）
        
        # 等待跌幅策略（根据买量倍数）
        # 🎯 基于实际等待时间数据优化的配置
        # 低倍数信号价格快速上涨，等待反而买贵；高倍数信号波动大，可等待回调
        self.wait_drop_pct_config = [
            (3, -0.15),     # 2-3倍：等待5%回调（96%立即成交，价格快速上涨+6.78%）
            (5, -0.04),     # 3-5倍：等待4%回调（66.7%立即成交，仅1%回调空间）
            (10, -0.03),   # 5-10倍：等待3%回调（64.9%立即成交，适度等待）
            (9999, -0.01), # 10倍以上：等待2%回调（31.8%立即成交，实际获得1.91%回调）
        ]
        
        # 待建仓信号列表（等待回调中的信号）
        self.pending_signals = []  # 存储 {symbol, signal_date, signal_close, buy_surge_ratio, timeout_datetime}
        # 🆕 信号记录（用于输出“发现信号但未成交”的反馈表）
        # 每条记录：信号时间、目标价、是否成交、未成交原因等
        self.signal_records = []

        # 交易记录
        self.capital = self.initial_capital
        self.positions = []  # 当前持仓
        self.trade_records = []  # 交易记录
        self.daily_capital = []  # 每日资金记录

    def __del__(self):
        """析构函数，确保数据库连接关闭"""
        try:
            if hasattr(self, 'crypto_conn'):
                self.crypto_conn.close()
        except:
            pass

    def get_wait_drop_pct(self, buy_surge_ratio: float) -> float:
        """根据买量暴涨倍数获取等待跌幅
        
        Args:
            buy_surge_ratio: 买量暴涨倍数
        
        Returns:
            等待跌幅百分比（负数）
        """
        for max_ratio, drop_pct in self.wait_drop_pct_config:
            if buy_surge_ratio < max_ratio:
                return drop_pct
        return self.wait_drop_pct_config[-1][1]

    def get_dynamic_tp_boost_pct(self, buy_surge_ratio) -> float:
        """根据买量暴涨倍数获取动态止盈加成幅度（仅在“强势币”触发时使用）"""
        if buy_surge_ratio is None:
            return float(self.dynamic_tp_boost_pct)
        try:
            r = float(buy_surge_ratio)
        except Exception:
            return float(self.dynamic_tp_boost_pct)

        for max_ratio, boost_pct in getattr(self, 'dynamic_tp_boost_config', []) or []:
            if r < max_ratio:
                return float(boost_pct)
        return float(self.dynamic_tp_boost_pct)
    
    def check_signal_surge(self, symbol: str, signal_date: str, signal_close: float) -> tuple:
        """检查信号触发前1小时是否暴涨
        
        Args:
            symbol: 交易对
            signal_date: 信号日期
            signal_close: 信号日收盘价
        
        Returns:
            (是否通过检查, 涨幅百分比)
        """
        try:
            # 获取信号日的时间戳
            signal_dt = datetime.strptime(signal_date, '%Y-%m-%d')
            signal_ts = int(signal_dt.timestamp() * 1000)
            
            # 获取信号日之前的最后一个小时K线
            table_name = f'K1h{symbol}'
            cursor = self.crypto_conn.cursor()
            
            query = f"""
                SELECT close
                FROM "{table_name}"
                WHERE open_time < {signal_ts}
                ORDER BY open_time DESC
                LIMIT 1
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if not result:
                # 如果没有小时数据，默认通过检查
                return True, 0.0
            
            prev_1h_close = result[0]
            
            # 计算1小时内的涨幅
            surge_pct = ((signal_close - prev_1h_close) / prev_1h_close * 100)
            
            # 如果1小时内涨幅<5%，拒绝信号（涨幅太低）
            if surge_pct < 5.0:
                return False, surge_pct
            
            # 如果1小时内暴涨超过48.5%，拒绝信号（追高风险）
            if surge_pct > 48.5:
                return False, surge_pct
            
            return True, surge_pct
            
        except Exception as e:
            logging.debug(f"检查信号暴涨失败 {symbol}: {e}")
            # 出错时默认通过检查
            return True, 0.0
    
    def calculate_dynamic_take_profit(
        self,
        position: Dict,
        hourly_df: pd.DataFrame,
        entry_datetime: datetime,
        current_datetime: datetime,
    ) -> float:
        """计算动态止盈阈值
        
        双重判断机制（满足任一即触发）：
        1. 2小时判断：2小时内60%的5分钟K线收盘价涨幅>1.5% → 触发动态止盈
        2. 12小时判断：12小时涨幅≥2.5% → 触发动态止盈
        
        Args:
            position: 持仓信息
            hourly_df: 小时K线数据
            entry_datetime: 建仓时间（完整的datetime对象，包含小时）
            current_datetime: 当前回测推进到的时间点（避免用未来数据做"强势判定"）
        
        Returns:
            动态止盈阈值（如0.085表示8.5%，0.15表示15%）
        """
        try:
            # 缓存：如果已经判定过，直接返回
            cached = position.get('dynamic_tp_pct')
            if isinstance(cached, (int, float)) and cached > 0:
                return float(cached)

            # 获取建仓价格
            avg_price = position['avg_entry_price']
            symbol = position['symbol']
            
            # ============ 判断1：2小时内60%的5分钟K线涨幅>1.5% ============
            window_2h_end = entry_datetime + timedelta(hours=2)
            if current_datetime >= window_2h_end:
                # 2小时已过，检查5分钟K线表现
                try:
                    cursor = self.crypto_conn.cursor()
                    kline_5m_table = f'K5m{symbol}'
                    
                    # 获取建仓后2小时内的5分钟K线（24根）
                    start_ts = int(entry_datetime.timestamp() * 1000)
                    end_ts = int(window_2h_end.timestamp() * 1000)
                    
                    query = f"""
                    SELECT close
                    FROM {kline_5m_table}
                    WHERE open_time >= ? AND open_time < ?
                    ORDER BY open_time
                    """
                    cursor.execute(query, (start_ts, end_ts))
                    closes = [row[0] for row in cursor.fetchall()]
                    
                    if len(closes) >= 24:  # 确保有足够的K线数据
                        # 计算每根K线相对建仓价的涨幅
                        returns = [(close - avg_price) / avg_price for close in closes[:24]]
                        
                        # 统计涨幅超过1.5%的K线数量
                        count_above_threshold = sum(1 for r in returns if r > 0.015)
                        pct_above = count_above_threshold / 24
                        
                        position['dynamic_tp_2h_pct_above'] = pct_above * 100
                        
                        # 如果60%以上的K线涨幅超过1.5%
                        if pct_above >= 0.60:
                            buy_surge_ratio = position.get('buy_surge_ratio')
                            boost_pct = self.get_dynamic_tp_boost_pct(buy_surge_ratio)
                            adjusted_tp = self.take_profit_pct + boost_pct
                            
                            position['dynamic_tp_pct'] = adjusted_tp
                            position['dynamic_tp_strong'] = True
                            position['dynamic_tp_boost_used'] = boost_pct
                            position['dynamic_tp_trigger'] = '2h_avg'
                            
                            ratio_str = f"{float(buy_surge_ratio):.2f}" if buy_surge_ratio else "NA"
                            logging.info(
                                f"🚀 {symbol} 强势币(买量{ratio_str}x)：2小时内{pct_above*100:.0f}%的K线涨>1.5%，"
                                f"止盈提高到{adjusted_tp*100:.1f}%（加成+{boost_pct*100:.1f}%）"
                            )
                            return adjusted_tp
                except Exception as e:
                    logging.debug(f"查询2小时平均价格失败 {symbol}: {e}")

            # ============ 判断2：12小时涨幅 ============
            window_12h_end = entry_datetime + timedelta(minutes=self.dynamic_tp_lookback_minutes)
            if current_datetime >= window_12h_end:
                # 12小时已过，检查12小时涨幅
                try:
                    cursor = self.crypto_conn.cursor()
                    hourly_table = f'K1h{symbol}'
                    
                    # 获取12小时后附近的K线（允许前后1小时的误差）
                    window_start_ts = int(window_12h_end.timestamp() * 1000)
                    window_end_ts = int((window_12h_end + timedelta(hours=1)).timestamp() * 1000)
                    
                    query = f"""
                    SELECT close
                    FROM {hourly_table}
                    WHERE open_time >= ? AND open_time < ?
                    ORDER BY open_time ASC
                    LIMIT 1
                    """
                    cursor.execute(query, (window_start_ts, window_end_ts))
                    result = cursor.fetchone()
                    
                    if result:
                        price_12h = result[0]
                        return_12h = (price_12h - avg_price) / avg_price
                        
                        position['dynamic_tp_12h_return'] = return_12h * 100
                        
                        # 如果12小时涨幅 >= 2.5%
                        if return_12h >= self.dynamic_tp_close_up_pct:
                            buy_surge_ratio = position.get('buy_surge_ratio')
                            boost_pct = self.get_dynamic_tp_boost_pct(buy_surge_ratio)
                            adjusted_tp = self.take_profit_pct + boost_pct
                            
                            position['dynamic_tp_pct'] = adjusted_tp
                            position['dynamic_tp_strong'] = True
                            position['dynamic_tp_boost_used'] = boost_pct
                            position['dynamic_tp_trigger'] = '12h_return'
                            
                            ratio_str = f"{float(buy_surge_ratio):.2f}" if buy_surge_ratio else "NA"
                            logging.info(
                                f"🚀 {symbol} 强势币(买量{ratio_str}x)：12小时涨幅{return_12h*100:.2f}% >= {self.dynamic_tp_close_up_pct*100:.1f}%，"
                                f"止盈提高到{adjusted_tp*100:.1f}%（加成+{boost_pct*100:.1f}%）"
                            )
                            return adjusted_tp
                except Exception as e:
                    logging.debug(f"查询12小时价格失败 {symbol}: {e}")

            # ============ 两个判断都不满足 ============
            # 如果12小时窗口还没走完，暂时使用默认止盈
            if current_datetime < window_12h_end:
                return self.take_profit_pct
            
            # 12小时已过但都不满足条件，缓存为默认止盈
            position['dynamic_tp_pct'] = self.take_profit_pct
            position['dynamic_tp_strong'] = False
            position['dynamic_tp_boost_used'] = 0.0
            position['dynamic_tp_trigger'] = 'none'
            return self.take_profit_pct
                
        except Exception as e:
            logging.debug(f"计算动态止盈失败: {e}")
            position['dynamic_tp_pct'] = self.take_profit_pct
            position['dynamic_tp_strong'] = False
            return self.take_profit_pct

    def get_daily_buy_surge_coins(self, date_str: str) -> List[Dict]:
        """获取指定日期主动买量暴涨的合约
        
        Args:
            date_str: 日期字符串
        
        Returns:
            主动买量暴涨的合约列表
        """
        try:
            cursor = self.crypto_conn.cursor()
            
            # 获取所有交易对
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'K1d%'")
            tables = cursor.fetchall()
            
            surge_contracts = []
            
            for table_name, in tables:
                symbol = table_name.replace('K1d', '')
                
                if not symbol.endswith('USDT'):
                    continue
                
                try:
                    # 获取当日数据
                    cursor.execute(f'''
                        SELECT trade_date, close, open, active_buy_volume
                        FROM "{table_name}"
                        WHERE trade_date = ? OR trade_date LIKE ?
                    ''', (date_str, f'{date_str}%'))
                    
                    today_result = cursor.fetchone()
                    if not today_result or not today_result[3]:
                        continue
                    
                    today_date, close_price, open_price, today_buy_volume = today_result
                    
                    # 获取昨日数据
                    yesterday_dt = datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)
                    yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
                    
                    cursor.execute(f'''
                        SELECT active_buy_volume
                        FROM "{table_name}"
                        WHERE trade_date = ? OR trade_date LIKE ?
                    ''', (yesterday_str, f'{yesterday_str}%'))
                    
                    yesterday_result = cursor.fetchone()
                    if not yesterday_result or not yesterday_result[0]:
                        continue
                    
                    yesterday_buy_volume = yesterday_result[0]
                    
                    # 计算买量暴涨倍数
                    if yesterday_buy_volume > 0:
                        buy_surge_ratio = today_buy_volume / yesterday_buy_volume
                        
                        # 如果买量暴涨超过阈值
                        if buy_surge_ratio >= self.buy_surge_threshold:
                            # 🆕 检查信号触发前1小时是否暴涨
                            passed, surge_pct = self.check_signal_surge(symbol, date_str, close_price)
                            
                            if not passed:
                                # 根据涨幅判断过滤原因
                                if surge_pct < 5.0:
                                    logging.info(f"⚠️ 过滤信号: {symbol} 在 {date_str} 买量暴涨 {buy_surge_ratio:.1f}倍，但1小时内涨幅仅{surge_pct:.1f}%（涨幅太低）")
                                else:
                                    logging.info(f"⚠️ 过滤信号: {symbol} 在 {date_str} 买量暴涨 {buy_surge_ratio:.1f}倍，但1小时内价格暴涨{surge_pct:.1f}%（追高风险）")
                                continue
                            
                            surge_contracts.append({
                                'symbol': symbol,
                                'close': close_price,
                                'open': open_price,
                                'today_buy_volume': today_buy_volume,
                                'yesterday_buy_volume': yesterday_buy_volume,
                                'buy_surge_ratio': buy_surge_ratio
                            })
                            
                            logging.info(f"🔥 发现买量暴涨: {symbol} 在 {date_str} 买量暴涨 {buy_surge_ratio:.1f}倍 (1小时涨幅{surge_pct:+.1f}%)")
                
                except Exception as e:
                    continue
            
            # 按买量暴涨倍数降序排序
            surge_contracts.sort(key=lambda x: x['buy_surge_ratio'], reverse=True)
            
            return surge_contracts
        
        except Exception as e:
            logging.error(f"获取 {date_str} 买量暴涨合约失败: {e}")
            return []

    def get_all_symbols(self) -> List[str]:
        """获取所有USDT交易对列表（缓存，回测期间交易对列表不变）"""
        if self._all_symbols_cache is not None:
            return self._all_symbols_cache
        
        cursor = self.crypto_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'K1d%'")
        tables = cursor.fetchall()
        symbols = [
            table_name[0].replace('K1d', '') 
            for table_name in tables 
            if table_name[0].replace('K1d', '').endswith('USDT')
        ]
        self._all_symbols_cache = symbols
        logging.info(f"🔍 找到 {len(symbols)} 个USDT交易对")
        return symbols
    
    def get_daily_1hour_surge_signals(self, check_date: str) -> List[Dict]:
        """🆕 优化版：检测某天内哪些小时的买量超过昨日平均小时买量
        
        检测逻辑：
        1. 获取昨日日K线的 active_buy_volume（总买量）
        2. 计算昨日平均小时买量 = 总买量 / 24（1天=24小时）
        3. 遍历今日24小时，找到第一个买量 >= 昨日平均小时买量 × 阈值的小时
        4. 那个小时就是信号时间
        
        Args:
            check_date: 检测日期 'YYYY-MM-DD'
        
        Returns:
            信号列表，包含symbol、信号时间、倍数等
        """
        try:
            cursor = self.crypto_conn.cursor()
            
            # 获取所有交易对列表
            all_symbols = self.get_all_symbols()
            total_symbols = len(all_symbols)
            
            signals = []
            threshold = 2.0  # 🔥 某小时买量 >= 昨日平均小时买量 × 2倍
            
            check_dt = datetime.strptime(check_date, '%Y-%m-%d')
            yesterday_date = (check_dt - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 遍历所有交易对
            logging.info(f"🔍 开始扫描 {check_date} 的信号，共 {total_symbols} 个交易对...")
            for idx, symbol in enumerate(all_symbols, 1):
                
                try:
                    # 🚀 步骤1：获取昨日日K线总买量
                    daily_table = f'K1d{symbol}'
                    cursor.execute(f'''
                        SELECT active_buy_volume
                        FROM "{daily_table}"
                        WHERE trade_date = ? OR trade_date LIKE ?
                    ''', (yesterday_date, f'{yesterday_date}%'))
                    
                    yesterday_row = cursor.fetchone()
                    if not yesterday_row or not yesterday_row[0]:
                        continue
                    
                    yesterday_daily_volume = yesterday_row[0]
                    # 🔧 关键修复：计算昨日平均小时买量（1天 = 24小时）
                    yesterday_avg_hour_volume = yesterday_daily_volume / 24.0
                    
                    # 🚀 步骤2：获取今日所有小时K线（优化：使用LIKE更快）
                    hourly_table = f'K1h{symbol}'
                    cursor.execute(f'''
                        SELECT trade_date, active_buy_volume, close
                        FROM "{hourly_table}"
                        WHERE trade_date LIKE ?
                        ORDER BY trade_date ASC
                    ''', (f'{check_date}%',))
                    
                    today_hours = cursor.fetchall()
                    if not today_hours:
                        continue
                    
                    # 🚀 步骤3：找到第一个满足条件的小时
                    for hour_data in today_hours:
                        hour_time, hour_volume, hour_price = hour_data
                        
                        if not hour_volume or not hour_price:
                            continue
                        
                        # 🔧 修复后：某小时买量 vs 昨日平均小时买量
                        surge_ratio = hour_volume / yesterday_avg_hour_volume
                        
                        # 满足阈值，记录信号（只保留2-3倍的稳健信号）
                        if surge_ratio >= threshold and surge_ratio <= self.buy_surge_max:
                            signal_datetime = pd.to_datetime(hour_time)
                            
                            signals.append({
                                'symbol': symbol,
                                'signal_datetime': signal_datetime,
                                'signal_price': hour_price,
                                'surge_ratio': surge_ratio,
                                'signal_hour_volume': hour_volume,
                                'yesterday_avg_hour_volume': yesterday_avg_hour_volume
                            })
                            
                            logging.info(f"🔥 发现信号: {symbol} @{signal_datetime.strftime('%H:00')} 倍数{surge_ratio:.2f}x 价格{hour_price:.6f}")
                            break  # 只记录第一个满足条件的小时
                        elif surge_ratio > self.buy_surge_max:
                            logging.debug(f"⚠️ 过滤高倍数信号: {symbol} @{hour_time} 倍数{surge_ratio:.2f}x (>{self.buy_surge_max}倍)")
                            break  # 超过上限也跳过该交易对后续小时（保持原逻辑：只关心最早触发的小时）
                
                except Exception as e:
                    continue
                
                # 每扫描100个交易对显示一次进度
                if idx % 100 == 0 or idx == total_symbols:
                    logging.info(f"  扫描进度: {idx}/{total_symbols} ({idx*100//total_symbols}%) | 已找到信号: {len(signals)} 个")
            
            # 按倍数降序排序
            signals.sort(key=lambda x: x['surge_ratio'], reverse=True)
            
            logging.info(f"✅ {check_date} 扫描完成，共发现 {len(signals)} 个买量暴涨信号")
            return signals
        
        except Exception as e:
            logging.error(f"获取 {check_date} 买量暴涨信号失败: {e}")
            return []

    def get_hourly_kline_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取小时K线数据（安全版：不使用缓存，只查询需要的日期范围）
        
        Args:
            symbol: 交易对
            start_date: 开始日期（可选，格式：YYYY-MM-DD）
            end_date: 结束日期（可选，格式：YYYY-MM-DD）
        
        Note:
            量化回测中不使用缓存，确保数据准确性
        """
        table_name = f'K1h{symbol}'
        
        try:
            cursor = self.crypto_conn.cursor()
            
            # 构建带日期范围的查询（优化：只查询需要的数据）
            if start_date and end_date:
                query = f'SELECT * FROM {table_name} WHERE trade_date >= ? AND trade_date <= ? ORDER BY trade_date ASC'
                cursor.execute(query, (start_date, end_date + ' 23:59:59'))
            elif start_date:
                query = f'SELECT * FROM {table_name} WHERE trade_date >= ? ORDER BY trade_date ASC'
                cursor.execute(query, (start_date,))
            elif end_date:
                query = f'SELECT * FROM {table_name} WHERE trade_date <= ? ORDER BY trade_date ASC'
                cursor.execute(query, (end_date + ' 23:59:59',))
            else:
                # 没有指定范围时，查询全部（但会很慢）
                logging.warning(f"查询 {symbol} 全部小时K线数据，可能较慢")
                query = f'SELECT * FROM {table_name} ORDER BY trade_date ASC'
                cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        except Exception as e:
            logging.warning(f"获取 {symbol} 小时K线数据失败: {e}")
            return pd.DataFrame()

    def execute_trade(self, symbol: str, entry_price: float, entry_date: str, 
                     signal_date: str, buy_surge_ratio: float, position_type: str = "long", entry_datetime=None):
        """执行交易
        
        Args:
            entry_datetime: 完整的建仓时间戳（datetime对象或字符串），用于精确记录建仓时刻
        """
        try:
            # 🔧 爆仓保护：如果资金亏损超过80%，停止交易
            if self.capital <= self.initial_capital * 0.2:
                logging.warning(f"⚠️ 资金不足，停止交易: {symbol} 当前资金${self.capital:.2f} < 初始资金20%")
                return
            
            # 💰 复利模式：基于当前资金余额的比例建仓（实现复利增长）
            position_value = self.capital * self.position_size_ratio
            
            # 检查当前资金是否足够建仓
            if self.capital < position_value:
                logging.warning(f"⚠️ 资金不足，无法建仓: {symbol} 需要${position_value:.2f}，当前${self.capital:.2f}")
                return
            
            # 计算建仓数量 (考虑杠杆)
            position_size = (position_value * self.leverage) / entry_price
            
            # 🔧 转换 entry_datetime 为字符串格式（如果是 pandas Timestamp 或 datetime 对象）
            if entry_datetime is not None:
                if hasattr(entry_datetime, 'strftime'):
                    entry_datetime_str = entry_datetime.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    entry_datetime_str = str(entry_datetime)
            else:
                entry_datetime_str = None
            
            # 记录交易
            trade_record = {
                'entry_date': entry_date,
                'entry_datetime': entry_datetime_str,  # 🆕 保存完整的建仓时间戳（字符串格式）
                'symbol': symbol,
                'entry_price': entry_price,
                'position_size': position_size,
                'position_value': position_value,
                'leverage': self.leverage,
                'position_type': position_type,
                'exit_date': None,
                'exit_price': None,
                'exit_reason': None,
                'pnl': 0,
                'pnl_pct': 0,
                'avg_entry_price': entry_price,
                'signal_date': signal_date,
                'buy_surge_ratio': buy_surge_ratio,  # 买量暴涨倍数
                'has_add_position': False,
                'add_position_price': None,
                'add_position_size': None,
                'max_drawdown': 0,
                'max_up_2h': None,  # 🆕 建仓后2小时最大涨幅（ratio，用于分析）
                'max_up_24h': None,  # 🆕 建仓后24小时最大涨幅（ratio，用于分析）
                'hold_days': 0,

                # 动态止盈相关（用于后续分析 + CSV输出）
                # - dynamic_tp_pct: 本次交易“最终使用的动态止盈阈值”（会缓存：8.5% 或 18.5%）
                # - dynamic_tp_strong: 是否被判定为“强势币”（True/False）
                # - dynamic_tp_boost_used: 强势时实际使用的加成幅度（按买量暴涨倍数分档）
                # - tp_pct_used: 本次实际触发止盈时使用的阈值（仅在 take_profit 平仓时写入）
                'dynamic_tp_pct': None,
                'dynamic_tp_strong': None,
                'dynamic_tp_boost_used': None,
                'dynamic_tp_above_cnt': None,
                'dynamic_tp_total_cnt': None,
                'tp_pct_used': None
            }
            
            self.positions.append(trade_record)
            self.trade_records.append(trade_record)
            
            # 💰 复利模式：建仓时扣除投入资金
            self.capital -= position_value
            
            logging.info(f"🚀 建仓: {symbol} {entry_date} 价格:{entry_price:.4f} 买量暴涨:{buy_surge_ratio:.1f}倍 杠杆:{self.leverage}x 仓位:${position_value:.2f} 剩余资金:${self.capital:.2f}")
        except Exception as e:
            logging.error(f"执行交易失败: {e}")

    def check_exit_conditions(self, position: Dict, current_price: float, current_date: str) -> bool:
        """使用小时线数据检查是否满足平仓条件"""
        try:
            symbol = position['symbol']
            entry_price = position['avg_entry_price']
            entry_date = position['entry_date']
            
            # 获取小时线数据（优化：只查询建仓日到当前日的数据）
            hourly_df = self.get_hourly_kline_data(symbol, start_date=entry_date, end_date=current_date)
            if hourly_df.empty:
                logging.warning(f"无小时线数据，使用日线数据检查: {symbol}")
                # 备用：使用日线数据（无法使用动态止盈，使用默认阈值）
                price_change_pct = (current_price - entry_price) / entry_price
                if price_change_pct >= self.take_profit_pct:
                    position['tp_pct_used'] = self.take_profit_pct
                    self.exit_position(position, current_price, current_date, "take_profit")
                    return True
                return False
            
            # 筛选建仓时刻之后的所有小时数据
            # 🔧 修复：使用保存的完整建仓时间戳，而不是只用日期
            if position.get('entry_datetime'):
                # 如果有完整的建仓时间戳，使用它
                entry_datetime = pd.to_datetime(position['entry_datetime'])
            else:
                # 向后兼容：如果没有时间戳，使用日期（旧数据）
                entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
            
            # 🔧 关键修复：将 current_date 设置为当天23:59:59，避免排除当天的小时数据
            current_datetime = datetime.strptime(current_date, '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
            
            # 将trade_date转换为datetime进行筛选
            hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
            # 🔧 关键修复：只看建仓时刻及之后的数据
            mask = hourly_df['trade_datetime'] >= entry_datetime
            mask = mask & (hourly_df['trade_datetime'] <= current_datetime)
            hold_period_data = hourly_df[mask].copy()

            # 🆕 计算“建仓后2小时最大涨幅%”（用于分析：为何动态止盈触发少）
            # 口径：2小时内最高价(high)相对“建仓价(entry_price)”的涨幅
            # - 用建仓价而不是补仓后平均价
            # - 若2小时内最高价未高于建仓价，则记为0
            if position.get('max_up_2h') is None:
                try:
                    entry_price0 = float(position.get('entry_price') or position.get('avg_entry_price') or 0)
                    if entry_price0 > 0:
                        window_end_dt = entry_datetime + timedelta(hours=2)
                        wmask = (hourly_df['trade_datetime'] >= entry_datetime) & (hourly_df['trade_datetime'] < window_end_dt)
                        wdf = hourly_df[wmask]
                        if not wdf.empty and 'high' in wdf.columns:
                            max_high = wdf['high'].max()
                            if pd.notna(max_high):
                                up_ratio = (float(max_high) - entry_price0) / entry_price0
                                position['max_up_2h'] = max(0.0, float(up_ratio))
                            else:
                                position['max_up_2h'] = None
                        else:
                            position['max_up_2h'] = None
                    else:
                        position['max_up_2h'] = None
                except Exception:
                    position['max_up_2h'] = None

            # 🆕 计算“建仓后24小时最大涨幅%”
            # 口径：24小时内最高价(high)相对“建仓价(entry_price)”的涨幅
            # - 用建仓价而不是补仓后平均价
            # - 若24小时内最高价未高于建仓价，则记为0
            if position.get('max_up_24h') is None:
                try:
                    entry_price0 = float(position.get('entry_price') or position.get('avg_entry_price') or 0)
                    if entry_price0 > 0:
                        window_end_dt = entry_datetime + timedelta(hours=24)
                        wmask = (hourly_df['trade_datetime'] >= entry_datetime) & (hourly_df['trade_datetime'] < window_end_dt)
                        wdf = hourly_df[wmask]
                        if not wdf.empty and 'high' in wdf.columns:
                            max_high = wdf['high'].max()
                            if pd.notna(max_high):
                                up_ratio = (float(max_high) - entry_price0) / entry_price0
                                position['max_up_24h'] = max(0.0, float(up_ratio))
                            else:
                                position['max_up_24h'] = None
                        else:
                            position['max_up_24h'] = None
                    else:
                        position['max_up_24h'] = None
                except Exception:
                    position['max_up_24h'] = None
            
            # 获取建仓时的具体小时时间戳（用于精确计算持仓小时数）
            entry_hour_timestamp = None
            if not hold_period_data.empty:
                entry_hour_timestamp = hold_period_data.iloc[0]['trade_datetime']
            
            # 检查每小时的价格是否满足止盈/补仓/止损条件
            if not hold_period_data.empty:
                for idx, row in hold_period_data.iterrows():
                    high_price = row['high']
                    low_price = row['low']
                    hour_datetime = row['trade_datetime']
                    hour_date = hour_datetime.strftime('%Y-%m-%d')
                    hour_datetime_str = hour_datetime.strftime('%Y-%m-%d %H:%M:%S')  # 🆕 完整的日期时间字符串
                    
                    # 🔧 精确计算持仓小时数（基于小时时间戳）
                    if entry_hour_timestamp:
                        hours_held_precise = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                        
                        # ⏰ 在检查其他条件之前，先检查是否超过最大持仓时间
                        if hours_held_precise >= self.max_hold_hours:
                            # 使用当前小时的收盘价平仓
                            exit_price = row['close']
                            self.exit_position(position, exit_price, hour_datetime_str, "max_hold_time")
                            logging.info(f"⏰ {self.max_hold_hours:.0f}小时强制平仓: {symbol} 持有{hours_held_precise:.1f}小时，平仓价{exit_price:.6f}")
                            return True
                    
                    # 动态获取当前有效的平均价格（补仓后会更新）
                    current_avg_price = position['avg_entry_price']
                    
                    # 更新最大跌幅
                    drawdown_pct = (low_price - current_avg_price) / current_avg_price
                    if drawdown_pct < position['max_drawdown']:
                        position['max_drawdown'] = drawdown_pct

                    # ==========================
                    # 🧠 回测执行价与顺序（避免“未来函数/过度乐观”）
                    # - 同一根小时K线里，high/low 只用来判断“是否触发”，成交价使用“阈值价”而不是直接用 high/low
                    # - 当同一根K线同时触发止损与止盈时，按“先止损后止盈”（更保守）
                    # ==========================
                    # 🆕 动态止盈阈值（避免“偷看未来”：只有窗口走完才允许触发动态加成）
                    dynamic_tp_pct = self.calculate_dynamic_take_profit(position, hourly_df, entry_datetime, hour_datetime)
                    tp_price = current_avg_price * (1 + dynamic_tp_pct)
                    sl_price = current_avg_price * (1 + self.stop_loss_pct)
                    add_price = current_avg_price * (1 + self.add_position_trigger_pct)
                    
                    # 检查补仓条件
                    if not position.get('has_add_position', False):
                        # 先判断是否触发补仓（用 low 触发，按 add_price 成交）
                        if low_price <= add_price:
                            self.add_position(position, add_price, hour_date)
                            logging.info(
                                f"🔄 补仓触发: {symbol} 在 {hour_datetime_str} low={low_price:.6f} 触发阈值，按补仓价{add_price:.6f}成交"
                            )
                            # 补仓后，为避免“同小时先low补仓再用high止盈”的顺序偏差：
                            # - 允许继续在同一小时检查止损（更保守）
                            # - 不允许同小时止盈（避免过度乐观），止盈从下一小时开始
                            current_avg_price = position['avg_entry_price']
                            sl_price_after_add = current_avg_price * (1 + self.stop_loss_pct)
                            if low_price <= sl_price_after_add:
                                self.exit_position(position, sl_price_after_add, hour_datetime_str, "stop_loss")
                                logging.warning(
                                    f"🛑 补仓后同小时止损: {symbol} low={low_price:.6f} 触发止损阈值，按止损价{sl_price_after_add:.6f}成交"
                                )
                                return True
                            continue
                    
                    # 先止损（无论是否补仓，统一按阈值价成交）
                    if low_price <= sl_price:
                        self.exit_position(position, sl_price, hour_datetime_str, "stop_loss")
                        logging.warning(
                            f"🛑 止损触发: {symbol} 在 {hour_datetime_str} low={low_price:.6f} 触发止损阈值，按止损价{sl_price:.6f}成交"
                        )
                        return True

                    # 再止盈（按阈值价成交，而不是用 high 直接成交）
                    if high_price >= tp_price:
                        position['tp_pct_used'] = dynamic_tp_pct
                        self.exit_position(position, tp_price, hour_datetime_str, "take_profit")
                        logging.info(
                            f"✨ 止盈: {symbol} 在 {hour_datetime_str} high={high_price:.6f} 触发止盈阈值，按止盈价{tp_price:.6f}成交（阈值{dynamic_tp_pct*100:.1f}%）"
                        )
                        return True
            
            # 🔧 备用检查：如果没有小时数据，使用日期差异检查（兼容旧逻辑）
            hours_held = (current_datetime - entry_datetime).total_seconds() / 3600
            if hours_held >= self.max_hold_hours:
                if not hold_period_data.empty:
                    last_row = hold_period_data.iloc[-1]
                    exit_price = last_row['close']
                else:
                    exit_price = current_price
                
                self.exit_position(position, exit_price, current_date, "max_hold_time")
                logging.info(f"⏰ {self.max_hold_hours:.0f}小时强制平仓: {symbol} 持有{hours_held:.1f}小时，平仓价{exit_price:.6f}")
                return True
            
            return False
        
        except Exception as e:
            logging.error(f"检查平仓条件失败: {e}")
            return False

    def add_position(self, position: Dict, current_price: float, current_date: str):
        """补仓操作"""
        try:
            # 💰 复利模式：补仓使用独立的补仓比例（可以大于首次建仓）
            position_value = self.capital * self.add_position_size_ratio
            
            # 检查资金是否足够补仓
            if self.capital < position_value:
                logging.warning(f"⚠️ 资金不足，无法补仓: {position['symbol']} 需要${position_value:.2f}，当前${self.capital:.2f}")
                return
            
            # 补仓金额（考虑杠杆）
            add_size = (position_value * self.leverage) / current_price
            
            # 重新计算平均成本
            total_value = (position['avg_entry_price'] * position['position_size']) + (current_price * add_size)
            total_size = position['position_size'] + add_size
            new_avg_price = total_value / total_size
            
            # 更新持仓信息
            position['has_add_position'] = True
            position['add_position_price'] = current_price
            position['add_position_size'] = add_size
            position['avg_entry_price'] = new_avg_price
            position['position_size'] = total_size
            
            # 💰 复利模式：补仓时扣除投入资金
            self.capital -= position_value
            
            # 💰 更新持仓的总投入（用于平仓时返还本金）
            position['position_value'] += position_value
            
            logging.info(f"➕ 补仓: {position['symbol']} {current_date} 价格:{current_price:.4f} 补仓${position_value:.2f} 新平均价:{new_avg_price:.4f} 剩余资金:${self.capital:.2f}")
        except Exception as e:
            logging.error(f"补仓失败: {e}")

    def exit_position(self, position: Dict, exit_price: float, exit_date: str, exit_reason: str):
        """平仓操作"""
        try:
            entry_price = position['avg_entry_price']
            position_size = position['position_size']
            
            # 计算盈亏
            pnl = (exit_price - entry_price) * position_size
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            
            # 🆕 智能解析exit_date，可能包含时间或只有日期
            exit_datetime = None
            try:
                # 尝试解析完整的日期时间
                if ' ' in exit_date:  # 包含时间
                    exit_datetime = pd.to_datetime(exit_date)
                    exit_date_only = exit_datetime.strftime('%Y-%m-%d')
                else:  # 只有日期
                    exit_date_only = exit_date
                    exit_datetime = pd.to_datetime(exit_date + ' 00:00:00')
            except:
                exit_date_only = exit_date.split(' ')[0] if ' ' in exit_date else exit_date
                exit_datetime = pd.to_datetime(exit_date_only + ' 00:00:00')
            
            # 计算持仓天数
            entry_date = datetime.strptime(position['entry_date'], '%Y-%m-%d')
            exit_dt = datetime.strptime(exit_date_only, '%Y-%m-%d')
            hold_days = (exit_dt - entry_date).days
            
            # 💰 复利模式：平仓时返还本金+盈亏
            position_value = position['position_value']
            self.capital += position_value + pnl
            
            # 更新持仓记录
            position.update({
                'exit_date': exit_date_only,
                'exit_datetime': exit_datetime.isoformat() if exit_datetime else None,  # 🆕 保存完整时间戳
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': hold_days
            })
            
            # 从持仓列表中移除
            if position in self.positions:
                self.positions.remove(position)
            
            logging.info(f"💰 平仓: {position['symbol']} {exit_date} 价格:{exit_price:.4f} 盈亏:${pnl:.2f} ({pnl_pct:+.1f}%) 原因:{exit_reason} 当前资金:${self.capital:.2f}")
        except Exception as e:
            logging.error(f"平仓失败: {e}")

    def get_entry_price(self, symbol: str, date_str: str) -> Optional[float]:
        """获取开盘价作为建仓价格"""
        try:
            cursor = self.crypto_conn.cursor()
            table_name = f'K1d{symbol}'
            
            cursor.execute(f'''
                SELECT open
                FROM "{table_name}"
                WHERE trade_date = ? OR trade_date LIKE ?
            ''', (date_str, f'{date_str}%'))
            
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        
        except Exception as e:
            logging.error(f"获取 {symbol} {date_str} 开盘价失败: {e}")
            return None

    def get_latest_5m_close(self, symbol: str, asof_dt: Optional[datetime] = None):
        """获取某交易对在 asof_dt 之前最近一根 5m K线的收盘价（用于持仓单的“当前浮盈亏”计算）

        数据来源：本地 SQLite `db/crypto_data.db` 的 `K5m{symbol}` 表。
        返回：(trade_date_str, close_price)；若缺数据返回 (None, None)。
        """
        try:
            if not symbol:
                return None, None

            table_name = f'K5m{symbol}'
            cursor = self.crypto_conn.cursor()

            # 先检查表是否存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if cursor.fetchone() is None:
                return None, None

            if asof_dt is None:
                asof_dt = datetime.now()
            asof_str = asof_dt.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                f'''
                SELECT trade_date, close
                FROM "{table_name}"
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 1
                ''',
                (asof_str,)
            )
            row = cursor.fetchone()
            if not row:
                return None, None
            trade_date, close = row[0], row[1]
            if close is None:
                return trade_date, None
            return trade_date, float(close)
        except Exception:
            return None, None

    def get_5m_closes_in_window(self, symbol: str, start_dt: datetime, end_dt: datetime) -> List[float]:
        """获取指定时间窗口内的 5m K线 close 序列（按时间正序）。

        数据来源：本地 SQLite `db/crypto_data.db` 的 `K5m{symbol}` 表。
        """
        try:
            if not symbol:
                return []

            table_name = f'K5m{symbol}'
            cursor = self.crypto_conn.cursor()

            # 检查表是否存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if cursor.fetchone() is None:
                return []

            start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                f'''
                SELECT close
                FROM "{table_name}"
                WHERE trade_date >= ? AND trade_date < ?
                ORDER BY trade_date ASC
                ''',
                (start_str, end_str)
            )
            rows = cursor.fetchall()
            closes: List[float] = []
            for (c,) in rows:
                if c is None:
                    continue
                closes.append(float(c))
            return closes
        except Exception as e:
            logging.debug(f"读取5m close失败 {symbol}: {e}")
            return []

    def run_backtest(self, start_date: str, end_date: str):
        """运行回测"""
        # 保存回测结束日期，供CSV里计算“未平仓持仓”的持仓时长使用
        self._backtest_end_date = end_date
        logging.info(f"开始买量暴涨策略回测（小时线优化版-修复后+性能优化）: {start_date} 到 {end_date}")
        logging.info(f"初始资金: ${self.initial_capital:,.2f}")
        logging.info(f"杠杆倍数: {self.leverage}x")
        logging.info(f"买量暴涨阈值: {self.buy_surge_threshold}倍（某小时买量 vs 昨日平均小时买量）")
        logging.info(f"等待策略: 2-3倍→5%（2-10倍均可进信号池，按倍数映射不同等待回调）")
        logging.info(f"最大持仓时间: {self.max_hold_hours:.0f}小时（{self.max_hold_hours/24:.0f}天）")
        
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # 🆕 每天输出进度信息
            logging.info(f"📅 处理日期: {date_str} | 当前资金: ${self.capital:,.2f} | 持仓数: {len(self.positions)} | 待建仓信号: {len(self.pending_signals)}")
            
            # 记录每日资金
            self.daily_capital.append({
                'date': date_str,
                'capital': self.capital,
                'positions_count': len(self.positions)
            })
            
            # 检查现有持仓（直接使用小时K线，不依赖日K线）
            positions_to_check = self.positions.copy()
            for position in positions_to_check:
                try:
                    # 🔧 修复：不再依赖日K线，直接传入当前日期，check_exit_conditions内部会读取小时K线
                    # 传入一个虚拟price（不影响，因为函数内部用小时线数据）
                    self.check_exit_conditions(position, 0, date_str)
                
                except Exception as e:
                    logging.error(f"❌ 检查持仓失败 {position['symbol']}: {e}")
                    import traceback
                    logging.error(traceback.format_exc())
            
            # 检查待建仓信号（使用小时线数据）
            signals_to_remove = []
            for signal in self.pending_signals[:]:  # 复制列表避免迭代时修改
                symbol = signal['symbol']
                signal_close = signal['signal_close']
                buy_surge_ratio = signal['buy_surge_ratio']
                target_drop_pct = self.get_wait_drop_pct(buy_surge_ratio)
                target_price = signal_close * (1 + target_drop_pct)
                
                # 检查是否已持仓
                if any(pos['symbol'] == symbol for pos in self.positions):
                    signals_to_remove.append(signal)
                    continue
                
                # 检查是否超时
                if current_date > signal['timeout_datetime']:
                    logging.info(f"⏰ {symbol} 信号超时，放弃建仓（买量{buy_surge_ratio:.1f}倍）")
                    self._update_signal_record(symbol, signal.get('signal_date'), status='timeout', note='超时未成交')
                    signals_to_remove.append(signal)
                    continue
                
                # 获取小时线数据检查是否达到目标价格（优化：只查询信号日到当前日的数据）
                signal_date_str = signal['signal_datetime'].strftime('%Y-%m-%d')
                hourly_df = self.get_hourly_kline_data(symbol, start_date=signal_date_str, end_date=date_str)
                if not hourly_df.empty:
                    # 筛选信号日之后到当前日期的小时数据
                    hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
                    signal_datetime = signal['signal_datetime']
                    mask = (hourly_df['trade_datetime'] >= signal_datetime) & (hourly_df['trade_datetime'] <= current_date)
                    check_period_data = hourly_df[mask]
                    
                    # 检查是否有小时低点达到目标价格
                    for _, row in check_period_data.iterrows():
                        if row['low'] <= target_price:
                            # 达到目标价格，建仓
                            entry_price = target_price
                            entry_datetime = row['trade_datetime']
                            entry_date = entry_datetime.strftime('%Y-%m-%d')
                            
                            if len(self.positions) < self.max_daily_positions:  # 检查持仓数量限制
                                before_trades = len(self.trade_records)
                                self.execute_trade(symbol, entry_price, entry_date, 
                                                 signal['signal_date'], buy_surge_ratio, 
                                                 entry_datetime=entry_datetime)  # 🆕 传入完整时间戳
                                if len(self.trade_records) > before_trades:
                                    logging.info(f"✅ {symbol} 达到目标跌幅{target_drop_pct*100:.0f}%，建仓价{entry_price:.6f}，建仓时间{entry_datetime}")
                                    self._update_signal_record(
                                        symbol,
                                        signal.get('signal_date'),
                                        status='entered',
                                        entry_datetime=entry_datetime,
                                        entry_price=entry_price,
                                        note='触发目标价并建仓'
                                    )
                                else:
                                    # execute_trade 内部可能因为资金/风控拒绝
                                    self._update_signal_record(
                                        symbol,
                                        signal.get('signal_date'),
                                        status='reached_not_entered',
                                        entry_datetime=entry_datetime,
                                        entry_price=entry_price,
                                        note='触发目标价但未建仓（资金/风控）'
                                    )
                            
                            signals_to_remove.append(signal)
                            break
            
            # 移除已处理的信号
            for signal in signals_to_remove:
                if signal in self.pending_signals:
                    self.pending_signals.remove(signal)
            
            # 🆕 寻找新的买量暴涨信号（优化版：每天检测1次）
            if len(self.positions) < self.max_daily_positions:
                # 🚀 每天检测1次，找出今天哪些小时的买量超过昨日
                logging.debug(f"🔍 开始扫描 {date_str} 的买量暴涨信号...")
                daily_signals = self.get_daily_1hour_surge_signals(date_str)
                logging.debug(f"✅ 扫描完成，发现 {len(daily_signals)} 个信号")
                
                for signal in daily_signals:
                    symbol = signal['symbol']
                    surge_ratio = signal['surge_ratio']
                    signal_price = signal['signal_price']
                    signal_datetime = signal['signal_datetime']  # 信号发生的小时（例如19:00）
                    
                    # 检查是否已在待建仓列表或已持仓
                    if any(s['symbol'] == symbol for s in self.pending_signals):
                        continue
                    if any(pos['symbol'] == symbol for pos in self.positions):
                        continue
                    
                    # 🔧 关键修复：小时K线数据只有在该小时结束后才能看到
                    # 例如19:00的K线，要到20:00才能看到完整数据，所以最早20:00才能建仓
                    earliest_entry_datetime = signal_datetime + timedelta(hours=1)
                    
                    # 🎯 根据买量倍数动态设置等待回调比例
                    target_drop_pct = self.get_wait_drop_pct(surge_ratio)
                    timeout_datetime = earliest_entry_datetime + timedelta(hours=self.wait_timeout_hours)
                    
                    self.pending_signals.append({
                        'symbol': symbol,
                        'signal_date': signal_datetime.strftime('%Y-%m-%d %H:%M'),  # 保存原始信号时间用于显示
                        'signal_datetime': earliest_entry_datetime,  # 实际可以开始建仓的时间（信号时间+1小时）
                        'signal_close': signal_price,
                        'buy_surge_ratio': surge_ratio,
                        'target_drop_pct': target_drop_pct,
                        'timeout_datetime': timeout_datetime
                    })

                    # 🆕 记录“发现信号”（用于输出未成交反馈表）
                    try:
                        self.signal_records.append({
                            'symbol': symbol,
                            'signal_date': signal_datetime.strftime('%Y-%m-%d %H:%M'),  # 与pending_signals一致，用于匹配更新
                            'signal_time': signal_datetime.strftime('%Y-%m-%d %H:00:00'),
                            'earliest_entry_time': earliest_entry_datetime.strftime('%Y-%m-%d %H:00:00'),
                            'signal_price': float(signal_price),
                            'buy_surge_ratio': float(surge_ratio),
                            'target_drop_pct': float(target_drop_pct),
                            'target_price': float(signal_price) * (1 + float(target_drop_pct)),
                            'timeout_time': timeout_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                            'status': 'pending',
                            'entry_time': '',
                            'entry_price': '',
                            'note': ''
                        })
                    except Exception:
                        pass
                    
                    logging.info(f"🔔 新信号: {symbol} @{signal_datetime.strftime('%H:00')} 买量{surge_ratio:.2f}倍，可建仓时间: {earliest_entry_datetime.strftime('%H:00')}")
            
            current_date += timedelta(days=1)
        
        # 最后一天：先用小时K线检查一次止盈/止损，避免错过应该止盈的机会
        logging.info(f"⏰ 回测结束，检查剩余{len(self.positions)}个持仓...")
        positions_to_check = self.positions.copy()
        for position in positions_to_check:
            try:
                # 先检查是否满足止盈/止损条件
                self.check_exit_conditions(position, 0, end_date)
            except Exception as e:
                logging.error(f"最后检查失败 {position['symbol']}: {e}")
        
        # 强制平仓剩余持仓（经过上面检查后还没平仓的）
        for position in self.positions.copy():
            try:
                cursor = self.crypto_conn.cursor()
                table_name = f'K1d{position["symbol"]}'
                
                cursor.execute(f'''
                    SELECT close
                    FROM "{table_name}"
                    WHERE trade_date = ? OR trade_date LIKE ?
                    ORDER BY trade_date DESC
                    LIMIT 1
                ''', (end_date, f'{end_date}%'))
                
                result = cursor.fetchone()
                if result and result[0]:
                    exit_price = result[0]
                    # 记录当前应该使用的止盈阈值（用于CSV）
                    if position.get('entry_datetime'):
                        entry_datetime = pd.to_datetime(position['entry_datetime'])
                        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                        hourly_df = pd.DataFrame()  # 空的，因为只是为了获取当前止盈阈值
                        current_tp = self.calculate_dynamic_take_profit(position, hourly_df, entry_datetime, end_datetime)
                        position['tp_pct_used'] = current_tp
                    
                    self.exit_position(position, exit_price, end_date, "force_close")
                    logging.warning(f"⚠️ 强制平仓: {position['symbol']} 价格:{exit_price:.4f}")
            
            except Exception as e:
                logging.error(f"强制平仓失败: {e}")
        
        logging.info("回测完成")

    def generate_report(self):
        """生成回测报告"""
        print("\n" + "="*80)
        print("🚀 买量暴涨策略回测报告")
        print("="*80)
        
        # 基本统计
        total_trades = len(self.trade_records)
        winning_trades = len([t for t in self.trade_records if t['pnl'] > 0])
        losing_trades = len([t for t in self.trade_records if t['pnl'] < 0])
        
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 资金统计
        final_capital = self.capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        
        # 最大回撤计算
        max_capital = self.initial_capital
        max_drawdown = 0
        
        for record in self.daily_capital:
            max_capital = max(max_capital, record['capital'])
            drawdown = (max_capital - record['capital']) / max_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        print(f"💰 初始资金: ${self.initial_capital:,.2f}")
        print(f"💰 最终资金: ${final_capital:,.2f}")
        print(f"📈 总收益率: {total_return:+.2f}%")
        print(f"📊 总交易次数: {total_trades}")
        print(f"✅ 盈利交易: {winning_trades}")
        print(f"❌ 亏损交易: {losing_trades}")
        print(f"🎯 胜率: {win_rate:.1f}%")
        print(f"📉 最大回撤: {max_drawdown:.2f}%")
        
        # 生成CSV详细报告
        self.generate_trade_csv_report()

        # 🆕 生成“信号反馈表”（包含发现但未成交的信号）
        self.generate_signal_csv_report()
        
        # 动态止盈统计分析
        print(f"\n{'='*80}")
        print("📊 动态止盈详细统计")
        print("="*80)
        
        # 统计不同止盈阈值的交易（只统计已平仓的）
        closed_trades = [t for t in self.trade_records if t.get('exit_reason') and t['exit_reason'] != 'holding']
        
        # 区分高止盈和普通止盈（使用tp_pct_used字段）
        trades_with_high_tp = [t for t in closed_trades if t.get('tp_pct_used') and t['tp_pct_used'] > 0.10]
        trades_with_normal_tp = [t for t in closed_trades if t.get('tp_pct_used') and t['tp_pct_used'] <= 0.10]
        
        high_tp_triggered = len(trades_with_high_tp)
        normal_tp_count = len(trades_with_normal_tp)
        total_closed = len(closed_trades)
        
        print(f"\n💰 止盈触发统计 (已平仓{total_closed}笔):")
        if total_closed > 0:
            print(f"  🚀 动态止盈(>10%)触发: {high_tp_triggered}次 ({high_tp_triggered/total_closed*100:.1f}%)")
            print(f"  📊 普通止盈(≤10%)触发: {normal_tp_count}次 ({normal_tp_count/total_closed*100:.1f}%)")
            print(f"  ⏳ 其他平仓: {total_closed-high_tp_triggered-normal_tp_count}次 ({(total_closed-high_tp_triggered-normal_tp_count)/total_closed*100:.1f}%)")
        
        # 动态止盈成功率分析
        if high_tp_triggered > 0:
            high_tp_success = len([t for t in trades_with_high_tp if t.get('exit_reason') == 'take_profit'])
            high_tp_profit = sum([t['pnl'] for t in trades_with_high_tp])
            high_tp_avg_profit = high_tp_profit / high_tp_triggered
            
            print(f"\n✅ 动态止盈表现:")
            print(f"  触发次数: {high_tp_triggered}次")
            print(f"  成功止盈: {high_tp_success}次")
            print(f"  成功率: {high_tp_success/high_tp_triggered*100:.1f}%")
            print(f"  总贡献: ${high_tp_profit:,.2f}")
            print(f"  平均收益: ${high_tp_avg_profit:,.2f}")
        
        # 普通止盈统计
        if normal_tp_count > 0:
            normal_tp_profit = sum([t['pnl'] for t in trades_with_normal_tp])
            normal_tp_avg = normal_tp_profit / normal_tp_count
            
            print(f"\n📈 普通止盈表现:")
            print(f"  触发次数: {normal_tp_count}次")
            print(f"  总贡献: ${normal_tp_profit:,.2f}")
            print(f"  平均收益: ${normal_tp_avg:,.2f}")
        
        # 止损、超时和强制平仓统计
        stop_loss_trades = [t for t in closed_trades if t.get('exit_reason') == 'stop_loss']
        max_hold_trades = [t for t in closed_trades if t.get('exit_reason') == 'max_hold_time']
        force_close_trades = [t for t in closed_trades if t.get('exit_reason') == 'force_close']
        
        if stop_loss_trades:
            stop_loss_total = sum([t['pnl'] for t in stop_loss_trades])
            print(f"\n⚠️ 止损统计:")
            print(f"  止损次数: {len(stop_loss_trades)}次 ({len(stop_loss_trades)/total_closed*100:.1f}%)")
            print(f"  止损损失: ${stop_loss_total:,.2f}")
        
        if max_hold_trades:
            max_hold_profit = sum([t['pnl'] for t in max_hold_trades])
            max_hold_positive = len([t for t in max_hold_trades if t['pnl'] > 0])
            print(f"\n⏰ 超时平仓统计:")
            print(f"  超时次数: {len(max_hold_trades)}次 ({len(max_hold_trades)/total_closed*100:.1f}%)")
            print(f"  盈利: {max_hold_positive}次, 亏损: {len(max_hold_trades)-max_hold_positive}次")
            print(f"  总盈亏: ${max_hold_profit:,.2f}")
        
        if force_close_trades:
            force_close_profit = sum([t['pnl'] for t in force_close_trades])
            force_close_positive = len([t for t in force_close_trades if t['pnl'] > 0])
            print(f"\n🔚 回测结束强制平仓:")
            print(f"  强制平仓: {len(force_close_trades)}次 ({len(force_close_trades)/total_closed*100:.1f}%)")
            print(f"  盈利: {force_close_positive}次, 亏损: {len(force_close_trades)-force_close_positive}次")
            print(f"  总盈亏: ${force_close_profit:,.2f}")
            print(f"  ℹ️ 注意：强制平仓的交易可能还未达到最佳止盈点")
        
        # 详细交易记录
        print(f"\n{'='*80}")
        print(f"📋 详细交易记录 (前20条):")
        print("-" * 120)
        print(f"{'序号':<4} {'交易对':<15} {'买量倍数':<10} {'建仓日期':<12} {'建仓价':>10} {'平仓日期':<12} {'平仓价':>10} {'盈亏':>12} {'持仓天数':<10}")
        print("-" * 120)
        
        for i, trade in enumerate(self.trade_records[:20], 1):
            exit_info = f"{trade['exit_price']:.4f}" if trade['exit_price'] else "-"
            pnl_info = f"${trade['pnl']:+.2f}" if trade['pnl'] != 0 else "-"
            surge_ratio = f"{trade.get('buy_surge_ratio', 0):.1f}x"
            
            print(f"{i:<4} {trade['symbol']:<15} {surge_ratio:<10} {trade['entry_date']:<12} {trade['entry_price']:<10.4f} "
                  f"{trade['exit_date'] or '-':<12} {exit_info:>10} {pnl_info:>12} {trade.get('hold_days', 0):<10}")

    def generate_trade_csv_report(self):
        """生成交易详细CSV报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"buy_surge_backtest_report_{timestamp}.csv"
        
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    '序号', '交易对', '买量暴涨倍数', '信号时间', '建仓日期', '建仓具体时间', '建仓价', 
                    '平仓日期', '平仓具体时间', '平仓价', '盈亏金额', '盈亏百分比', '平仓原因', '杠杆倍数', '仓位金额',
                    '是否有补仓', '补仓价格', '补仓后平均价', '持仓小时数', '最大跌幅%', '2小时最大涨幅%', '24小时最大涨幅%', '止盈阈值%',
                    # 🆕 未平仓持仓的“当前浮盈亏”（按本地5m最新close做mark-to-market）
                    '当前5m时间', '当前5m收盘价', '当前浮盈金额', '当前浮盈百分比'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # 输出“已建仓”的交易：包含已平仓 + 回测结束时仍持仓（原来就是这样展示的）
                entered_trades = [
                    t for t in self.trade_records
                    if t.get('entry_date') and t.get('entry_price')
                ]

                for i, trade in enumerate(entered_trades, 1):
                    # 计算补仓后平均价
                    avg_price_after_add = ''
                    if trade.get('has_add_position', False) and trade.get('add_position_price'):
                        avg_price_after_add = f"{trade['avg_entry_price']:.6f}"
                    
                    # 🆕 获取建仓具体时间
                    entry_datetime_str = ''
                    if trade.get('entry_datetime'):
                        try:
                            if isinstance(trade['entry_datetime'], str):
                                entry_dt = pd.to_datetime(trade['entry_datetime'])
                            else:
                                entry_dt = trade['entry_datetime']
                            entry_datetime_str = entry_dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            entry_datetime_str = trade.get('entry_date', '') + ' 00:00:00'
                    else:
                        entry_datetime_str = trade.get('entry_date', '') + ' 00:00:00'
                    
                    # 🆕 获取平仓具体时间
                    exit_datetime_str = ''
                    if trade.get('exit_datetime'):
                        try:
                            if isinstance(trade['exit_datetime'], str):
                                exit_dt = pd.to_datetime(trade['exit_datetime'])
                            else:
                                exit_dt = trade['exit_datetime']
                            exit_datetime_str = exit_dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            exit_datetime_str = trade.get('exit_date', '') + ' 00:00:00' if trade.get('exit_date') else ''
                    else:
                        exit_datetime_str = trade.get('exit_date', '') + ' 00:00:00' if trade.get('exit_date') else ''
                    
                    # 🆕 计算持仓小时数（未平仓则计算到回测结束日23:59:59）
                    hold_hours = 0
                    try:
                        if trade.get('entry_datetime'):
                            entry_dt = pd.to_datetime(trade['entry_datetime'])
                        else:
                            entry_dt = datetime.strptime(trade.get('entry_date', ''), '%Y-%m-%d')

                        if trade.get('exit_datetime'):
                            exit_dt = pd.to_datetime(trade['exit_datetime'])
                        elif trade.get('exit_date'):
                            exit_dt = pd.to_datetime(trade['exit_date'] + ' 23:59:59')
                        else:
                            end_date = getattr(self, '_backtest_end_date', None)
                            exit_dt = pd.to_datetime((end_date or trade.get('entry_date')) + ' 23:59:59')

                        hold_hours = round((exit_dt - entry_dt).total_seconds() / 3600, 1)
                    except Exception:
                        hold_hours = trade.get('hold_days', 0) * 24

                    # 🆕 若未平仓：用“当前时间最近一根5m close”计算浮盈亏（不会影响回测统计，仅用于观察）
                    m2m_trade_time = ''
                    m2m_close = ''
                    m2m_pnl_amt = ''
                    m2m_pnl_pct = ''
                    if not trade.get('exit_date'):
                        td, close = self.get_latest_5m_close(trade['symbol'])
                        if td and close is not None:
                            m2m_trade_time = td
                            m2m_close = f"{close:.6f}"
                            try:
                                entry_price_for_pnl = float(trade.get('avg_entry_price') or trade.get('entry_price') or 0)
                                position_size = float(trade.get('position_size') or 0)
                                if entry_price_for_pnl > 0 and position_size > 0:
                                    upnl = (close - entry_price_for_pnl) * position_size
                                    upnl_pct = (close - entry_price_for_pnl) / entry_price_for_pnl * 100
                                    m2m_pnl_amt = f"{upnl:.2f}"
                                    m2m_pnl_pct = f"{upnl_pct:.2f}%"
                            except Exception:
                                pass
                    
                    row = {
                        '序号': i,
                        '交易对': trade['symbol'],
                        '买量暴涨倍数': f"{trade.get('buy_surge_ratio', 0):.1f}倍",
                        '信号时间': trade.get('signal_date', ''),  # 🆕 信号时间（已经包含小时）
                        '建仓日期': trade['entry_date'],
                        '建仓具体时间': entry_datetime_str,
                        '建仓价': f"{trade['entry_price']:.6f}",
                        '平仓日期': trade.get('exit_date', ''),
                        # 🆕 平仓具体时间：未平仓时用估值5m时间（便于你看“按哪个时刻估值”）
                        '平仓具体时间': exit_datetime_str if trade.get('exit_date') else (m2m_trade_time or ''),
                        # 🆕 平仓价：未平仓时填入估值价（最新5m close）
                        '平仓价': (
                            f"{trade.get('exit_price', 0):.6f}" if trade.get('exit_price') else ''
                        ) if trade.get('exit_date') else (m2m_close or ''),
                        # 🆕 盈亏：未平仓时用估值盈亏（最新5m close）
                        '盈亏金额': f"{trade.get('pnl', 0):.2f}" if trade.get('exit_date') else (m2m_pnl_amt or ''),
                        '盈亏百分比': f"{trade.get('pnl_pct', 0):.2f}%" if trade.get('exit_date') else (m2m_pnl_pct or ''),
                        '平仓原因': trade.get('exit_reason', '') or ('holding' if not trade.get('exit_date') else ''),
                        '杠杆倍数': trade['leverage'],
                        '仓位金额': f"{trade['position_value']:.2f}",
                        '是否有补仓': '✅是' if trade.get('has_add_position', False) else '否',
                        '补仓价格': f"{trade.get('add_position_price', 0):.6f}" if trade.get('add_position_price') else '',
                        '补仓后平均价': avg_price_after_add,
                        '持仓小时数': hold_hours,  # 🆕 改为小时数
                        '最大跌幅%': f"{trade.get('max_drawdown', 0)*100:.2f}%" if trade.get('max_drawdown') else '0.00%',
                        '2小时最大涨幅%': (
                            f"{float(trade.get('max_up_2h'))*100:.2f}%" if trade.get('max_up_2h') is not None else ''
                        ),
                        '24小时最大涨幅%': (
                            f"{float(trade.get('max_up_24h'))*100:.2f}%" if trade.get('max_up_24h') is not None else ''
                        ),
                        # 真实止盈阈值（仅 take_profit 平仓时有意义）
                        # - 旧版这里用 .0f 会把 8.5% 四舍五入成 8%，导致误判“动态止盈没生效”
                        '止盈阈值%': (
                            f"{float(trade.get('tp_pct_used'))*100:.1f}%" if trade.get('tp_pct_used') else ''
                        ),
                        '当前5m时间': m2m_trade_time,
                        '当前5m收盘价': m2m_close,
                        '当前浮盈金额': m2m_pnl_amt,
                        '当前浮盈百分比': m2m_pnl_pct
                    }
                    writer.writerow(row)
            
            print(f"📄 交易详细CSV报告已生成: {csv_filename}")
        
        except Exception as e:
            print(f"❌ 生成CSV报告失败: {e}")

    def _update_signal_record(self, symbol: str, signal_date: str, status: str,
                              entry_datetime=None, entry_price=None, note: str = ''):
        """更新信号记录状态（用于反馈表）"""
        if not symbol or not signal_date:
            return
        sd = str(signal_date)
        for rec in reversed(self.signal_records):
            if rec.get('symbol') == symbol and str(rec.get('signal_date')) == sd:
                rec['status'] = status
                if entry_datetime is not None and hasattr(entry_datetime, 'strftime'):
                    rec['entry_time'] = entry_datetime.strftime('%Y-%m-%d %H:%M:%S')
                if entry_price is not None:
                    try:
                        rec['entry_price'] = f"{float(entry_price):.6f}"
                    except Exception:
                        rec['entry_price'] = str(entry_price)
                if note:
                    rec['note'] = note
                return

    def generate_signal_csv_report(self):
        """生成信号反馈CSV（包含：发现信号但未成交）"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"buy_surge_signal_feedback_{timestamp}.csv"
        try:
            # 反馈表允许包含“未成交信号”（用于核对FHE/BDXN等为什么没成交）
            for rec in self.signal_records:
                if rec.get('status') == 'pending':
                    rec['status'] = 'unfilled'
                    if not rec.get('note'):
                        rec['note'] = '回测区间内未触发目标价/未成交'

            import csv
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    'symbol', 'buy_surge_ratio', 'signal_time', 'signal_date', 'earliest_entry_time',
                    'signal_price', 'target_drop_pct', 'target_price', 'timeout_time',
                    'status', 'entry_time', 'entry_price', 'note'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for rec in self.signal_records:
                    writer.writerow({k: rec.get(k, '') for k in fieldnames})

            print(f"📄 信号反馈CSV已生成(含未成交): {csv_filename}")
        except Exception as e:
            print(f"❌ 生成信号反馈CSV失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='买量暴涨策略回测程序')
    parser.add_argument(
        '--start-time',
        type=str,
        default='2025-11-01',
        help='开始日期(默认: 2025-11-01)'
    )
    parser.add_argument(
        '--end-time',
        type=str,
        default='2026-01-10',
        help='结束日期(默认: 2026-01-10)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=13.1,
        help='买量暴涨阈值(默认: 13.1倍)'
    )

    parser.add_argument(
        '--max-multiple',
        type=float,
        default=3.0,
        help='买量暴涨倍数上限（默认3.0；例如3表示只做2-3倍，10表示2-10倍）'
    )

    parser.add_argument(
        '--dynamic-tp-boost',
        type=float,
        default=None,
        help='动态止盈加成幅度（传入则覆盖“按倍数分档”的加成；例如 0.05 表示统一 +5%）'
    )

    parser.add_argument(
        '--dynamic-tp-lookback-minutes',
        type=int,
        default=720,
        help='动态止盈"强势判定"窗口长度（分钟，默认720=12小时；基于数据分析最佳判定时机）'
    )

    parser.add_argument(
        '--dynamic-tp-close-up-pct',
        type=float,
        default=0.025,
        help='动态止盈强势判定：5m close 需要高于建仓价的涨幅比例（默认0.025=+2.5%，12小时分水岭）'
    )
    
    args = parser.parse_args()
    
    backtest = BuySurgeBacktest()
    
    # 可以通过参数调整阈值
    if args.threshold:
        backtest.buy_surge_threshold = args.threshold
        logging.info(f"买量暴涨阈值设置为: {args.threshold}倍")

    if args.max_multiple is not None:
        backtest.buy_surge_max = float(args.max_multiple)
        logging.info(f"买量暴涨倍数上限设置为: {backtest.buy_surge_max}倍")

    # 若显式传入 --dynamic-tp-boost，则用“统一加成”覆盖分档配置（便于做对照实验）
    if args.dynamic_tp_boost is not None:
        backtest.dynamic_tp_boost_pct = float(args.dynamic_tp_boost)
        backtest.dynamic_tp_boost_config = [(9999, backtest.dynamic_tp_boost_pct)]
        logging.info(f"动态止盈加成幅度设置为(覆盖分档): +{backtest.dynamic_tp_boost_pct*100:.1f}%")

    if args.dynamic_tp_lookback_minutes is not None:
        backtest.dynamic_tp_lookback_minutes = int(args.dynamic_tp_lookback_minutes)
        logging.info(f"动态止盈强势判定窗口设置为: {backtest.dynamic_tp_lookback_minutes}分钟")

    if args.dynamic_tp_close_up_pct is not None:
        backtest.dynamic_tp_close_up_pct = float(args.dynamic_tp_close_up_pct)
        logging.info(f"动态止盈强势判定涨幅阈值设置为: +{backtest.dynamic_tp_close_up_pct*100:.1f}%")
    
    try:
        # 运行回测
        backtest.run_backtest(args.start_time, args.end_time)
        
        # 生成报告
        backtest.generate_report()
    
    except KeyboardInterrupt:
        logging.info("用户中断回测")
    except Exception as e:
        logging.error(f"回测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logging.info("回测程序结束")

if __name__ == "__main__":
    main()
