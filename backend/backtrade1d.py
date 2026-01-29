"""
根据U本位合约K线数据模拟交易脚本

功能：
1. 从本地SQLite数据库（crypto_data.db）读取所有USDT交易对的K线数据
2. 计算每天的涨幅（pct_chg），找出涨幅第一的交易对
3. 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
4. 建仓策略：
   - 初始资金：10000 USDT
   - 每次建仓金额：账户余额的3%
   - 杠杆：3倍
   - 建仓条件：涨幅>=20% 且 该交易对未持仓
   - 建仓方向：卖空（做空）
   - 建仓价格：第二天开盘价
5. 平仓策略：
   - 止盈：价格下跌20%时盈利平仓（买入平仓）
   - 止损：价格上涨49%时止损平仓（买入平仓）
#    - 补仓：第一次触发止损时，进行补仓（补仓数量=持仓数量），补仓后重新计算平均建仓价和止盈止损价格
#    - 如果已补仓过，再次触发止损则直接平仓
6. 持仓管理：
   - 支持同时持有多个仓位
   - 已开仓的交易对在未平仓期间，不重复建仓同一交易对
   - 每天检查所有持仓的平仓条件
7. 数据保存：
   - 交易记录保存到SQLite数据库（backtrade_records表）
   - 交易记录保存到CSV文件（backtrade_records_{start_date}_{end_date}.csv）

注意：本策略是做空策略，建仓方向是卖空，平仓方向是买入平仓
"""

import os
import logging
import re

import pandas as pd  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from db import engine, create_table, create_trade_table
from data import get_local_symbols, get_local_kline_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 交易参数
INITIAL_CAPITAL = 1000  # 初始资金10000美金
LEVERAGE = 5 # 三倍杠杆
PROFIT_THRESHOLD = 0.2   # 止盈25%（建仓价格盈利25%）
LOSS_THRESHOLD = 0.19  # 止损49%平仓
POSITION_SIZE_RATIO = 0.05 # 每次建仓金额为账户余额的9%
MIN_PCT_CHG = 0.1  # 最小涨幅15%才建仓

# INITIAL_CAPITAL = 700  # 初始资金10000美金
# LEVERAGE = 20 # 三倍杠杆
# PROFIT_THRESHOLD = 0.04   # 止盈25%（建仓价格盈利25%）
# LOSS_THRESHOLD = 0.019  # 止损49%平仓
# POSITION_SIZE_RATIO = 0.06 # 每次建仓金额为账户余额的9%
# MIN_PCT_CHG = 0.1  # 最小涨幅15%才建仓


"""
效果最佳的回测数据startdate2021-12-01 enddate2026-01-03
INITIAL_CAPITAL = 10000  # 初始资金10000美金
LEVERAGE = 3  # 三倍杠杆
PROFIT_THRESHOLD = 0.25   # 止盈25%（建仓价格盈利25%）
LOSS_THRESHOLD = 0.29  # 止损49%平仓
POSITION_SIZE_RATIO = 0.03  # 每次建仓金额为账户余额的3%
MIN_PCT_CHG = 0.1  # 最小涨幅15%才建仓
--------------------------------
INITIAL_CAPITAL = 10000  # 初始资金10000美金
LEVERAGE = 3  # 三倍杠杆
PROFIT_THRESHOLD = 0.26   # 止盈25%（建仓价格盈利25%）
LOSS_THRESHOLD = 0.29  # 止损49%平仓
POSITION_SIZE_RATIO = 0.03  # 每次建仓金额为账户余额的3%
MIN_PCT_CHG = 0.1 
INFO:root:成功保存 1097 条交易记录到CSV文件: backtrade_records_2021-12-01_2026-01-03.csv
INFO:root:============================================================
INFO:root:回测统计:
INFO:root:初始资金: 10000.00 USDT
INFO:root:最终资金: 22394.13 USDT
INFO:root:总盈亏: 12394.13 USDT
INFO:root:总收益率: 123.94%
INFO:root:交易次数: 1097
INFO:root:盈利次数: 627
INFO:root:亏损次数: 470
INFO:root:胜率: 57.16%
INFO:root:============================================================


补仓或第一次回测
INFO:root:成功保存 1012 条交易记录到CSV文件: backtrade_records_2021-12-01_2026-01-03.csv
INFO:root:============================================================
INFO:root:回测统计:
INFO:root:初始资金: 10000.00 USDT
INFO:root:最终资金: 67149.01 USDT
INFO:root:总盈亏: 57149.01 USDT
INFO:root:总收益率: 571.49%
INFO:root:交易次数: 1012
INFO:root:盈利次数: 788
INFO:root:亏损次数: 224
INFO:root:胜率: 77.87%
INFO:root:============================================================

最成功的回测数据startdate2025-01-01 enddate2025-12-31
INITIAL_CAPITAL = 10000  # 初始资金10000美金
LEVERAGE = 3  # 三倍杠杆
PROFIT_THRESHOLD = 0.20   # 止盈25%（建仓价格盈利25%）
LOSS_THRESHOLD = 0.29  # 止损49%平仓
POSITION_SIZE_RATIO = 0.18 # 每次建仓金额为账户余额的9%
MIN_PCT_CHG = 0.1

INFO:root:成功保存 288 条交易记录到数据库
INFO:root:成功保存 288 条交易记录到CSV文件: backtrade_records_2025-01-01_2025-12-31.csv
INFO:root:============================================================
INFO:root:回测统计:
INFO:root:初始资金: 10000.00 USDT
INFO:root:最终资金: 144916.51 USDT
INFO:root:总盈亏: 134916.51 USDT
INFO:root:总收益率: 1349.17%
INFO:root:交易次数: 288
INFO:root:盈利次数: 232
INFO:root:亏损次数: 56
INFO:root:胜率: 80.56%
INFO:root:============================================================
"""

def get_top_gainer_by_date(date: str) -> Optional[Tuple[str, float]]:
    """
    获取指定日期涨幅第一的交易对
    
    Args:
        date: 日期字符串，格式 'YYYY-MM-DD'
    
    Returns:
        Tuple[symbol, pct_chg] 或 None
    """
    symbols = get_local_symbols(interval="1d")
    top_gainer = None
    max_pct_chg = float('-inf')
    
    for symbol in symbols:
        try:
            df = get_local_kline_data(symbol, interval="1d")
            if df.empty:
                continue
            
            # 将trade_date转换为字符串格式进行比较（处理多种日期格式）
            # 如果已经是字符串格式，先提取日期部分；如果是datetime，直接转换
            if df['trade_date'].dtype == 'object':
                # 字符串格式，提取日期部分
                df['trade_date_str'] = df['trade_date'].str[:10]
            else:
                # datetime格式
                df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            
            # 查找指定日期的数据
            date_data = df[df['trade_date_str'] == date]
            if date_data.empty:
                continue
            
            row = date_data.iloc[0]
            pct_chg = row['pct_chg']
            
            # 如果pct_chg是NaN，尝试使用收盘价和开盘价计算涨幅
            if pd.isna(pct_chg):
                # 查找前一天的收盘价
                date_dt = datetime.strptime(date, '%Y-%m-%d')
                prev_date = (date_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                prev_data = df[df['trade_date_str'] == prev_date]
                
                if not prev_data.empty and not pd.isna(prev_data.iloc[0]['close']):
                    prev_close = prev_data.iloc[0]['close']
                    current_close = row['close']
                    if not pd.isna(current_close) and prev_close > 0:
                        # 计算涨幅
                        pct_chg = (current_close - prev_close) / prev_close * 100
                    else:
                        continue
                else:
                    continue
            
            if pct_chg > max_pct_chg:
                max_pct_chg = pct_chg
                top_gainer = symbol
        except Exception as e:
            logging.debug(f"获取 {symbol} 在 {date} 的数据失败: {e}")
            continue
    
    if top_gainer:
        return (top_gainer, max_pct_chg)
    return None


def get_all_top_gainers(start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取指定日期范围内所有涨幅第一的交易对（优化版本）
    
    Args:
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'
    
    Returns:
        DataFrame包含日期、交易对、涨幅
    """
    symbols = get_local_symbols(interval="1d")
    all_data = []
    
    # 一次性读取所有交易对的数据
    logging.info(f"正在读取 {len(symbols)} 个交易对的数据...")
    for symbol in symbols:
        try:
            df = get_local_kline_data(symbol, interval="1d")
            if df.empty:
                continue
            
            # 标准化trade_date格式
            if df['trade_date'].dtype == 'object':
                df['trade_date_str'] = df['trade_date'].str[:10]
            else:
                df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            
            # 筛选日期范围
            date_mask = (df['trade_date_str'] >= start_date) & (df['trade_date_str'] <= end_date)
            df_filtered = df[date_mask].copy()
            
            if df_filtered.empty:
                continue
            
            # 添加symbol列
            df_filtered['symbol'] = symbol
            
            # 处理NaN的pct_chg
            for idx, row in df_filtered.iterrows():
                if pd.isna(row['pct_chg']):
                    # 尝试计算涨幅
                    date_str = row['trade_date_str']
                    date_dt = datetime.strptime(date_str, '%Y-%m-%d')
                    prev_date = (date_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                    prev_data = df[df['trade_date_str'] == prev_date]
                    
                    if not prev_data.empty and not pd.isna(prev_data.iloc[0]['close']):
                        prev_close = prev_data.iloc[0]['close']
                        current_close = row['close']
                        if not pd.isna(current_close) and prev_close > 0:
                            df_filtered.at[idx, 'pct_chg'] = (current_close - prev_close) / prev_close * 100
            
            # 只保留需要的列
            df_filtered = df_filtered[['trade_date_str', 'symbol', 'pct_chg']].copy()
            all_data.append(df_filtered)
        except Exception as e:
            logging.debug(f"读取 {symbol} 数据失败: {e}")
            continue
    
    if not all_data:
        logging.warning("未找到任何数据")
        return pd.DataFrame(columns=['date', 'symbol', 'pct_chg'])
    
    # 合并所有数据
    logging.info("正在合并数据并计算涨幅第一...")
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 过滤掉pct_chg为NaN的行
    combined_df = combined_df[combined_df['pct_chg'].notna()]
    
    # 先重命名列，避免后续警告
    combined_df = combined_df.rename(columns={'trade_date_str': 'date'})
    
    # 按日期分组，使用nlargest找出每天涨幅最大的交易对
    # 在 apply 函数中显式选择需要的列，这样分组列会被保留，避免警告
    def get_top_gainer(group):
        """获取每组中涨幅最大的交易对"""
        top = group.nlargest(1, 'pct_chg')
        return top[['date', 'symbol', 'pct_chg']]
    
    top_gainers = (
        combined_df.groupby('date', group_keys=False)
        .apply(get_top_gainer)
        .reset_index(drop=True)
    )
    
    # 按日期排序
    top_gainers = top_gainers.sort_values('date').reset_index(drop=True)
    
    # 记录日志
    for _, row in top_gainers.iterrows():
        logging.info(f"{row['date']}: 涨幅第一 {row['symbol']}, 涨幅 {row['pct_chg']:.2f}%")
    
    return top_gainers[['date', 'symbol', 'pct_chg']]


def get_kline_data_for_date(symbol: str, date: str) -> Optional[pd.Series]:
    """
    获取指定交易对在指定日期的K线数据
    
    Args:
        symbol: 交易对符号
        date: 日期字符串 'YYYY-MM-DD'
    
    Returns:
        Series包含该日期的K线数据，或None
    """
    try:
        df = get_local_kline_data(symbol, interval="1d")
        if df.empty:
            return None
        
        # 将trade_date转换为日期字符串格式进行比较（处理多种日期格式）
        # 如果已经是字符串格式，先提取日期部分；如果是datetime，直接转换
        if df['trade_date'].dtype == 'object':
            # 字符串格式，提取日期部分
            df['trade_date_str'] = df['trade_date'].str[:10]
        else:
            # datetime格式
            df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        
        date_data = df[df['trade_date_str'] == date]
        if date_data.empty:
            return None
        
        return date_data.iloc[0]
    except Exception as e:
        logging.error(f"获取 {symbol} 在 {date} 的K线数据失败: {e}")
        return None


def create_trade_table():
    """创建交易记录表（使用 db.py 中的函数）"""
    from db import create_trade_table as _create_trade_table
    return _create_trade_table()


def simulate_trading(
    start_date: str,
    end_date: str,
    initial_capital: Optional[float] = None,
    leverage: Optional[float] = None,
    profit_threshold: Optional[float] = None,
    loss_threshold: Optional[float] = None,
    position_size_ratio: Optional[float] = None,
    min_pct_chg: Optional[float] = None
) -> Optional[Dict]:
    """
    模拟交易
    
    Args:
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'
        initial_capital: 初始资金（USDT），默认使用全局变量 INITIAL_CAPITAL
        leverage: 杠杆倍数，默认使用全局变量 LEVERAGE
        profit_threshold: 止盈阈值（小数，如0.04表示4%），默认使用全局变量 PROFIT_THRESHOLD
        loss_threshold: 止损阈值（小数，如0.019表示1.9%），默认使用全局变量 LOSS_THRESHOLD
        position_size_ratio: 每次建仓金额占账户余额的比例（小数，如0.06表示6%），默认使用全局变量 POSITION_SIZE_RATIO
        min_pct_chg: 最小涨幅百分比（小数，如0.1表示10%），默认使用全局变量 MIN_PCT_CHG
    
    Returns:
        Dict: 包含回测统计信息的字典，如果没有交易记录则返回None
    """
    # 使用传入的参数或默认值
    _initial_capital = initial_capital if initial_capital is not None else INITIAL_CAPITAL
    _leverage = leverage if leverage is not None else LEVERAGE
    _profit_threshold = profit_threshold if profit_threshold is not None else PROFIT_THRESHOLD
    _loss_threshold = loss_threshold if loss_threshold is not None else LOSS_THRESHOLD
    _position_size_ratio = position_size_ratio if position_size_ratio is not None else POSITION_SIZE_RATIO
    _min_pct_chg = min_pct_chg if min_pct_chg is not None else MIN_PCT_CHG
    
    # 创建交易记录表
    create_trade_table()
    
    # 获取所有涨幅第一的交易对
    logging.info(f"正在获取 {start_date} 到 {end_date} 期间的涨幅第一交易对...")
    top_gainers_df = get_all_top_gainers(start_date, end_date)
    
    if top_gainers_df.empty:
        logging.warning("未找到任何涨幅第一的交易对")
        return None
    
    logging.info(f"共找到 {len(top_gainers_df)} 个涨幅第一的交易对")
    logging.info(f"策略参数: 初始资金={_initial_capital}, 杠杆={_leverage}x, 止盈={_profit_threshold*100:.1f}%, 止损={_loss_threshold*100:.1f}%, 建仓比例={_position_size_ratio*100:.1f}%, 最小涨幅={_min_pct_chg*100:.1f}%")
    
    # 当前持仓
    current_positions = []  # 支持多个仓位同时存在
    capital = _initial_capital
    trade_records = []
    
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    while current_date <= end_dt:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 检查所有持仓是否需要平仓
        positions_to_close = []
        for i, current_position in enumerate(current_positions):
            symbol = current_position['symbol']
            entry_price = current_position['entry_price']
            entry_date = current_position['entry_date']
            
            # 获取当天的K线数据
            kline_data = get_kline_data_for_date(symbol, date_str)
            if kline_data is None:
                logging.warning(f"{date_str}: {symbol} 无K线数据，跳过")
                current_date += timedelta(days=1)
                continue
            
            open_price = kline_data['open']
            high_price = kline_data['high']
            low_price = kline_data['low']
            close_price = kline_data['close']
            
            # 做空交易：价格下跌我们盈利，价格上涨我们亏损
            # 计算涨跌幅（相对于建仓价）
            price_change_high = (high_price - entry_price) / entry_price  # 价格上涨幅度
            price_change_low = (low_price - entry_price) / entry_price    # 价格下跌幅度
            
            exit_reason = None
            exit_price = None
            
            # 检查是否达到平仓条件
            # 做空：价格下跌达到止盈阈值时盈利平仓，价格上涨达到止损阈值时亏损平仓
            if price_change_low <= -_profit_threshold:
                # 价格下跌达到止盈阈值，盈利平仓
                exit_price = entry_price * (1 - _profit_threshold)
                add_position_count = current_position.get('add_position_count', 0)
                if add_position_count > 0:
                    exit_reason = f"价格下跌{_profit_threshold*100:.1f}%，盈利平仓（已补仓{add_position_count}次）"
                else:
                    exit_reason = f"价格下跌{_profit_threshold*100:.1f}%，盈利平仓"
            elif price_change_high >= _loss_threshold:
                # 价格上涨达到止损阈值
                add_position_count = current_position.get('add_position_count', 0)
                MAX_ADD_POSITION_COUNT = 2  # 最多补仓2次
                
                if add_position_count < MAX_ADD_POSITION_COUNT:
                    # 触发止损，进行补仓（可以补仓2次）
                    # 补仓价格：使用触发止损时的价格（止损价格）
                    add_position_price = entry_price * (1 + _loss_threshold)
                    # 补仓数量：等于原持仓数量
                    original_position_size = current_position['position_size']
                    add_position_size = original_position_size
                    
                    # 计算新的平均持仓价格 = (原建仓价 * 原数量 + 补仓价 * 补仓数量) / 总数量
                    total_position_size = original_position_size + add_position_size
                    new_avg_entry_price = (entry_price * original_position_size + add_position_price * add_position_size) / total_position_size
                    
                    # 计算补仓需要的保证金
                    # 简化计算：补仓金额 = 账户余额的_position_size_ratio
                    add_position_value = capital * _position_size_ratio
                    
                    # 检查资金是否足够
                    if capital < add_position_value:
                        logging.warning(f"{date_str}: {symbol} 资金不足，无法补仓。当前资金: {capital:.2f} USDT，需要: {add_position_value:.2f} USDT")
                        # 资金不足，直接止损
                        exit_price = add_position_price
                        exit_reason = f"价格上涨{_loss_threshold*100:.1f}%，止损平仓（资金不足无法补仓）"
                    else:
                        # 更新持仓信息
                        current_position['entry_price'] = new_avg_entry_price
                        current_position['position_size'] = total_position_size
                        current_position['position_value'] = current_position.get('position_value', 0) + add_position_value
                        current_position['add_position_count'] = add_position_count + 1
                        
                        # 扣除补仓保证金
                        capital -= add_position_value
                        
                        logging.info(
                            f"{date_str}: 第{add_position_count + 1}次补仓 {symbol} | "
                            f"原建仓价: {entry_price:.8f} | "
                            f"补仓价: {add_position_price:.8f} | "
                            f"新平均价: {new_avg_entry_price:.8f} | "
                            f"原持仓数量: {original_position_size:.4f} | "
                            f"补仓数量: {add_position_size:.4f} | "
                            f"总持仓数量: {total_position_size:.4f} | "
                            f"补仓金额: {add_position_value:.2f} USDT | "
                            f"账户余额: {capital:.2f} USDT"
                        )
                        # 补仓后继续持有，不进行平仓
                        continue
                else:
                    # 已经补仓2次，再次触发止损，直接止损平仓
                    exit_price = entry_price * (1 + _loss_threshold)
                    exit_reason = f"价格上涨{_loss_threshold*100:.1f}%，止损平仓（已补仓2次）"
            else:
                # 未达到平仓条件，继续持有
                # 做空：价格下跌是盈利，价格上涨是亏损
                # 更新最大盈利（价格下跌幅度）和最大亏损（价格上涨幅度）
                current_position['max_profit'] = max(
                    current_position.get('max_profit', 0),
                    -price_change_low  # 价格下跌幅度转为盈利
                )
                current_position['max_loss'] = max(
                    current_position.get('max_loss', 0),
                    price_change_high  # 价格上涨幅度为亏损
                )
                continue  # 继续持有，检查下一个仓位
            
            # 平仓
            if exit_price:
                hold_days = (current_date - datetime.strptime(entry_date, '%Y-%m-%d')).days
                # 做空：盈亏 = (建仓价 - 平仓价) * 持仓数量
                # 注意：持仓数量已经包含了杠杆，所以不需要再乘以LEVERAGE
                profit_loss = (entry_price - exit_price) * current_position['position_size']
                profit_loss_pct = (entry_price - exit_price) / entry_price
                
                # 记录补仓次数
                add_position_count = current_position.get('add_position_count', 0)
                
                trade_record = {
                    'entry_date': entry_date,
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': _leverage,
                    'exit_date': date_str,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'max_profit': current_position.get('max_profit', 0),
                    'max_loss': current_position.get('max_loss', 0),
                    'hold_days': hold_days,
                    'add_position_count': add_position_count  # 记录补仓次数
                }
                
                trade_records.append(trade_record)
                # 平仓时：释放保证金 + 盈亏
                position_value = current_position.get('position_value', 0)
                capital += position_value + profit_loss
                
                # 记录补仓信息
                position_info = ""
                if add_position_count > 0:
                    position_info = f" | 已补仓{add_position_count}次"
                
                logging.info(
                    f"{date_str}: 平仓（买入） {symbol} | "
                    f"建仓价（卖空）: {entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓天数: {hold_days} | "
                    f"原因: {exit_reason}{position_info} | "
                    f"当前资金: {capital:.2f} USDT"
                )
                
                positions_to_close.append(i)  # 标记需要平仓的仓位索引
        
        # 从后往前删除已平仓的仓位（避免索引错乱）
        for i in reversed(positions_to_close):
            current_positions.pop(i)
        
        # 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
        today_top = top_gainers_df[top_gainers_df['date'] == date_str]
        if not today_top.empty:
            symbol = today_top.iloc[0]['symbol']
            pct_chg = today_top.iloc[0]['pct_chg']
            
            # 检查该交易对是否已经在持仓中且未止盈
            already_holding = any(pos['symbol'] == symbol for pos in current_positions)
            
            # 只有当涨幅>=20%且该交易对未持仓时才建仓
            # 建仓条件：涨幅>=20% 且 该交易对未持仓
            # 如果已在持仓中，跳过建仓（避免重复持仓同一交易对）
            if pct_chg >= _min_pct_chg * 100 and not already_holding:
                # 获取第二天的开盘价（建仓价）
                next_date = current_date + timedelta(days=1)
                next_date_str = next_date.strftime('%Y-%m-%d')
                
                if next_date <= end_dt:
                    kline_data = get_kline_data_for_date(symbol, next_date_str)
                    if kline_data is not None:
                        # 建仓价使用开盘价
                        entry_price = kline_data['open']
                        
                        # 每次建仓金额为账户余额的_position_size_ratio
                        # 持仓数量 = (建仓金额 * 杠杆) / 建仓价
                        position_size = (capital * _position_size_ratio * _leverage) / entry_price
                        
                        position_value = capital * _position_size_ratio  # 建仓金额
                        capital -= position_value  # 扣除建仓金额（作为保证金）
                        
                        new_position = {
                            'symbol': symbol,
                            'entry_price': entry_price,
                            'entry_date': next_date_str,
                            'position_size': position_size,
                            'entry_pct_chg': pct_chg,
                            'position_value': position_value,  # 记录建仓金额（保证金）
                            'max_profit': 0,
                            'max_loss': 0,
                            'add_position_count': 0  # 记录补仓次数
                        }
                        current_positions.append(new_position)
                        
                        logging.info(
                            f"{next_date_str}: 建仓（卖空） {symbol} | "
                            f"建仓价（卖空）: {entry_price:.8f} | "
                            f"持仓数量: {position_size:.4f} | "
                            f"建仓金额: {position_value:.2f} USDT (账户余额的{_position_size_ratio*100:.1f}%) | "
                            f"昨日涨幅: {pct_chg:.2f}% | "
                            f"杠杆: {_leverage}x | "
                            f"账户余额: {capital:.2f} USDT | "
                            f"当前持仓数: {len(current_positions)}"
                        )
            elif already_holding:
                logging.info(f"{date_str}: {symbol} 涨幅 {pct_chg:.2f}%，已在持仓中，跳过建仓")
            else:
                logging.debug(f"{date_str}: {symbol} 涨幅 {pct_chg:.2f}% < {_min_pct_chg*100:.1f}%，不建仓")
        
        current_date += timedelta(days=1)
    
    # 如果最后还有持仓，以最后一天的收盘价平仓
    if current_positions:
        last_date_str = end_date
        for current_position in current_positions:
            symbol = current_position['symbol']
            entry_price = current_position['entry_price']
            entry_date = current_position['entry_date']
            
            kline_data = get_kline_data_for_date(symbol, last_date_str)
            if kline_data is not None:
                exit_price = kline_data['close']
                hold_days = (datetime.strptime(last_date_str, '%Y-%m-%d') - 
                            datetime.strptime(entry_date, '%Y-%m-%d')).days
                # 做空：盈亏 = (建仓价 - 平仓价) * 持仓数量
                # 注意：持仓数量已经包含了杠杆，所以不需要再乘以LEVERAGE
                profit_loss = (entry_price - exit_price) * current_position['position_size']
                profit_loss_pct = (entry_price - exit_price) / entry_price
                
                add_position_count = current_position.get('add_position_count', 0)
                
                trade_record = {
                    'entry_date': entry_date,
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': _leverage,
                    'exit_date': last_date_str,
                    'exit_price': exit_price,
                    'exit_reason': '回测结束强制平仓',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'max_profit': current_position.get('max_profit', 0),
                    'max_loss': current_position.get('max_loss', 0),
                    'hold_days': hold_days,
                    'add_position_count': add_position_count  # 记录补仓次数
                }
                
                trade_records.append(trade_record)
                # 强制平仓时：释放保证金 + 盈亏
                position_value = current_position.get('position_value', 0)
                capital += position_value + profit_loss
                
                position_info = ""
                if add_position_count > 0:
                    position_info = f" | 已补仓{add_position_count}次"
                
                logging.info(
                    f"{last_date_str}: 强制平仓（买入） {symbol} | "
                    f"建仓价（卖空）: {entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓天数: {hold_days}{position_info}"
                )
            else:
                logging.warning(f"{last_date_str}: {symbol} 无K线数据，无法强制平仓")
    
    # 保存交易记录到数据库和CSV文件
    if trade_records:
        df_trades = pd.DataFrame(trade_records)
        
        # 保存到数据库
        df_trades.to_sql(
            name='backtrade_records',
            con=engine,
            if_exists='append',
            index=False
        )
        logging.info(f"成功保存 {len(trade_records)} 条交易记录到数据库")
        
        # 保存到CSV文件
        csv_filename = f"backtrade_records_{start_date}_{end_date}.csv"
        df_trades.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        logging.info(f"成功保存 {len(trade_records)} 条交易记录到CSV文件: {csv_filename}")
        
        # 打印统计信息
        win_trades = len(df_trades[df_trades['profit_loss'] > 0])
        loss_trades = len(df_trades[df_trades['profit_loss'] < 0])
        win_rate = win_trades / len(df_trades) * 100 if len(df_trades) > 0 else 0
        total_profit_loss = capital - _initial_capital  # 总盈亏 = 最终资金 - 初始资金
        
        logging.info("=" * 60)
        logging.info("回测统计:")
        logging.info(f"初始资金: {_initial_capital:.2f} USDT")
        logging.info(f"最终资金: {capital:.2f} USDT")
        logging.info(f"总盈亏: {total_profit_loss:.2f} USDT")
        logging.info(f"总收益率: {(capital - _initial_capital) / _initial_capital * 100:.2f}%")
        logging.info(f"交易次数: {len(trade_records)}")
        logging.info(f"盈利次数: {win_trades}")
        logging.info(f"亏损次数: {loss_trades}")
        logging.info(f"胜率: {win_rate:.2f}%")
        logging.info("=" * 60)
        
        # 返回统计信息
        return {
            'initial_capital': _initial_capital,
            'final_capital': capital,
            'total_profit_loss': total_profit_loss,
            'total_return_rate': (capital - _initial_capital) / _initial_capital * 100,
            'total_trades': len(trade_records),
            'win_trades': win_trades,
            'loss_trades': loss_trades,
            'win_rate': win_rate,
            'csv_filename': csv_filename
        }
    else:
        logging.warning("没有交易记录需要保存")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='币安U本位合约回测脚本')
    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='开始日期，格式: YYYY-MM-DD'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='结束日期，格式: YYYY-MM-DD'
    )
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        logging.error("日期格式错误，请使用 YYYY-MM-DD 格式")
        exit(1)
    
    simulate_trading(args.start_date, args.end_date)
