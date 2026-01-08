"""
币安U本位合约K线数据下载服务端

使用 FastAPI 提供 RESTful API 接口来下载和管理K线数据

功能特性：
- 支持下载币安U本位合约K线数据
- 智能跳过：如果本地数据最后时间 >= end_time，自动跳过下载（除非update_existing=True）
- 自动分段下载：当数据条数超过1500条时自动分段
- 请求频率控制：自动延迟避免API限制

启动服务：
    uvicorn api_server:app --host 0.0.0.0 --port 8000

API文档：
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import logging
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd  # pyright: ignore[reportMissingImports]
import numpy as np  # pyright: ignore[reportMissingImports]

from download_klines import (
    download_kline_data,
    download_all_symbols,
    download_missing_symbols,
    get_local_symbols,
    get_existing_dates
)
from data import (
    get_local_kline_data,
    delete_all_tables,
    check_data_integrity,
    generate_download_script_from_check,
    download_missing_data_from_check,
    generate_integrity_report,
    recheck_problematic_symbols
)

# 导入订单计算函数
from order import calculate_short_exit_price, calculate_long_exit_price

# 导入回测函数
from backtrade import simulate_trading

# 导入回测函数
from backtrade import simulate_trading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="币安K线数据下载服务",
    description="提供币安U本位合约K线数据的下载和管理API",
    version="1.0.0"
)

# 配置CORS中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],  # 允许的前端地址
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
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
    symbol: Optional[str] = Field(default=None, description="交易对符号，如 BTCUSDT。如果为None，则下载所有交易对")
    start_time: Optional[str] = Field(default=None, description="开始时间，格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")
    end_time: Optional[str] = Field(default=None, description="结束时间，格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")
    days_back: Optional[int] = Field(default=None, description="回溯天数，如果提供了start_time和end_time则忽略此参数")
    limit: Optional[int] = Field(default=None, description="每次请求的最大条数（默认None，自动使用1500）")
    update_existing: bool = Field(default=False, description="是否更新已存在的数据。如果为False，当本地数据最后时间 >= end_time时会自动跳过下载")
    missing_only: bool = Field(default=False, description="只下载缺失的交易对")
    auto_split: bool = Field(default=True, description="当数据条数超过限制时自动分段下载（默认: True）")
    request_delay: float = Field(default=0.1, description="每次API请求之间的延迟时间（秒），避免频率限制（默认: 0.1）")
    batch_size: int = Field(default=30, description="每处理多少个交易对后暂停（默认: 30）")
    batch_delay: float = Field(default=3.0, description="每批处理后的暂停时间（秒）（默认: 3.0）")


class DeleteTablesRequest(BaseModel):
    """删除表请求模型"""
    confirm: bool = Field(default=False, description="确认删除，必须设置为True才会执行删除")


class OrderCalculateRequest(BaseModel):
    """订单计算请求模型"""
    price: float = Field(description="当前价格")
    entry_pct_chg: float = Field(description="建仓涨幅百分比（例如：4 表示 4%）")
    loss_threshold: float = Field(description="止损阈值百分比（例如：1.9 表示 1.9%）")
    profit_threshold: float = Field(description="止盈阈值百分比（例如：4 表示 4%）")
    order_type: str = Field(default="short", description="订单类型：'short' 或 'long'")


class BacktestRequest(BaseModel):
    """回测请求模型"""
    start_date: str = Field(description="开始日期，格式: YYYY-MM-DD")
    end_date: str = Field(description="结束日期，格式: YYYY-MM-DD")
    initial_capital: Optional[float] = Field(default=None, description="初始资金（USDT）")
    leverage: Optional[float] = Field(default=None, description="杠杆倍数")
    profit_threshold: Optional[float] = Field(default=None, description="止盈阈值（小数，如0.04表示4%）")
    loss_threshold: Optional[float] = Field(default=None, description="止损阈值（小数，如0.019表示1.9%）")
    position_size_ratio: Optional[float] = Field(default=None, description="每次建仓金额占账户余额的比例（小数，如0.06表示6%）")
    min_pct_chg: Optional[float] = Field(default=None, description="最小涨幅百分比（小数，如0.1表示10%）")
    delay_entry: bool = Field(default=False, description="是否启用延迟入场策略（等待涨势减弱后建仓）")
    delay_hours: int = Field(default=12, description="延迟入场的小时数（仅在delay_entry=True时生效）")


# 存储下载任务状态
download_tasks = {}


def parse_datetime(time_str: str) -> Optional[datetime]:
    """解析时间字符串"""
    if not time_str:
        return None
    try:
        if len(time_str) == 10:  # YYYY-MM-DD
            dt = datetime.strptime(time_str, '%Y-%m-%d')
            if time_str == time_str[:10]:  # 如果是日期格式，设置为当天的23:59:59
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt
        else:  # YYYY-MM-DD HH:MM:SS
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"时间格式错误: {time_str}, 错误: {e}")


@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "message": "币安K线数据下载服务",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "下载K线数据": "/api/download",
            "查询本地交易对": "/api/symbols",
            "查询交易对数据日期": "/api/dates/{interval}/{symbol}",
            "获取K线数据": "/api/kline/{interval}/{symbol}",
            "删除所有表": "/api/tables/delete"
        }
    }


@app.post("/api/download")
async def download_klines(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    下载K线数据
    
    支持同步和异步下载模式
    
    智能跳过功能：
    - 如果提供了end_time且update_existing=False，会检查本地数据的最后时间
    - 如果本地最后时间 >= end_time，则跳过该交易对的下载
    - 设置update_existing=True可以强制更新，忽略此检查
    """
    try:
        # 解析时间参数
        start_time = parse_datetime(request.start_time) if request.start_time else None
        end_time = parse_datetime(request.end_time) if request.end_time else None
        
        # 如果提供了时间参数，确保格式正确
        if request.start_time and not start_time:
            raise HTTPException(status_code=400, detail="开始时间格式错误")
        if request.end_time and not end_time:
            raise HTTPException(status_code=400, detail="结束时间格式错误")
        
        if request.missing_only:
            # 只下载缺失的交易对
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
            # 下载指定交易对
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
            # 下载所有交易对
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
    """
    获取本地数据库中指定时间间隔的交易对列表
    
    Args:
        interval: K线间隔，默认 '1d'
    """
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
    """
    获取指定交易对在数据库中已存在的日期列表
    
    Args:
        interval: K线间隔
        symbol: 交易对符号
    """
    try:
        dates = get_existing_dates(symbol, interval)
        return {
            "interval": interval,
            "symbol": symbol,
            "count": len(dates),
            "dates": sorted(list(dates)) if dates else []
        }
    except Exception as e:
        logging.error(f"获取日期列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.get("/api/kline/{interval}/{symbol}")
async def get_kline_data(
    interval: str,
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    获取指定交易对的K线数据
    
    Args:
        interval: K线间隔
        symbol: 交易对符号
        start_date: 开始日期（可选），格式: YYYY-MM-DD
        end_date: 结束日期（可选），格式: YYYY-MM-DD
    """
    try:
        df = get_local_kline_data(symbol, interval)
        
        if df.empty:
            return {
                "interval": interval,
                "symbol": symbol,
                "count": 0,
                "data": []
            }
        
        # 如果提供了日期范围，进行过滤
        if start_date or end_date:
            if df['trade_date'].dtype == 'object':
                df['trade_date_str'] = df['trade_date'].str[:10]
            else:
                df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            
            if start_date:
                df = df[df['trade_date_str'] >= start_date]
            if end_date:
                df = df[df['trade_date_str'] <= end_date]
        
        # 转换为字典列表，处理NaN值
        # 使用fillna将所有NaN值替换为None（使用np.nan然后转换）
        df_clean = df.copy()
        # 先替换所有NaN为None（通过转换为object类型）
        for col in df_clean.columns:
            if df_clean[col].dtype != 'object':
                df_clean[col] = df_clean[col].where(pd.notna(df_clean[col]), None)
        
        # 确保数值类型可以JSON序列化
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                continue
            # 将numpy类型转换为Python原生类型
            try:
                df_clean[col] = df_clean[col].apply(
                    lambda x: None if (pd.isna(x) or (isinstance(x, float) and x != x)) 
                    else (str(x) if isinstance(x, (pd.Timestamp, pd.DatetimeIndex)) 
                    else (x.item() if hasattr(x, 'item') else x))
                )
            except Exception as e:
                logging.warning(f"处理列 {col} 时出错: {e}，尝试直接转换")
                # 如果apply失败，尝试直接转换
                try:
                    df_clean[col] = df_clean[col].astype(str).replace('nan', None)
                except:
                    pass
        
        # 转换为字典列表，并再次清理NaN值
        data = df_clean.to_dict('records')
        
        # 最终清理：确保所有NaN值都是None，并且所有numpy类型都转换为Python原生类型
        for record in data:
            for key, value in record.items():
                if value is None:
                    continue
                # 检查NaN值
                if pd.isna(value) or (isinstance(value, float) and value != value):
                    record[key] = None
                # 转换numpy类型
                elif isinstance(value, (np.integer, np.floating)):
                    try:
                        record[key] = int(value) if isinstance(value, np.integer) else float(value)
                    except:
                        record[key] = None
                # 转换pandas Timestamp
                elif isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
                    record[key] = str(value)
        
        return {
            "interval": interval,
            "symbol": symbol,
            "count": len(data),
            "data": data
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logging.error(f"获取K线数据失败: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.post("/api/tables/delete")
async def delete_tables(request: DeleteTablesRequest):
    """
    删除数据库中所有的表
    
    警告：此操作不可逆！
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="必须设置 confirm=true 才会执行删除操作"
        )
    
    try:
        deleted_count = delete_all_tables(confirm=True)
        return {
            "status": "success",
            "message": f"成功删除 {deleted_count} 个表"
        }
    except Exception as e:
        logging.error(f"删除表失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.post("/api/calculate-order")
async def calculate_order(request: OrderCalculateRequest):
    """
    计算订单价格（建仓价格、止损价格、止盈价格）
    
    根据当前价格、建仓涨幅、止损阈值和止盈阈值计算订单价格
    """
    try:
        # 将百分比转换为小数
        entry_pct_chg = request.entry_pct_chg / 100
        loss_threshold = request.loss_threshold / 100
        profit_threshold = request.profit_threshold / 100
        
        # 根据订单类型计算价格
        if request.order_type.lower() == "short":
            entry_price, stop_loss_price, take_profit_price = calculate_short_exit_price(
                request.price,
                entry_pct_chg,
                loss_threshold,
                profit_threshold
            )
        elif request.order_type.lower() == "long":
            entry_price, stop_loss_price, take_profit_price = calculate_long_exit_price(
                request.price,
                entry_pct_chg,
                loss_threshold,
                profit_threshold
            )
        else:
            raise HTTPException(status_code=400, detail="订单类型必须是 'short' 或 'long'")
        
        # 使用Decimal确保精度，返回字符串格式以保留8位小数精度
        def format_to_8_decimal(value):
            return f"{Decimal(str(value)).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP):.8f}"
        
        return {
            "entry_price": format_to_8_decimal(entry_price),
            "stop_loss_price": format_to_8_decimal(stop_loss_price),
            "take_profit_price": format_to_8_decimal(take_profit_price),
            "order_type": request.order_type.lower()
        }
    except Exception as e:
        logging.error(f"计算订单价格失败: {e}")
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """
    运行回测交易
    
    根据指定的日期范围运行回测策略
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 运行回测（同步执行，因为需要返回结果）
        result = simulate_trading(
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            profit_threshold=request.profit_threshold,
            loss_threshold=request.loss_threshold,
            position_size_ratio=request.position_size_ratio,
            min_pct_chg=request.min_pct_chg,
            delay_entry=request.delay_entry,
            delay_hours=request.delay_hours
        )
        
        if result is None:
            raise HTTPException(status_code=400, detail="回测失败：未找到交易数据或没有交易记录")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")


class DataIntegrityRequest(BaseModel):
    """数据完整性检查请求模型"""
    symbol: Optional[str] = Field(default=None, description="交易对符号（如BTCUSDT），如果不指定则检查所有交易对")
    interval: str = Field(default="1d", description="K线间隔")
    start_date: Optional[str] = Field(default=None, description="开始日期（格式: YYYY-MM-DD）")
    end_date: Optional[str] = Field(default=None, description="结束日期（格式: YYYY-MM-DD）")
    check_duplicates: bool = Field(default=True, description="是否检查重复数据")
    check_missing_dates: bool = Field(default=True, description="是否检查缺失日期")
    check_data_quality: bool = Field(default=True, description="是否检查数据质量")


@app.post("/api/data-integrity")
async def check_data_integrity_api(request: DataIntegrityRequest):
    """
    检查K线数据完整性
    
    检查项包括：
    - 重复数据检查
    - 缺失日期检查
    - 数据质量检查（空值、异常值等）
    """
    try:
        results = check_data_integrity(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            verbose=False  # API调用时不输出到控制台
        )
        
        return results
    except Exception as e:
        logging.error(f"数据完整性检查失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


class GenerateReportRequest(BaseModel):
    """生成报告请求模型"""
    check_results: Dict  # 数据完整性检查结果
    interval: str = Field(description="K线间隔")
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")
    check_duplicates: bool = Field(default=True, description="是否检查了重复数据")
    check_missing_dates: bool = Field(default=True, description="是否检查了缺失日期")
    check_data_quality: bool = Field(default=True, description="是否检查了数据质量")
    output_format: str = Field(default="text", description="输出格式: text, json, html, markdown")


@app.post("/api/generate-integrity-report")
async def generate_integrity_report_api(request: GenerateReportRequest):
    """
    生成数据完整性检查报告
    """
    try:
        report_content = generate_integrity_report(
            check_results=request.check_results,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            output_format=request.output_format,
            output_file=None  # API调用时不保存文件
        )
        
        return {
            "report": report_content,
            "format": request.output_format
        }
    except Exception as e:
        logging.error(f"生成报告失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


class GenerateDownloadScriptRequest(BaseModel):
    """生成下载脚本请求模型"""
    check_results: Dict  # 数据完整性检查结果
    interval: str = Field(description="K线间隔")
    auto_execute: bool = Field(default=False, description="是否自动执行下载")


@app.post("/api/generate-download-script")
async def generate_download_script_api(request: GenerateDownloadScriptRequest):
    """
    根据数据完整性检查结果生成下载脚本
    """
    try:
        script_content = generate_download_script_from_check(
            check_results=request.check_results,
            interval=request.interval,
            output_file=None,  # API调用时不保存文件
            auto_execute=request.auto_execute
        )
        
        return {
            "script": script_content,
            "auto_executed": request.auto_execute
        }
    except Exception as e:
        logging.error(f"生成下载脚本失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.post("/api/download-missing-data")
async def download_missing_data_api(request: DataIntegrityRequest):
    """
    根据数据完整性检查结果自动下载缺失的数据
    """
    try:
        # 先执行检查
        check_results_before = check_data_integrity(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            verbose=False
        )
        
        # 执行下载
        download_stats = download_missing_data_from_check(
            check_results=check_results_before,
            interval=request.interval,
            verbose=False
        )
        
        # 等待数据库写入完成
        import time
        time.sleep(1)
        
        # 下载后重新检查，获取最新的检查结果
        check_results_after = check_data_integrity(
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            check_duplicates=request.check_duplicates,
            check_missing_dates=request.check_missing_dates,
            check_data_quality=request.check_data_quality,
            verbose=False
        )
        
        return {
            "check_results_before": check_results_before,
            "check_results_after": check_results_after,
            "download_stats": download_stats
        }
    except Exception as e:
        logging.error(f"下载缺失数据失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


class RecheckRequest(BaseModel):
    """复检请求模型"""
    check_results: Dict  # 数据完整性检查结果
    interval: str = Field(description="K线间隔")
    start_date: Optional[str] = Field(default=None, description="开始日期（格式: YYYY-MM-DD）")
    end_date: Optional[str] = Field(default=None, description="结束日期（格式: YYYY-MM-DD）")
    output_file: Optional[str] = Field(default=None, description="输出文件路径（可选），如果指定则生成TXT报告文件")


@app.post("/api/recheck-problematic-symbols")
async def recheck_problematic_symbols_api(request: RecheckRequest):
    """
    复检有问题的交易对，对比交易所API数据和本地数据
    
    用于识别问题是出在交易所API还是本地数据
    """
    try:
        # 如果指定了输出文件，生成报告文件
        output_file = request.output_file
        if not output_file:
            # 如果没有指定，自动生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"recheck_report_{request.interval}_{timestamp}.txt"
        
        recheck_results = recheck_problematic_symbols(
            check_results=request.check_results,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            verbose=False,  # API调用时不输出详细信息
            output_file=output_file
        )
        
        result = {
            "success": True,
            "recheck_results": recheck_results,
            "report_file": output_file
        }
        
        # 读取报告文件内容
        import os
        report_path = os.path.join(os.getcwd(), output_file)
        if os.path.exists(report_path):
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    result["report_content"] = f.read()
                logging.info(f"报告文件已生成: {report_path}")
            except Exception as e:
                logging.error(f"读取报告文件失败: {e}")
                result["report_error"] = f"读取报告文件失败: {str(e)}"
        else:
            logging.warning(f"报告文件不存在: {report_path}")
            result["report_error"] = f"报告文件不存在: {report_path}"
        
        return result
    except Exception as e:
        logging.error(f"复检失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"复检失败: {str(e)}")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

