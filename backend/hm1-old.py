#!/usr/bin/env python3
"""
买量暴涨策略回测程序
基于主动买量暴涨信号的快进快出策略（优化版-等待回调+动态止盈）

策略逻辑：
1. 信号识别：
   - 扫描所有USDT交易对，寻找当日主动买量 vs 昨日主动买量 >= 阈值（默认20倍，可通过--threshold参数调整）
   - 信号过滤：检查信号触发前1小时涨幅
     * 涨幅<5%：拒绝信号（涨幅太低）
     * 涨幅>48.5%：拒绝信号（追高风险）
     * 5%≤涨幅≤48.5%：通过检查

2. 等待回调策略（根据买量倍数动态调整）：
   - 20-30倍买量：等待回调3%
   - 30-60倍买量：等待回调4%
   - 60-100倍买量：等待回调5%
   - 100倍以上：等待回调6%
   - 超时机制：信号后48小时内未达到目标跌幅则放弃

3. 建仓参数：
   - 杠杆倍数：4倍
   - 单次建仓占资金比例：5%
   - 最大持仓数量：10个
   - 使用小时K线数据检查是否达到目标回调价格

4. 补仓机制：
   - 触发条件：价格从建仓价下跌18%
   - 补仓数量：等于首次建仓数量
   - 重新计算平均成本
   - 补仓后立即检查止盈/止损（基于新平均成本）

5. 止盈机制（动态调整）：
   - 基础止盈：20%
   - 动态止盈（基于建仓后2小时的价格表现）：
     * 80%时间在+10%以上：止盈提高到30%（强势币）
     * 80%时间在+2%~+10%：止盈提高到25%（稳健币）
     * 其他情况：使用基础止盈20%

6. 止损机制：
   - 补仓后基于新平均成本下跌18%触发止损
   - 使用小时K线数据实时检查

7. 持仓限制：
   - 最大持仓时间：72小时（3天）强制平仓
   - 使用小时K线数据进行精确的持仓时间计算

8. 数据源：
   - 日K线数据：从 K1d{symbol} 表读取（如 K1dBTCUSDT）
   - 小时K线数据：从 K1h{symbol} 表读取（如 K1hBTCUSDT）
   - 数据库路径：支持环境变量 DB_PATH，默认使用项目根目录下的 data/crypto_data.db

9. 报告生成：
   - CSV详细报告保存到 data/backtrade_records/ 目录
   - 文件名格式：buy_surge_backtest_report_YYYYMMDD_HHMMSS.csv
   - 包含完整的交易记录和统计信息

使用方法：
    python hm1.py --start-time 2025-11-01 --end-time 2026-01-10 --threshold 20.0

参数说明：
    --start-time: 回测开始日期（默认: 2025-11-01）
    --end-time: 回测结束日期（默认: 2026-01-10）
    --threshold: 买量暴涨阈值倍数（默认: 20.0）

核心数据支撑（基于48个买量暴涨20倍案例分析）：
- 100%的案例后续会上涨
- 61.7%能涨超20%
- 平均最高涨幅49.14%
- 72.3%在3天内达到最高点
- 第7天平均亏损7%（需要快进快出）
- 平均风险收益比：1:1.78

风险提示：
- 63.8%的案例会回撤超20%
- 必须严格执行3天止盈策略
- 第7天大概率套牢（64.9%亏损）

作者：量化交易助手
创建时间：2026-01-11
最后更新：2026-01-12
"""

import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import pandas as pd  # pyright: ignore[reportMissingImports]
import os
from pathlib import Path
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from db import engine
from data import get_local_symbols, get_local_kline_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class BuySurgeBacktest:
    """买量暴涨策略回测器"""

    def __init__(self):
        # 回测参数
        self.initial_capital = 10000.0  # 初始资金
        self.leverage = 4.0  # 杠杆倍数（4倍）
        self.position_size_ratio = 0.05  # 单次建仓占资金比例
        self.buy_surge_threshold = 20.0  # 买量暴涨阈值（20倍）
        self.take_profit_pct = 0.20  # 止盈比例 (20%)
        self.add_position_trigger_pct = -0.18  # 补仓触发比例 (-18%)
        self.stop_loss_pct = -0.18  # 止损比例 (-18%，补仓后基于新平均成本)
        self.max_hold_hours = 72  # 最大持仓小时数 (72小时/3天强制平仓)
        self.max_daily_positions = 5  # 每天最多建仓数量
        self.wait_timeout_hours = 48  # 等待超时时间（小时）
        
        # 等待跌幅策略（根据买量倍数）
        self.wait_drop_pct_config = [
            (30, -0.03),   # 20-30倍：等待3%
            (60, -0.04),   # 30-60倍：等待4%
            (100, -0.05),  # 60-100倍：等待5%
            (9999, -0.06), # 100倍以上：等待6%
        ]
        
        # 待建仓信号列表（等待回调中的信号）
        self.pending_signals = []  # 存储 {symbol, signal_date, signal_close, buy_surge_ratio, timeout_datetime}

        # 交易记录
        self.capital = self.initial_capital
        self.positions = []  # 当前持仓
        self.trade_records = []  # 交易记录
        self.daily_capital = []  # 每日资金记录


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
            # 获取信号日结束的时间点（即第二天凌晨 00:00）
            signal_dt = datetime.strptime(signal_date, '%Y-%m-%d')
            signal_end_ts = int((signal_dt + timedelta(days=1)).timestamp() * 1000)
            
            # 获取信号日最后一条小时K线（即 23:00 - 00:00）
            table_name = f'K1h{symbol}'  # 使用项目标准表名格式
            
            query = text(f"""
                SELECT open, close
                FROM "{table_name}"
                WHERE open_time < :signal_end_ts
                ORDER BY open_time DESC
                LIMIT 1
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, {"signal_end_ts": signal_end_ts}).fetchone()
            
            if not result:
                # 如果没有小时数据，默认通过检查
                return True, 0.0
            
            last_hour_open = result[0]
            last_hour_close = result[1]
            
            # 计算最后1小时内的涨幅
            surge_pct = ((last_hour_close - last_hour_open) / last_hour_open * 100)
            
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
    
    def calculate_dynamic_take_profit(self, position: Dict, hourly_df: pd.DataFrame, entry_date: str) -> float:
        """计算动态止盈阈值
        
        Args:
            position: 持仓信息
            hourly_df: 小时K线数据
            entry_date: 建仓日期
        
        Returns:
            动态止盈阈值（如0.20表示20%，0.30表示30%）
        """
        try:
            # 获取建仓价格
            avg_price = position['avg_entry_price']
            # 解析建仓日期时间（支持带时间或不带时间的格式）
            try:
                if len(entry_date) > 10:  # 包含时间
                    entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S')
                else:  # 只有日期
                    entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
            except:
                entry_datetime = datetime.strptime(entry_date.split()[0], '%Y-%m-%d')
            
            # 筛选建仓后2小时的数据
            entry_ts = int(entry_datetime.timestamp() * 1000)
            two_hours_later_ts = entry_ts + 2 * 3600 * 1000
            
            hourly_data_2h = hourly_df[
                (hourly_df['open_time'] >= entry_ts) & 
                (hourly_df['open_time'] < two_hours_later_ts)
            ]
            
            # 如果数据不足2小时，使用默认止盈
            if len(hourly_data_2h) < 2:
                return self.take_profit_pct
            
            # 统计价格相对建仓价的位置
            above_10pct_count = 0  # 在建仓价+10%以上的小时数
            above_2to10pct_count = 0  # 在建仓价+2%到+10%之间的小时数
            total_hours = len(hourly_data_2h)
            
            for _, row in hourly_data_2h.iterrows():
                close_price = row['close']
                price_change_pct = (close_price - avg_price) / avg_price
                
                if price_change_pct >= 0.10:  # ≥+10%
                    above_10pct_count += 1
                elif price_change_pct >= 0.02:  # +2%到+10%之间
                    above_2to10pct_count += 1
            
            # 计算比例
            pct_above_10 = above_10pct_count / total_hours if total_hours > 0 else 0
            pct_above_2to10 = above_2to10pct_count / total_hours if total_hours > 0 else 0
            
            # 动态调整止盈阈值
            if pct_above_10 >= 0.80:  # 80%时间在+10%以上
                adjusted_tp = self.take_profit_pct + 0.10  # 提高10%
                logging.info(f"🚀 {position['symbol']} 强势币，80%时间在+10%以上，止盈提高到{adjusted_tp*100:.0f}%")
                return adjusted_tp
            elif pct_above_2to10 >= 0.80:  # 80%时间在+2%到+10%之间
                adjusted_tp = self.take_profit_pct + 0.05  # 提高5%
                logging.info(f"📈 {position['symbol']} 稳健币，80%时间在+2%~+10%，止盈提高到{adjusted_tp*100:.0f}%")
                return adjusted_tp
            else:
                return self.take_profit_pct
                
        except Exception as e:
            logging.debug(f"计算动态止盈失败: {e}")
            return self.take_profit_pct

    def get_daily_buy_surge_coins(self, date_str: str) -> List[Dict]:
        """获取指定日期主动买量暴涨的合约
        
        Args:
            date_str: 日期字符串
        
        Returns:
            主动买量暴涨的合约列表
        """
        try:
            # 获取所有交易对（使用项目标准函数）
            symbols = get_local_symbols(interval="1d")
            surge_contracts = []
            
            with engine.connect() as conn:
                for symbol in symbols:
                    if not symbol.endswith('USDT'):
                        continue
                    
                    table_name = f"K1d{symbol}"
                    try:
                        # 获取当日数据
                        today_query = text(f'''
                            SELECT trade_date, close, open, active_buy_volume
                            FROM "{table_name}"
                            WHERE trade_date = :date_str OR trade_date LIKE :date_str_like
                        ''')
                        today_result = conn.execute(today_query, {
                            "date_str": date_str,
                            "date_str_like": f'{date_str}%'
                        }).fetchone()
                        
                        if not today_result or not today_result[3]:
                            continue
                        
                        today_date, close_price, open_price, today_buy_volume = today_result
                        
                        # 获取昨日数据
                        yesterday_dt = datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)
                        yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
                        
                        yesterday_query = text(f'''
                            SELECT active_buy_volume
                            FROM "{table_name}"
                            WHERE trade_date = :yesterday_str OR trade_date LIKE :yesterday_str_like
                        ''')
                        yesterday_result = conn.execute(yesterday_query, {
                            "yesterday_str": yesterday_str,
                            "yesterday_str_like": f'{yesterday_str}%'
                        }).fetchone()
                        
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

    def execute_trade(self, symbol: str, entry_price: float, entry_datetime: datetime, 
                     signal_date: str, buy_surge_ratio: float, position_type: str = "long"):
        """执行交易
        
        Args:
            symbol: 交易对
            entry_price: 建仓价格
            entry_datetime: 建仓时间（datetime对象）
            signal_date: 信号日期
            buy_surge_ratio: 买量暴涨倍数
            position_type: 仓位类型
        """
        try:
            # 计算建仓金额
            position_value = self.capital * self.position_size_ratio
            
            # 计算建仓数量 (考虑杠杆)
            position_size = (position_value * self.leverage) / entry_price
            
            # 格式化建仓日期时间（包含时间）
            entry_date_str = entry_datetime.strftime('%Y-%m-%d %H:%M:%S')
            
            # 记录交易
            trade_record = {
                'entry_date': entry_date_str,
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
                'hold_days': 0
            }
            
            self.positions.append(trade_record)
            self.trade_records.append(trade_record)
            
            # 更新资金（减去占用的资金）
            self.capital -= position_value
            
            logging.info(f"🚀 建仓: {symbol} {entry_date_str} 价格:{entry_price:.4f} 买量暴涨:{buy_surge_ratio:.1f}倍 杠杆:{self.leverage}x 仓位:${position_value:.2f}")
        except Exception as e:
            logging.error(f"执行交易失败: {e}")

    def check_exit_conditions(self, position: Dict, current_price: float, current_date: str) -> bool:
        """使用小时线数据检查是否满足平仓条件"""
        try:
            symbol = position['symbol']
            entry_price = position['avg_entry_price']
            entry_date = position['entry_date']
            
            # 获取小时线数据
            hourly_df = get_local_kline_data(symbol, interval="1h")
            if hourly_df.empty:
                logging.warning(f"无小时线数据，使用日线数据检查: {symbol}")
                # 备用：使用日线数据（无法使用动态止盈，使用默认阈值）
                price_change_pct = (current_price - entry_price) / entry_price
                if price_change_pct >= self.take_profit_pct:
                    # 将日期字符串转换为datetime对象（使用当天的结束时间）
                    current_datetime = datetime.strptime(current_date, '%Y-%m-%d')
                    current_datetime = current_datetime.replace(hour=23, minute=59, second=59)
                    self.exit_position(position, current_price, current_datetime, "take_profit")
                    return True
                return False
            
            # 解析建仓日期时间（支持带时间或不带时间的格式）
            try:
                if len(entry_date) > 10:  # 包含时间
                    entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S')
                else:  # 只有日期
                    entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
            except:
                entry_datetime = datetime.strptime(entry_date.split()[0], '%Y-%m-%d')
            
            current_datetime = datetime.strptime(current_date, '%Y-%m-%d')
            
            # 将trade_date转换为datetime进行筛选
            hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
            mask = hourly_df['trade_datetime'] >= entry_datetime
            mask = mask & (hourly_df['trade_datetime'] <= current_datetime)
            hold_period_data = hourly_df[mask].copy()
            
            # 🆕 计算动态止盈阈值（基于建仓后2小时的价格表现）
            dynamic_tp_pct = self.calculate_dynamic_take_profit(position, hourly_df, entry_date)
            
            # 检查每小时的价格是否满足止盈/补仓/止损条件
            if not hold_period_data.empty:
                for _, row in hold_period_data.iterrows():
                    high_price = row['high']
                    low_price = row['low']
                    hour_datetime = row['trade_datetime']  # 已经是datetime对象
                    
                    # 动态获取当前有效的平均价格（补仓后会更新）
                    current_avg_price = position['avg_entry_price']
                    
                    # 更新最大跌幅
                    drawdown_pct = (low_price - current_avg_price) / current_avg_price
                    if drawdown_pct < position['max_drawdown']:
                        position['max_drawdown'] = drawdown_pct
                    
                    # 检查补仓条件
                    if not position.get('has_add_position', False):
                        add_trigger_pct = (low_price - current_avg_price) / current_avg_price
                        if add_trigger_pct <= self.add_position_trigger_pct:
                            hour_date_str = hour_datetime.strftime('%Y-%m-%d')
                            self.add_position(position, low_price, hour_date_str)
                            logging.info(f"🔄 补仓触发: {symbol} 在 {hour_datetime.strftime('%Y-%m-%d %H:%M:%S')} 最低价{low_price:.6f}跌破-18%")
                            
                            # ✅ 补仓后立即检查本小时是否能止盈或止损（基于新平均价）
                            new_avg_price = position['avg_entry_price']
                            
                            # 检查止盈（使用动态止盈阈值）
                            profit_pct_after_add = (high_price - new_avg_price) / new_avg_price
                            if profit_pct_after_add >= dynamic_tp_pct:
                                self.exit_position(position, high_price, hour_datetime, "take_profit")
                                logging.info(f"✨ 补仓后同小时止盈: {symbol} 在 {hour_datetime.strftime('%Y-%m-%d %H:%M:%S')} 最高价{high_price:.6f}达到止盈（阈值{dynamic_tp_pct*100:.0f}%）")
                                return True
                            
                            # 检查止损
                            stop_loss_pct_after_add = (low_price - new_avg_price) / new_avg_price
                            if stop_loss_pct_after_add <= self.stop_loss_pct:
                                self.exit_position(position, low_price, hour_datetime, "stop_loss")
                                logging.info(f"🛑 补仓后同小时止损: {symbol} 在 {hour_datetime.strftime('%Y-%m-%d %H:%M:%S')} 最低价{low_price:.6f}触发止损")
                                return True
                            
                            # 既没止盈也没止损，继续下一小时
                            continue
                    
                    # 检查止盈条件（使用动态止盈阈值）
                    profit_pct = (high_price - current_avg_price) / current_avg_price
                    if profit_pct >= dynamic_tp_pct:
                        self.exit_position(position, high_price, hour_datetime, "take_profit")
                        logging.info(f"✨ 止盈: {symbol} 在 {hour_datetime.strftime('%Y-%m-%d %H:%M:%S')} 达到{profit_pct*100:.1f}%（阈值{dynamic_tp_pct*100:.0f}%）")
                        return True
                    
                    # 检查止损条件（补仓后）
                    if position.get('has_add_position', False):
                        stop_loss_pct_check = (low_price - current_avg_price) / current_avg_price
                        if stop_loss_pct_check <= self.stop_loss_pct:
                            self.exit_position(position, low_price, hour_datetime, "stop_loss")
                            logging.info(f"🛑 止损触发: {symbol} 在 {hour_datetime.strftime('%Y-%m-%d %H:%M:%S')} 最低价{low_price:.6f}跌破止损线")
                            return True
            
            # 检查是否超过72小时强制平仓
            hours_held = (current_datetime - entry_datetime).total_seconds() / 3600
            if hours_held >= self.max_hold_hours:
                if not hold_period_data.empty:
                    last_row = hold_period_data.iloc[-1]
                    exit_price = last_row['close']
                    exit_datetime = last_row['trade_datetime']  # 使用最后一条小时数据的datetime
                else:
                    exit_price = current_price
                    exit_datetime = current_datetime  # 使用当前日期时间
                
                self.exit_position(position, exit_price, exit_datetime, "max_hold_time")
                logging.info(f"⏰ {self.max_hold_hours:.0f}小时强制平仓: {symbol} 持有{hours_held:.1f}小时，平仓价{exit_price:.6f}，平仓时间{exit_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                return True
            
            return False
        
        except Exception as e:
            logging.error(f"检查平仓条件失败: {e}")
            return False

    def add_position(self, position: Dict, current_price: float, current_date: str):
        """补仓操作"""
        try:
            original_size = position['position_size']
            
            # 补仓相同数量
            add_size = original_size
            
            # 计算补仓消耗的资金（保证金）
            add_value = (add_size * current_price) / self.leverage
            
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
            position['position_value'] += add_value
            
            # 更新总资金
            self.capital -= add_value
            
            logging.info(f"➕ 补仓: {position['symbol']} {current_date} 价格:{current_price:.4f} 保证金:${add_value:.2f} 新平均价:{new_avg_price:.4f}")
        except Exception as e:
            logging.error(f"补仓失败: {e}")

    def exit_position(self, position: Dict, exit_price: float, exit_datetime: datetime, exit_reason: str):
        """平仓操作
        
        Args:
            exit_datetime: 平仓时间（datetime对象）
        """
        try:
            entry_price = position['avg_entry_price']
            position_size = position['position_size']
            
            # 计算盈亏
            pnl = (exit_price - entry_price) * position_size
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            
            # 解析建仓日期时间（支持带时间或不带时间的格式）
            entry_date_str = position['entry_date']
            try:
                if len(entry_date_str) > 10:  # 包含时间
                    entry_dt = datetime.strptime(entry_date_str, '%Y-%m-%d %H:%M:%S')
                else:  # 只有日期
                    entry_dt = datetime.strptime(entry_date_str, '%Y-%m-%d')
            except:
                entry_dt = datetime.strptime(entry_date_str.split()[0], '%Y-%m-%d')
            
            # 计算持仓天数（精确到小时）
            time_diff = exit_datetime - entry_dt
            hold_days = time_diff.total_seconds() / 86400  # 转换为天数（包含小数部分）
            
            # 格式化平仓日期时间（包含时间）
            exit_date_str = exit_datetime.strftime('%Y-%m-%d %H:%M:%S')
            
            # 更新资金 (返回保证金 + 盈亏)
            self.capital += position['position_value'] + pnl
            
            # 更新持仓记录
            position.update({
                'exit_date': exit_date_str,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': round(hold_days, 2)  # 保留2位小数
            })
            
            # 从持仓列表中移除
            if position in self.positions:
                self.positions.remove(position)
            
            logging.info(f"💰 平仓: {position['symbol']} {exit_date_str} 价格:{exit_price:.4f} 盈亏:${pnl:.2f} ({pnl_pct:+.1f}%) 原因:{exit_reason}")
        except Exception as e:
            logging.error(f"平仓失败: {e}")

    def get_entry_price(self, symbol: str, date_str: str) -> Optional[float]:
        """获取开盘价作为建仓价格"""
        try:
            table_name = f'K1d{symbol}'  # 使用项目标准表名格式
            
            query = text(f'''
                SELECT open
                FROM "{table_name}"
                WHERE trade_date = :date_str OR trade_date LIKE :date_str_like
            ''')
            
            with engine.connect() as conn:
                result = conn.execute(query, {
                    "date_str": date_str,
                    "date_str_like": f'{date_str}%'
                }).fetchone()
            
            return result[0] if result and result[0] else None
        
        except Exception as e:
            logging.error(f"获取 {symbol} {date_str} 开盘价失败: {e}")
            return None

    def run_backtest(self, start_date: str, end_date: str):
        """运行回测"""
        logging.info(f"开始买量暴涨策略回测（优化版-等待回调）: {start_date} 到 {end_date}")
        logging.info(f"初始资金: ${self.initial_capital:,.2f}")
        logging.info(f"杠杆倍数: {self.leverage}x")
        logging.info(f"买量暴涨阈值: {self.buy_surge_threshold}倍")
        logging.info(f"等待策略: 13.1-30倍→3%, 30-60倍→4%, 60-100倍→5%, 100倍+→6%")
        logging.info(f"最大持仓时间: {self.max_hold_hours:.0f}小时（{self.max_hold_hours/24:.0f}天）")
        
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # 记录每日资金
            self.daily_capital.append({
                'date': date_str,
                'capital': self.capital,
                'positions_count': len(self.positions)
            })
            
            # 检查现有持仓
            positions_to_check = self.positions.copy()
            for position in positions_to_check:
                try:
                    table_name = f'K1d{position["symbol"]}'  # 使用项目标准表名格式
                    
                    query = text(f'''
                        SELECT close
                        FROM "{table_name}"
                        WHERE trade_date = :date_str OR trade_date LIKE :date_str_like
                    ''')
                    
                    with engine.connect() as conn:
                        result = conn.execute(query, {
                            "date_str": date_str,
                            "date_str_like": f'{date_str}%'
                        }).fetchone()
                    
                    if result and result[0]:
                        current_price = result[0]
                        self.check_exit_conditions(position, current_price, date_str)
                
                except Exception as e:
                    logging.debug(f"检查持仓失败: {e}")
            
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
                    signals_to_remove.append(signal)
                    continue
                
                # 获取小时线数据检查是否达到目标价格
                hourly_df = get_local_kline_data(symbol, interval="1h")
                if not hourly_df.empty:
                    # 筛选信号日之后到当前日期的小时数据
                    # 信号日期时间已经是信号日的结束时间（23:59:59），所以从第二天开始检查
                    hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
                    signal_datetime = signal['signal_datetime']
                    # 从信号日的第二天00:00:00开始检查（信号日结束时间+1秒）
                    check_start_datetime = signal_datetime + timedelta(seconds=1)
                    mask = (hourly_df['trade_datetime'] >= check_start_datetime) & (hourly_df['trade_datetime'] <= current_date)
                    check_period_data = hourly_df[mask]
                    
                    # 检查是否有小时低点达到目标价格
                    for _, row in check_period_data.iterrows():
                        if row['low'] <= target_price:
                            # 达到目标价格，建仓
                            entry_price = target_price
                            entry_datetime = row['trade_datetime']  # 已经是datetime对象
                            
                            if len(self.positions) < 10:  # 检查持仓数量限制
                                self.execute_trade(symbol, entry_price, entry_datetime, 
                                                 signal['signal_date'], buy_surge_ratio)
                                logging.info(f"✅ {symbol} 达到目标跌幅{target_drop_pct*100:.0f}%，建仓价{entry_price:.6f}，建仓时间{entry_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            signals_to_remove.append(signal)
                            break
            
            # 移除已处理的信号
            for signal in signals_to_remove:
                if signal in self.pending_signals:
                    self.pending_signals.remove(signal)
            
            # 寻找新的买量暴涨信号
            if len(self.positions) < 10:
                surge_coins = self.get_daily_buy_surge_coins(date_str)
                
                for coin in surge_coins:
                    symbol = coin['symbol']
                    buy_surge_ratio = coin['buy_surge_ratio']
                    signal_close = coin['close']
                    
                    # 检查是否已在待建仓列表或已持仓
                    if any(s['symbol'] == symbol for s in self.pending_signals):
                        continue
                    if any(pos['symbol'] == symbol for pos in self.positions):
                        continue
                    
                    # 添加到待建仓信号列表
                    # 信号日期是检测到买量暴涨的那一天，建仓应该在信号日之后（第二天）开始检查
                    # 信号日期时间设置为信号日的结束时间（23:59:59），这样第二天开始检查回调
                    target_drop_pct = self.get_wait_drop_pct(buy_surge_ratio)
                    signal_datetime = current_date.replace(hour=23, minute=59, second=59)  # 信号日结束时间
                    timeout_datetime = signal_datetime + timedelta(hours=self.wait_timeout_hours)
                    
                    self.pending_signals.append({
                        'symbol': symbol,
                        'signal_date': date_str,
                        'signal_datetime': signal_datetime,  # 信号日结束时间
                        'signal_close': signal_close,
                        'buy_surge_ratio': buy_surge_ratio,
                        'target_drop_pct': target_drop_pct,
                        'timeout_datetime': timeout_datetime
                    })
                    
                    logging.info(f"🔔 新信号: {symbol} 买量{buy_surge_ratio:.1f}倍，等待跌{target_drop_pct*100:.0f}%")
            
            current_date += timedelta(days=1)
        
        # 最后强制平仓
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        for position in self.positions.copy():
            try:
                table_name = f'K1d{position["symbol"]}'  # 使用项目标准表名格式
                
                query = text(f'''
                    SELECT close
                    FROM "{table_name}"
                    WHERE trade_date = :end_date OR trade_date LIKE :end_date_like
                    ORDER BY trade_date DESC
                    LIMIT 1
                ''')
                
                with engine.connect() as conn:
                    result = conn.execute(query, {
                        "end_date": end_date,
                        "end_date_like": f'{end_date}%'
                    }).fetchone()
                
                if result and result[0]:
                    exit_price = result[0]
                    self.exit_position(position, exit_price, end_datetime, "force_close")
            
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
        
        # 详细交易记录
        print(f"\n📋 详细交易记录 (前20条):")
        print("-" * 150)
        print(f"{'序号':<4} {'交易对':<15} {'买量倍数':<10} {'建仓日期时间':<20} {'建仓价':>10} {'平仓日期时间':<20} {'平仓价':>10} {'盈亏':>12} {'持仓天数':<10}")
        print("-" * 150)
        
        for i, trade in enumerate(self.trade_records[:20], 1):
            exit_info = f"{trade['exit_price']:.4f}" if trade['exit_price'] else "-"
            pnl_info = f"${trade['pnl']:+.2f}" if trade['pnl'] != 0 else "-"
            surge_ratio = f"{trade.get('buy_surge_ratio', 0):.1f}x"
            
            print(f"{i:<4} {trade['symbol']:<15} {surge_ratio:<10} {trade['entry_date']:<20} {trade['entry_price']:<10.4f} "
                  f"{trade['exit_date'] or '-':<20} {exit_info:>10} {pnl_info:>12} {trade.get('hold_days', 0):<10}")

    def generate_trade_csv_report(self):
        """生成交易详细CSV报告"""
        # 创建保存目录（如果不存在）
        csv_dir = Path(__file__).parent.parent / "data" / "backtrade_records"
        csv_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = csv_dir / f"buy_surge_backtest_report_{timestamp}.csv"
        
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    '序号', '交易对', '买量暴涨倍数', '信号日期', '建仓日期', '建仓价', '平仓日期', '平仓价',
                    '盈亏金额', '盈亏百分比', '平仓原因', '杠杆倍数', '仓位金额',
                    '是否有补仓', '补仓价格', '补仓后平均价', '持仓天数', '最大跌幅%', '止盈阈值%'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for i, trade in enumerate(self.trade_records, 1):
                    # 计算补仓后平均价
                    avg_price_after_add = ''
                    if trade.get('has_add_position', False) and trade.get('add_position_price'):
                        avg_price_after_add = f"{trade['avg_entry_price']:.6f}"
                    
                    row = {
                        '序号': i,
                        '交易对': trade['symbol'],
                        '买量暴涨倍数': f"{trade.get('buy_surge_ratio', 0):.1f}倍",
                        '信号日期': trade.get('signal_date', ''),
                        '建仓日期': trade['entry_date'],
                        '建仓价': f"{trade['entry_price']:.6f}",
                        '平仓日期': trade.get('exit_date', ''),
                        '平仓价': f"{trade.get('exit_price', 0):.6f}" if trade.get('exit_price') else '',
                        '盈亏金额': f"{trade.get('pnl', 0):.2f}",
                        '盈亏百分比': f"{trade.get('pnl_pct', 0):.2f}%",
                        '平仓原因': trade.get('exit_reason', ''),
                        '杠杆倍数': trade['leverage'],
                        '仓位金额': f"{trade['position_value']:.2f}",
                        '是否有补仓': '✅是' if trade.get('has_add_position', False) else '否',
                        '补仓价格': f"{trade.get('add_position_price', 0):.6f}" if trade.get('add_position_price') else '',
                        '补仓后平均价': avg_price_after_add,
                        '持仓天数': trade.get('hold_days', 0),
                        '最大跌幅%': f"{trade.get('max_drawdown', 0)*100:.2f}%" if trade.get('max_drawdown') else '0.00%',
                        '止盈阈值%': f"{self.take_profit_pct*100:.0f}%"
                    }
                    writer.writerow(row)
            
            print(f"📄 交易详细CSV报告已生成: {csv_filename}")
        
        except Exception as e:
            print(f"❌ 生成CSV报告失败: {e}")

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
    
    args = parser.parse_args()
    
    backtest = BuySurgeBacktest()
    
    # 可以通过参数调整阈值
    if args.threshold:
        backtest.buy_surge_threshold = args.threshold
        logging.info(f"买量暴涨阈值设置为: {args.threshold}倍")
    
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
