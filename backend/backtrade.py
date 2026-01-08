"""
根据U本位合约K线数据模拟交易脚本

功能：
1. 从本地SQLite数据库（crypto_data.db）读取所有USDT交易对的K线数据
2. 计算每天的涨幅（pct_chg），找出涨幅第一的交易对
3. 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
4. 建仓策略：
   - 初始资金：可配置（默认10000 USDT）
   - 每次建仓金额：账户余额的百分比（可配置，默认3%）
   - 杠杆：可配置（默认3倍）
   - 建仓条件：涨幅>=阈值（可配置，默认20%） 且 该交易对未持仓
   - 建仓方向：卖空（做空）
   - 建仓价格：
     * 立即入场模式（默认）：第二天开盘价建仓
     * 延迟入场模式（可选）：等待约12小时，监控1小时K线数据，当涨势减弱时建仓
       - 涨势减弱判断条件：
         a) 连续3小时涨幅递减且最后1小时下跌
         b) 从最高点回落超过2%
         c) 最近3小时平均涨幅小于1%
       - 如果超过延迟时间仍未建仓，则使用当前价格强制建仓
       - 注意：延迟入场模式需要1小时K线数据支持
5. 平仓策略：
   - 止盈：价格下跌达到阈值时盈利平仓（买入平仓，可配置，默认20%）
   - 止损：价格上涨达到阈值时止损平仓（买入平仓，可配置，默认49%）
   - 补仓：第一次触发止损时，进行补仓（补仓数量=持仓数量），补仓后重新计算平均建仓价和止盈止损价格
   - 如果已补仓过，再次触发止损则直接平仓
6. 持仓管理：
   - 支持同时持有多个仓位
   - 已开仓的交易对在未平仓期间，不重复建仓同一交易对
   - 每天检查所有持仓的平仓条件
7. 数据保存：
   - 交易记录保存到SQLite数据库（backtrade_records表）
   - 交易记录保存到CSV文件（backtrade_records_{start_date}_{end_date}.csv）

使用方法：
1. 命令行运行：
   python backtrade.py --start-date 2021-12-01 --end-date 2026-01-03
   
   可选参数：
   --initial-capital: 初始资金（USDT）
   --leverage: 杠杆倍数
   --profit-threshold: 止盈阈值（小数，如0.04表示4%）
   --loss-threshold: 止损阈值（小数，如0.019表示1.9%）
   --position-size-ratio: 每次建仓金额占账户余额的比例（小数，如0.06表示6%）
   --min-pct-chg: 最小涨幅百分比（小数，如0.1表示10%）
   --delay-entry: 启用延迟入场策略（需要1小时K线数据）
   --delay-hours: 延迟入场的小时数（默认12小时）

2. API调用（通过FastAPI服务器）：
   POST /api/backtest
   {
     "start_date": "2021-12-01",
     "end_date": "2026-01-03",
     "delay_entry": true,
     "delay_hours": 12,
     ...
   }

3. 前端界面：
   在回测页面勾选"启用延迟入场策略"，设置延迟小时数，然后运行回测

注意：
- 本策略是做空策略，建仓方向是卖空，平仓方向是买入平仓
- 延迟入场策略需要先下载1小时K线数据：python download_klines.py --interval 1h --start-time 2021-01-01 --end-time 2026-01-01
"""

import os
import logging
import re

import pandas as pd  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from db import engine, create_table
from data import get_local_symbols, get_local_kline_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 交易参数
INITIAL_CAPITAL = 10000  # 初始资金10000美金
LEVERAGE = 5 # 三倍杠杆
PROFIT_THRESHOLD = 0.20   # 止盈25%（建仓价格盈利25%）
LOSS_THRESHOLD = 0.19  # 止损49%平仓
POSITION_SIZE_RATIO = 0.05 # 每次建仓金额为账户余额的9%
MIN_PCT_CHG = 0.1  # 最小涨幅15%才建仓


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
    
    # 按日期分组，使用nlargest找出每天涨幅最大的交易对
    top_gainers = (
        combined_df.groupby('trade_date_str', group_keys=False)
        .apply(lambda x: x.nlargest(1, 'pct_chg'))
        .reset_index(drop=True)
    )
    
    # 重命名列
    top_gainers = top_gainers.rename(columns={'trade_date_str': 'date'})
    
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


def get_hourly_kline_data_for_date(symbol: str, date: str, hours: int = 12) -> Optional[pd.DataFrame]:
    """
    获取指定交易对在指定日期开始的前N个小时的1小时K线数据
    
    Args:
        symbol: 交易对符号
        date: 日期字符串 'YYYY-MM-DD'
        hours: 需要获取的小时数，默认12小时
    
    Returns:
        DataFrame包含该时间段的1小时K线数据，或None
    """
    try:
        df = get_local_kline_data(symbol, interval="1h")
        if df.empty:
            return None
        
        # 处理trade_date格式
        if df['trade_date'].dtype == 'object':
            df['trade_date_dt'] = pd.to_datetime(df['trade_date'])
        else:
            df['trade_date_dt'] = pd.to_datetime(df['trade_date'])
        
        # 筛选指定日期开始的前N个小时
        start_datetime = datetime.strptime(date, '%Y-%m-%d')
        end_datetime = start_datetime + timedelta(hours=hours)
        
        mask = (df['trade_date_dt'] >= start_datetime) & (df['trade_date_dt'] < end_datetime)
        filtered_df = df[mask].copy()
        
        if filtered_df.empty:
            return None
        
        # 按时间排序
        filtered_df = filtered_df.sort_values('trade_date_dt').reset_index(drop=True)
        
        return filtered_df
    except Exception as e:
        logging.debug(f"获取 {symbol} 在 {date} 的1小时K线数据失败: {e}")
        return None


def get_daily_hourly_kline_data(symbol: str, date: str) -> Optional[pd.DataFrame]:
    """
    获取指定交易对在指定日期当天的所有1小时K线数据（24小时）
    
    Args:
        symbol: 交易对符号
        date: 日期字符串 'YYYY-MM-DD'
    
    Returns:
        DataFrame包含该日期当天的所有1小时K线数据，或None
    """
    try:
        df = get_local_kline_data(symbol, interval="1h")
        if df.empty:
            return None
        
        # 处理trade_date格式
        # 小时线数据的 trade_date 格式是 'YYYY-MM-DD HH:MM:SS'，需要转换为 datetime
        # 首先检查 trade_date 的实际格式
        if df['trade_date'].dtype == 'object':
            # 字符串格式，尝试多种格式解析
            # 先尝试完整格式 'YYYY-MM-DD HH:MM:SS'
            df['trade_date_dt'] = pd.to_datetime(df['trade_date'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
            # 如果解析失败（NaT），尝试其他格式
            if df['trade_date_dt'].isna().any():
                # 尝试不带格式的自动解析
                df.loc[df['trade_date_dt'].isna(), 'trade_date_dt'] = pd.to_datetime(
                    df.loc[df['trade_date_dt'].isna(), 'trade_date'], 
                    errors='coerce'
                )
        else:
            # 如果已经是 datetime 类型，直接使用
            df['trade_date_dt'] = pd.to_datetime(df['trade_date'])
        
        # 筛选指定日期当天的所有小时数据
        start_datetime = datetime.strptime(date, '%Y-%m-%d')
        end_datetime = start_datetime + timedelta(days=1)
        
        mask = (df['trade_date_dt'] >= start_datetime) & (df['trade_date_dt'] < end_datetime)
        filtered_df = df[mask].copy()
        
        if filtered_df.empty:
            return None
        
        # 确保 trade_date_dt 是 datetime 类型，并且保留原始的 trade_date 字符串
        if filtered_df['trade_date_dt'].dtype != 'datetime64[ns]':
            filtered_df['trade_date_dt'] = pd.to_datetime(filtered_df['trade_date_dt'], errors='coerce')
        
        # 确保 trade_date 列保留原始字符串格式（用于后续提取小时信息）
        # 重要：保留原始的 trade_date 字符串，不要覆盖
        # 如果 trade_date 不是字符串类型，从 trade_date_dt 转换回字符串（保留小时信息）
        if filtered_df['trade_date'].dtype != 'object':
            # 如果 trade_date 不是字符串，从 trade_date_dt 转换回字符串
            filtered_df['trade_date'] = filtered_df['trade_date_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # 如果已经是字符串类型，确保格式正确（包含小时信息）
            # 检查是否有小时信息（长度应该 >= 13）
            mask_short = filtered_df['trade_date'].str.len() < 13
            if mask_short.any():
                # 如果有短字符串，从 trade_date_dt 转换
                filtered_df.loc[mask_short, 'trade_date'] = filtered_df.loc[mask_short, 'trade_date_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 按时间排序
        filtered_df = filtered_df.sort_values('trade_date_dt').reset_index(drop=True)
        
        return filtered_df
    except Exception as e:
        logging.debug(f"获取 {symbol} 在 {date} 的当天1小时K线数据失败: {e}")
        return None


def check_momentum_weakening(hourly_df: pd.DataFrame, min_hours: int = 3) -> Tuple[bool, Optional[float]]:
    """
    检查涨势是否减弱
    
    策略：
    1. 计算每小时的涨幅
    2. 如果连续N个小时涨幅递减，或者价格开始回落，则认为涨势减弱
    3. 返回是否可以建仓，以及建议的建仓价格
    
    Args:
        hourly_df: 1小时K线数据DataFrame
        min_hours: 至少需要多少个小时的数据才能判断，默认3小时
    
    Returns:
        Tuple[bool, Optional[float]]: (是否可以建仓, 建议建仓价格)
    """
    if hourly_df.empty or len(hourly_df) < min_hours:
        return False, None
    
    # 计算每小时的涨幅（相对于前一个小时的收盘价）
    hourly_df = hourly_df.copy()
    hourly_df['hourly_pct_chg'] = hourly_df['close'].pct_change() * 100
    
    # 获取最近N个小时的数据
    recent_hours = hourly_df.tail(min_hours)
    
    # 策略1：如果连续3个小时涨幅递减（涨幅越来越小），认为涨势减弱
    pct_changes = recent_hours['hourly_pct_chg'].values
    if len(pct_changes) >= 3:
        # 检查是否递减（涨幅越来越小）
        is_decreasing = all(pct_changes[i] >= pct_changes[i+1] for i in range(len(pct_changes)-1))
        if is_decreasing and pct_changes[-1] < 0:  # 最后一个小时已经下跌
            # 使用当前价格作为建仓价
            entry_price = recent_hours.iloc[-1]['close']
            return True, entry_price
    
    # 策略2：如果价格从最高点回落超过2%，认为涨势减弱
    if len(hourly_df) >= 2:
        max_price = hourly_df['high'].max()
        current_price = hourly_df.iloc[-1]['close']
        if max_price > 0:
            decline_pct = (max_price - current_price) / max_price * 100
            if decline_pct >= 2.0:  # 从最高点回落超过2%
                entry_price = current_price
                return True, entry_price
    
    # 策略3：如果已经过了12小时，且最近3小时的平均涨幅小于1%，认为涨势减弱
    if len(recent_hours) >= 3:
        avg_pct_chg = recent_hours['hourly_pct_chg'].mean()
        if avg_pct_chg < 1.0:  # 平均涨幅小于1%
            entry_price = recent_hours.iloc[-1]['close']
            return True, entry_price
    
    return False, None


def create_trade_table():
    """创建交易记录表"""
    table_name = 'backtrade_records'
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        )
        table_exists = result.fetchone() is not None
        
        if not table_exists:
            text_create = f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_pct_chg REAL,
                position_size REAL NOT NULL,
                leverage INTEGER NOT NULL,
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                profit_loss REAL,
                profit_loss_pct REAL,
                max_profit REAL,
                max_loss REAL,
                hold_days INTEGER,
                        add_position_count INTEGER DEFAULT 0,
                        delay_entry INTEGER DEFAULT 0,
                        entry_reason TEXT DEFAULT 'immediate',
                        delay_hours INTEGER,
                        exit_hour TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                    """
            conn.execute(text(text_create))
            conn.commit()
            logging.info(f"交易记录表 '{table_name}' 创建成功")
        else:
            # 检查并添加缺失的字段
            result = conn.execute(
                text(f"PRAGMA table_info({table_name});")
            )
            columns = [row[1] for row in result.fetchall()]
            
            # 添加 add_position_count 字段
            if 'add_position_count' not in columns:
                logging.info(f"添加 add_position_count 字段到表 '{table_name}'")
                # 如果存在旧的has_added_position字段，先删除
                if 'has_added_position' in columns:
                    logging.info(f"删除旧的 has_added_position 字段")
                    # SQLite不支持直接删除列，需要重建表
                    # 先检查是否存在临时表
                    temp_table_name = f"{table_name}_old"
                    result_temp = conn.execute(
                        text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{temp_table_name}';")
                    )
                    temp_exists = result_temp.fetchone() is not None
                    if temp_exists:
                        conn.execute(text(f"DROP TABLE {temp_table_name};"))
                    
                    # 定义新的表结构
                    text_create_new = f"""
                    CREATE TABLE {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        entry_date TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        entry_pct_chg REAL,
                        position_size REAL NOT NULL,
                        leverage INTEGER NOT NULL,
                        exit_date TEXT,
                        exit_price REAL,
                        exit_reason TEXT,
                        profit_loss REAL,
                        profit_loss_pct REAL,
                        max_profit REAL,
                        max_loss REAL,
                        hold_days INTEGER,
                        add_position_count INTEGER DEFAULT 0,
                        delay_entry INTEGER DEFAULT 0,
                        entry_reason TEXT,
                        delay_hours INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                    
                    conn.execute(text(f"ALTER TABLE {table_name} RENAME TO {temp_table_name};"))
                    conn.execute(text(text_create_new))
                    conn.execute(text(f"""
                        INSERT INTO {table_name} 
                        (entry_date, symbol, entry_price, entry_pct_chg, position_size, leverage, 
                         exit_date, exit_price, exit_reason, profit_loss, profit_loss_pct, 
                         max_profit, max_loss, hold_days, add_position_count, delay_entry, entry_reason, delay_hours, created_at)
                        SELECT 
                        entry_date, symbol, entry_price, entry_pct_chg, position_size, leverage,
                        exit_date, exit_price, exit_reason, profit_loss, profit_loss_pct,
                        max_profit, max_loss, hold_days, 
                        CASE WHEN has_added_position = 1 THEN 1 ELSE 0 END,
                        0, 'immediate', NULL,
                        created_at
                        FROM {temp_table_name};
                    """))
                    conn.execute(text(f"DROP TABLE {temp_table_name};"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN add_position_count INTEGER DEFAULT 0;")
                    )
                conn.commit()
            
            # 添加延迟入场相关字段
            if 'delay_entry' not in columns:
                logging.info(f"添加 delay_entry 字段到表 '{table_name}'")
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN delay_entry INTEGER DEFAULT 0;")
                )
                conn.commit()
            
            if 'entry_reason' not in columns:
                logging.info(f"添加 entry_reason 字段到表 '{table_name}'")
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN entry_reason TEXT DEFAULT 'immediate';")
                )
                conn.commit()
            
            if 'delay_hours' not in columns:
                logging.info(f"添加 delay_hours 字段到表 '{table_name}'")
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN delay_hours INTEGER;")
                )
                conn.commit()
            
            if 'exit_hour' not in columns:
                logging.info(f"添加 exit_hour 字段到表 '{table_name}'")
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN exit_hour TEXT;")
                )
                conn.commit()
            
            logging.info(f"交易记录表 '{table_name}' 已存在")
        
        return table_exists


def simulate_trading(
    start_date: str,
    end_date: str,
    initial_capital: Optional[float] = None,
    leverage: Optional[float] = None,
    profit_threshold: Optional[float] = None,
    loss_threshold: Optional[float] = None,
    position_size_ratio: Optional[float] = None,
    min_pct_chg: Optional[float] = None,
    delay_entry: bool = False,
    delay_hours: int = 12
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
        delay_entry: 是否启用延迟入场策略，默认False（立即入场）
        delay_hours: 延迟入场的小时数，默认12小时（仅在delay_entry=True时生效）
    
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
    if delay_entry:
        logging.info(f"延迟入场策略: 启用，延迟{delay_hours}小时，等待涨势减弱后建仓")
    
    # 当前持仓
    current_positions = []  # 支持多个仓位同时存在
    pending_positions = []  # 待建仓列表：{symbol, pct_chg, target_date, created_date}
    capital = _initial_capital
    trade_records = []
    
    # 延迟入场统计
    delay_entry_stats = {
        'total_pending': 0,  # 总待建仓数量
        'successful_entries': 0,  # 成功建仓数量（涨势减弱时建仓）
        'forced_entries': 0,  # 强制建仓数量（超时强制建仓）
        'failed_entries': 0,  # 失败建仓数量（超过延迟时间仍未建仓）
        'entry_reasons': {
            'momentum_weakening': 0,  # 涨势减弱建仓
            'timeout': 0  # 超时强制建仓
        }
    }
    
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    while current_date <= end_dt:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 检查所有持仓是否需要平仓（使用小时线数据）
        positions_to_close = []
        for i, current_position in enumerate(current_positions):
            symbol = current_position['symbol']
            entry_price = current_position['entry_price']
            entry_date = current_position['entry_date']
            
            # 获取当天的小时线数据（用于止盈止损判断）
            hourly_df = get_daily_hourly_kline_data(symbol, date_str)
            
            exit_reason = None
            exit_price = None
            exit_hour = None  # 记录触发的小时
            
            # 如果小时线数据不可用，回退到日线数据
            if hourly_df is None or hourly_df.empty:
                logging.debug(f"{date_str}: {symbol} 无小时线数据，使用日线数据判断")
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
                
                # 检查是否达到平仓条件
                if price_change_low <= -_profit_threshold:
                    # 价格下跌达到止盈阈值，盈利平仓
                    exit_price = entry_price * (1 - _profit_threshold)
                    # 使用日线数据时，exit_hour 设置为当日收盘时间（23:00:00）
                    exit_hour = f"{date_str} 23:00:00"
                    add_position_count = current_position.get('add_position_count', 0)
                    if add_position_count > 0:
                        exit_reason = f"价格下跌{_profit_threshold*100:.1f}%，盈利平仓（已补仓{add_position_count}次，{exit_hour}触发）"
                    else:
                        exit_reason = f"价格下跌{_profit_threshold*100:.1f}%，盈利平仓（{exit_hour}触发）"
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
                            # 使用日线数据时，exit_hour 设置为当日收盘时间（23:00:00）
                            exit_hour = f"{date_str} 23:00:00"
                            exit_reason = f"价格上涨{_loss_threshold*100:.1f}%，止损平仓（资金不足无法补仓，{exit_hour}触发）"
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
                        # 使用日线数据时，exit_hour 设置为当日收盘时间（23:00:00）
                        exit_hour = f"{date_str} 23:00:00"
                        exit_reason = f"价格上涨{_loss_threshold*100:.1f}%，止损平仓（已补仓2次，{exit_hour}触发）"
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
            else:
                # 使用小时线数据逐小时检查止盈止损
                # 按时间顺序遍历当天的小时线数据
                for idx, hour_row in hourly_df.iterrows():
                    # 获取时间信息：优先使用 trade_date 原始字符串，确保小时信息不丢失
                    hour_time = None
                    hour_time_str = None
                    
                    # 优先使用 trade_date 原始字符串（保留完整的时间信息）
                    if 'trade_date' in hour_row and hour_row['trade_date'] is not None:
                        hour_time_str = str(hour_row['trade_date']).strip()
                        # 确保字符串格式正确（应该是 'YYYY-MM-DD HH:MM:SS'）
                        if len(hour_time_str) >= 13:
                            # 尝试解析时间字符串
                            try:
                                hour_time = pd.to_datetime(hour_time_str, format='%Y-%m-%d %H:%M:%S', errors='coerce')
                                # 验证解析后的时间是否包含小时信息
                                if pd.isna(hour_time):
                                    hour_time = None
                            except:
                                try:
                                    hour_time = pd.to_datetime(hour_time_str, errors='coerce')
                                    if pd.isna(hour_time):
                                        hour_time = None
                                except:
                                    hour_time = None
                        else:
                            # 字符串格式不正确，清空
                            hour_time_str = None
                            hour_time = None
                    
                    # 如果从 trade_date 解析失败，尝试使用 trade_date_dt
                    if hour_time is None or pd.isna(hour_time):
                        if 'trade_date_dt' in hour_row and not pd.isna(hour_row.get('trade_date_dt')):
                            hour_time = hour_row['trade_date_dt']
                            if not isinstance(hour_time, (pd.Timestamp, datetime)):
                                hour_time = pd.to_datetime(hour_time)
                            # 从 trade_date_dt 生成字符串（确保包含小时信息）
                            if not hour_time_str or len(hour_time_str) < 13:
                                hour_time_str = hour_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 如果还是无法获取时间，跳过这条记录
                    if hour_time is None or pd.isna(hour_time):
                        logging.warning(f"{date_str}: {symbol} 小时线数据第{idx}条缺少时间信息，跳过")
                        continue
                    
                    # 确保 hour_time 是 Timestamp 或 datetime 对象
                    if not isinstance(hour_time, (pd.Timestamp, datetime)):
                        hour_time = pd.to_datetime(hour_time)
                    
                    # 如果 hour_time_str 为空或格式不正确，从 hour_time 生成（确保包含小时信息）
                    if not hour_time_str or len(hour_time_str) < 13:
                        # 确保 hour_time 有正确的小时信息
                        if isinstance(hour_time, (pd.Timestamp, datetime)):
                            hour_time_str = hour_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            hour_time_str = None
                    
                    # 调试：打印时间信息（仅在触发时打印）
                    # logging.debug(f"{date_str}: {symbol} 第{idx}小时 - hour_time_str: {hour_time_str}, hour_time: {hour_time}")
                    
                    hour_open = hour_row['open']
                    hour_high = hour_row['high']
                    hour_low = hour_row['low']
                    hour_close = hour_row['close']
                    
                    # 计算该小时的涨跌幅（相对于建仓价）
                    price_change_high = (hour_high - entry_price) / entry_price  # 价格上涨幅度
                    price_change_low = (hour_low - entry_price) / entry_price    # 价格下跌幅度
                    
                    # 检查是否触发止盈
                    if price_change_low <= -_profit_threshold:
                        # 触发止盈，使用触发时的价格（止盈价格）
                        exit_price = entry_price * (1 - _profit_threshold)
                        # 格式化时间：优先使用 hour_time_str 提取小时，确保正确
                        exit_hour = None
                        
                        # 方法1：直接从 hour_time_str 字符串中提取小时部分
                        if hour_time_str and len(hour_time_str) >= 13:
                            try:
                                # 格式：'YYYY-MM-DD HH:MM:SS'，提取前13个字符：'YYYY-MM-DD HH'
                                date_hour_part = hour_time_str[:13]
                                # 解析：'2025-12-30 02' -> datetime对象
                                dt = pd.to_datetime(date_hour_part, format='%Y-%m-%d %H', errors='coerce')
                                if not pd.isna(dt):
                                    # 格式化：'2025-12-30 02:00:00'
                                    exit_hour = dt.strftime('%Y-%m-%d %H:00:00')
                            except Exception as e:
                                logging.debug(f"解析时间字符串失败: {hour_time_str}, 错误: {e}")
                        
                        # 方法2：如果方法1失败，从完整字符串解析
                        if not exit_hour and hour_time_str and len(hour_time_str) >= 13:
                            try:
                                dt = pd.to_datetime(hour_time_str, format='%Y-%m-%d %H:%M:%S', errors='coerce')
                                if not pd.isna(dt):
                                    exit_hour = dt.strftime('%Y-%m-%d %H:00:00')
                            except:
                                pass
                        
                        # 方法3：如果前两种方法都失败，使用 hour_time
                        if not exit_hour:
                            exit_hour = hour_time.strftime('%Y-%m-%d %H:00:00')
                        
                        # 调试：如果 exit_hour 是 00:00:00，但 hour_time_str 有小时信息，记录警告
                        if exit_hour and exit_hour.endswith(' 00:00:00') and hour_time_str and len(hour_time_str) >= 13:
                            # 检查 hour_time_str 中的小时部分
                            hour_part = hour_time_str[11:13] if len(hour_time_str) >= 13 else None
                            if hour_part and hour_part != '00':
                                logging.warning(f"{date_str}: {symbol} 时间解析异常 - hour_time_str: {hour_time_str}, hour_part: {hour_part}, exit_hour: {exit_hour}, hour_time: {hour_time}")
                        add_position_count = current_position.get('add_position_count', 0)
                        if add_position_count > 0:
                            exit_reason = f"价格下跌{_profit_threshold*100:.1f}%，盈利平仓（已补仓{add_position_count}次，{exit_hour}触发）"
                        else:
                            exit_reason = f"价格下跌{_profit_threshold*100:.1f}%，盈利平仓（{exit_hour}触发）"
                        break  # 触发后立即退出循环
                    
                    # 检查是否触发止损
                    elif price_change_high >= _loss_threshold:
                        # 触发止损
                        add_position_count = current_position.get('add_position_count', 0)
                        MAX_ADD_POSITION_COUNT = 2  # 最多补仓2次
                        
                        if add_position_count < MAX_ADD_POSITION_COUNT:
                            # 触发止损，进行补仓
                            add_position_price = entry_price * (1 + _loss_threshold)
                            original_position_size = current_position['position_size']
                            add_position_size = original_position_size
                            
                            total_position_size = original_position_size + add_position_size
                            new_avg_entry_price = (entry_price * original_position_size + add_position_price * add_position_size) / total_position_size
                            
                            add_position_value = capital * _position_size_ratio
                            
                            if capital < add_position_value:
                                # 格式化时间用于日志
                                hour_str = hour_time.strftime('%H:00')
                                logging.warning(f"{date_str} {hour_str}: {symbol} 资金不足，无法补仓")
                                exit_price = add_position_price
                                # 格式化时间：优先使用 hour_time_str 提取小时
                                if hour_time_str and len(hour_time_str) >= 13:
                                    try:
                                        date_hour_part = hour_time_str[:13]
                                        dt = pd.to_datetime(date_hour_part, format='%Y-%m-%d %H', errors='coerce')
                                        if not pd.isna(dt):
                                            exit_hour = dt.strftime('%Y-%m-%d %H:00:00')
                                        else:
                                            exit_hour = hour_time.strftime('%Y-%m-%d %H:00:00')
                                    except:
                                        exit_hour = hour_time.strftime('%Y-%m-%d %H:00:00')
                                else:
                                    exit_hour = hour_time.strftime('%Y-%m-%d %H:00:00')
                                exit_reason = f"价格上涨{_loss_threshold*100:.1f}%，止损平仓（资金不足无法补仓，{exit_hour}触发）"
                                break
                            else:
                                # 更新持仓信息
                                current_position['entry_price'] = new_avg_entry_price
                                current_position['position_size'] = total_position_size
                                current_position['position_value'] = current_position.get('position_value', 0) + add_position_value
                                current_position['add_position_count'] = add_position_count + 1
                                
                                capital -= add_position_value
                                
                                # 格式化时间用于日志（补仓时不设置 exit_hour，因为继续持有）
                                hour_str = hour_time.strftime('%H:00')
                                logging.info(
                                    f"{date_str} {hour_str}: 第{add_position_count + 1}次补仓 {symbol} | "
                                    f"原建仓价: {entry_price:.8f} | "
                                    f"补仓价: {add_position_price:.8f} | "
                                    f"新平均价: {new_avg_entry_price:.8f} | "
                                    f"补仓金额: {add_position_value:.2f} USDT"
                                )
                                # 补仓后继续持有，跳出小时循环，继续检查下一个仓位
                                # 注意：补仓时不设置 exit_hour，因为继续持有
                                break
                        else:
                            # 已经补仓2次，再次触发止损，直接止损平仓
                            exit_price = entry_price * (1 + _loss_threshold)
                            # 格式化时间：优先使用 hour_time_str 提取小时
                            exit_hour = None
                            if hour_time_str and len(hour_time_str) >= 13:
                                try:
                                    date_hour_part = hour_time_str[:13]
                                    dt = pd.to_datetime(date_hour_part, format='%Y-%m-%d %H', errors='coerce')
                                    if not pd.isna(dt):
                                        exit_hour = dt.strftime('%Y-%m-%d %H:00:00')
                                except:
                                    pass
                            if not exit_hour:
                                if hour_time_str and len(hour_time_str) >= 13:
                                    try:
                                        dt = pd.to_datetime(hour_time_str, format='%Y-%m-%d %H:%M:%S', errors='coerce')
                                        if not pd.isna(dt):
                                            exit_hour = dt.strftime('%Y-%m-%d %H:00:00')
                                    except:
                                        pass
                            if not exit_hour:
                                exit_hour = hour_time.strftime('%Y-%m-%d %H:00:00')
                            exit_reason = f"价格上涨{_loss_threshold*100:.1f}%，止损平仓（已补仓2次，{exit_hour}触发）"
                            break  # 触发后立即退出循环
                
                # 如果没有触发止盈止损，更新最大盈利和最大亏损
                if exit_price is None:
                    # 计算当天的最高价和最低价
                    day_high = hourly_df['high'].max()
                    day_low = hourly_df['low'].min()
                    price_change_high = (day_high - entry_price) / entry_price
                    price_change_low = (day_low - entry_price) / entry_price
                    
                    current_position['max_profit'] = max(
                        current_position.get('max_profit', 0),
                        -price_change_low  # 价格下跌幅度转为盈利
                    )
                    current_position['max_loss'] = max(
                        current_position.get('max_loss', 0),
                        price_change_high  # 价格上涨幅度为亏损
                    )
                    continue  # 继续持有，检查下一个仓位
            
            # 平仓处理（统一处理日线和小时线触发的平仓）
            if exit_price:
                hold_days = (current_date - datetime.strptime(entry_date, '%Y-%m-%d')).days
                # 做空：盈亏 = (建仓价 - 平仓价) * 持仓数量
                # 注意：持仓数量已经包含了杠杆，所以不需要再乘以LEVERAGE
                profit_loss = (entry_price - exit_price) * current_position['position_size']
                profit_loss_pct = (entry_price - exit_price) / entry_price
                
                # 记录补仓次数
                add_position_count = current_position.get('add_position_count', 0)
                
                # 记录延迟入场信息
                is_delay_entry = current_position.get('delay_entry', False)
                entry_reason = current_position.get('entry_reason', 'immediate' if not delay_entry else 'unknown')
                delay_hours_used = delay_hours if is_delay_entry else None
                
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
                    'add_position_count': add_position_count,  # 记录补仓次数
                    'delay_entry': is_delay_entry,  # 是否延迟入场
                    'entry_reason': entry_reason,  # 建仓原因：immediate/momentum_weakening/timeout
                    'delay_hours': delay_hours_used,  # 延迟小时数（如果延迟入场）
                    'exit_hour': exit_hour  # 触发平仓的小时（如果使用小时线数据）
                }
                
                trade_records.append(trade_record)
                # 平仓时：释放保证金 + 盈亏
                position_value = current_position.get('position_value', 0)
                capital += position_value + profit_loss
                
                # 记录补仓信息
                position_info = ""
                if add_position_count > 0:
                    position_info = f" | 已补仓{add_position_count}次"
                
                # 记录触发时间信息
                time_info = ""
                if exit_hour:
                    time_info = f" | 触发时间: {exit_hour}"
                
                logging.info(
                    f"{date_str}: 平仓（买入） {symbol} | "
                    f"建仓价（卖空）: {entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓天数: {hold_days} | "
                    f"原因: {exit_reason}{position_info}{time_info} | "
                    f"当前资金: {capital:.2f} USDT"
                )
                
                positions_to_close.append(i)  # 标记需要平仓的仓位索引
        
        # 从后往前删除已平仓的仓位（避免索引错乱）
        for i in reversed(positions_to_close):
            current_positions.pop(i)
        
        # 处理延迟入场的待建仓列表
        if delay_entry and pending_positions:
            pending_to_remove = []
            for i, pending in enumerate(pending_positions):
                symbol = pending['symbol']
                target_date = pending['target_date']
                created_date = pending['created_date']
                pct_chg = pending['pct_chg']
                
                # 如果到了目标日期，开始监控
                if date_str == target_date:
                    # 获取1小时K线数据
                    hourly_df = get_hourly_kline_data_for_date(symbol, date_str, hours=delay_hours)
                    
                    if hourly_df is not None and len(hourly_df) >= 3:
                        # 检查涨势是否减弱
                        can_entry, entry_price = check_momentum_weakening(hourly_df, min_hours=3)
                        
                        if can_entry and entry_price:
                            # 涨势减弱，可以建仓
                            position_size = (capital * _position_size_ratio * _leverage) / entry_price
                            position_value = capital * _position_size_ratio
                            
                            if capital >= position_value:
                                capital -= position_value
                                
                                new_position = {
                                    'symbol': symbol,
                                    'entry_price': entry_price,
                                    'entry_date': date_str,
                                    'position_size': position_size,
                                    'entry_pct_chg': pct_chg,
                                    'position_value': position_value,
                                    'max_profit': 0,
                                    'max_loss': 0,
                                    'add_position_count': 0,
                                    'delay_entry': True,  # 标记为延迟入场
                                    'entry_reason': 'momentum_weakening'  # 建仓原因
                                }
                                current_positions.append(new_position)
                                
                                delay_entry_stats['successful_entries'] += 1
                                delay_entry_stats['entry_reasons']['momentum_weakening'] += 1
                                
                                logging.info(
                                    f"{date_str}: 延迟入场建仓（卖空） {symbol} | "
                                    f"建仓价: {entry_price:.8f} | "
                                    f"原因: 涨势减弱 | "
                                    f"持仓数量: {position_size:.4f} | "
                                    f"建仓金额: {position_value:.2f} USDT | "
                                    f"昨日涨幅: {pct_chg:.2f}% | "
                                    f"延迟时间: {delay_hours}小时"
                                )
                                
                                pending_to_remove.append(i)
                            else:
                                logging.warning(f"{date_str}: {symbol} 资金不足，无法延迟入场建仓")
                                delay_entry_stats['failed_entries'] += 1
                                pending_to_remove.append(i)
                        else:
                            # 检查是否超过延迟时间
                            created_dt = datetime.strptime(created_date, '%Y-%m-%d')
                            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                            hours_passed = (current_date - created_dt).days * 24
                            
                            if hours_passed >= delay_hours:
                                # 超时，强制建仓（使用当前价格）
                                kline_data = get_kline_data_for_date(symbol, date_str)
                                if kline_data is not None:
                                    entry_price = kline_data['close']  # 使用收盘价
                                    position_size = (capital * _position_size_ratio * _leverage) / entry_price
                                    position_value = capital * _position_size_ratio
                                    
                                    if capital >= position_value:
                                        capital -= position_value
                                        
                                        new_position = {
                                            'symbol': symbol,
                                            'entry_price': entry_price,
                                            'entry_date': date_str,
                                            'position_size': position_size,
                                            'entry_pct_chg': pct_chg,
                                            'position_value': position_value,
                                            'max_profit': 0,
                                            'max_loss': 0,
                                            'add_position_count': 0,
                                            'delay_entry': True,
                                            'entry_reason': 'timeout'  # 超时强制建仓
                                        }
                                        current_positions.append(new_position)
                                        
                                        delay_entry_stats['forced_entries'] += 1
                                        delay_entry_stats['entry_reasons']['timeout'] += 1
                                        
                                        logging.info(
                                            f"{date_str}: 延迟入场超时强制建仓（卖空） {symbol} | "
                                            f"建仓价: {entry_price:.8f} | "
                                            f"原因: 超过延迟时间{delay_hours}小时 | "
                                            f"持仓数量: {position_size:.4f} | "
                                            f"建仓金额: {position_value:.2f} USDT"
                                        )
                                        
                                        pending_to_remove.append(i)
                                    else:
                                        logging.warning(f"{date_str}: {symbol} 资金不足，无法强制建仓")
                                        delay_entry_stats['failed_entries'] += 1
                                        pending_to_remove.append(i)
                                else:
                                    logging.warning(f"{date_str}: {symbol} 无K线数据，无法强制建仓")
                                    delay_entry_stats['failed_entries'] += 1
                                    pending_to_remove.append(i)
                    else:
                        # 数据不足，检查是否超时
                        created_dt = datetime.strptime(created_date, '%Y-%m-%d')
                        hours_passed = (current_date - created_dt).days * 24
                        
                        if hours_passed >= delay_hours:
                            # 超时，强制建仓
                            kline_data = get_kline_data_for_date(symbol, date_str)
                            if kline_data is not None:
                                entry_price = kline_data['close']
                                position_size = (capital * _position_size_ratio * _leverage) / entry_price
                                position_value = capital * _position_size_ratio
                                
                                if capital >= position_value:
                                    capital -= position_value
                                    
                                    new_position = {
                                        'symbol': symbol,
                                        'entry_price': entry_price,
                                        'entry_date': date_str,
                                        'position_size': position_size,
                                        'entry_pct_chg': pct_chg,
                                        'position_value': position_value,
                                        'max_profit': 0,
                                        'max_loss': 0,
                                        'add_position_count': 0,
                                        'delay_entry': True,
                                        'entry_reason': 'timeout'
                                    }
                                    current_positions.append(new_position)
                                    
                                    delay_entry_stats['forced_entries'] += 1
                                    delay_entry_stats['entry_reasons']['timeout'] += 1
                                    
                                    logging.info(
                                        f"{date_str}: 延迟入场超时强制建仓（数据不足） {symbol} | "
                                        f"建仓价: {entry_price:.8f}"
                                    )
                                    
                                    pending_to_remove.append(i)
                                else:
                                    delay_entry_stats['failed_entries'] += 1
                                    pending_to_remove.append(i)
                            else:
                                delay_entry_stats['failed_entries'] += 1
                                pending_to_remove.append(i)
            
            # 从后往前删除已处理的待建仓（避免索引错乱）
            for i in reversed(pending_to_remove):
                pending_positions.pop(i)
                delay_entry_stats['total_pending'] += 1
        
        # 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
        today_top = top_gainers_df[top_gainers_df['date'] == date_str]
        if not today_top.empty:
            symbol = today_top.iloc[0]['symbol']
            pct_chg = today_top.iloc[0]['pct_chg']
            
            # 检查该交易对是否已经在持仓中且未止盈
            already_holding = any(pos['symbol'] == symbol for pos in current_positions)
            already_pending = any(p['symbol'] == symbol for p in pending_positions)
            
            # 只有当涨幅>=阈值且该交易对未持仓时才建仓
            if pct_chg >= _min_pct_chg * 100 and not already_holding and not already_pending:
                if delay_entry:
                    # 延迟入场策略：加入待建仓列表
                    next_date = current_date + timedelta(days=1)
                    next_date_str = next_date.strftime('%Y-%m-%d')
                    
                    if next_date <= end_dt:
                        pending_positions.append({
                            'symbol': symbol,
                            'pct_chg': pct_chg,
                            'target_date': next_date_str,
                            'created_date': date_str
                        })
                        logging.info(
                            f"{date_str}: 发现涨幅第一 {symbol} (涨幅{pct_chg:.2f}%)，加入待建仓列表，将在{next_date_str}开始监控（延迟{delay_hours}小时）"
                        )
                        delay_entry_stats['total_pending'] += 1
                else:
                    # 立即建仓策略（原有逻辑）
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
                                'add_position_count': 0,  # 记录补仓次数
                                'delay_entry': False,  # 立即入场
                                'entry_reason': 'immediate'  # 立即建仓
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
                
                # 记录延迟入场信息
                is_delay_entry = current_position.get('delay_entry', False)
                entry_reason = current_position.get('entry_reason', 'immediate' if not delay_entry else 'unknown')
                delay_hours_used = delay_hours if is_delay_entry else None
                
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
                    'add_position_count': add_position_count,  # 记录补仓次数
                    'delay_entry': is_delay_entry,  # 是否延迟入场
                    'entry_reason': entry_reason,  # 建仓原因：immediate/momentum_weakening/timeout
                    'delay_hours': delay_hours_used,  # 延迟小时数（如果延迟入场）
                    'exit_hour': None  # 强制平仓，无触发小时
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
        
        # 延迟入场统计（如果启用了延迟入场）
        if delay_entry:
            logging.info("-" * 60)
            logging.info("延迟入场统计:")
            logging.info(f"总待建仓数量: {delay_entry_stats['total_pending']}")
            logging.info(f"成功建仓（涨势减弱）: {delay_entry_stats['successful_entries']}")
            logging.info(f"强制建仓（超时）: {delay_entry_stats['forced_entries']}")
            logging.info(f"失败建仓: {delay_entry_stats['failed_entries']}")
            if delay_entry_stats['total_pending'] > 0:
                success_rate = (delay_entry_stats['successful_entries'] / delay_entry_stats['total_pending']) * 100
                logging.info(f"延迟入场成功率: {success_rate:.2f}%")
        
        logging.info("=" * 60)
        
        # 返回统计信息
        result = {
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
        
        # 添加延迟入场统计（如果启用了延迟入场）
        if delay_entry:
            result['delay_entry'] = {
                'enabled': True,
                'delay_hours': delay_hours,
                'total_pending': delay_entry_stats['total_pending'],
                'successful_entries': delay_entry_stats['successful_entries'],
                'forced_entries': delay_entry_stats['forced_entries'],
                'failed_entries': delay_entry_stats['failed_entries'],
                'entry_reasons': delay_entry_stats['entry_reasons'],
                'success_rate': (delay_entry_stats['successful_entries'] / delay_entry_stats['total_pending'] * 100) if delay_entry_stats['total_pending'] > 0 else 0
            }
        else:
            result['delay_entry'] = {
                'enabled': False
            }
        
        return result
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
    parser.add_argument(
        '--initial-capital',
        type=float,
        default=None,
        help='初始资金（USDT）'
    )
    parser.add_argument(
        '--leverage',
        type=float,
        default=None,
        help='杠杆倍数'
    )
    parser.add_argument(
        '--profit-threshold',
        type=float,
        default=None,
        help='止盈阈值（小数，如0.04表示4%）'
    )
    parser.add_argument(
        '--loss-threshold',
        type=float,
        default=None,
        help='止损阈值（小数，如0.019表示1.9%）'
    )
    parser.add_argument(
        '--position-size-ratio',
        type=float,
        default=None,
        help='每次建仓金额占账户余额的比例（小数，如0.06表示6%）'
    )
    parser.add_argument(
        '--min-pct-chg',
        type=float,
        default=None,
        help='最小涨幅百分比（小数，如0.1表示10%）'
    )
    parser.add_argument(
        '--delay-entry',
        action='store_true',
        help='启用延迟入场策略（需要1小时K线数据）'
    )
    parser.add_argument(
        '--delay-hours',
        type=int,
        default=12,
        help='延迟入场的小时数（默认12小时，仅在--delay-entry时生效）'
    )
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        logging.error("日期格式错误，请使用 YYYY-MM-DD 格式")
        exit(1)
    
    # 验证延迟入场参数
    if args.delay_entry and (args.delay_hours <= 0 or args.delay_hours > 24):
        logging.error("延迟小时数必须在1-24之间")
        exit(1)
    
    simulate_trading(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        leverage=args.leverage,
        profit_threshold=args.profit_threshold,
        loss_threshold=args.loss_threshold,
        position_size_ratio=args.position_size_ratio,
        min_pct_chg=args.min_pct_chg,
        delay_entry=args.delay_entry,
        delay_hours=args.delay_hours
    )
