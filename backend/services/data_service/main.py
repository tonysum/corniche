"""
数据管理服务 (Data Service)
端口: 8001

职责:
- K线数据下载和管理
- 数据查询和检索
- 数据完整性检查
- 数据修复和重检
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timezone
import logging
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path

from download_klines import (
    download_kline_data,
    download_all_symbols,
    download_missing_symbols,
    get_local_symbols,
    get_existing_dates,
    calculate_data_count,
    split_time_range,
    calculate_interval_seconds
)
from data import (
    get_local_kline_data,
    delete_all_tables,
    delete_kline_data,
    check_data_integrity,
    generate_download_script_from_check,
    download_missing_data_from_check,
    generate_integrity_report,
    recheck_problematic_symbols,
    get_local_symbols
)
try:
    from api import kline_candlestick_data, kline2df
    from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
        KlineCandlestickDataIntervalEnum
    )
    BINANCE_API_AVAILABLE = True
except ImportError:
    BINANCE_API_AVAILABLE = False
    logging.warning("Binance API module not available, real-time K-line feature disabled")
try:
    from top3_api import get_top3_gainers
    TOP3_API_AVAILABLE = True
except ImportError:
    TOP3_API_AVAILABLE = False
    logging.warning("top3_api module not available, 24h top gainers feature disabled")
from services.shared.config import DATA_SERVICE_PORT, ALLOWED_ORIGINS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="数据管理服务",
    description="提供币安U本位合约K线数据的下载和管理API",
    version="1.0.0"
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IntervalEnum(str, Enum):
    """K线间隔枚举"""
    m1 = "1m"
    m3 = "3m"
    m5 = "5m"
    m15 = "15m"
    m30 = "30m"
    h1 = "1h"
    h2 = "2h"
    h4 = "4h"
    h6 = "6h"
    h8 = "8h"
    h12 = "12h"
    d1 = "1d"
    d3 = "3d"
    w1 = "1w"
    M1 = "1M"


class DownloadRequest(BaseModel):
    """下载请求模型"""
    interval: IntervalEnum = Field(default=IntervalEnum.d1, description="K线间隔")
    symbol: Optional[str] = Field(default=None, description="交易对符号（如BTCUSDT），如果不指定则下载所有交易对")
    start_time: Optional[str] = Field(default=None, description="开始时间（格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）")
    end_time: Optional[str] = Field(default=None, description="结束时间（格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）")
    limit: Optional[int] = Field(default=1500, description="每次请求的最大数据条数")
    update_existing: bool = Field(default=False, description="是否更新已存在的数据")
    missing_only: bool = Field(default=False, description="是否只下载缺失的交易对")
    days_back: Optional[int] = Field(default=None, description="从当前时间往前推的天数（如果提供了start_time和end_time则忽略此参数）")
    auto_split: bool = Field(default=True, description="是否自动分段下载（当数据条数超过limit时）")
    request_delay: float = Field(default=0.1, description="请求之间的延迟时间（秒）")
    batch_size: Optional[int] = Field(default=None, description="批量下载时的批次大小")
    batch_delay: Optional[float] = Field(default=None, description="批次之间的延迟时间（秒）")


class DeleteTablesRequest(BaseModel):
    """删除表请求模型"""
    confirm: bool = Field(description="确认删除，必须为True才能执行删除操作")


class DataIntegrityRequest(BaseModel):
    """数据完整性检查请求模型"""
    symbol: Optional[str] = Field(default=None, description="交易对符号（如BTCUSDT），如果不指定则检查所有交易对")
    interval: str = Field(default="1d", description="K线间隔")
    start_date: Optional[str] = Field(default=None, description="开始日期（格式: YYYY-MM-DD）")
    end_date: Optional[str] = Field(default=None, description="结束日期（格式: YYYY-MM-DD）")
    check_duplicates: bool = Field(default=True, description="是否检查重复数据")
    check_missing_dates: bool = Field(default=True, description="是否检查缺失日期")
    check_data_quality: bool = Field(default=True, description="是否检查数据质量")


class GenerateReportRequest(BaseModel):
    """生成报告请求模型"""
    check_results: Dict = Field(description="数据完整性检查结果")
    interval: str = Field(description="K线间隔")
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")
    format: str = Field(default="txt", description="报告格式：txt, json, html, md")


class GenerateDownloadScriptRequest(BaseModel):
    """生成下载脚本请求模型"""
    check_results: Dict = Field(description="数据完整性检查结果")
    interval: str = Field(description="K线间隔")


class RecheckRequest(BaseModel):
    """复检请求模型"""
    check_results: Dict = Field(description="数据完整性检查结果")
    interval: str = Field(description="K线间隔")
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")


class DeleteKlineDataRequest(BaseModel):
    """删除K线数据请求模型"""
    symbol: str = Field(..., description="交易对符号，例如 'BTCUSDT'")
    interval: str = Field(..., description="K线间隔，例如 '1d', '1h', '4h'")
    start_time: Optional[str] = Field(None, description="开始时间（格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'），如果为None则删除全部")
    end_time: Optional[str] = Field(None, description="结束时间（格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'），如果为None则删除全部")


class UpdateKlineDataRequest(BaseModel):
    """更新K线数据请求模型"""
    symbol: str = Field(..., description="交易对符号，例如 'BTCUSDT'")
    interval: str = Field(..., description="K线间隔，例如 '1d', '1h', '4h'")
    trade_date: str = Field(..., description="交易日期（格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'）")
    open: Optional[float] = Field(None, description="开盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    close: Optional[float] = Field(None, description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")
    quote_volume: Optional[float] = Field(None, description="成交额")
    trade_count: Optional[int] = Field(None, description="成交笔数")
    active_buy_volume: Optional[float] = Field(None, description="主动买入成交量")
    active_buy_quote_volume: Optional[float] = Field(None, description="主动买入成交额")


def parse_datetime(time_str: str) -> Optional[datetime]:
    """解析时间字符串，支持多种格式"""
    if not time_str:
        return None
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"无法解析时间格式: {time_str}")


@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "service": "数据管理服务",
        "version": "1.0.0",
        "port": DATA_SERVICE_PORT,
        "docs": "/docs",
        "endpoints": {
            "下载K线数据": "/api/download",
            "查询本地交易对": "/api/symbols",
            "查询交易对数据日期": "/api/dates/{interval}/{symbol}",
            "获取K线数据": "/api/kline/{interval}/{symbol}",
            "删除所有表": "/api/tables/delete",
            "数据完整性检查": "/api/data-integrity",
            "生成完整性报告": "/api/generate-integrity-report",
            "生成下载脚本": "/api/generate-download-script",
            "下载缺失数据": "/api/download-missing-data",
            "复检问题数据": "/api/recheck-problematic-symbols",
            "删除K线数据": "/api/kline-data (DELETE)",
            "更新K线数据": "/api/kline-data (PUT)"
        }
    }


@app.post("/api/download")
async def download_klines(request: DownloadRequest, background_tasks: BackgroundTasks):
    """下载K线数据"""
    try:
        start_time = parse_datetime(request.start_time) if request.start_time else None
        end_time = parse_datetime(request.end_time) if request.end_time else None
        
        if request.start_time and not start_time:
            raise HTTPException(status_code=400, detail="开始时间格式错误")
        if request.end_time and not end_time:
            raise HTTPException(status_code=400, detail="结束时间格式错误")
        
        if request.missing_only:
            background_tasks.add_task(
                download_missing_symbols,
                interval=request.interval.value,
                days_back=request.days_back,
                start_time=start_time,
                end_time=end_time,
                limit=request.limit,
                auto_split=request.auto_split,
                request_delay=request.request_delay,
                batch_size=request.batch_size,
                batch_delay=request.batch_delay
            )
            return {
                "status": "started",
                "message": "已开始下载缺失的交易对数据",
                "interval": request.interval.value,
                "mode": "missing_only"
            }
        elif request.symbol:
            background_tasks.add_task(
                download_kline_data,
                symbol=request.symbol,
                interval=request.interval.value,
                start_time=start_time,
                end_time=end_time,
                limit=request.limit,
                update_existing=request.update_existing,
                auto_split=request.auto_split,
                request_delay=request.request_delay
            )
            return {
                "status": "started",
                "message": f"已开始下载 {request.symbol} 的K线数据",
                "symbol": request.symbol,
                "interval": request.interval.value
            }
        else:
            background_tasks.add_task(
                download_all_symbols,
                interval=request.interval.value,
                days_back=request.days_back,
                start_time=start_time,
                end_time=end_time,
                limit=request.limit,
                update_existing=request.update_existing,
                symbols=None,
                auto_split=request.auto_split,
                request_delay=request.request_delay,
                batch_size=request.batch_size,
                batch_delay=request.batch_delay
            )
            return {
                "status": "started",
                "message": "已开始下载所有交易对的K线数据",
                "interval": request.interval.value
            }
    except Exception as e:
        logging.error(f"下载K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@app.get("/api/symbols")
async def get_symbols(interval: str = "1d"):
    """获取本地数据库中指定时间间隔的交易对列表"""
    try:
        symbols = get_local_symbols(interval)
        return {
            "interval": interval,
            "count": len(symbols),
            "symbols": symbols
        }
    except Exception as e:
        logging.error(f"获取交易对列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/dates/{interval}/{symbol}")
async def get_dates(interval: str, symbol: str):
    """获取指定交易对的数据日期列表"""
    try:
        dates = get_existing_dates(symbol, interval)
        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(dates),
            "dates": sorted(list(dates))
        }
    except Exception as e:
        logging.error(f"获取日期列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/kline/{interval}/{symbol}")
async def get_kline_data(
    interval: str,
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
):
    """获取K线数据"""
    try:
        df = get_local_kline_data(symbol, interval)
        if df.empty:
            # 检查表是否存在
            from db import engine
            from sqlalchemy import text
            table_name = f'K{interval}{symbol}'
            try:
                with engine.connect() as conn:
                    result = conn.execute(
                        text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
                    )
                    table_exists = result.fetchone() is not None
                
                if not table_exists:
                    # 表不存在，返回友好的错误信息
                    return {
                        "symbol": symbol,
                        "interval": interval,
                        "count": 0,
                        "data": [],
                        "message": f"交易对 {symbol} 在 {interval} 间隔下暂无数据，请先下载数据"
                    }
            except Exception:
                pass  # 如果检查表存在性失败，继续返回空数据
            
            return {
                "symbol": symbol,
                "interval": interval,
                "count": 0,
                "data": []
            }
        
        # 处理trade_date格式，创建用于筛选的日期字符串列
        if df['trade_date'].dtype == 'object':
            # 字符串格式，提取日期部分用于筛选
            df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            # 转换为datetime用于排序和精确筛选
            df['trade_date_dt'] = pd.to_datetime(df['trade_date'])
        else:
            # 已经是datetime格式
            df['trade_date_str'] = df['trade_date'].dt.strftime('%Y-%m-%d')
            df['trade_date_dt'] = pd.to_datetime(df['trade_date'])
        
        # 统一时间范围筛选逻辑：使用完整的datetime进行比较
        if start_date:
            try:
                if len(start_date) == 10:  # YYYY-MM-DD
                    start_dt = pd.to_datetime(start_date)
                else:  # YYYY-MM-DD HH:MM:SS
                    start_dt = pd.to_datetime(start_date)
                df = df[df['trade_date_dt'] >= start_dt]
            except ValueError:
                # 如果解析失败，回退到字符串比较
                df = df[df['trade_date_str'] >= start_date]
        
        if end_date:
            try:
                if len(end_date) == 10:  # YYYY-MM-DD
                    # 对于日期格式，如果结束日期是今天，限制为当前时间（UTC），确保与币安API的时间范围一致
                    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    now_utc = pd.Timestamp.now(tz='UTC').tz_localize(None)
                    if end_dt > now_utc:
                        end_dt = now_utc
                else:  # YYYY-MM-DD HH:MM:SS
                    end_dt = pd.to_datetime(end_date)
                    # 如果指定的结束时间超过当前时间，限制为当前时间
                    now_utc = pd.Timestamp.now(tz='UTC').tz_localize(None)
                    if end_dt > now_utc:
                        end_dt = now_utc
                df = df[df['trade_date_dt'] <= end_dt]
            except ValueError:
                # 如果解析失败，回退到字符串比较
                df = df[df['trade_date_str'] <= end_date]
        
        # 按完整时间排序（确保顺序正确，升序）- 使用trade_date_dt而不是trade_date_str
        df = df.sort_values('trade_date_dt', ascending=True)
        
        # 获取总数（在限制之前）
        total_count = len(df)
        
        # 如果指定了offset和limit，进行分页
        if offset is not None and limit is not None:
            # 从后往前取（最新的数据），但保持升序
            # 先取最后 offset+limit 条，然后取前 limit 条，最后重新排序确保升序
            df_selected = df.tail(offset + limit).head(limit)
            df = df_selected.sort_values('trade_date_dt', ascending=True)
        elif limit is not None:
            # 只指定limit，取最新的limit条，但保持升序
            df_selected = df.tail(limit)
            df = df_selected.sort_values('trade_date_dt', ascending=True)
        elif offset is not None:
            # 只指定offset，从后往前跳过offset条
            df_selected = df.head(-offset) if offset > 0 else df
            df = df_selected.sort_values('trade_date_dt', ascending=True)
        
        # 删除临时列
        if 'trade_date_dt' in df.columns:
            df = df.drop(columns=['trade_date_dt'])
        if 'trade_date_str' in df.columns:
            df = df.drop(columns=['trade_date_str'])
        
        # 清理无效的浮点值（inf, -inf, NaN）以确保JSON兼容性
        df = df.replace([np.inf, -np.inf], np.nan)  # 将inf替换为NaN
        
        # 转换为字典列表
        data = df.to_dict('records')
        
        # 清理函数：确保所有数值都是JSON兼容的
        def clean_value(value):
            # 处理 None
            if value is None:
                return None
            
            # 处理 pandas NaT (Not a Time) 和 NaN
            try:
                if pd.isna(value):
                    return None
            except (TypeError, ValueError):
                pass
            
            # 处理 NumPy 类型
            if isinstance(value, (np.integer, np.floating)):
                # 检查是否为 inf 或 nan
                try:
                    if np.isinf(value) or np.isnan(value):
                        return None
                except (TypeError, ValueError):
                    return None
                # 转换为 Python 原生类型
                if isinstance(value, np.integer):
                    return int(value)
                else:
                    return float(value)
            
            # 处理 Python 原生数值类型
            if isinstance(value, (int, float)):
                # 检查是否为 inf 或 nan
                try:
                    if np.isinf(value) or np.isnan(value):
                        return None
                except (TypeError, ValueError):
                    pass
                return value
            
            # 处理 datetime 类型
            if isinstance(value, (pd.Timestamp, datetime)):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            
            # 处理字符串
            if isinstance(value, str):
                return value
            
            # 其他类型直接返回
            return value
        
        # 清理数据中的每个值
        cleaned_data = []
        for record in data:
            cleaned_record = {}
            for key, value in record.items():
                if isinstance(value, dict):
                    cleaned_record[key] = {k: clean_value(v) for k, v in value.items()}
                elif isinstance(value, (list, tuple)):
                    cleaned_record[key] = [clean_value(v) for v in value]
                else:
                    cleaned_record[key] = clean_value(value)
            cleaned_data.append(cleaned_record)
        
        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(cleaned_data),
            "total_count": total_count,  # 返回总数据量
            "data": cleaned_data
        }
    except Exception as e:
        logging.error(f"获取K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.post("/api/tables/delete")
async def delete_tables(request: DeleteTablesRequest):
    """删除所有表"""
    if not request.confirm:
        raise HTTPException(status_code=400, detail="必须设置 confirm=true 才能执行删除操作")
    
    try:
        count = delete_all_tables(confirm=True)
        return {
            "status": "success",
            "message": f"已删除 {count} 个表"
        }
    except Exception as e:
        logging.error(f"删除表失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.post("/api/data-integrity")
async def check_data_integrity_api(request: DataIntegrityRequest):
    """检查K线数据完整性"""
    try:
        result = check_data_integrity(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            verbose=True
        )
        return result
    except Exception as e:
        logging.error(f"数据完整性检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


@app.post("/api/generate-integrity-report")
async def generate_integrity_report_api(request: GenerateReportRequest):
    """生成数据完整性报告"""
    try:
        # 从check_results中提取检查配置
        check_duplicates = request.check_results.get('check_duplicates', True)
        check_missing_dates = request.check_results.get('check_missing_dates', True)
        check_data_quality = request.check_results.get('check_data_quality', True)
        
        # 将format映射到output_format，并处理格式转换
        format_mapping = {
            'txt': 'text',
            'text': 'text',
            'json': 'json',
            'html': 'html',
            'md': 'markdown',
            'markdown': 'markdown'
        }
        output_format = format_mapping.get(request.format.lower(), 'text')
        
        report_content = generate_integrity_report(
            check_results=request.check_results,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=check_duplicates,
            check_missing_dates=check_missing_dates,
            check_data_quality=check_data_quality,
            output_format=output_format
        )
        return {
            "status": "success",
            "format": request.format,
            "report": report_content
        }
    except Exception as e:
        logging.error(f"生成报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.post("/api/generate-download-script")
async def generate_download_script_api(request: GenerateDownloadScriptRequest):
    """生成下载脚本"""
    try:
        script_content = generate_download_script_from_check(
            check_results=request.check_results,
            interval=request.interval
        )
        return {
            "status": "success",
            "script": script_content
        }
    except Exception as e:
        logging.error(f"生成脚本失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.post("/api/download-missing-data")
async def download_missing_data_api(request: DataIntegrityRequest):
    """下载缺失数据"""
    try:
        # 先检查数据完整性
        check_results = check_data_integrity(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            verbose=True
        )
        
        # 下载缺失数据
        download_stats = download_missing_data_from_check(
            check_results=check_results,
            interval=request.interval,
            verbose=True
        )
        
        # 重新检查数据完整性
        check_results_after = check_data_integrity(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            verbose=True
        )
        
        return {
            "status": "success",
            "check_results_before": check_results,
            "download_stats": download_stats,
            "check_results_after": check_results_after
        }
    except Exception as e:
        logging.error(f"下载缺失数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@app.post("/api/recheck-problematic-symbols")
async def recheck_problematic_symbols_api(request: RecheckRequest):
    """复检问题数据"""
    try:
        import time
        recheck_results = recheck_problematic_symbols(
            check_results=request.check_results,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            verbose=True
        )
        
        # 生成报告文件
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"recheck_report_{request.interval}_{timestamp}.txt"
        
        recheck_results_with_report = recheck_problematic_symbols(
            check_results=request.check_results,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            verbose=True,
            output_file=output_file
        )
        
        # 读取报告文件内容
        report_content = None
        report_file = None
        if output_file and Path(output_file).exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            report_file = output_file
        
        return {
            "status": "success",
            "recheck_results": recheck_results_with_report,
            "report_file": report_file,
            "report_content": report_content
        }
    except Exception as e:
        logging.error(f"复检失败: {e}")
        raise HTTPException(status_code=500, detail=f"复检失败: {str(e)}")


@app.delete("/api/kline-data")
async def delete_kline_data_api(request: DeleteKlineDataRequest):
    """删除K线数据"""
    try:
        result = delete_kline_data(
            symbol=request.symbol,
            interval=request.interval,
            start_time=request.start_time,
            end_time=request.end_time,
            verbose=True
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])
        
        return {
            "status": "success",
            "message": result['message'],
            "deleted_count": result['deleted_count']
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"删除K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.put("/api/kline-data")
async def update_kline_data_api(request: UpdateKlineDataRequest):
    """更新单条K线数据"""
    try:
        from db import engine
        from sqlalchemy import text
        
        table_name = f'K{request.interval}{request.symbol}'
        
        # 检查表是否存在
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            )
            table_exists = result.fetchone() is not None
            
            if not table_exists:
                raise HTTPException(status_code=404, detail=f'表 {table_name} 不存在')
            
            # 检查记录是否存在并获取当前值
            check_stmt = f"SELECT * FROM {table_name} WHERE trade_date = :trade_date"
            check_result = conn.execute(text(check_stmt), {"trade_date": request.trade_date})
            existing_record = check_result.fetchone()
            
            if not existing_record:
                raise HTTPException(status_code=404, detail=f'未找到日期为 {request.trade_date} 的数据')
            
            # 获取列名
            columns = check_result.keys()
            column_dict = {col: idx for idx, col in enumerate(columns)}
            
            # 构建UPDATE语句，只更新提供的字段
            update_fields = []
            update_values = {"trade_date": request.trade_date}
            
            # 获取当前值用于计算diff和pct_chg
            current_open = existing_record[column_dict.get('open', 2)] if 'open' in column_dict else None
            current_close = existing_record[column_dict.get('close', 5)] if 'close' in column_dict else None
            
            if request.open is not None:
                update_fields.append("open = :open")
                update_values["open"] = request.open
                current_open = request.open
            if request.high is not None:
                update_fields.append("high = :high")
                update_values["high"] = request.high
            if request.low is not None:
                update_fields.append("low = :low")
                update_values["low"] = request.low
            if request.close is not None:
                update_fields.append("close = :close")
                update_values["close"] = request.close
                current_close = request.close
            if request.volume is not None:
                update_fields.append("volume = :volume")
                update_values["volume"] = request.volume
            if request.quote_volume is not None:
                update_fields.append("quote_volume = :quote_volume")
                update_values["quote_volume"] = request.quote_volume
            if request.trade_count is not None:
                update_fields.append("trade_count = :trade_count")
                update_values["trade_count"] = request.trade_count
            if request.active_buy_volume is not None:
                update_fields.append("active_buy_volume = :active_buy_volume")
                update_values["active_buy_volume"] = request.active_buy_volume
            if request.active_buy_quote_volume is not None:
                update_fields.append("active_buy_quote_volume = :active_buy_quote_volume")
                update_values["active_buy_quote_volume"] = request.active_buy_quote_volume
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="至少需要提供一个要更新的字段")
            
            # 重新计算diff和pct_chg（如果提供了open或close）
            if (request.open is not None or request.close is not None) and current_open and current_close:
                diff = current_close - current_open
                pct_chg = diff / current_open if current_open != 0 else 0
                update_fields.append("diff = :diff")
                update_fields.append("pct_chg = :pct_chg")
                update_values["diff"] = diff
                update_values["pct_chg"] = pct_chg
            
            update_stmt = f"UPDATE {table_name} SET {', '.join(update_fields)} WHERE trade_date = :trade_date"
            conn.execute(text(update_stmt), update_values)
            conn.commit()
            
            # 获取更新后的数据
            updated_result = conn.execute(text(check_stmt), {"trade_date": request.trade_date})
            updated_record = updated_result.fetchone()
            updated_columns = updated_result.keys()
            
            updated_data = dict(zip(updated_columns, updated_record))
            
            return {
                "status": "success",
                "message": f"成功更新 {request.symbol} {request.interval} 在 {request.trade_date} 的数据",
                "data": updated_data
            }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新K线数据失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@app.get("/api/top-gainers")
async def get_top_gainers(date: Optional[str] = None, top_n: int = 3):
    """
    获取指定日期涨幅前三的交易对
    
    Args:
        date: 日期（格式: YYYY-MM-DD），如果不指定则使用前一天
        top_n: 返回前N名，默认3
    
    Returns:
        涨幅排名列表
    """
    try:
        from datetime import datetime, timedelta
        
        # 如果没有指定日期，使用前一天
        if not date:
            yesterday = datetime.now() - timedelta(days=1)
            date = yesterday.strftime('%Y-%m-%d')
        
        # 获取所有交易对
        symbols = get_local_symbols(interval="1d")
        if not symbols:
            return {
                "date": date,
                "top_gainers": [],
                "message": "未找到交易对数据"
            }
        
        all_data = []
        
        # 读取所有交易对的数据
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
                
                # 筛选指定日期
                df_filtered = df[df['trade_date_str'] == date].copy()
                
                if df_filtered.empty:
                    continue
                
                # 添加symbol列
                df_filtered['symbol'] = symbol
                
                # 处理pct_chg
                row = df_filtered.iloc[0]
                pct_chg = row.get('pct_chg')
                
                # 如果pct_chg为NaN，尝试计算
                if pd.isna(pct_chg):
                    date_dt = datetime.strptime(date, '%Y-%m-%d')
                    prev_date = (date_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                    prev_data = df[df['trade_date_str'] == prev_date]
                    
                    if not prev_data.empty and not pd.isna(prev_data.iloc[0]['close']):
                        prev_close = prev_data.iloc[0]['close']
                        current_close = row['close']
                        if not pd.isna(current_close) and prev_close > 0:
                            pct_chg = (current_close - prev_close) / prev_close * 100
                
                if not pd.isna(pct_chg):
                    all_data.append({
                        'symbol': symbol,
                        'pct_chg': float(pct_chg),
                        'close': float(row['close']) if not pd.isna(row['close']) else None,
                        'open': float(row['open']) if not pd.isna(row['open']) else None,
                        'high': float(row['high']) if not pd.isna(row['high']) else None,
                        'low': float(row['low']) if not pd.isna(row['low']) else None,
                        'volume': float(row['volume']) if not pd.isna(row['volume']) else None,
                    })
            except Exception as e:
                logging.debug(f"读取 {symbol} 数据失败: {e}")
                continue
        
        if not all_data:
            return {
                "date": date,
                "top_gainers": [],
                "message": f"未找到 {date} 的数据"
            }
        
        # 按涨幅排序，取前N名
        sorted_data = sorted(all_data, key=lambda x: x['pct_chg'], reverse=True)
        top_gainers = sorted_data[:top_n]
        
        return {
            "date": date,
            "top_gainers": top_gainers,
            "total_count": len(all_data)
        }
    except Exception as e:
        logging.error(f"获取涨幅排名失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/top-gainers-24h")
async def get_top_gainers_24h(top_n: int = 3):
    """
    获取过去24小时涨幅前三的交易对（使用币安API）
    
    Args:
        top_n: 返回前N名，默认3
    
    Returns:
        涨幅排名列表
    """
    if not TOP3_API_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="24小时涨幅数据服务不可用，请检查top3_api模块"
        )
    
    try:
        logging.info("开始获取24小时涨幅排名...")
        
        # 检查函数是否可用
        if not callable(get_top3_gainers):
            raise ValueError("get_top3_gainers 不是一个可调用函数")
        
        df = get_top3_gainers()
        
        # 检查返回值
        if df is None:
            logging.warning("get_top3_gainers() 返回 None")
            return {
                "top_gainers": [],
                "message": "未找到24小时涨幅数据（API返回None）"
            }
        
        if not isinstance(df, pd.DataFrame):
            logging.warning(f"get_top3_gainers() 返回了非DataFrame类型: {type(df)}")
            return {
                "top_gainers": [],
                "message": f"数据格式错误: {type(df)}"
            }
        
        logging.info(f"获取到数据: {len(df) if not df.empty else 0} 条")
        
        if df.empty:
            logging.warning("get_top3_gainers() 返回空DataFrame")
            return {
                "top_gainers": [],
                "message": "未找到24小时涨幅数据"
            }
        
        # 转换为字典列表
        top_gainers = []
        for idx, row in df.head(top_n).iterrows():
            try:
                symbol = str(row.get('symbol', '')) if pd.notna(row.get('symbol')) else ''
                price_change_percent = float(row.get('price_change_percent', 0)) if pd.notna(row.get('price_change_percent')) else 0
                
                gainer = {
                    'symbol': symbol,
                    'price_change_percent': price_change_percent,
                    'last_price': float(row.get('last_price', 0)) if pd.notna(row.get('last_price')) else None,
                    'open_price': float(row.get('open_price', 0)) if pd.notna(row.get('open_price')) else None,
                    'high_price': float(row.get('high_price', 0)) if pd.notna(row.get('high_price')) else None,
                    'low_price': float(row.get('low_price', 0)) if pd.notna(row.get('low_price')) else None,
                    'volume': float(row.get('volume', 0)) if pd.notna(row.get('volume')) else None,
                }
                top_gainers.append(gainer)
                logging.debug(f"添加交易对: {symbol}, 涨幅: {price_change_percent}%")
            except Exception as e:
                logging.error(f"处理第 {idx} 行数据失败: {e}")
                continue
        
        logging.info(f"成功处理 {len(top_gainers)} 个交易对")
        return {
            "top_gainers": top_gainers,
            "total_count": len(df)
        }
    except Exception as e:
        logging.error(f"获取24小时涨幅排名失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/kline-binance/{interval}/{symbol}")
async def get_kline_data_from_binance(
    interval: str,
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
):
    """从币安API获取实时K线数据"""
    if not BINANCE_API_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="币安API模块不可用，无法获取实时数据"
        )
    
    try:
        # 转换时间间隔
        try:
            interval_enum = KlineCandlestickDataIntervalEnum[f"INTERVAL_{interval}"].value
        except KeyError:
            raise HTTPException(status_code=400, detail=f"不支持的K线间隔: {interval}")
        
        # 转换时间参数
        start_timestamp = None
        end_timestamp = None
        
        # 解析日期范围（用于后续过滤）
        start_dt_filter = None
        end_dt_filter = None
        
        if start_date:
            try:
                if len(start_date) == 10:  # YYYY-MM-DD
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    start_dt_filter = start_dt.replace(tzinfo=timezone.utc)
                else:  # YYYY-MM-DD HH:MM:SS
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
                    start_dt_filter = start_dt.replace(tzinfo=timezone.utc)
                start_timestamp = int(start_dt_filter.timestamp() * 1000)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"开始日期格式错误: {start_date}")
        
        if end_date:
            try:
                if len(end_date) == 10:  # YYYY-MM-DD
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    end_dt_filter = end_dt.replace(tzinfo=timezone.utc)
                else:  # YYYY-MM-DD HH:MM:SS
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                    end_dt_filter = end_dt.replace(tzinfo=timezone.utc)
                
                # 限制结束时间不超过当前时间（UTC），避免请求未来的数据
                now_utc = datetime.now(timezone.utc)
                if end_dt_filter > now_utc:
                    end_dt_filter = now_utc
                
                end_timestamp = int(end_dt_filter.timestamp() * 1000)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"结束日期格式错误: {end_date}")
        
        # 计算需要的数据条数，决定是否需要分段请求
        max_limit = 1500  # 币安API单次请求最大限制
        need_split = False
        
        if start_dt_filter and end_dt_filter:
            # 计算预计数据条数
            data_count = calculate_data_count(start_dt_filter, end_dt_filter, interval)
            if data_count > max_limit:
                need_split = True
                logging.info(f"数据条数({data_count})超过限制({max_limit})，将分段请求")
        
        # 调用币安API（可能需要分段）
        all_klines = []
        
        if need_split and start_dt_filter and end_dt_filter:
            # 分段请求
            time_ranges = split_time_range(start_dt_filter, end_dt_filter, interval, max_limit)
            logging.info(f"将分为 {len(time_ranges)} 段请求")
            
            for idx, (seg_start, seg_end) in enumerate(time_ranges, 1):
                seg_start_ts = int(seg_start.timestamp() * 1000)
                seg_end_ts = int(seg_end.timestamp() * 1000)
                
                logging.info(f"请求第 {idx}/{len(time_ranges)} 段: {seg_start.strftime('%Y-%m-%d %H:%M:%S')} 到 {seg_end.strftime('%Y-%m-%d %H:%M:%S')}")
                
                seg_klines = kline_candlestick_data(
                    symbol=symbol,
                    interval=interval_enum,
                    starttime=seg_start_ts,
                    endtime=seg_end_ts,
                    limit=max_limit
                )
                
                if seg_klines:
                    all_klines.extend(seg_klines)
                
                # 避免API频率限制
                import time
                time.sleep(0.1)
        else:
            # 单次请求
            # 如果没有指定limit，或者limit小于max_limit，使用max_limit确保获取足够的数据
            request_limit = max_limit  # 默认使用1500，确保获取足够的数据
            if limit and limit < max_limit:
                request_limit = limit  # 如果用户明确指定了更小的limit，使用用户的设置
            elif limit and limit > max_limit:
                request_limit = max_limit  # 不能超过币安API的限制
            
            logging.info(f"单次请求，使用limit={request_limit}")
            
            klines = kline_candlestick_data(
                symbol=symbol,
                interval=interval_enum,
                starttime=start_timestamp,
                endtime=end_timestamp,
                limit=request_limit
            )
            
            if klines:
                all_klines = klines
        
        if not all_klines:
            return {
                "symbol": symbol,
                "interval": interval,
                "count": 0,
                "data": []
            }
        
        # 转换为DataFrame并格式化
        df = kline2df(all_klines)
        
        # 确保trade_date是datetime类型（带时区）
        if df['trade_date'].dtype == 'object':
            df['trade_date'] = pd.to_datetime(df['trade_date'], utc=True)
        elif not hasattr(df['trade_date'].dtype, 'tz') or df['trade_date'].dtype.tz is None:
            # 如果没有时区信息，假设是UTC
            df['trade_date'] = pd.to_datetime(df['trade_date'], utc=True)
        
        # 根据日期范围过滤数据（币安API可能返回范围外的数据）
        if start_dt_filter is not None:
            df = df[df['trade_date'] >= start_dt_filter]
        if end_dt_filter is not None:
            df = df[df['trade_date'] <= end_dt_filter]
        
        # 将trade_date转换为字符串格式
        if interval in ['1d', '3d', '1w', '1M']:
            df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d')
        else:
            df['trade_date'] = df['trade_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 按时间排序（降序，最新的在前）
        df = df.sort_values('trade_date', ascending=False)
        
        # 清理无效值
        df = df.replace([np.inf, -np.inf], np.nan)
        
        # 转换为字典列表
        data = df.to_dict('records')
        
        # 清理JSON不兼容的值
        def clean_value(value):
            if value is None:
                return None
            try:
                if pd.isna(value):
                    return None
            except (TypeError, ValueError):
                pass
            if isinstance(value, (np.integer, np.int64, np.int32)):
                return int(value)
            elif isinstance(value, (np.floating, np.float64, np.float32)):
                if np.isinf(value) or np.isnan(value):
                    return None
                return float(value)
            elif isinstance(value, (pd.Timestamp, datetime)):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            return value
        
        cleaned_data = []
        for record in data:
            cleaned_record = {}
            for key, value in record.items():
                cleaned_record[key] = clean_value(value)
            cleaned_data.append(cleaned_record)
        
        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(cleaned_data),
            "data": cleaned_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"从币安API获取K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "数据管理服务",
        "port": DATA_SERVICE_PORT
    }


@app.get("/api/download-database", response_class=FileResponse)
async def download_database():
    """
    下载数据库文件 crypto_data.db
    
    返回数据库文件的二进制流，浏览器会自动下载到默认下载文件夹
    文件名格式: crypto_data_YYYYMMDD_HHMMSS.db
    
    注意：在 Swagger UI 中可能无法直接下载，建议直接在浏览器中访问此 URL
    """
    from services.shared.config import DB_PATH
    import os
    
    db_path = Path(DB_PATH)
    
    # 检查文件是否存在
    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"数据库文件不存在: {db_path}"
        )
    
    # 检查文件大小
    file_size = db_path.stat().st_size
    
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"数据库文件为空: {db_path}"
        )
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"crypto_data_{timestamp}.db"
    
    logging.info(f"下载数据库文件: {db_path}, 大小: {file_size} 字节 ({file_size / (1024*1024):.2f} MB)")
    
    # 返回文件
    return FileResponse(
        path=str(db_path),
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_size)
        }
    )


@app.post("/api/upload-database")
async def upload_database(file: UploadFile = File(...)):
    """
    上传数据库文件到服务器的 data/tmp 文件夹
    
    参数:
    - file: 上传的数据库文件（必须是 .db 文件）
    
    返回:
    - 上传成功信息，包括文件路径和大小
    """
    from services.shared.config import DB_PATH
    import shutil
    
    # 验证文件类型
    if not file.filename or not file.filename.endswith('.db'):
        raise HTTPException(
            status_code=400,
            detail="只能上传 .db 文件"
        )
    
    # 确定目标目录（data/tmp）
    db_path = Path(DB_PATH)
    data_dir = db_path.parent  # data 目录
    tmp_dir = data_dir / "tmp"
    
    # 创建 tmp 目录（如果不存在）
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = file.filename or "crypto_data.db"
    # 保留原始文件名，但添加时间戳
    base_name = Path(original_filename).stem
    extension = Path(original_filename).suffix
    saved_filename = f"{base_name}_{timestamp}{extension}"
    saved_path = tmp_dir / saved_filename
    
    try:
        # 保存文件
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 获取文件大小
        file_size = saved_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        logging.info(f"上传数据库文件成功: {saved_path}, 大小: {file_size} 字节 ({file_size_mb:.2f} MB)")
        
        return {
            "status": "success",
            "message": "数据库文件上传成功",
            "filename": saved_filename,
            "path": str(saved_path),
            "size": file_size,
            "size_mb": round(file_size_mb, 2),
            "upload_time": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"上传数据库文件失败: {e}")
        # 如果保存失败，尝试删除已创建的文件
        if saved_path.exists():
            try:
                saved_path.unlink()
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"上传失败: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=DATA_SERVICE_PORT)

