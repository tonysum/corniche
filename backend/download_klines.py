"""
币安U本位合约K线数据下载脚本

功能：
1. 获取所有USDT交易对
2. 下载每个交易对的K线数据
3. 保存到本地SQLite数据库，表名格式：K{interval}{symbol}（例如：K1dBTCUSDT, K1hETHUSDT）
4. 支持增量更新(避免重复下载)
   - 日线及以上：按日期去重，不更新最后一天
   - 小时线及以下：按时间点去重，不更新最后一条
5. 智能跳过：下载前检查本地数据最后时间，如果 >= end_time则跳过该交易对（除非使用--update）
6. 支持指定开始和结束时间，确保不同时间间隔的数据时间范围一致
7. 默认不下载当天数据（因为当天数据不完整）
8. 自动分段下载：当数据条数超过1500条时，自动分段下载，每段最多1500条
9. 请求频率控制：每次API请求之间自动延迟，避免触发API频率限制
   - 每次请求延迟：默认0.1秒（可通过--request-delay调整）
   - 批次暂停：每处理指定数量的交易对后暂停（默认30个后暂停3秒）

使用方法举例：

1. 下载所有交易对的日线数据（默认）：
   python download_klines.py

2. 下载指定时间范围的日线数据：
   python download_klines.py --interval 1d --start-time 2025-01-01 --end-time 2025-12-31

3. 下载1小时K线数据，指定时间范围：
   python download_klines.py --interval 1h --start-time 2025-01-01 --end-time 2025-12-31

4. 下载4小时K线数据，指定时间范围（自动分段下载）：
   python download_klines.py --interval 4h --start-time 2022-01-01 --end-time 2025-12-31

5. 下载5分钟K线数据，指定时间范围：
   python download_klines.py --interval 5m --start-time 2025-01-01 --end-time 2025-12-31

6. 下载指定交易对的数据：
   python download_klines.py --interval 1d --start-time 2025-01-01 --end-time 2025-12-31 --symbols BTCUSDT ETHUSDT

7. 下载最近30天的数据：
   python download_klines.py --interval 1d --days 30

8. 只下载缺失的交易对：
   python download_klines.py --interval 1d --missing-only

9. 更新已存在的数据：
   python download_klines.py --interval 1d --update

10. 使用精确时间（包含时分秒），自动分段下载：
    python download_klines.py --interval 1h --start-time "2025-01-01 00:00:00" --end-time "2025-12-31 23:59:59"

11. 自定义请求延迟和批次设置：
    python download_klines.py --interval 1h --start-time 2024-01-01 --end-time 2025-12-31 --request-delay 0.2 --batch-size 20 --batch-delay 5.0

12. 禁用自动分段下载（使用原有单次下载逻辑）：
    python download_klines.py --interval 4h --start-time 2022-01-01 --end-time 2025-12-31 --no-auto-split

命令行参数：
  --interval: K线间隔 (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
  --start-time: 开始时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)
  --end-time: 结束时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)
  --days: 回溯天数（如果提供了--start-time和--end-time则忽略此参数）
  --limit: 每次请求的最大条数（默认None，自动使用1500。如果只提供start-time和end-time会自动计算）
  --auto-split: 当数据条数超过限制时自动分段下载（默认: True）
  --no-auto-split: 禁用自动分段下载
  --request-delay: 每次API请求之间的延迟时间（秒），避免频率限制（默认: 0.1）
  --batch-size: 每处理多少个交易对后暂停（默认: 30）
  --batch-delay: 每批处理后的暂停时间（秒）（默认: 3.0）
  --update: 更新已存在的数据
  --missing-only: 只下载缺失的交易对
  --symbols: 指定要下载的交易对列表

注意事项：
- 表名格式：K{interval}{symbol}，例如日线数据存储在 K1dBTCUSDT 表中
- 默认不下载当天的数据（因为当天数据不完整）
- 增量更新规则：
  * 日线及以上（1d, 3d, 1w, 1M）：按日期去重，不更新最后一天
  * 小时线及以下（1h, 4h, 5m等）：按时间点去重，不更新最后一条
- 如果提供了--start-time和--end-time，会自动计算数据条数
- 当数据条数超过1500条时，会自动分段下载，每段最多1500条
- 每次API请求之间会自动延迟（默认0.1秒），避免触发频率限制
- 每处理指定数量的交易对后会暂停（默认30个后暂停3秒）
- 如果提供了--start-time和--end-time，会优先使用这些参数，忽略--days参数
"""

import os
import sys
import logging
import time
import pandas as pd      # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from api import (
    in_exchange_trading_symbols,
    kline_candlestick_data,
    kline2df
)

from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (  # pyright: ignore[reportMissingImports]
    KlineCandlestickDataIntervalEnum
)
from db import engine, create_table

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def get_local_symbols(interval: str = "1d") -> List[str]:
    """获取本地数据库中已存在的交易对列表"""
    # 表名格式: K{interval}{symbol}, 例如: K1dBTCUSDT
    prefix = f'K{interval}'
    stmt = f"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '{prefix}%'"
    with engine.connect() as conn:
        result = conn.execute(text(stmt))
        table_names = result.fetchall()
    # 去掉前缀 'K{interval}', 例如 'K1d' -> ''
    prefix_len = len(prefix)
    local_symbols = [name[0][prefix_len:] for name in table_names]
    return local_symbols


def calculate_interval_seconds(interval: str) -> int:
    """
    计算K线间隔对应的秒数
    
    Args:
        interval: K线间隔字符串，如 '1m', '1h', '1d' 等
    
    Returns:
        int: 对应的秒数
    """
    interval_map = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '6h': 21600,
        '8h': 28800,
        '12h': 43200,
        '1d': 86400,
        '3d': 259200,
        '1w': 604800,
        '1M': 2592000,  # 假设1个月=30天
    }
    return interval_map.get(interval, 86400)


def calculate_data_count(start_time: datetime, end_time: datetime, interval: str) -> int:
    """
    计算指定时间范围内的数据条数
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        interval: K线间隔
    
    Returns:
        int: 数据条数
    """
    if not start_time or not end_time:
        return 0
    
    # 确保两个datetime对象都有相同的时区信息
    if start_time.tzinfo is None and end_time.tzinfo is not None:
        # start_time没有时区，end_time有时区，将start_time转换为UTC
        start_time = start_time.replace(tzinfo=timezone.utc)
    elif start_time.tzinfo is not None and end_time.tzinfo is None:
        # start_time有时区，end_time没有时区，将end_time转换为UTC
        end_time = end_time.replace(tzinfo=timezone.utc)
    elif start_time.tzinfo is None and end_time.tzinfo is None:
        # 两个都没有时区，假设是UTC
        start_time = start_time.replace(tzinfo=timezone.utc)
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    interval_seconds = calculate_interval_seconds(interval)
    total_seconds = int((end_time - start_time).total_seconds())
    count = total_seconds // interval_seconds + 1
    return count


def split_time_range(start_time: datetime, end_time: datetime, interval: str, max_count: int = 1500) -> List[tuple]:
    """
    将时间范围分割成多个段，每段不超过max_count条数据
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        interval: K线间隔
        max_count: 每段最大数据条数，默认1500
    
    Returns:
        List[tuple]: [(start1, end1), (start2, end2), ...] 时间范围列表
    """
    if not start_time or not end_time:
        return []
    
    # 确保两个datetime对象都有相同的时区信息
    if start_time.tzinfo is None and end_time.tzinfo is not None:
        # start_time没有时区，end_time有时区，将start_time转换为UTC
        start_time = start_time.replace(tzinfo=timezone.utc)
    elif start_time.tzinfo is not None and end_time.tzinfo is None:
        # start_time有时区，end_time没有时区，将end_time转换为UTC
        end_time = end_time.replace(tzinfo=timezone.utc)
    elif start_time.tzinfo is None and end_time.tzinfo is None:
        # 两个都没有时区，假设是UTC
        start_time = start_time.replace(tzinfo=timezone.utc)
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    interval_seconds = calculate_interval_seconds(interval)
    max_seconds = (max_count - 1) * interval_seconds  # 减1是因为包含起始和结束时间
    
    ranges = []
    current_start = start_time
    
    while current_start < end_time:
        # 计算当前段的结束时间
        current_end = current_start + timedelta(seconds=max_seconds)
        if current_end > end_time:
            current_end = end_time
        
        ranges.append((current_start, current_end))
        current_start = current_end + timedelta(seconds=interval_seconds)
    
    return ranges


def get_existing_dates(symbol: str, interval: str = "1d") -> set:
    """获取指定交易对在数据库中已存在的日期集合"""
    table_name = f'K{interval}{symbol}'
    try:
        stmt = f"SELECT trade_date FROM {table_name}"
        with engine.connect() as conn:
            result = conn.execute(text(stmt))
            dates = result.fetchall()
        return {date[0] for date in dates}
    except Exception as e:
        logging.warning(f"获取 {symbol} 已存在日期失败: {e}")
        return set()


def _insert_with_skip_duplicates(df: pd.DataFrame, table_name: str, engine) -> int:
    """
    逐条插入数据，跳过重复的trade_date
    
    Args:
        df: 要插入的DataFrame
        table_name: 表名
        engine: 数据库引擎
    
    Returns:
        int: 成功插入的行数
    """
    saved_count = 0
    
    for _, row in df.iterrows():
        try:
            # 将row转换为字典
            row_dict = row.to_dict()
            
            # 构建INSERT语句，使用命名参数（:param）
            columns = ', '.join(df.columns)
            placeholders = ', '.join([f':{col}' for col in df.columns])
            
            stmt = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            with engine.connect() as conn:
                # SQLAlchemy的execute方法使用字典作为参数
                conn.execute(text(stmt), row_dict)
                conn.commit()
            saved_count += 1
        except Exception as e:
            # 如果是UNIQUE constraint错误，跳过这条数据
            if 'UNIQUE constraint' in str(e) or 'IntegrityError' in str(type(e).__name__):
                continue
            else:
                trade_date = row_dict.get('trade_date', 'unknown') if 'row_dict' in locals() else 'unknown'
                logging.error(f"插入数据失败: {e}, trade_date: {trade_date}")
                raise
    
    return saved_count


def get_last_trade_date(symbol: str, interval: str = "1d") -> Optional[str]:
    """
    获取指定交易对在数据库中的最后一条数据的trade_date
    
    Args:
        symbol: 交易对符号
        interval: K线间隔
    
    Returns:
        Optional[str]: 最后一条数据的trade_date，如果表不存在或没有数据则返回None
    """
    table_name = f'K{interval}{symbol}'
    try:
        stmt = f"SELECT trade_date FROM {table_name} ORDER BY trade_date DESC LIMIT 1"
        with engine.connect() as conn:
            result = conn.execute(text(stmt))
            row = result.fetchone()
            if row:
                return row[0]
        return None
    except Exception as e:
        # 表不存在或其他错误，返回None
        return None


def compare_trade_dates(last_date: str, end_time: datetime, interval: str) -> bool:
    """
    比较本地最后一条数据的时间与end_time
    
    Args:
        last_date: 本地最后一条数据的trade_date（字符串格式）
        end_time: 要下载的结束时间
        interval: K线间隔
    
    Returns:
        bool: 如果last_date >= end_time对应的日期/时间，返回True（表示已是最新数据）
    """
    try:
        if interval in ['1d', '3d', '1w', '1M']:
            # 日线及以上，比较日期
            last_date_obj = datetime.strptime(last_date, '%Y-%m-%d').date()
            # 确保end_time有时区信息，然后转换为date
            if end_time.tzinfo is None:
                end_date = end_time.date()
            else:
                end_date = end_time.astimezone(timezone.utc).date()
            result = last_date_obj >= end_date
            comparison_op = ">=" if result else "<"
            logging.info(f"日期比较: 本地最后日期={last_date_obj}, 结束日期={end_date}, 结果={result} (本地{comparison_op}结束)")
            return result
        else:
            # 小时线及以下，比较完整时间
            last_date_obj = datetime.strptime(last_date, '%Y-%m-%d %H:%M:%S')
            # 确保两个datetime对象都有相同的时区信息
            if end_time.tzinfo is not None:
                # end_time有时区信息，将last_date_obj也转换为UTC时区
                last_date_obj = last_date_obj.replace(tzinfo=timezone.utc)
            elif last_date_obj.tzinfo is not None:
                # last_date_obj有时区信息，将end_time也转换为UTC时区
                end_time = end_time.replace(tzinfo=timezone.utc)
            
            result = last_date_obj >= end_time
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            comparison_op = ">=" if result else "<"
            logging.info(f"时间比较: 本地最后时间={last_date}, 结束时间={end_time_str}, 结果={result} (本地{comparison_op}结束)")
            return result
    except Exception as e:
        logging.warning(f"比较日期失败: {e}, last_date={last_date}, end_time={end_time}, interval={interval}")
        return False


def download_kline_data(
    symbol: str,
    interval: str = "1d",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: Optional[int] = 1500,
    update_existing: bool = False,
    auto_split: bool = True,
    request_delay: float = 0.1
) -> bool:
    """
    下载指定交易对的K线数据并保存到数据库
    
    注意：默认不会下载当天的数据, 因为当天数据不完整(还在交易中)。
    只有在第二天更新前一天的数据才准确。
    
    Args:
        symbol: 交易对符号, 如 'BTCUSDT'
        interval: K线间隔, 默认 '1d'(日线)
        start_time: 开始时间, 默认None(从最早开始)
        end_time: 结束时间, 默认None(到昨天的结束时间, 不包含今天)
        limit: 每次请求的最大条数, 默认1500。如果为None且提供了start_time和end_time，会自动计算
        update_existing: 是否更新已存在的数据, 默认False
        auto_split: 当数据条数超过limit时是否自动分段下载, 默认True
        request_delay: 每次API请求之间的延迟时间（秒），避免频率限制, 默认0.1秒
    
    Returns:
        bool: 是否成功下载
    """
    table_name = f'K{interval}{symbol}'
    
    try:
        # 如果未启用update_existing，先检查本地最后一条数据的时间
        # 这个检查必须在任何API调用之前进行，避免不必要的网络请求
        if not update_existing:
            # 确定要比较的结束时间：如果提供了end_time就用它，否则根据K线间隔计算
            check_end_time = end_time
            if check_end_time is None:
                now = datetime.now()
                if interval in ['1d', '3d', '1w', '1M']:
                    # 日线及以上, 使用昨天的结束时间
                    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    check_end_time = today - timedelta(seconds=1)  # 昨天的23:59:59
                else:
                    # 小时线及以下, 使用当前时间之前的最新完整K线时间
                    interval_seconds = calculate_interval_seconds(interval)
                    now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
                    current_timestamp = int(now_utc.timestamp())
                    kline_index = current_timestamp // interval_seconds
                    current_kline_start_timestamp = kline_index * interval_seconds
                    latest_complete_kline_start_timestamp = current_kline_start_timestamp - interval_seconds
                    check_end_time = datetime.fromtimestamp(latest_complete_kline_start_timestamp, tz=timezone.utc)
            
            last_trade_date = get_last_trade_date(symbol, interval)
            if last_trade_date:
                if compare_trade_dates(last_trade_date, check_end_time, interval):
                    end_time_str = check_end_time.strftime('%Y-%m-%d' if interval in ['1d', '3d', '1w', '1M'] else '%Y-%m-%d %H:%M:%S')
                    logging.info(f"{symbol} 本地数据最后时间({last_trade_date}) >= 结束时间({end_time_str})，跳过下载（使用--update可强制更新）")
                    return True
        
        # 创建表(如果不存在)
        create_table(table_name)
        
        # 获取已存在的日期
        existing_dates = get_existing_dates(symbol, interval) if not update_existing else set()
        
        # 转换时间间隔
        interval_enum = KlineCandlestickDataIntervalEnum[f"INTERVAL_{interval}"].value
        
        # 转换时间格式(如果需要)
        # 如果end_time为None, 根据K线间隔设置默认结束时间
        if end_time is None:
            now = datetime.now()
            if interval in ['1d', '3d', '1w', '1M']:
                # 日线及以上, 默认设置为昨天的结束时间(不包含今天)
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = today - timedelta(seconds=1)  # 昨天的23:59:59
            else:
                # 小时线及以下, 设置为当前时间之前的最新完整K线时间
                interval_seconds = calculate_interval_seconds(interval)
                now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
                current_timestamp = int(now_utc.timestamp())
                kline_index = current_timestamp // interval_seconds
                current_kline_start_timestamp = kline_index * interval_seconds
                # 最新完整K线的开始时间 = 当前K线开始时间 - 一个K线周期
                latest_complete_kline_start_timestamp = current_kline_start_timestamp - interval_seconds
                end_time = datetime.fromtimestamp(latest_complete_kline_start_timestamp, tz=timezone.utc)
                logging.info(f"{symbol} 默认结束时间设置为最新完整K线时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # 如果提供了start_time和end_time，检查是否需要分段下载
        max_limit = limit if limit is not None else 1500
        
        if start_time and end_time and auto_split:
            # 计算预计数据条数
            data_count = calculate_data_count(start_time, end_time, interval)
            logging.info(f"{symbol} 预计数据条数: {data_count}, 限制: {max_limit}")
            
            if data_count > max_limit:
                # 需要分段下载
                logging.info(f"{symbol} 数据条数({data_count})超过限制({max_limit})，将分段下载")
                time_ranges = split_time_range(start_time, end_time, interval, max_limit)
                logging.info(f"{symbol} 将分为 {len(time_ranges)} 段下载")
                
                all_dfs = []
                for idx, (seg_start, seg_end) in enumerate(time_ranges, 1):
                    logging.info(f"{symbol} 正在下载第 {idx}/{len(time_ranges)} 段: {seg_start.strftime('%Y-%m-%d %H:%M:%S')} 到 {seg_end.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    seg_start_ts = int(seg_start.timestamp() * 1000)
                    seg_end_ts = int(seg_end.timestamp() * 1000)
                    
                    # 请求前暂停，避免频率限制
                    if request_delay > 0:
                        time.sleep(request_delay)
                    
                    try:
                        klines = kline_candlestick_data(
                            symbol=symbol,
                            interval=interval_enum,
                            starttime=seg_start_ts,
                            endtime=seg_end_ts,
                            limit=max_limit
                        )
                        
                        if klines:
                            seg_df = kline2df(klines)
                            if not seg_df.empty:
                                all_dfs.append(seg_df)
                                logging.info(f"{symbol} 第 {idx} 段下载成功，获得 {len(seg_df)} 条数据")
                            else:
                                logging.warning(f"{symbol} 第 {idx} 段转换后的DataFrame为空")
                        else:
                            logging.warning(f"{symbol} 第 {idx} 段没有获取到K线数据")
                    except Exception as e:
                        logging.error(f"{symbol} 第 {idx} 段下载失败: {e}")
                        continue
                
                if not all_dfs:
                    logging.warning(f"{symbol} 所有分段都没有获取到数据")
                    return False
                
                # 合并所有分段的数据
                df = pd.concat(all_dfs, ignore_index=True)
                
                # 将trade_date转换为字符串格式(用于数据库存储和去重)
                # 根据K线间隔选择合适的日期格式
                if interval in ['1d', '3d', '1w', '1M']:
                    # 日线及以上, 使用日期格式
                    df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d')
                else:
                    # 小时线及以下, 使用完整时间格式
                    df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # 去重（按trade_date）
                df = df.drop_duplicates(subset=['trade_date'], keep='first')
                logging.info(f"{symbol} 分段下载完成，合并后共 {len(df)} 条数据（去重前: {sum(len(d) for d in all_dfs)} 条）")
            else:
                # 不需要分段，直接下载
                start_timestamp = int(start_time.timestamp() * 1000)
                end_timestamp = int(end_time.timestamp() * 1000)
                
                # 请求前暂停
                if request_delay > 0:
                    time.sleep(request_delay)
                
                logging.info(f"正在下载 {symbol} 的K线数据...")
                klines = kline_candlestick_data(
                    symbol=symbol,
                    interval=interval_enum,
                    starttime=start_timestamp,
                    endtime=end_timestamp,
                    limit=max_limit
                )
                
                if not klines:
                    logging.warning(f"{symbol} 没有获取到K线数据")
                    return False
                
                df = kline2df(klines)
        else:
            # 原有逻辑：单次下载（不自动分段或没有提供时间范围）
            start_timestamp = None
            end_timestamp = None
            if start_time:
                start_timestamp = int(start_time.timestamp() * 1000)
            if end_time:
                end_timestamp = int(end_time.timestamp() * 1000)
            
            # 请求前暂停
            if request_delay > 0:
                time.sleep(request_delay)
            
            # 下载K线数据
            logging.info(f"正在下载 {symbol} 的K线数据...")
            klines = kline_candlestick_data(
                symbol=symbol,
                interval=interval_enum,
                starttime=start_timestamp,
                endtime=end_timestamp,
                limit=max_limit
            )
            
            if not klines:
                logging.warning(f"{symbol} 没有获取到K线数据")
                return False
            
            # 转换为DataFrame
            df = kline2df(klines)
        
        if df.empty:
            logging.warning(f"{symbol} 转换后的DataFrame为空")
            return False
        
        # 将trade_date转换为字符串格式(用于数据库存储和去重)
        # 注意：分段下载时已经在合并前转换过了，这里需要检查是否已转换
        if df['trade_date'].dtype == 'object':
            # 已经是字符串格式，跳过转换
            pass
        else:
            # 根据K线间隔选择合适的日期格式
            if interval in ['1d', '3d', '1w', '1M']:
                # 日线及以上, 使用日期格式
                df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d')
            else:
                # 小时线及以下, 使用完整时间格式
                df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 过滤掉不完整的数据
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        before_filter = len(df)
        
        if interval in ['1d', '3d', '1w', '1M']:
            # 日线及以上, 过滤掉今天的日期（因为今天的数据不完整）
            df = df[df['trade_date'] != today_str]
        else:
            # 小时线及以下, 计算当前时间之前的最新完整K线时间
            # 例如：4小时K线，如果现在是10:00，那么08:00的K线应该已经完整了
            interval_seconds = calculate_interval_seconds(interval)
            
            # 计算当前时间所在K线的开始时间
            # 将当前时间向下取整到最近的K线开始时间
            # 使用UTC时间，因为币安API返回的时间戳是UTC
            now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
            current_timestamp = int(now_utc.timestamp())
            # 计算从1970-01-01 00:00:00 UTC到当前时间经过了多少个K线周期
            kline_index = current_timestamp // interval_seconds
            # 计算当前K线的开始时间戳
            current_kline_start_timestamp = kline_index * interval_seconds
            # 最新完整K线的结束时间 = 当前K线的开始时间（因为当前K线还未结束）
            # 所以最新完整K线的开始时间 = 当前K线开始时间 - 一个K线周期
            latest_complete_kline_start_timestamp = current_kline_start_timestamp - interval_seconds
            latest_complete_time = datetime.fromtimestamp(latest_complete_kline_start_timestamp, tz=timezone.utc)
            
            # 过滤掉晚于最新完整K线时间的数据
            def is_complete_kline(trade_date_str: str) -> bool:
                try:
                    # 小时线及以下使用完整时间格式
                    # trade_date_str是UTC时间字符串（从币安API获取）
                    trade_date_obj = datetime.strptime(trade_date_str, '%Y-%m-%d %H:%M:%S')
                    # 将trade_date_obj转换为UTC时间对象进行比较
                    trade_date_utc = trade_date_obj.replace(tzinfo=timezone.utc)
                    # 如果K线时间 <= 最新完整K线时间，则认为是完整的
                    return trade_date_utc <= latest_complete_time
                except:
                    return True  # 如果解析失败，保留数据（让其他逻辑处理）
            
            df = df[df['trade_date'].apply(is_complete_kline)]
            
            if before_filter > len(df):
                logging.info(f"{symbol} 过滤掉 {before_filter - len(df)} 条不完整的K线数据（最新完整K线时间: {latest_complete_time.strftime('%Y-%m-%d %H:%M:%S')}）")
        
        after_filter = len(df)
        if after_filter < before_filter:
            logging.info(f"{symbol} 共过滤掉 {before_filter - after_filter} 条不完整数据")
        
        # 再次去重（确保DataFrame内部没有重复的trade_date）
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['trade_date'], keep='first')
        after_dedup = len(df)
        if after_dedup < before_dedup:
            logging.info(f"{symbol} DataFrame内部去重，移除 {before_dedup - after_dedup} 条重复数据")
        
        # 过滤已存在的数据
        if existing_dates and not update_existing:
            before_count = len(df)
            df = df[~df['trade_date'].isin(existing_dates)]
            after_count = len(df)
            if after_count < before_count:
                logging.info(f"{symbol} 过滤掉 {before_count - after_count} 条已存在的数据")
        
        if df.empty:
            logging.info(f"{symbol} 没有新数据需要保存")
            return True
        
        # 保存到数据库前，再次获取最新的已存在数据（防止并发插入）
        if not update_existing:
            current_existing_dates = get_existing_dates(symbol, interval)
            if current_existing_dates:
                before_final_check = len(df)
                df = df[~df['trade_date'].isin(current_existing_dates)]
                after_final_check = len(df)
                if after_final_check < before_final_check:
                    logging.info(f"{symbol} 最终检查过滤掉 {before_final_check - after_final_check} 条已存在的数据")
                if df.empty:
                    logging.info(f"{symbol} 最终检查后没有新数据需要保存")
                    return True
        
        # 保存到数据库
        # SQLite对单次插入的参数数量有限制（默认999）
        # 每条K线数据有15个字段，所以每批最多插入 999/15 ≈ 66 条
        # 为了安全，使用50条作为批次大小
        BATCH_SIZE = 50  # 每批插入50条，避免超过SQLite参数限制（15字段 * 50条 = 750参数 < 999）
        total_rows = len(df)
        
        saved_count = 0
        
        if total_rows <= BATCH_SIZE:
            # 数据量小，直接插入
            try:
                df.to_sql(
                    name=table_name,
                    con=engine,
                    if_exists='append',
                    index=False,
                    method='multi'
                )
                saved_count = len(df)
            except Exception as e:
                # 如果出现UNIQUE constraint错误，逐条插入跳过重复的
                if 'UNIQUE constraint' in str(e) or 'IntegrityError' in str(type(e).__name__):
                    logging.warning(f"{symbol} 批量插入遇到重复数据，改为逐条插入跳过重复项")
                    saved_count = _insert_with_skip_duplicates(df, table_name, engine)
                else:
                    raise
        else:
            # 数据量大，分批插入
            for i in range(0, total_rows, BATCH_SIZE):
                batch_df = df.iloc[i:i+BATCH_SIZE]
                try:
                    batch_df.to_sql(
                        name=table_name,
                        con=engine,
                        if_exists='append',
                        index=False,
                        method='multi'
                    )
                    saved_count += len(batch_df)
                except Exception as e:
                    # 如果出现UNIQUE constraint错误，逐条插入跳过重复的
                    if 'UNIQUE constraint' in str(e) or 'IntegrityError' in str(type(e).__name__):
                        logging.warning(f"{symbol} 第 {i//BATCH_SIZE + 1} 批插入遇到重复数据，改为逐条插入跳过重复项")
                        saved_count += _insert_with_skip_duplicates(batch_df, table_name, engine)
                    else:
                        raise
                
                if (i + BATCH_SIZE) % (BATCH_SIZE * 10) == 0 or (i + BATCH_SIZE) >= total_rows:
                    # 每插入10批（500条）或最后一批时输出进度
                    logging.info(f"{symbol} 已保存 {saved_count}/{total_rows} 条数据")
        
        if saved_count < total_rows:
            logging.info(f"{symbol} 成功保存 {saved_count} 条K线数据（共 {total_rows} 条，跳过 {total_rows - saved_count} 条重复数据）")
        else:
            logging.info(f"{symbol} 成功保存 {saved_count} 条K线数据")
        return True
        
    except Exception as e:
        logging.error(f"下载 {symbol} K线数据失败: {e}")
        return False


def download_all_symbols(
    interval: str = "1d",
    days_back: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: Optional[int] = 1500,
    update_existing: bool = False,
    symbols: Optional[List[str]] = None,
    auto_split: bool = True,
    request_delay: float = 0.1,
    batch_size: int = 30,
    batch_delay: float = 3.0
):
    """
    下载所有交易对的K线数据
    
    Args:
        interval: K线间隔, 默认 '1d'
        days_back: 回溯天数, 默认None(下载所有数据), 如果提供了start_time和end_time则忽略此参数
        start_time: 开始时间, 默认None(根据days_back计算或下载所有数据)
        end_time: 结束时间, 默认None(昨天的结束时间)
        limit: 每次请求的最大条数, 默认1500
        update_existing: 是否更新已存在的数据, 默认False
        symbols: 指定要下载的交易对列表, 默认None(下载所有)
    """
    # 获取交易对列表
    if symbols is None:
        logging.info("正在获取所有交易对...")
        all_symbols = in_exchange_trading_symbols()
        if not all_symbols:
            logging.error("无法获取交易对列表")
            return
    else:
        all_symbols = symbols
    
    logging.info(f"共找到 {len(all_symbols)} 个交易对")
    
    # 计算时间范围
    # 如果提供了start_time和end_time，优先使用；否则使用默认逻辑
    if end_time is None:
        now = datetime.now()
        if interval in ['1d', '3d', '1w', '1M']:
            # 日线及以上, 默认结束时间为昨天的结束时间(不包含今天)
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = today - timedelta(seconds=1)  # 昨天的23:59:59
        else:
            # 小时线及以下, 设置为当前时间之前的最新完整K线时间
            interval_seconds = calculate_interval_seconds(interval)
            now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
            current_timestamp = int(now_utc.timestamp())
            kline_index = current_timestamp // interval_seconds
            current_kline_start_timestamp = kline_index * interval_seconds
            latest_complete_kline_start_timestamp = current_kline_start_timestamp - interval_seconds
            end_time = datetime.fromtimestamp(latest_complete_kline_start_timestamp, tz=timezone.utc)
            logging.info(f"默认结束时间设置为最新完整K线时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    if start_time is None:
        # 如果没有提供start_time，根据days_back计算
        if days_back:
            start_time = end_time - timedelta(days=days_back)
        # 如果days_back也为None，则start_time保持为None（下载所有数据）
    
    # 下载每个交易对的数据
    success_count = 0
    fail_count = 0
    
    for i, symbol in enumerate(all_symbols, 1):
        logging.info(f"[{i}/{len(all_symbols)}] 处理交易对: {symbol}")
        if download_kline_data(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            update_existing=update_existing,
            auto_split=auto_split,
            request_delay=request_delay
        ):
            success_count += 1
        else:
            fail_count += 1
        
        # 每处理指定数量的交易对后暂停，避免触发交易所API限制
        if i % batch_size == 0:
            logging.info(f"已处理 {i} 个交易对, 暂停 {batch_delay} 秒以避免API限制...")
            time.sleep(batch_delay)
    
    logging.info(f"下载完成！成功: {success_count}, 失败: {fail_count}")


def download_missing_symbols(
    interval: str = "1d",
    days_back: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: Optional[int] = 1500,
    auto_split: bool = True,
    request_delay: float = 0.1,
    batch_size: int = 30,
    batch_delay: float = 3.0
):
    """只下载本地数据库中缺失的交易对数据"""
    logging.info("正在检查缺失的交易对...")
    
    # 获取交易所所有交易对
    exchange_symbols = in_exchange_trading_symbols()
    if not exchange_symbols:
        logging.error("无法获取交易所交易对列表")
        return
    
    # 获取本地已有交易对
    local_symbols = get_local_symbols(interval)
    
    # 找出缺失的交易对
    missing_symbols = [s for s in exchange_symbols if s not in local_symbols]
    
    if not missing_symbols:
        logging.info("没有缺失的交易对")
        return
    
    logging.info(f"找到 {len(missing_symbols)} 个缺失的交易对")
    
    # 下载缺失的交易对数据
    download_all_symbols(
        interval=interval,
        days_back=days_back,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        update_existing=False,
        symbols=missing_symbols,
        auto_split=auto_split,
        request_delay=request_delay,
        batch_size=batch_size,
        batch_delay=batch_delay
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='下载币安U本位合约K线数据')
    parser.add_argument(
        '--interval',
        type=str,
        default='1d',
        choices=['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'],
        help='K线间隔(默认: 1d)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='回溯天数(默认: None, 下载所有数据), 如果提供了--start-time和--end-time则忽略此参数'
    )
    parser.add_argument(
        '--start-time',
        type=str,
        default=None,
        help='开始时间, 格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS (默认: None, 根据--days计算或下载所有数据)'
    )
    parser.add_argument(
        '--end-time',
        type=str,
        default=None,
        help='结束时间, 格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS (默认: None, 昨天的结束时间)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='每次请求的最大条数(默认: None, 自动使用1500。如果只提供start-time和end-time会自动计算)'
    )
    parser.add_argument(
        '--auto-split',
        action='store_true',
        default=True,
        help='当数据条数超过限制时自动分段下载(默认: True)'
    )
    parser.add_argument(
        '--no-auto-split',
        action='store_false',
        dest='auto_split',
        help='禁用自动分段下载'
    )
    parser.add_argument(
        '--request-delay',
        type=float,
        default=0.1,
        help='每次API请求之间的延迟时间（秒），避免频率限制(默认: 0.1)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=30,
        help='每处理多少个交易对后暂停(默认: 30)'
    )
    parser.add_argument(
        '--batch-delay',
        type=float,
        default=3.0,
        help='每批处理后的暂停时间（秒）(默认: 3.0)'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='更新已存在的数据'
    )
    parser.add_argument(
        '--missing-only',
        action='store_true',
        help='只下载缺失的交易对'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        help='指定要下载的交易对列表, 例如: --symbols BTCUSDT ETHUSDT'
    )
    
    args = parser.parse_args()
    
    # 解析时间参数
    start_time = None
    end_time = None
    
    if args.start_time:
        try:
            # 尝试解析日期时间格式
            if len(args.start_time) == 10:  # YYYY-MM-DD
                start_time = datetime.strptime(args.start_time, '%Y-%m-%d')
            else:  # YYYY-MM-DD HH:MM:SS
                start_time = datetime.strptime(args.start_time, '%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            logging.error(f"开始时间格式错误: {args.start_time}, 错误: {e}")
            logging.error("请使用格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")
            sys.exit(1)
    
    if args.end_time:
        try:
            # 尝试解析日期时间格式
            if len(args.end_time) == 10:  # YYYY-MM-DD
                end_time = datetime.strptime(args.end_time, '%Y-%m-%d')
                # 如果是日期格式，设置为当天的23:59:59
                end_time = end_time.replace(hour=23, minute=59, second=59)
            else:  # YYYY-MM-DD HH:MM:SS
                end_time = datetime.strptime(args.end_time, '%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            logging.error(f"结束时间格式错误: {args.end_time}, 错误: {e}")
            logging.error("请使用格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")
            sys.exit(1)
    
    if args.missing_only:
        # 只下载缺失的交易对
        download_missing_symbols(
            interval=args.interval,
            days_back=args.days,
            start_time=start_time,
            end_time=end_time,
            limit=args.limit,
            auto_split=args.auto_split,
            request_delay=args.request_delay,
            batch_size=args.batch_size,
            batch_delay=args.batch_delay
        )
    else:
        # 下载所有或指定的交易对
        download_all_symbols(
            interval=args.interval,
            days_back=args.days,
            start_time=start_time,
            end_time=end_time,
            limit=args.limit,
            update_existing=args.update,
            symbols=args.symbols,
            auto_split=args.auto_split,
            request_delay=args.request_delay,
            batch_size=args.batch_size,
            batch_delay=args.batch_delay
        )

