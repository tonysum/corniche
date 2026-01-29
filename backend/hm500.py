#!/usr/bin/env python3
"""
买量暴涨策略回测程序 - 5分钟优化版 + 动态止盈优化
基于5分钟主动买量暴涨（相对昨日平均5分钟买量）信号的做多策略，支持自定义买量暴涨倍数阈值

策略逻辑：
1. 扫描所有USDT交易对，使用5分钟K线数据检测买量暴涨信号（可自定义买量暴涨倍数阈值）
2. 满足条件：等待价格从信号日收盘价回调后买入
   - 100-200倍买量：等待回调9%
   - 200-300倍买量：等待回调5%
   - 300倍以上：等待回调5%
3. 杠杆4倍，单次建仓占资金比例5%
4. 补仓一次（下跌15%），补仓数量等于首次建仓，重新计算平均成本
5. 🆕 动态止盈策略（优化版）：
   - 检测建仓后1小时内，价格在建仓价+3%以上的时间占比
   - 占比>=60%：止盈提高到13%（强势币）
   - 占比<60%：保持基础止盈7%（普通币）
6. 止损：补仓后基于新平均成本下跌18%
7. 最大持仓天数：3天
8. 超时机制：信号后24小时内未达到目标跌幅则放弃

🎯 动态止盈策略优势：
- 1小时快速识别强势币，更灵活
- 60%时间占比阈值，能识别更多机会
- 13%止盈阈值，兼顾收益与成功率
- 理论收益：52%（13% × 4倍杠杆）

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
最后更新：2026-01-14（优化动态止盈参数：1小时/60%/13%）
"""

import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import pandas as pd
from db import engine
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class BuySurgeBacktest:
    """买量暴涨策略回测器"""

    def __init__(self):
        # PostgreSQL 使用 engine，不需要手动连接
        pass

        # 回测参数
        self.initial_capital = 10000.0  # 初始资金
        self.leverage = 4.0  # 杠杆倍数（4倍）
        self.position_size_ratio = 0.05  # 单次建仓占资金比例（2%，平衡收益与风险）
        
        # 🎯 买量暴涨倍数区间配置（基于250笔完整交易数据优化 - 2026-01-15）
        # 最终优化结果：只保留综合评分>50的顶级区间
        # ✅ 100-150倍：168笔交易，胜率61.3%，止盈率51.2%，盈利$770（占99%总盈利）
        # ✅ 800-900倍：11笔交易，胜率63.6%，止盈率63.6%（最高），盈利$33
        # ❌ 已排除：450-500倍（亏损-$128，胜率45.5%）及其他表现一般的区间
        self.buy_surge_ranges = [
            (100, 200),   # 核心区间（占67%交易量，贡献99%盈利）
            (200, 1000),   # 高质量区间（止盈率最高63.6%）
        ]
        
        self.take_profit_pct = 0.11  # 基础止盈比例 (11%)
        self.dynamic_tp_boost = 0.03  # 动态止盈提升幅度 (5%，强势币会在基础止盈上增加此幅度)
        self.add_position_trigger_pct = -0.15  # 补仓触发比例 (-15%)
        self.stop_loss_pct = -0.18  # 止损比例 (-18%，补仓后基于新平均成本)
        self.max_hold_hours = 72  # 最大持仓小时数 (72小时/3天强制平仓)
        self.max_positions = 10  # 最大同时持仓数量（足够捕捉信号，避免过度分散）
        self.wait_timeout_hours = 24  # 等待超时时间（小时）
        
        # 等待跌幅策略（根据买量倍数 - 5分钟版本）
        # 🎯 基于5分钟买量暴涨倍数优化的配置
        # 低倍数信号价格快速上涨，等待反而买贵；高倍数信号波动大，可等待回调
        self.wait_drop_pct_config = [
            (100, -0.1),     # <50倍：等待9%回调
            (300, -0.1),    # 50-200倍：等待9%回调
            (500, -0.1),    # 300-1000倍：等待3%回调
            (800, 0.00),   # 300倍以上：等待2%回调
        ]
        
        # 待建仓信号列表（等待回调中的信号）
        self.pending_signals = []  # 存储 {symbol, signal_date, signal_close, buy_surge_ratio, timeout_datetime}

        # 交易记录
        self.capital = self.initial_capital
        self.positions = []  # 当前持仓
        self.trade_records = []  # 交易记录
        self.daily_capital = []  # 每日资金记录

    def __del__(self):
        """析构函数（PostgreSQL 使用连接池，不需要手动关闭）"""
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
            table_name = f'HourlyKline_{symbol}'
            safe_table_name = f'"{table_name}"'
            
            with engine.connect() as conn:
                query = f"""
                    SELECT close
                    FROM {safe_table_name}
                    WHERE open_time < :signal_ts
                    ORDER BY open_time DESC
                    LIMIT 1
                """
                
                result = conn.execute(text(query), {"signal_ts": signal_ts})
                row = result.fetchone()
            
            if not row:
                # 如果没有小时数据，默认通过检查
                return True, 0.0
            
            prev_1h_close = row[0]
            
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
    
    def calculate_dynamic_take_profit(self, position: Dict, hourly_df: pd.DataFrame, entry_datetime: datetime) -> float:
        """计算动态止盈阈值（优化版：基于1小时内价格在建仓价+2%以上的时间占比）
        
        核心逻辑：
        1. 检测建仓后1小时内，价格在建仓价+2%以上的时间占比
        2. 如果占比>=60%，止盈设为13%
        3. 否则保持基础止盈11%
        
        Args:
            position: 持仓信息
            hourly_df: 5分钟K线数据
            entry_datetime: 建仓时间（完整的datetime对象，包含小时）
        
        Returns:
            动态止盈阈值（如0.11表示11%，0.13表示13%）
        """
        try:
            # 获取建仓价格
            avg_price = position['avg_entry_price']
            
            # 🔧 确保5分钟数据有trade_datetime列（如果没有则创建）
            if 'trade_datetime' not in hourly_df.columns:
                hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
            
            # 🚀 检查建仓后1小时内价格在建仓价+2%以上的时间占比
            # 观察窗口：建仓后1小时（12个5分钟周期）
            one_hour_later = entry_datetime + timedelta(hours=1)
            
            data_1h = hourly_df[
                (hourly_df['trade_datetime'] >= entry_datetime) & 
                (hourly_df['trade_datetime'] < one_hour_later)
            ]
            
            # 如果数据不足30分钟（6个周期），暂时使用基础止盈
            if len(data_1h) < 6:
                return self.take_profit_pct
            
            # 计算价格在建仓价+2%以上的5分钟周期数
            threshold_price = avg_price * 1.02  # ✅ 从+3%降低到+2%，识别更多强势币
            above_threshold_count = len(data_1h[data_1h['close'] >= threshold_price])
            total_count = len(data_1h)
            time_above_pct = above_threshold_count / total_count if total_count > 0 else 0
            
            # 如果时间占比>=60%，说明是强势币，在基础止盈上增加动态提升幅度
            if time_above_pct >= 0.60:
                adjusted_tp = self.take_profit_pct + self.dynamic_tp_boost  # 基础11% + 提升5% = 16%
                logging.info(f"🚀 {position['symbol']} 强势币！1小时内价格>+2%占比{time_above_pct*100:.1f}%，止盈提高到{adjusted_tp*100:.0f}%")
                return adjusted_tp
            else:
                # 时间占比<60%，保持基础止盈
                logging.debug(f"📉 {position['symbol']} 普通币，1小时内价格>+2%占比{time_above_pct*100:.1f}%，保持基础止盈{self.take_profit_pct*100:.0f}%")
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
            # 获取所有交易对（PostgreSQL）
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE :prefix
                    ORDER BY table_name
                """), {"prefix": "DailyKline_%"})
                tables = result.fetchall()
            
            surge_contracts = []
            
            for table_row in tables:
                table_name = table_row[0]
                symbol = table_name.replace('DailyKline_', '')
                
                if not symbol.endswith('USDT'):
                    continue
                
                try:
                    safe_table_name = f'"{table_name}"'
                    
                    # 获取当日数据
                    with engine.connect() as conn:
                        result = conn.execute(text(f'''
                            SELECT trade_date, close, open, active_buy_volume
                            FROM {safe_table_name}
                            WHERE trade_date = :date_str OR trade_date LIKE :date_pattern
                        '''), {
                            "date_str": date_str,
                            "date_pattern": f'{date_str}%'
                        })
                        today_result = result.fetchone()
                    
                    if not today_result or not today_result[3]:
                        continue
                    
                    today_date, close_price, open_price, today_buy_volume = today_result
                    
                    # 获取昨日数据
                    yesterday_dt = datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)
                    yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
                    
                    with engine.connect() as conn:
                        result = conn.execute(text(f'''
                            SELECT active_buy_volume
                            FROM {safe_table_name}
                            WHERE trade_date = :yesterday_str OR trade_date LIKE :yesterday_pattern
                        '''), {
                            "yesterday_str": yesterday_str,
                            "yesterday_pattern": f'{yesterday_str}%'
                        })
                        yesterday_result = result.fetchone()
                    
                    if not yesterday_result or not yesterday_result[0]:
                        continue
                    
                    yesterday_buy_volume = yesterday_result[0]
                    
                    # 计算买量暴涨倍数
                    if yesterday_buy_volume > 0:
                        buy_surge_ratio = today_buy_volume / yesterday_buy_volume
                        
                        # 🎯 检查是否在任一配置的买量区间内
                        is_in_range = False
                        for range_min, range_max in self.buy_surge_ranges:
                            if range_min <= buy_surge_ratio <= range_max:
                                is_in_range = True
                                break
                        
                        # 如果买量暴涨在配置区间内
                        if is_in_range:
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

    def get_daily_5m_surge_signals(self, check_date: str) -> List[Dict]:
        """🆕 5分钟优化版：检测某天内哪些5分钟的买量超过昨日平均5分钟买量
        
        检测逻辑：
        1. 获取昨日日K线的 active_buy_volume（总买量）
        2. 计算昨日平均5分钟买量 = 总买量 / 288（1天=288个5分钟）
        3. 遍历今日所有5分钟K线，找到第一个买量 >= 昨日平均5分钟买量 × 阈值的5分钟
        4. 那个5分钟就是信号时间
        
        Args:
            check_date: 检测日期 'YYYY-MM-DD'
        
        Returns:
            信号列表，包含symbol、信号时间、倍数等
        """
        try:
            # 获取所有交易对（PostgreSQL）
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE :prefix
                    ORDER BY table_name
                """), {"prefix": "DailyKline_%"})
                daily_tables = result.fetchall()
            
            signals = []
            
            check_dt = datetime.strptime(check_date, '%Y-%m-%d')
            yesterday_date = (check_dt - timedelta(days=1)).strftime('%Y-%m-%d')
            
            for table_row in daily_tables:
                table_name = table_row[0]
                symbol = table_name.replace('DailyKline_', '')
                
                if not symbol.endswith('USDT'):
                    continue
                
                try:
                    # 🚀 步骤1：获取昨日日K线总买量
                    daily_table = f'DailyKline_{symbol}'
                    safe_daily_table = f'"{daily_table}"'
                    
                    with engine.connect() as conn:
                        result = conn.execute(text(f'''
                            SELECT active_buy_volume
                            FROM {safe_daily_table}
                            WHERE trade_date = :yesterday_date OR trade_date LIKE :yesterday_pattern
                        '''), {
                            "yesterday_date": yesterday_date,
                            "yesterday_pattern": f'{yesterday_date}%'
                        })
                        yesterday_row = result.fetchone()
                    
                    if not yesterday_row or not yesterday_row[0]:
                        continue
                    
                    yesterday_daily_volume = yesterday_row[0]
                    # 计算昨日平均5分钟买量（1天 = 288个5分钟）
                    yesterday_avg_5m_volume = yesterday_daily_volume / 288.0
                    
                    # 🚀 步骤2：获取今日所有5分钟K线（只需1次查询！）
                    kline5m_table = f'Kline5m_{symbol}'
                    safe_kline5m_table = f'"{kline5m_table}"'
                    
                    with engine.connect() as conn:
                        result = conn.execute(text(f'''
                            SELECT trade_date, active_buy_volume, close
                            FROM {safe_kline5m_table}
                            WHERE trade_date >= :start_time AND trade_date < :end_time
                            ORDER BY trade_date ASC
                        '''), {
                            "start_time": f'{check_date} 00:00:00',
                            "end_time": f'{(check_dt + timedelta(days=1)).strftime("%Y-%m-%d")} 00:00:00'
                        })
                        today_5m_periods = result.fetchall()
                    if not today_5m_periods:
                        continue
                    
                    # 🚀 步骤3：找到第一个满足条件的5分钟周期
                    for period_data in today_5m_periods:
                        period_time, period_volume, period_price = period_data
                        
                        if not period_volume or not period_price:
                            continue
                        
                        # 计算倍数（相对昨日平均5分钟买量）
                        surge_ratio = period_volume / yesterday_avg_5m_volume
                        
                        # 🎯 检查是否在任一配置的买量区间内
                        is_in_range = False
                        for range_min, range_max in self.buy_surge_ranges:
                            if range_min <= surge_ratio <= range_max:
                                is_in_range = True
                                break
                        
                        if not is_in_range:
                            continue  # 不在任何配置区间内，跳过
                        
                        # 满足区间要求，记录信号
                        signal_datetime = pd.to_datetime(period_time)
                        
                        # 🛡️ 诱多过滤：暂时禁用（误杀率太高，信号后立即上涨往往是强势特征）
                        # 原逻辑：信号后5分钟上涨>0.5%就过滤，但这会误杀大量优质交易（如+20%的快速拉升币）
                        # 分析发现：78%的交易建仓后都会回调，等待回调策略已经能起到过滤作用
                        is_fake_signal = False
                        # try:
                        #     # 获取信号后5分钟和10分钟的价格
                        #     time_5min_later = signal_datetime + timedelta(minutes=5)
                        #     time_10min_later = signal_datetime + timedelta(minutes=10)
                        #     
                        #     # 查询信号后的价格
                        #     cursor.execute(f'''
                        #         SELECT trade_date, close
                        #         FROM "{kline5m_table}"
                        #         WHERE trade_date >= ? AND trade_date <= ?
                        #         ORDER BY trade_date ASC
                        #         LIMIT 3
                        #     ''', (time_5min_later, time_10min_later))
                        #     
                        #     future_prices = cursor.fetchall()
                        #     
                        #     if future_prices:
                        #         # 检查信号后5分钟的价格
                        #         price_5min = future_prices[0][1] if len(future_prices) > 0 else None
                        #         
                        #         if price_5min:
                        #             price_change_5min = (price_5min / period_price - 1) * 100
                        #             
                        #             # 关键规则：信号后5分钟价格上涨 > +0.5% → 诱多
                        #             if price_change_5min > 0.5:
                        #                 is_fake_signal = True
                        #                 logging.info(f"⚠️ 过滤诱多信号: {symbol} @{signal_datetime.strftime('%H:%M')} "
                        #                            f"倍数{surge_ratio:.2f}x 信号后5分钟价格上涨{price_change_5min:.2f}% (诱多特征)")
                        # 
                        # except Exception as e:
                        #     # 如果检查失败，保守处理，不过滤
                        #     logging.debug(f"诱多检查失败 {symbol}: {e}")
                        #     is_fake_signal = False
                        
                        # 不过滤任何信号（等待回调策略已经能起到筛选作用）
                        if not is_fake_signal:
                            signals.append({
                                'symbol': symbol,
                                'signal_datetime': signal_datetime,
                                'signal_price': period_price,
                                'surge_ratio': surge_ratio,
                                'signal_5m_volume': period_volume,
                                'yesterday_avg_5m_volume': yesterday_avg_5m_volume
                            })
                        
                            logging.info(f"🔥 发现信号: {symbol} @{signal_datetime.strftime('%H:%M')} 倍数{surge_ratio:.2f}x 价格{period_price:.6f}")
                        
                        break  # 只记录第一个满足条件的5分钟
                
                except Exception as e:
                    continue
            
            # 按倍数降序排序
            signals.sort(key=lambda x: x['surge_ratio'], reverse=True)
            
            return signals
        
        except Exception as e:
            logging.error(f"获取 {check_date} 买量暴涨信号失败: {e}")
            return []

    def get_hourly_kline_data(self, symbol: str) -> pd.DataFrame:
        """获取本地数据库中指定交易对的小时K线数据"""
        table_name = f'HourlyKline_{symbol}'
        safe_table_name = f'"{table_name}"'
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {safe_table_name} ORDER BY trade_date ASC"))
                data = result.fetchall()
                columns = result.keys()
                df = pd.DataFrame(data, columns=columns)
                return df
        except Exception as e:
            logging.warning(f"获取 {symbol} 小时K线数据失败: {e}")
            return pd.DataFrame()

    def get_5m_kline_data(self, symbol: str) -> pd.DataFrame:
        """获取本地数据库中指定交易对的5分钟K线数据"""
        table_name = f'Kline5m_{symbol}'
        safe_table_name = f'"{table_name}"'
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {safe_table_name} ORDER BY trade_date ASC"))
                data = result.fetchall()
                columns = result.keys()
                df = pd.DataFrame(data, columns=columns)
                return df
        except Exception as e:
            logging.warning(f"获取 {symbol} 5分钟K线数据失败: {e}")
            return pd.DataFrame()

    def execute_trade(self, symbol: str, entry_price: float, entry_date: str, 
                     signal_date: str, buy_surge_ratio: float, position_type: str = "long", 
                     entry_datetime=None, signal_price=None):
        """执行交易
        
        Args:
            entry_datetime: 完整的建仓时间戳（datetime对象或字符串），用于精确记录建仓时刻
            signal_price: 信号触发时的价格，用于基于信号价计算止盈
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
                'signal_price': signal_price if signal_price else entry_price,  # 🆕 记录信号价格
                'buy_surge_ratio': buy_surge_ratio,  # 买量暴涨倍数
                'has_add_position': False,
                'add_position_price': None,
                'add_position_size': None,
                'max_drawdown': 0,
                'hold_days': 0,
                'last_checked_datetime': None  # 🚀 性能优化：记录最后检查的时间戳
            }
            
            self.positions.append(trade_record)
            self.trade_records.append(trade_record)
            
            # 💰 复利模式：建仓时扣除投入资金
            self.capital -= position_value
            
            logging.info(f"🚀 建仓: {symbol} {entry_date} 价格:{entry_price:.4f} 买量暴涨:{buy_surge_ratio:.1f}倍 杠杆:{self.leverage}x 仓位:${position_value:.2f} 剩余资金:${self.capital:.2f}")
        except Exception as e:
            logging.error(f"执行交易失败: {e}")

    def check_exit_conditions(self, position: Dict, current_price: float, current_date: str) -> bool:
        """🚀 智能混合检测：根据情况选择最优检查方式"""
        try:
            symbol = position['symbol']
            entry_price = position['avg_entry_price']
            entry_date = position['entry_date']
            
            # 确定建仓时间
            if position.get('entry_datetime'):
                entry_datetime = pd.to_datetime(position['entry_datetime'])
            else:
                entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
            
            # 🔧 修复：使用当天23:59:59作为截止时间，避免排除当天的小时数据
            current_datetime = datetime.strptime(current_date, '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
            
            # 第1步：查询小时线数据（粗筛）
            hourly_df = self.get_hourly_kline_data(symbol)
            if hourly_df.empty:
                logging.warning(f"无小时线数据，使用备用方案: {symbol}")
                price_change_pct = (current_price - entry_price) / entry_price
                if price_change_pct >= self.take_profit_pct:
                    position['dynamic_tp_pct'] = self.take_profit_pct
                    self.exit_position(position, current_price, current_date, "take_profit")
                    return True
                return False
            
            hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
            
            # 筛选建仓后的小时线数据
            mask_hourly = hourly_df['trade_datetime'] >= entry_datetime
            mask_hourly = mask_hourly & (hourly_df['trade_datetime'] <= current_datetime)
            hourly_period = hourly_df[mask_hourly].copy()
            
            if hourly_period.empty:
                return False
            
            # 延迟加载5分钟数据（只在需要时加载）
            interval_5m_df = None
            dynamic_tp_pct = None
            
            # 第2步：遍历每个小时，智能选择检查方式
            for _, hour_row in hourly_period.iterrows():
                hour_datetime = hour_row['trade_datetime']
                hour_high = hour_row['high']
                hour_low = hour_row['low']
                
                current_avg_price = position['avg_entry_price']
                
                # 延迟计算动态止盈阈值
                if dynamic_tp_pct is None:
                    if interval_5m_df is None:
                        interval_5m_df = self.get_5m_kline_data(symbol)
                        if not interval_5m_df.empty:
                            interval_5m_df['trade_datetime'] = pd.to_datetime(interval_5m_df['trade_date'])
                    if interval_5m_df is not None and not interval_5m_df.empty:
                        dynamic_tp_pct = self.calculate_dynamic_take_profit(position, interval_5m_df, entry_datetime)
                    else:
                        dynamic_tp_pct = self.take_profit_pct
                
                # 确保 dynamic_tp_pct 不为 None（类型检查）
                if dynamic_tp_pct is None:
                    dynamic_tp_pct = self.take_profit_pct
                
                # 计算这1小时可能触发的事件
                profit_pct = (hour_high - current_avg_price) / current_avg_price
                loss_pct = (hour_low - current_avg_price) / current_avg_price
                
                could_take_profit = profit_pct >= dynamic_tp_pct * 0.95
                could_add_position = (not position.get('has_add_position', False) and 
                                     loss_pct <= self.add_position_trigger_pct * 1.05)
                could_stop_loss = (position.get('has_add_position', False) and 
                                  loss_pct <= self.stop_loss_pct * 1.05)
                
                # 检查最大持仓时间
                hours_held = (hour_datetime - entry_datetime).total_seconds() / 3600
                could_max_hold = hours_held >= self.max_hold_hours - 1  # 预留1小时余量
                
                # 统计可能触发的事件数
                event_count = sum([could_take_profit, could_add_position, could_stop_loss, could_max_hold])
                
                # 如果这1小时不可能触发任何事件，跳过
                if event_count == 0:
                    continue
                
                # 加载这1小时的5分钟数据
                if interval_5m_df is None:
                    interval_5m_df = self.get_5m_kline_data(symbol)
                    if interval_5m_df.empty:
                        continue
                    interval_5m_df['trade_datetime'] = pd.to_datetime(interval_5m_df['trade_date'])
                
                # 获取这1小时的5分钟数据
                hour_start = hour_datetime
                hour_end = hour_datetime + timedelta(hours=1)
                mask_5m = (interval_5m_df['trade_datetime'] >= hour_start) & (interval_5m_df['trade_datetime'] < hour_end)
                this_hour_5m = interval_5m_df[mask_5m].copy()
                
                if this_hour_5m.empty:
                    continue
                
                # 🚀 智能选择检查方式
                result = self._smart_check_hour(position, this_hour_5m, dynamic_tp_pct, entry_datetime, symbol, interval_5m_df)
                if result:
                    return True
            
            return False
        
        except Exception as e:
            logging.error(f"检查平仓条件失败: {e}")
            return False
    
    def _smart_check_hour(self, position: Dict, hour_5m_df: pd.DataFrame, dynamic_tp_pct: float, 
                          entry_datetime: datetime, symbol: str, all_5m_df: pd.DataFrame = None) -> bool:
        """智能检查这1小时的5分钟数据：根据可能触发的事件数量选择最优方式
        
        Args:
            all_5m_df: 完整的5分钟数据（用于计算整个持仓期间的最大跌幅）
        """
        
        current_avg_price = position['avg_entry_price']
        
        # 计算止盈/止损/补仓的阈值价格
        take_profit_price = current_avg_price * (1 + dynamic_tp_pct)
        add_position_price = current_avg_price * (1 + self.add_position_trigger_pct)
        stop_loss_price = current_avg_price * (1 + self.stop_loss_pct)
        
        # 判断这1小时可能触发的事件
        hour_high = hour_5m_df['high'].max()
        hour_low = hour_5m_df['low'].min()
        
        could_take_profit = hour_high >= take_profit_price
        could_add_position = (not position.get('has_add_position', False) and 
                             hour_low <= add_position_price)
        could_stop_loss = (position.get('has_add_position', False) and 
                          hour_low <= stop_loss_price)
        
        # 统计可能触发的事件数
        event_count = sum([could_take_profit, could_add_position, could_stop_loss])
        
        # 🚀 情况1：只可能止盈（最快）
        if event_count == 1 and could_take_profit:
            profit_bars = hour_5m_df[hour_5m_df['high'] >= take_profit_price]
            if not profit_bars.empty:
                first_bar = profit_bars.iloc[0]
                position['dynamic_tp_pct'] = dynamic_tp_pct
                exit_price = take_profit_price  # ✅ 使用止盈触发价而非K线最高价
                exit_datetime = first_bar['trade_datetime'].strftime('%Y-%m-%d %H:%M:%S')
                
                # 🔧 修复：止盈前更新最大跌幅（扫描整个持仓期间，从建仓到止盈）
                if all_5m_df is not None and not all_5m_df.empty:
                    # 获取建仓时间
                    entry_dt = entry_datetime
                    # 筛选从建仓到止盈的所有5分钟K线（包括建仓时刻）
                    mask = (all_5m_df['trade_datetime'] >= entry_dt) & (all_5m_df['trade_datetime'] <= first_bar['trade_datetime'])
                    bars_in_period = all_5m_df[mask]
                    if not bars_in_period.empty:
                        min_low = bars_in_period['low'].min()
                        # 最大跌幅 = (建仓价 - 最低价) / 建仓价，做多策略用正数表示下跌
                        drawdown_pct = (current_avg_price - min_low) / current_avg_price
                        if drawdown_pct > position.get('max_drawdown', 0):
                            position['max_drawdown'] = drawdown_pct
                
                self.exit_position(position, exit_price, exit_datetime, "take_profit")
                logging.info(f"💰 止盈(快速): {symbol} 高{exit_price:.6f}")
                return True
        
        # 🚀 情况2：只可能止损（快）
        elif event_count == 1 and could_stop_loss:
            loss_bars = hour_5m_df[hour_5m_df['low'] <= stop_loss_price]
            if not loss_bars.empty:
                first_bar = loss_bars.iloc[0]
                exit_price = stop_loss_price  # ✅ 使用止损触发价而非K线最低价
                exit_datetime = first_bar['trade_datetime'].strftime('%Y-%m-%d %H:%M:%S')
                
                # 🔧 修复：止损前更新最大跌幅
                drawdown_pct = (current_avg_price - exit_price) / current_avg_price
                if drawdown_pct > position.get('max_drawdown', 0):
                    position['max_drawdown'] = drawdown_pct
                
                self.exit_position(position, exit_price, exit_datetime, "stop_loss")
                logging.info(f"🛑 止损(快速): {symbol} 触发价{exit_price:.6f}")
                return True
        
        # 🚀 情况3：只可能补仓（快）
        elif event_count == 1 and could_add_position:
            add_bars = hour_5m_df[hour_5m_df['low'] <= add_position_price]
            if not add_bars.empty:
                first_bar = add_bars.iloc[0]
                add_price = add_position_price  # ✅ 使用补仓触发价而非K线最低价
                add_datetime = first_bar['trade_datetime']
                add_date = add_datetime.strftime('%Y-%m-%d')
                
                # 🔧 修复：补仓前更新最大跌幅
                drawdown_pct = (current_avg_price - add_price) / current_avg_price
                if drawdown_pct > position.get('max_drawdown', 0):
                    position['max_drawdown'] = drawdown_pct
                
                self.add_position(position, add_price, add_date)
                logging.info(f"🔄 补仓(快速): {symbol} 触发价{add_price:.6f}")
                
                # 补仓后检查这根K线及之后的K线是否止盈/止损
                new_avg_price = position['avg_entry_price']
                new_tp_price = new_avg_price * (1 + dynamic_tp_pct)
                new_sl_price = new_avg_price * (1 + self.stop_loss_pct)
                
                # 从补仓的这根K线开始检查
                after_add_df = hour_5m_df[hour_5m_df['trade_datetime'] >= add_datetime]
                
                # 检查止盈
                profit_after_add = after_add_df[after_add_df['high'] >= new_tp_price]
                if not profit_after_add.empty:
                    first_profit = profit_after_add.iloc[0]
                    position['dynamic_tp_pct'] = dynamic_tp_pct
                    exit_price = new_tp_price  # ✅ 使用止盈触发价而非K线最高价
                    exit_datetime = first_profit['trade_datetime'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 🔧 修复：补仓后止盈前更新最大跌幅（扫描整个持仓期间）
                    if all_5m_df is not None and not all_5m_df.empty:
                        # 筛选从建仓到止盈的所有5分钟K线（包括建仓时刻）
                        mask = (all_5m_df['trade_datetime'] >= entry_datetime) & (all_5m_df['trade_datetime'] <= first_profit['trade_datetime'])
                        bars_in_period = all_5m_df[mask]
                        if not bars_in_period.empty:
                            min_low = bars_in_period['low'].min()
                            drawdown_pct = (new_avg_price - min_low) / new_avg_price
                            if drawdown_pct > position.get('max_drawdown', 0):
                                position['max_drawdown'] = drawdown_pct
                    
                    self.exit_position(position, exit_price, exit_datetime, "take_profit")
                    logging.info(f"✨ 补仓后止盈: {symbol} 高{exit_price:.6f}")
                    return True
                
                # 检查止损
                loss_after_add = after_add_df[after_add_df['low'] <= new_sl_price]
                if not loss_after_add.empty:
                    first_loss = loss_after_add.iloc[0]
                    exit_price = new_sl_price  # ✅ 使用止损触发价而非K线最低价
                    exit_datetime = first_loss['trade_datetime'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 🔧 修复：止损前更新最大跌幅
                    drawdown_pct = (new_avg_price - exit_price) / new_avg_price
                    if drawdown_pct > position.get('max_drawdown', 0):
                        position['max_drawdown'] = drawdown_pct
                    
                    self.exit_position(position, exit_price, exit_datetime, "stop_loss")
                    logging.info(f"🛑 补仓后止损: {symbol} 触发价{exit_price:.6f}")
                    return True
        
        # 🐌 情况4：多个事件可能冲突，必须逐根检查
        else:
            for idx, row in hour_5m_df.iterrows():
                high_price = row['high']
                low_price = row['low']
                period_datetime = row['trade_datetime']
                period_date = period_datetime.strftime('%Y-%m-%d')
                period_datetime_str = period_datetime.strftime('%Y-%m-%d %H:%M:%S')
                
                # 检查最大持仓时间
                hours_held = (period_datetime - entry_datetime).total_seconds() / 3600
                if hours_held >= self.max_hold_hours:
                    exit_price = row['close']
                    
                    # 🔧 修复：强平前更新最大跌幅（扫描整个持仓期间）
                    if all_5m_df is not None and not all_5m_df.empty:
                        # 筛选从建仓到强平的所有5分钟K线（包括建仓时刻）
                        mask = (all_5m_df['trade_datetime'] >= entry_datetime) & (all_5m_df['trade_datetime'] <= period_datetime)
                        bars_in_period = all_5m_df[mask]
                        if not bars_in_period.empty:
                            min_low = bars_in_period['low'].min()
                            drawdown_pct = (current_avg_price - min_low) / current_avg_price
                            if drawdown_pct > position.get('max_drawdown', 0):
                                position['max_drawdown'] = drawdown_pct
                    
                    self.exit_position(position, exit_price, period_datetime_str, "max_hold_time")
                    logging.info(f"⏰ 最大持仓: {symbol}")
                    return True
                
                current_avg_price = position['avg_entry_price']
                
                # 更新最大跌幅
                drawdown_pct = (current_avg_price - low_price) / current_avg_price
                if drawdown_pct > position['max_drawdown']:
                    position['max_drawdown'] = drawdown_pct
                
                # 优先级1：检查止盈
                profit_pct = (high_price - current_avg_price) / current_avg_price
                if profit_pct >= dynamic_tp_pct:
                    position['dynamic_tp_pct'] = dynamic_tp_pct
                    take_profit_price = current_avg_price * (1 + dynamic_tp_pct)  # 计算止盈触发价
                    
                    # 🔧 修复：止盈前确保最大跌幅已更新（扫描整个持仓期间）
                    if all_5m_df is not None and not all_5m_df.empty:
                        # 筛选从建仓到止盈的所有5分钟K线（包括建仓时刻）
                        mask = (all_5m_df['trade_datetime'] >= entry_datetime) & (all_5m_df['trade_datetime'] <= period_datetime)
                        bars_in_period = all_5m_df[mask]
                        if not bars_in_period.empty:
                            min_low = bars_in_period['low'].min()
                            drawdown_pct = (current_avg_price - min_low) / current_avg_price
                            if drawdown_pct > position.get('max_drawdown', 0):
                                position['max_drawdown'] = drawdown_pct
                    
                    self.exit_position(position, take_profit_price, period_datetime_str, "take_profit")  # ✅ 使用止盈触发价
                    logging.info(f"💰 止盈(逐根): {symbol} 触发价{take_profit_price:.6f}")
                    return True
                
                # 优先级2：检查补仓
                if not position.get('has_add_position', False):
                    add_trigger_pct = (low_price - current_avg_price) / current_avg_price
                    if add_trigger_pct <= self.add_position_trigger_pct:
                        add_position_price = current_avg_price * (1 + self.add_position_trigger_pct)  # 计算补仓触发价
                        # 🔧 修复：补仓前更新最大跌幅（虽然前面已经更新过，但为了确保记录到触发点）
                        drawdown_at_add = (current_avg_price - add_position_price) / current_avg_price
                        if drawdown_at_add > position.get('max_drawdown', 0):
                            position['max_drawdown'] = drawdown_at_add
                        
                        self.add_position(position, add_position_price, period_date)  # ✅ 使用补仓触发价
                        logging.info(f"🔄 补仓(逐根): {symbol} 触发价{add_position_price:.6f}")
                        
                        # 补仓后检查同一根K线
                        new_avg_price = position['avg_entry_price']
                        
                        profit_after_add = (high_price - new_avg_price) / new_avg_price
                        if profit_after_add >= dynamic_tp_pct:
                            position['dynamic_tp_pct'] = dynamic_tp_pct
                            new_tp_price = new_avg_price * (1 + dynamic_tp_pct)  # 计算补仓后止盈触发价
                            
                            # 🔧 修复：补仓后同K线止盈前更新最大跌幅（扫描整个持仓期间）
                            if all_5m_df is not None and not all_5m_df.empty:
                                # 筛选从建仓到止盈的所有5分钟K线（包括建仓时刻）
                                mask = (all_5m_df['trade_datetime'] >= entry_datetime) & (all_5m_df['trade_datetime'] <= period_datetime)
                                bars_in_period = all_5m_df[mask]
                                if not bars_in_period.empty:
                                    min_low = bars_in_period['low'].min()
                                    drawdown_pct = (new_avg_price - min_low) / new_avg_price
                                    if drawdown_pct > position.get('max_drawdown', 0):
                                        position['max_drawdown'] = drawdown_pct
                            
                            self.exit_position(position, new_tp_price, period_datetime_str, "take_profit")  # ✅ 使用止盈触发价
                            logging.info(f"✨ 补仓后止盈(同K线): {symbol} 触发价{new_tp_price:.6f}")
                            return True
                        
                        loss_after_add = (low_price - new_avg_price) / new_avg_price
                        if loss_after_add <= self.stop_loss_pct:
                            new_sl_price = new_avg_price * (1 + self.stop_loss_pct)  # 计算补仓后止损触发价
                            # 🔧 修复：止损前更新最大跌幅
                            drawdown_at_loss = (new_avg_price - new_sl_price) / new_avg_price
                            if drawdown_at_loss > position.get('max_drawdown', 0):
                                position['max_drawdown'] = drawdown_at_loss
                            
                            self.exit_position(position, new_sl_price, period_datetime_str, "stop_loss")  # ✅ 使用止损触发价
                            logging.info(f"🛑 补仓后止损(同K线): {symbol} 触发价{new_sl_price:.6f}")
                            return True
                        
                        continue
                
                # 优先级3：检查止损
                if position.get('has_add_position', False):
                    loss_pct = (low_price - current_avg_price) / current_avg_price
                    if loss_pct <= self.stop_loss_pct:
                        stop_loss_price = current_avg_price * (1 + self.stop_loss_pct)  # 计算止损触发价
                        # 🔧 修复：止损前确保最大跌幅已更新（虽然前面已经更新过，但为了保险再次检查）
                        drawdown_at_stop = (current_avg_price - stop_loss_price) / current_avg_price
                        if drawdown_at_stop > position.get('max_drawdown', 0):
                            position['max_drawdown'] = drawdown_at_stop
                        
                        self.exit_position(position, stop_loss_price, period_datetime_str, "stop_loss")  # ✅ 使用止损触发价
                        logging.info(f"🛑 止损(逐根): {symbol} 触发价{stop_loss_price:.6f}")
                        return True
        
        return False

    def add_position(self, position: Dict, current_price: float, current_date: str):
        """补仓操作"""
        try:
            # 💰 复利模式：补仓也基于当前资金余额的比例（而非首次建仓金额）
            position_value = self.capital * self.position_size_ratio
            
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
            # ⚠️ 注意：position_size在建仓时已经乘以了杠杆
            leverage = position.get('leverage', 1.0)
            pnl = (exit_price - entry_price) * position_size  # 绝对盈亏（美元）
            price_change_pct = (exit_price - entry_price) / entry_price  # 价格变化
            pnl_pct = price_change_pct * leverage * 100  # 盈亏百分比（基于投入）
            
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
            table_name = f'DailyKline_{symbol}'  # 🔧 修复：使用DailyKline_表（数据更完整）
            safe_table_name = f'"{table_name}"'
            
            with engine.connect() as conn:
                result = conn.execute(text(f'''
                    SELECT open
                    FROM {safe_table_name}
                    WHERE trade_date = :date_str OR trade_date LIKE :date_pattern
                '''), {
                    "date_str": date_str,
                    "date_pattern": f'{date_str}%'
                })
                row = result.fetchone()
                return row[0] if row and row[0] else None
        
        except Exception as e:
            logging.error(f"获取 {symbol} {date_str} 开盘价失败: {e}")
            return None

    def run_backtest(self, start_date: str, end_date: str):
        """运行回测"""
        logging.info(f"开始买量暴涨策略回测（5分钟优化版 + 精简区间）: {start_date} 到 {end_date}")
        logging.info(f"初始资金: ${self.initial_capital:,.2f}")
        logging.info(f"杠杆倍数: {self.leverage}x")
        logging.info(f"单笔仓位: {self.position_size_ratio*100:.1f}%，最大持仓: {self.max_positions}个")
        logging.info(f"🎯 买量区间（基于250笔完整数据优化）: 100-150倍（核心） + 800-900倍（优质）")
        logging.info(f"📊 预期表现: 179笔交易（占71.6%），胜率61.5%，止盈率52.5%")
        logging.info(f"等待策略: 统一10%回调")
        logging.info(f"最大持仓时间: {self.max_hold_hours:.0f}小时（{self.max_hold_hours/24:.0f}天）")
        logging.info(f"⚡ 优势：聚焦顶级区间，提升整体质量")
        
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
                    table_name = f'DailyKline_{position["symbol"]}'  # 🔧 修复：使用DailyKline_表（数据更完整）
                    safe_table_name = f'"{table_name}"'
                    
                    with engine.connect() as conn:
                        result = conn.execute(text(f'''
                            SELECT close
                            FROM {safe_table_name}
                            WHERE trade_date = :date_str OR trade_date LIKE :date_pattern
                        '''), {
                            "date_str": date_str,
                            "date_pattern": f'{date_str}%'
                        })
                        row = result.fetchone()
                    current_price = row[0] if (row and row[0]) else 0.0
                    
                    # 🔧 关键修复：即使日K线数据缺失，也要调用check_exit_conditions
                    # 因为check_exit_conditions内部会使用小时和5分钟数据，不依赖current_price
                    self.check_exit_conditions(position, current_price, date_str)
                
                except Exception as e:
                    logging.debug(f"检查持仓失败: {e}")
            
            # 检查待建仓信号（使用5分钟数据）
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
                
                # 获取5分钟数据检查是否达到目标价格
                interval_5m_df = self.get_5m_kline_data(symbol)
                if not interval_5m_df.empty:
                    # 筛选信号日之后到当前日期的5分钟数据
                    interval_5m_df['trade_datetime'] = pd.to_datetime(interval_5m_df['trade_date'])
                    signal_datetime = signal['signal_datetime']
                    mask = (interval_5m_df['trade_datetime'] >= signal_datetime) & (interval_5m_df['trade_datetime'] <= current_date)
                    check_period_data = interval_5m_df[mask]
                    
                    # 检查是否有5分钟低点达到目标价格
                    for _, row in check_period_data.iterrows():
                        if row['low'] <= target_price:
                            # 达到目标价格，建仓
                            entry_price = target_price
                            entry_datetime = row['trade_datetime']
                            entry_date = entry_datetime.strftime('%Y-%m-%d')
                            
                            if len(self.positions) < self.max_positions:  # 检查持仓数量限制
                                self.execute_trade(symbol, entry_price, entry_date, 
                                                 signal['signal_date'], buy_surge_ratio, 
                                                 entry_datetime=entry_datetime,  # 🆕 传入完整时间戳
                                                 signal_price=signal_close)  # 🆕 传入信号价格
                                logging.info(f"✅ {symbol} 达到目标跌幅{target_drop_pct*100:.0f}%，建仓价{entry_price:.6f}，建仓时间{entry_datetime}")
                            else:
                                logging.info(f"⚠️ 持仓数量已达上限({self.max_positions})，跳过交易对 {symbol}")
                            
                            signals_to_remove.append(signal)
                            break
            
            # 移除已处理的信号
            for signal in signals_to_remove:
                if signal in self.pending_signals:
                    self.pending_signals.remove(signal)
            
            # 🆕 寻找新的买量暴涨信号（5分钟优化版：每天检测1次）
            # 💡 pending_signals不占用持仓槽位，只在真正建仓时检查持仓数量
            if len(self.positions) < self.max_positions:
                # 🚀 每天检测1次，找出今天哪些5分钟的买量超过昨日平均5分钟买量
                daily_signals = self.get_daily_5m_surge_signals(date_str)
                
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
                    
                    # 🔧 关键修复：5分钟K线数据只有在该5分钟结束后才能看到
                    # 例如19:00的K线，要到19:05才能看到完整数据，所以最早19:05才能建仓
                    earliest_entry_datetime = signal_datetime + timedelta(minutes=5)
                    
                    # 🎯 根据买量倍数动态设置等待回调比例
                    target_drop_pct = self.get_wait_drop_pct(surge_ratio)
                    timeout_datetime = earliest_entry_datetime + timedelta(hours=self.wait_timeout_hours)
                    
                    self.pending_signals.append({
                        'symbol': symbol,
                        'signal_date': signal_datetime.strftime('%Y-%m-%d %H:%M'),  # 保存原始信号时间用于显示
                        'signal_datetime': earliest_entry_datetime,  # 实际可以开始建仓的时间（信号时间+5分钟）
                        'signal_close': signal_price,
                        'buy_surge_ratio': surge_ratio,
                        'target_drop_pct': target_drop_pct,
                        'timeout_datetime': timeout_datetime
                    })
                    
                    logging.info(f"🔔 新信号: {symbol} @{signal_datetime.strftime('%H:%M')} 买量{surge_ratio:.2f}倍，可建仓时间: {earliest_entry_datetime.strftime('%H:%M')}")
            
            current_date += timedelta(days=1)
        
        # 最后强制平仓
        for position in self.positions.copy():
            try:
                table_name = f'DailyKline_{position["symbol"]}'  # 🔧 修复：使用DailyKline_表（数据更完整）
                safe_table_name = f'"{table_name}"'
                
                with engine.connect() as conn:
                    result = conn.execute(text(f'''
                        SELECT close
                        FROM {safe_table_name}
                        WHERE trade_date = :end_date OR trade_date LIKE :end_pattern
                        ORDER BY trade_date DESC
                        LIMIT 1
                    '''), {
                        "end_date": end_date,
                        "end_pattern": f'{end_date}%'
                    })
                    row = result.fetchone()
                if row and row[0]:
                    exit_price = row[0]
                    self.exit_position(position, exit_price, end_date, "force_close")
            
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
                    '是否有补仓', '补仓价格', '补仓后平均价', '持仓小时数', '最大跌幅%', '最大涨幅%', '止盈阈值%'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for i, trade in enumerate(self.trade_records, 1):
                    # 防止死循环：限制最多处理1000条记录
                    if i > 1000:
                        logging.warning(f"⚠️ CSV报告已达到1000条记录限制，停止写入")
                        break
                    
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
                    
                    # 🆕 计算持仓小时数
                    hold_hours = 0
                    if trade.get('entry_datetime') and trade.get('exit_datetime'):
                        try:
                            if isinstance(trade['entry_datetime'], str):
                                entry_dt = pd.to_datetime(trade['entry_datetime'])
                            else:
                                entry_dt = trade['entry_datetime']
                            
                            if isinstance(trade['exit_datetime'], str):
                                exit_dt = pd.to_datetime(trade['exit_datetime'])
                            else:
                                exit_dt = trade['exit_datetime']
                            
                            hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                            hold_hours = round(hold_hours, 1)  # 保留1位小数
                        except:
                            hold_hours = trade.get('hold_days', 0) * 24
                    else:
                        hold_hours = trade.get('hold_days', 0) * 24
                    
                    # 🆕 计算最大涨幅（从建仓后72小时内的最高价）
                    max_gain = 0
                    if trade.get('entry_datetime'):
                        try:
                            symbol = trade['symbol']
                            if isinstance(trade['entry_datetime'], str):
                                entry_dt = pd.to_datetime(trade['entry_datetime'])
                            else:
                                entry_dt = trade['entry_datetime']
                            
                            # 计算72小时后的时间
                            end_dt = entry_dt + pd.Timedelta(hours=72)
                            
                            # 如果有平仓时间，取较小值
                            if trade.get('exit_datetime'):
                                if isinstance(trade['exit_datetime'], str):
                                    exit_dt = pd.to_datetime(trade['exit_datetime'])
                                else:
                                    exit_dt = trade['exit_datetime']
                                end_dt = min(end_dt, exit_dt)
                            
                            # 获取5分钟K线数据
                            interval_5m_df = self.get_5m_kline_data(symbol)
                            if not interval_5m_df.empty:
                                interval_5m_df['trade_datetime'] = pd.to_datetime(interval_5m_df['trade_date'])
                                # 筛选建仓到72小时（或平仓时间）的数据
                                mask = (interval_5m_df['trade_datetime'] >= entry_dt) & (interval_5m_df['trade_datetime'] <= end_dt)
                                period_df = interval_5m_df[mask]
                                
                                if not period_df.empty:
                                    max_high = period_df['high'].max()
                                    avg_price = trade['avg_entry_price']
                                    max_gain = (max_high - avg_price) / avg_price
                        except Exception as e:
                            logging.debug(f"计算最大涨幅失败: {e}")
                            max_gain = 0
                    
                    row = {
                        '序号': i,
                        '交易对': trade['symbol'],
                        '买量暴涨倍数': f"{trade.get('buy_surge_ratio', 0):.1f}倍",
                        '信号时间': trade.get('signal_date', ''),  # 🆕 信号时间（已经包含小时）
                        '建仓日期': trade['entry_date'],
                        '建仓具体时间': entry_datetime_str,
                        '建仓价': f"{trade['entry_price']:.6f}",
                        '平仓日期': trade.get('exit_date', ''),
                        '平仓具体时间': exit_datetime_str,  # 🆕 平仓具体时间
                        '平仓价': f"{trade.get('exit_price', 0):.6f}" if trade.get('exit_price') else '',
                        '盈亏金额': f"{trade.get('pnl', 0):.2f}",
                        '盈亏百分比': f"{trade.get('pnl_pct', 0):.2f}%",
                        '平仓原因': trade.get('exit_reason', ''),
                        '杠杆倍数': trade['leverage'],
                        '仓位金额': f"{trade['position_value']:.2f}",
                        '是否有补仓': '✅是' if trade.get('has_add_position', False) else '否',
                        '补仓价格': f"{trade.get('add_position_price', 0):.6f}" if trade.get('add_position_price') else '',
                        '补仓后平均价': avg_price_after_add,
                        '持仓小时数': hold_hours,  # 🆕 改为小时数
                        '最大跌幅%': f"{trade.get('max_drawdown', 0)*100:.2f}%" if trade.get('max_drawdown') else '0.00%',
                        '最大涨幅%': f"{max_gain*100:.2f}%",  # 🆕 最大涨幅（72小时内最高价相对建仓价）
                        '止盈阈值%': f"{trade.get('dynamic_tp_pct', self.take_profit_pct)*100:.0f}%"  # 使用实际的动态止盈阈值
                    }
                    writer.writerow(row)
            
            print(f"📄 交易详细CSV报告已生成: {csv_filename}")
        
        except Exception as e:
            print(f"❌ 生成CSV报告失败: {e}")

def main():
    """主函数"""
    # 动态获取今天的日期作为默认结束日期
    today = datetime.now().strftime('%Y-%m-%d')
    
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
        default=today,
        help=f'结束日期(默认: 今天 {today})'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=400.0,
        help='买量暴涨阈值下限(默认: 400.0倍 - 5分钟买量 vs 昨日平均5分钟买量)'
    )
    
    args = parser.parse_args()
    
    backtest = BuySurgeBacktest()
    
    # 🎯 买量区间配置已在类初始化时设置（支持多区间）
    # 当前配置: 100-350倍 + 500-1000倍
    logging.info(f"买量暴涨区间设置为: {backtest.buy_surge_ranges}")
    
    # 可以通过参数调整阈值（已废弃，现在使用区间配置）
    # if args.threshold:
    #     backtest.buy_surge_threshold = args.threshold
    
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
