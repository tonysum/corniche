"""
回测服务 (Backtest Service)
端口: 8002

职责:
- 交易策略回测
- 回测结果计算和统计
- 回测历史记录管理
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging
from sqlalchemy import text

from backtrade import StandardBacktest
from smartmoney import SmartMoneyBacktest
from hm1 import BuySurgeBacktest
from backtrade4 import Backtrade4Backtest
from hm20260121 import BuySurgeBacktest as BuySurgeBacktestHourly
from hm1sy20260125 import BuySurgeBacktest as BuySurgeBacktestV2
from hm_20260126 import BuySurgeBacktest as BuySurgeBacktestV3
from services.shared.config import BACKTEST_SERVICE_PORT, ALLOWED_ORIGINS, PG_DB, PG_HOST
from db import engine
import pandas as pd
import numpy as np

# 导入分析函数
from jcfx20260129 import analyze_top_gainer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="回测服务",
    description="提供交易策略回测API",
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


class BacktestRequest(BaseModel):
    """回测请求模型"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: float = Field(default=10000.0, description="初始资金（USDT）")
    leverage: int = Field(default=20, description="杠杆倍数")
    profit_threshold: float = Field(default=0.065, description="止盈阈值（小数，如0.065表示6.5%）")
    loss_threshold: float = Field(default=0.019, description="止损阈值（小数，如0.019表示1.9%）")
    position_size_ratio: float = Field(default=0.1, description="每次建仓使用的资金比例（小数，如0.1表示10%）")
    min_pct_chg: float = Field(default=0.0, description="最小涨幅要求（小数，如0.0表示0%）")
    delay_entry: bool = Field(default=False, description="是否启用延迟入场")
    delay_hours: int = Field(default=12, description="延迟入场小时数（仅在delay_entry=True时有效）")


@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "service": "回测服务",
        "version": "1.0.0",
        "port": BACKTEST_SERVICE_PORT,
        "docs": "/docs",
        "endpoints": {
            "运行回测": "/api/backtest",
            "聪明钱回测": "/api/backtest/smartmoney",
            "买量暴涨回测": "/api/backtest/buy-surge",
            "买量暴涨回测(小时线优化版)": "/api/backtest/buy-surge-hourly",
            "买量暴涨回测(V2-PostgreSQL版)": "/api/backtest/buy-surge-v2",
            "买量暴涨回测(V3-最新版)": "/api/backtest/buy-surge-v3",
            "Backtrade4回测": "/api/backtest/backtrade4",
            "数据库统计": "/api/database-stats",
            "健康检查": "/api/health"
        }
    }


@app.options("/api/backtest")
async def options_backtest():
    """处理 CORS 预检请求"""
    return {"message": "OK"}

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
        
        # 创建回测实例并运行回测
        backtest = StandardBacktest()
        result = backtest.run_backtest(
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


class SmartMoneyBacktestRequest(BaseModel):
    """聪明钱回测请求模型"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: Optional[float] = Field(default=None, description="初始资金（USDT），默认10000")
    enable_dynamic_leverage: Optional[bool] = Field(default=None, description="是否启用动态杠杆策略，默认True")
    enable_long_trade: Optional[bool] = Field(default=None, description="是否允许做多，默认True")
    trade_direction: Optional[str] = Field(default=None, description="交易方向: 'short'/'long'/'auto'，默认'auto'")
    enable_volume_position_sizing: Optional[bool] = Field(default=None, description="是否启用成交额分级仓位，默认True")
    enable_risk_control: Optional[bool] = Field(default=None, description="是否启用实盘风控检查，默认True")
    position_size_ratio: Optional[float] = Field(default=None, description="基础仓位比例（小数，如0.1表示10%），默认0.1")
    min_pct_chg: Optional[float] = Field(default=None, description="最小涨幅要求（小数，如0.25表示25%），默认0.25")


@app.post("/api/backtest/smartmoney")
async def run_smartmoney_backtest(request: SmartMoneyBacktestRequest):
    """
    运行聪明钱策略回测
    
    聪明钱策略特点：
    - 动态杠杆策略：根据入场涨幅动态调整杠杆、止盈、止损
    - 双向交易模式：支持做多和做空
    - 巨鲸数据分析：结合巨鲸多空比决定交易方向
    - 成交额分级仓位：根据24h成交额动态调整仓位大小
    - 入场等待机制：等待开盘价上涨一定幅度后再建仓
    - 实盘风控系统：基于币安期货API获取实时市场情绪数据
    
    支持自定义参数，如果不提供则使用默认值
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 创建回测实例
        backtest = SmartMoneyBacktest()
        
        # 如果提供了参数，更新回测实例的参数
        if request.initial_capital is not None:
            backtest.initial_capital = request.initial_capital
            backtest.capital = request.initial_capital
        
        if request.enable_dynamic_leverage is not None:
            backtest.enable_dynamic_leverage = request.enable_dynamic_leverage
        
        if request.enable_long_trade is not None:
            backtest.enable_long_trade = request.enable_long_trade
        
        if request.trade_direction is not None:
            backtest.trade_direction = request.trade_direction
        
        if request.enable_volume_position_sizing is not None:
            backtest.enable_volume_position_sizing = request.enable_volume_position_sizing
        
        if request.enable_risk_control is not None:
            backtest.enable_risk_control = request.enable_risk_control
        
        if request.position_size_ratio is not None:
            backtest.position_size_ratio = request.position_size_ratio
        
        if request.min_pct_chg is not None:
            backtest.min_pct_chg = request.min_pct_chg
        
        # 运行聪明钱回测
        result = backtest.run_backtest(
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        if result is None:
            raise HTTPException(status_code=400, detail="回测失败：未找到交易数据或没有交易记录")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"聪明钱回测失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"聪明钱回测失败: {str(e)}")


class BuySurgeBacktestRequest(BaseModel):
    """买量暴涨策略回测请求模型"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: Optional[float] = Field(default=None, description="初始资金（USDT），默认10000")
    leverage: Optional[float] = Field(default=None, description="杠杆倍数，默认4倍")
    position_size_ratio: Optional[float] = Field(default=None, description="单次建仓占资金比例（小数，如0.05表示5%），默认0.05")
    buy_surge_threshold: Optional[float] = Field(default=None, description="买量暴涨阈值倍数（如20.0表示20倍），默认20.0")
    take_profit_pct: Optional[float] = Field(default=None, description="止盈比例（小数，如0.20表示20%），默认0.20")
    add_position_trigger_pct: Optional[float] = Field(default=None, description="补仓触发比例（负数，如-0.18表示-18%），默认-0.18")
    stop_loss_pct: Optional[float] = Field(default=None, description="止损比例（负数，如-0.18表示-18%），默认-0.18")
    max_hold_hours: Optional[int] = Field(default=None, description="最大持仓小时数，默认72小时（3天）")
    wait_timeout_hours: Optional[int] = Field(default=None, description="等待超时时间（小时），默认48小时")


@app.post("/api/backtest/buy-surge")
async def run_buy_surge_backtest(request: BuySurgeBacktestRequest):
    """
    运行买量暴涨策略回测
    
    买量暴涨策略特点：
    - 信号识别：扫描所有USDT交易对，寻找当日主动买量 vs 昨日主动买量 >= 阈值（默认20倍）
    - 信号过滤：检查信号触发前1小时涨幅（5%≤涨幅≤48.5%）
    - 等待回调策略：根据买量倍数动态调整等待回调幅度（3%-6%）
    - 动态止盈：基于建仓后2小时的价格表现动态调整止盈阈值（20%-30%）
    - 补仓机制：价格下跌18%时补仓，重新计算平均成本
    - 快进快出：最大持仓72小时（3天）强制平仓
    
    支持自定义参数，如果不提供则使用默认值
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 创建回测实例
        backtest = BuySurgeBacktest()
        
        # 如果提供了参数，更新回测实例的参数
        if request.initial_capital is not None:
            backtest.initial_capital = request.initial_capital
            backtest.capital = request.initial_capital
        
        if request.leverage is not None:
            backtest.leverage = request.leverage
        
        if request.position_size_ratio is not None:
            backtest.position_size_ratio = request.position_size_ratio
        
        if request.buy_surge_threshold is not None:
            backtest.buy_surge_threshold = request.buy_surge_threshold
        
        if request.take_profit_pct is not None:
            backtest.take_profit_pct = request.take_profit_pct
        
        if request.add_position_trigger_pct is not None:
            backtest.add_position_trigger_pct = request.add_position_trigger_pct
        
        if request.stop_loss_pct is not None:
            backtest.stop_loss_pct = request.stop_loss_pct
        
        if request.max_hold_hours is not None:
            backtest.max_hold_hours = request.max_hold_hours
        
        if request.wait_timeout_hours is not None:
            backtest.wait_timeout_hours = request.wait_timeout_hours
        
        # 运行回测
        backtest.run_backtest(request.start_date, request.end_date)
        
        # 计算统计信息
        total_trades = len(backtest.trade_records)
        winning_trades = len([t for t in backtest.trade_records if t['pnl'] > 0])
        losing_trades = len([t for t in backtest.trade_records if t['pnl'] < 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        final_capital = backtest.capital
        total_return = (final_capital - backtest.initial_capital) / backtest.initial_capital * 100
        
        # 计算最大回撤
        max_capital = backtest.initial_capital
        max_drawdown = 0
        for record in backtest.daily_capital:
            max_capital = max(max_capital, record['capital'])
            drawdown = (max_capital - record['capital']) / max_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 生成CSV报告
        backtest.generate_trade_csv_report()
        
        # 返回结果
        return {
            "status": "success",
            "strategy": "买量暴涨策略",
            "start_date": request.start_date,
            "end_date": request.end_date,
            "statistics": {
                "initial_capital": backtest.initial_capital,
                "final_capital": final_capital,
                "total_return": round(total_return, 2),
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 1),
                "max_drawdown": round(max_drawdown, 2)
            },
            "parameters": {
                "leverage": backtest.leverage,
                "position_size_ratio": backtest.position_size_ratio,
                "buy_surge_threshold": backtest.buy_surge_threshold,
                "take_profit_pct": backtest.take_profit_pct,
                "add_position_trigger_pct": backtest.add_position_trigger_pct,
                "stop_loss_pct": backtest.stop_loss_pct,
                "max_hold_hours": backtest.max_hold_hours,
                "wait_timeout_hours": backtest.wait_timeout_hours
            },
            "trade_records": backtest.trade_records[:50],  # 返回前50条交易记录
            "daily_capital": backtest.daily_capital  # 每日资金记录
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"买量暴涨回测失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"买量暴涨回测失败: {str(e)}")


class Backtrade4BacktestRequest(BaseModel):
    """Backtrade4回测请求模型"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: Optional[float] = Field(default=None, description="初始资金（USDT），默认10000")
    enable_dynamic_leverage: Optional[bool] = Field(default=None, description="是否启用动态杠杆策略，默认True")
    enable_long_trade: Optional[bool] = Field(default=None, description="是否允许做多，默认True")
    trade_direction: Optional[str] = Field(default=None, description="交易方向: 'short'/'long'/'auto'，默认'auto'")
    enable_volume_position_sizing: Optional[bool] = Field(default=None, description="是否启用成交额分级仓位，默认True")
    enable_risk_control: Optional[bool] = Field(default=None, description="是否启用实盘风控检查，默认False")
    position_size_ratio: Optional[float] = Field(default=None, description="基础仓位比例（小数，如0.1表示10%），默认0.1")
    min_pct_chg: Optional[float] = Field(default=None, description="最小涨幅要求（小数，如0.25表示25%），默认0.25")


@app.post("/api/backtest/backtrade4")
async def run_backtrade4_backtest(request: Backtrade4BacktestRequest):
    """
    运行Backtrade4策略回测
    
    Backtrade4策略特点：
    - 动态杠杆策略：根据入场涨幅动态调整杠杆、止盈、止损
    - 双向交易模式：支持做多和做空两种交易方向
    - 巨鲸数据分析：结合巨鲸多空比决定交易方向
    - 成交额分级仓位：根据24h成交额动态调整仓位大小
    - 入场等待机制：等待开盘价上涨一定幅度后再建仓
    - 实盘风控系统：基于币安期货API获取实时市场情绪数据
    - 逐小时检查：使用小时K线数据逐小时检查止盈止损条件
    
    支持自定义参数，如果不提供则使用默认值
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 创建回测实例
        backtest = Backtrade4Backtest()
        
        # 如果提供了参数，更新回测实例的参数
        if request.initial_capital is not None:
            backtest.initial_capital = request.initial_capital
        
        if request.enable_dynamic_leverage is not None:
            backtest.enable_dynamic_leverage = request.enable_dynamic_leverage
        
        if request.enable_long_trade is not None:
            backtest.enable_long_trade = request.enable_long_trade
        
        if request.trade_direction is not None:
            backtest.trade_direction = request.trade_direction
        
        if request.enable_volume_position_sizing is not None:
            backtest.enable_volume_position_sizing = request.enable_volume_position_sizing
        
        if request.enable_risk_control is not None:
            backtest.enable_risk_control = request.enable_risk_control
        
        if request.position_size_ratio is not None:
            backtest.position_size_ratio = request.position_size_ratio
        
        if request.min_pct_chg is not None:
            backtest.min_pct_chg = request.min_pct_chg
        
        # 运行Backtrade4回测
        result = backtest.run_backtest(
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        if result is None:
            raise HTTPException(status_code=400, detail="回测失败：未找到交易数据或没有交易记录")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Backtrade4回测失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Backtrade4回测失败: {str(e)}")


class BuySurgeHourlyBacktestRequest(BaseModel):
    """买量暴涨策略回测请求模型（小时线优化版）"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: float = Field(default=10000.0, description="初始资金（USDT），默认10000")
    leverage: float = Field(default=4.0, description="杠杆倍数，默认4倍")
    position_size_ratio: float = Field(default=0.06, description="单次建仓占资金比例（小数，如0.06表示6%），默认0.06")
    buy_surge_threshold: float = Field(default=2.2, description="买量暴涨阈值倍数（如2.2表示2.2倍），默认2.2")
    buy_surge_max: float = Field(default=3.0, description="买量暴涨倍数上限（默认接受2-3倍），默认3.0")
    take_profit_pct: float = Field(default=0.33, description="基础止盈比例（小数，如0.33表示33%），默认0.33")
    add_position_trigger_pct: float = Field(default=-0.18, description="补仓触发比例（负数，如-0.18表示-18%），默认-0.18")
    stop_loss_pct: float = Field(default=-0.18, description="止损比例（负数，如-0.18表示-18%），默认-0.18")
    max_hold_hours: int = Field(default=72, description="最大持仓小时数，默认72小时（3天）")
    wait_timeout_hours: int = Field(default=48, description="等待超时时间（小时），默认48小时")
    enable_trader_filter: bool = Field(default=True, description="是否启用顶级交易者过滤，默认True")
    min_account_ratio: float = Field(default=0.70, description="最小账户多空比（信号筛选），默认0.70")


@app.post("/api/backtest/buy-surge-hourly")
async def run_buy_surge_hourly_backtest(request: BuySurgeHourlyBacktestRequest):
    """
    运行买量暴涨策略回测（小时线优化版）
    
    买量暴涨策略特点（小时线优化版）：
    - 信号识别：扫描所有USDT交易对，寻找某小时主动买量 >= 昨日平均小时买量 × 阈值（默认2倍）
    - 信号过滤：检查信号触发前1小时涨幅（5%≤涨幅≤48.5%）
    - 顶级交易者风控：基于Binance顶级交易者持仓数据筛选信号（账户多空比 >= 0.70）
    - 等待回调策略：根据买量倍数动态调整等待回调幅度（2-3倍→15%，3-5倍→4%，5-10倍→3%）
    - 动态止盈：基于建仓后2小时和12小时的价格表现动态调整止盈阈值（11%-30%）
    - 补仓机制：价格下跌18%时虚拟补仓，调整止损/止盈基准
    - 24小时弱势平仓：24小时涨幅 < 8%时强制平仓
    - 快进快出：最大持仓72小时（3天）强制平仓
    
    支持自定义参数，如果不提供则使用默认值
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 创建回测实例
        logging.info("🔧 正在创建回测实例...")
        backtest = BuySurgeBacktestHourly()
        logging.info("✅ 回测实例创建成功")
        
        # 设置回测参数（使用请求中的值，如果没有提供则使用默认值）
        logging.info("⚙️  正在设置回测参数...")
        backtest.initial_capital = request.initial_capital
        backtest.capital = request.initial_capital
        backtest.leverage = request.leverage
        backtest.position_size_ratio = request.position_size_ratio
        backtest.buy_surge_threshold = request.buy_surge_threshold
        backtest.buy_surge_max = request.buy_surge_max
        backtest.take_profit_pct = request.take_profit_pct
        backtest.add_position_trigger_pct = request.add_position_trigger_pct
        backtest.stop_loss_pct = request.stop_loss_pct
        backtest.max_hold_hours = request.max_hold_hours
        backtest.wait_timeout_hours = request.wait_timeout_hours
        backtest.enable_trader_filter = request.enable_trader_filter
        backtest.min_account_ratio = request.min_account_ratio
        logging.info("✅ 参数设置完成")
        
        # 运行回测
        logging.info("🚀 开始运行回测...")
        backtest.run_backtest(request.start_date, request.end_date)
        logging.info("✅ 回测运行完成")
        
        # 🆕 生成完整报告（输出详细信息到日志）
        backtest.generate_report()
        
        # 计算统计信息
        total_trades = len(backtest.trade_records)
        winning_trades = len([t for t in backtest.trade_records if t['pnl'] > 0])
        losing_trades = len([t for t in backtest.trade_records if t['pnl'] < 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        final_capital = backtest.capital
        total_return = (final_capital - backtest.initial_capital) / backtest.initial_capital * 100 if backtest.initial_capital > 0 else 0
        
        # 计算最大回撤
        max_capital = backtest.initial_capital
        max_drawdown = 0
        for record in backtest.daily_capital:
            max_capital = max(max_capital, record['capital'])
            drawdown = (max_capital - record['capital']) / max_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 生成CSV报告
        backtest.generate_trade_csv_report()
        
        # 🆕 计算详细统计信息（与直接运行脚本时相同）
        closed_trades = [t for t in backtest.trade_records if t.get('exit_reason') and t['exit_reason'] != 'holding']
        
        # 区分高止盈和普通止盈（使用tp_pct_used字段）
        trades_with_high_tp = [t for t in closed_trades if t.get('tp_pct_used') and t['tp_pct_used'] > 0.10]
        trades_with_normal_tp = [t for t in closed_trades if t.get('tp_pct_used') and t['tp_pct_used'] <= 0.10]
        
        high_tp_triggered = len(trades_with_high_tp)
        normal_tp_count = len(trades_with_normal_tp)
        total_closed = len(closed_trades)
        
        # 动态止盈成功率分析
        high_tp_stats = {}
        if high_tp_triggered > 0:
            high_tp_success = len([t for t in trades_with_high_tp if t.get('exit_reason') == 'take_profit'])
            high_tp_profit = sum([t['pnl'] for t in trades_with_high_tp])
            high_tp_avg_profit = high_tp_profit / high_tp_triggered
            high_tp_stats = {
                "triggered_count": high_tp_triggered,
                "success_count": high_tp_success,
                "success_rate": round(high_tp_success / high_tp_triggered * 100, 1) if high_tp_triggered > 0 else 0,
                "total_profit": round(high_tp_profit, 2),
                "avg_profit": round(high_tp_avg_profit, 2)
            }
        
        # 普通止盈统计
        normal_tp_stats = {}
        if normal_tp_count > 0:
            normal_tp_profit = sum([t['pnl'] for t in trades_with_normal_tp])
            normal_tp_avg = normal_tp_profit / normal_tp_count
            normal_tp_stats = {
                "triggered_count": normal_tp_count,
                "total_profit": round(normal_tp_profit, 2),
                "avg_profit": round(normal_tp_avg, 2)
            }
        
        # 止损、超时和强制平仓统计
        stop_loss_trades = [t for t in closed_trades if t.get('exit_reason') == 'stop_loss']
        stop_loss_trader_trades = [t for t in closed_trades if t.get('exit_reason') == 'stop_loss_trader']
        max_hold_trades = [t for t in closed_trades if t.get('exit_reason') == 'max_hold_time']
        force_close_trades = [t for t in closed_trades if t.get('exit_reason') == 'force_close']
        
        stop_loss_stats = {}
        if stop_loss_trades:
            stop_loss_total = sum([t['pnl'] for t in stop_loss_trades])
            stop_loss_stats = {
                "count": len(stop_loss_trades),
                "percentage": round(len(stop_loss_trades) / total_closed * 100, 1) if total_closed > 0 else 0,
                "total_loss": round(stop_loss_total, 2)
            }
        
        stop_loss_trader_stats = {}
        if stop_loss_trader_trades:
            stop_loss_trader_total = sum([t['pnl'] for t in stop_loss_trader_trades])
            stop_loss_trader_stats = {
                "count": len(stop_loss_trader_trades),
                "percentage": round(len(stop_loss_trader_trades) / total_closed * 100, 1) if total_closed > 0 else 0,
                "total_loss": round(stop_loss_trader_total, 2),
                "avg_loss": round(stop_loss_trader_total / len(stop_loss_trader_trades), 2) if stop_loss_trader_trades else 0
            }
        
        max_hold_stats = {}
        if max_hold_trades:
            max_hold_profit = sum([t['pnl'] for t in max_hold_trades])
            max_hold_positive = len([t for t in max_hold_trades if t['pnl'] > 0])
            max_hold_stats = {
                "count": len(max_hold_trades),
                "percentage": round(len(max_hold_trades) / total_closed * 100, 1) if total_closed > 0 else 0,
                "positive_count": max_hold_positive,
                "negative_count": len(max_hold_trades) - max_hold_positive,
                "total_pnl": round(max_hold_profit, 2)
            }
        
        force_close_stats = {}
        if force_close_trades:
            force_close_profit = sum([t['pnl'] for t in force_close_trades])
            force_close_positive = len([t for t in force_close_trades if t['pnl'] > 0])
            force_close_stats = {
                "count": len(force_close_trades),
                "percentage": round(len(force_close_trades) / total_closed * 100, 1) if total_closed > 0 else 0,
                "positive_count": force_close_positive,
                "negative_count": len(force_close_trades) - force_close_positive,
                "total_pnl": round(force_close_profit, 2)
            }
        
        # 返回结果
        return {
            "status": "success",
            "strategy": "买量暴涨策略（小时线优化版）",
            "start_date": request.start_date,
            "end_date": request.end_date,
            "statistics": {
                "initial_capital": backtest.initial_capital,
                "final_capital": final_capital,
                "total_return": round(total_return, 2),
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 1),
                "max_drawdown": round(max_drawdown, 2)
            },
            "detailed_statistics": {
                "take_profit_stats": {
                    "total_closed": total_closed,
                    "high_tp": {
                        "count": high_tp_triggered,
                        "percentage": round(high_tp_triggered / total_closed * 100, 1) if total_closed > 0 else 0,
                        **high_tp_stats
                    },
                    "normal_tp": {
                        "count": normal_tp_count,
                        "percentage": round(normal_tp_count / total_closed * 100, 1) if total_closed > 0 else 0,
                        **normal_tp_stats
                    },
                    "other_exits": {
                        "count": total_closed - high_tp_triggered - normal_tp_count,
                        "percentage": round((total_closed - high_tp_triggered - normal_tp_count) / total_closed * 100, 1) if total_closed > 0 else 0
                    }
                },
                "stop_loss": stop_loss_stats,
                "stop_loss_trader": stop_loss_trader_stats,
                "max_hold_timeout": max_hold_stats,
                "force_close": force_close_stats
            },
            "parameters": {
                "leverage": backtest.leverage,
                "position_size_ratio": backtest.position_size_ratio,
                "buy_surge_threshold": backtest.buy_surge_threshold,
                "buy_surge_max": backtest.buy_surge_max,
                "take_profit_pct": backtest.take_profit_pct,
                "add_position_trigger_pct": backtest.add_position_trigger_pct,
                "stop_loss_pct": backtest.stop_loss_pct,
                "max_hold_hours": backtest.max_hold_hours,
                "wait_timeout_hours": backtest.wait_timeout_hours,
                "enable_trader_filter": backtest.enable_trader_filter,
                "min_account_ratio": backtest.min_account_ratio
            },
            "trade_records": backtest.trade_records[:50],  # 返回前50条交易记录
            "daily_capital": backtest.daily_capital,  # 每日资金记录
            "signal_records": backtest.signal_records,  # 🆕 返回所有信号记录（包含发现但未成交的信号，包含账户多空比信息）
            "csv_filename": getattr(backtest, 'csv_filename', None)  # CSV文件路径
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"买量暴涨回测（小时线优化版）失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"买量暴涨回测（小时线优化版）失败: {str(e)}")





@app.get("/api/jcfx-analysis")
async def get_jcfx_analysis(date: Optional[str] = None):
    """
    获取涨幅第一做空分析结果
    
    Args:
        date: 分析日期（可选），格式: YYYY-MM-DD
    """
    try:
        # 运行分析
        result = analyze_top_gainer(target_date=date)
        
        if result is None:
            raise HTTPException(status_code=404, detail="未找到分析结果或该日期没有数据")
            
        # 展平结果以便前端使用
        flat_result = {
            "analysis_date": result.get("analysis_date"),
            "timestamp": result.get("timestamp"),
            **result.get("signal", {})
        }
            
        # 确保数值可以JSON序列化
        cleaned_result = {}
        for k, v in flat_result.items():
            if isinstance(v, (pd.Timestamp, datetime)):
                cleaned_result[k] = str(v)
            elif isinstance(v, (np.integer, np.floating)):
                cleaned_result[k] = v.item()
            elif pd.isna(v):
                cleaned_result[k] = None
            else:
                cleaned_result[k] = v
                
        return cleaned_result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


class BuySurgeV2BacktestRequest(BaseModel):
    """买量暴涨策略回测请求模型 (V2 - PostgreSQL 优化版)"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: float = Field(default=10000.0, description="初始资金（USDT），默认10000")
    leverage: float = Field(default=4.0, description="杠杆倍数，默认4倍")
    position_size_ratio: float = Field(default=0.01, description="单次建仓占资金比例（小数，如0.01表示1%），默认0.01")
    buy_surge_threshold: float = Field(default=2.0, description="买量暴涨阈值倍数（如2.0表示2倍），默认2.0")
    buy_surge_max: float = Field(default=10.0, description="买量暴涨倍数上限（默认接受2-10倍），默认10.0")
    take_profit_pct: float = Field(default=0.33, description="基础止盈比例（小数，如0.33表示33%），默认0.33")
    add_position_trigger_pct: float = Field(default=-0.18, description="补仓触发比例（负数，如-0.18表示-18%），默认-0.18")
    stop_loss_pct: float = Field(default=-0.18, description="止损比例（负数，如-0.18表示-18%），默认-0.18")
    max_hold_hours: int = Field(default=72, description="最大持仓小时数，默认72小时（3天）")
    wait_timeout_hours: int = Field(default=37, description="等待超时时间（小时），默认37小时")
    enable_trader_filter: bool = Field(default=True, description="是否启用顶级交易者过滤，默认True")
    min_account_ratio: float = Field(default=0.84, description="最小账户多空比（信号筛选），默认0.84")


@app.post("/api/backtest/buy-surge-v2")
async def run_buy_surge_v2_backtest(request: BuySurgeV2BacktestRequest):
    """
    运行买量暴涨策略回测 (V2 - PostgreSQL 优化版)
    
    买量暴涨策略特点 (V2)：
    - PostgreSQL 优化：完全适配 PostgreSQL 数据库架构，表名动态映射 (K1d/K1h/K5m)
    - 信号识别：扫描所有交易对，寻找某小时买量暴涨信号
    - 顶级交易者风控：基于账户多空比筛选信号，默认阈值 0.84
    - 动态止盈：基于 2h/12h 价格表现动态调整止盈 (11%-33%)
    - 虚拟补仓机制：价格下跌触发虚拟补仓，调整止盈止损基准而不实际占用额外本金
    - 资金管理优化：单笔 1% 仓位，并发上限 20，追求极致复利
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 创建回测实例
        logging.info("🔧 正在创建 BuySurgeV2 回测实例...")
        backtest = BuySurgeBacktestV2()
        logging.info("✅ BuySurgeV2 回测实例创建成功")
        
        # 设置回测参数
        backtest.initial_capital = request.initial_capital
        backtest.capital = request.initial_capital
        backtest.leverage = request.leverage
        backtest.position_size_ratio = request.position_size_ratio
        backtest.buy_surge_threshold = request.buy_surge_threshold
        backtest.buy_surge_max = request.buy_surge_max
        backtest.take_profit_pct = request.take_profit_pct
        backtest.add_position_trigger_pct = request.add_position_trigger_pct
        backtest.stop_loss_pct = request.stop_loss_pct
        backtest.max_hold_hours = request.max_hold_hours
        backtest.wait_timeout_hours = request.wait_timeout_hours
        backtest.enable_trader_filter = request.enable_trader_filter
        backtest.min_account_ratio = request.min_account_ratio
        
        # 运行回测
        logging.info(f"🚀 开始运行 BuySurgeV2 回测: {request.start_date} 到 {request.end_date}")
        backtest.run_backtest(request.start_date, request.end_date)
        logging.info("✅ BuySurgeV2 回测运行完成")
        
        # 计算统计信息
        total_trades = len(backtest.trade_records)
        winning_trades = len([t for t in backtest.trade_records if t['pnl'] > 0])
        losing_trades = len([t for t in backtest.trade_records if t['pnl'] < 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        final_capital = backtest.capital
        total_return = (final_capital - backtest.initial_capital) / backtest.initial_capital * 100 if backtest.initial_capital > 0 else 0
        
        # 计算最大回撤
        max_capital = backtest.initial_capital
        max_drawdown = 0
        for record in backtest.daily_capital:
            max_capital = max(max_capital, record['capital'])
            drawdown = (max_capital - record['capital']) / max_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 返回结果
        return {
            "status": "success",
            "strategy": "买量暴涨策略 (V2 - PostgreSQL版)",
            "start_date": request.start_date,
            "end_date": request.end_date,
            "statistics": {
                "initial_capital": backtest.initial_capital,
                "final_capital": final_capital,
                "total_return": round(total_return, 2),
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 1),
                "max_drawdown": round(max_drawdown, 2)
            },
            "parameters": {
                "leverage": backtest.leverage,
                "position_size_ratio": backtest.position_size_ratio,
                "buy_surge_threshold": backtest.buy_surge_threshold,
                "buy_surge_max": backtest.buy_surge_max,
                "take_profit_pct": backtest.take_profit_pct,
                "add_position_trigger_pct": backtest.add_position_trigger_pct,
                "stop_loss_pct": backtest.stop_loss_pct,
                "max_hold_hours": backtest.max_hold_hours,
                "wait_timeout_hours": backtest.wait_timeout_hours,
                "enable_trader_filter": backtest.enable_trader_filter,
                "min_account_ratio": backtest.min_account_ratio
            },
            "trade_records": backtest.trade_records[:100],  # 返回前100条交易记录
            "daily_capital": backtest.daily_capital,
            "signal_records": backtest.signal_records
        }
    except Exception as e:
        logging.error(f"BuySurgeV2 回测失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")


class BuySurgeV3BacktestRequest(BaseModel):
    """买量暴涨策略回测请求模型 (V3 - 最新版)"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")
    initial_capital: float = Field(default=10000.0, description="初始资金（USDT），默认10000")
    leverage: float = Field(default=4.0, description="杠杆倍数，默认4倍")
    position_size_ratio: float = Field(default=0.05, description="单次建仓占资金比例（小数，如0.05表示5%），默认0.05")
    buy_surge_threshold: float = Field(default=2.0, description="买量暴涨阈值倍数（如2.0表示2倍），默认2.0")
    buy_surge_max: float = Field(default=3.0, description="买量暴涨倍数上限（默认接受2-3倍），默认3.0")
    take_profit_pct: float = Field(default=0.33, description="基础止盈比例（小数，如0.33表示33%），默认0.33")
    add_position_trigger_pct: float = Field(default=-0.18, description="补仓触发比例（负数，如-0.18表示-18%），默认-0.18")
    stop_loss_pct: float = Field(default=-0.18, description="止损比例（负数，如-0.18表示-18%），默认-0.18")
    max_hold_hours: int = Field(default=72, description="最大持仓小时数，默认72小时（3天）")
    wait_timeout_hours: int = Field(default=37, description="等待超时时间（小时），默认37小时")
    max_daily_positions: int = Field(default=6, description="并发持仓上限，默认6")
    enable_trader_filter: bool = Field(default=True, description="是否启用顶级交易者过滤，默认True")
    min_account_ratio: float = Field(default=0.84, description="最小账户多空比（信号筛选），默认0.84")
    account_ratio_stop_threshold: float = Field(default=-0.10, description="账户多空比下降止损阈值，默认-0.10")


@app.post("/api/backtest/buy-surge-v3")
async def run_buy_surge_v3_backtest(request: BuySurgeV3BacktestRequest):
    """
    运行买量暴涨策略回测 (V3 - 最新版)
    
    买量暴涨策略特点 (V3)：
    - 最新优化：包含所有最新的策略调整和修复
    - PostgreSQL 优化：完全适配 PostgreSQL 数据库架构
    - 信号识别：扫描所有交易对，寻找某小时买量暴涨信号
    - 顶级交易者风控：基于账户多空比筛选信号，默认阈值 0.84
    - 动态止盈：基于 2h/12h 价格表现动态调整止盈
    - 虚拟补仓机制：价格下跌触发虚拟补仓，调整止盈止损基准
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 创建回测实例
        logging.info("🔧 正在创建 BuySurgeV3 回测实例...")
        backtest = BuySurgeBacktestV3()
        logging.info("✅ BuySurgeV3 回测实例创建成功")
        
        # 设置回测参数
        backtest.initial_capital = request.initial_capital
        backtest.capital = request.initial_capital
        backtest.leverage = request.leverage
        backtest.position_size_ratio = request.position_size_ratio
        backtest.buy_surge_threshold = request.buy_surge_threshold
        backtest.buy_surge_max = request.buy_surge_max
        backtest.take_profit_pct = request.take_profit_pct
        backtest.add_position_trigger_pct = request.add_position_trigger_pct
        backtest.stop_loss_pct = request.stop_loss_pct
        backtest.max_hold_hours = request.max_hold_hours
        backtest.wait_timeout_hours = request.wait_timeout_hours
        backtest.max_daily_positions = request.max_daily_positions
        backtest.enable_trader_filter = request.enable_trader_filter
        backtest.min_account_ratio = request.min_account_ratio
        backtest.account_ratio_stop_threshold = request.account_ratio_stop_threshold
        
        # 运行回测
        logging.info(f"🚀 开始运行 BuySurgeV3 回测: {request.start_date} 到 {request.end_date}")
        backtest.run_backtest(request.start_date, request.end_date)
        logging.info("✅ BuySurgeV3 回测运行完成")
        
        # 计算统计信息
        total_trades = len(backtest.trade_records)
        winning_trades = len([t for t in backtest.trade_records if t['pnl'] > 0])
        losing_trades = len([t for t in backtest.trade_records if t['pnl'] < 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        final_capital = backtest.capital
        total_return = (final_capital - backtest.initial_capital) / backtest.initial_capital * 100 if backtest.initial_capital > 0 else 0
        
        # 计算最大回撤
        max_capital = backtest.initial_capital
        max_drawdown = 0
        for record in backtest.daily_capital:
            max_capital = max(max_capital, record['capital'])
            drawdown = (max_capital - record['capital']) / max_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 生成CSV报告
        csv_filename = backtest.generate_trade_csv_report()
        
        # 返回结果
        return {
            "status": "success",
            "strategy": "买量暴涨策略 (V3 - 最新版)",
            "start_date": request.start_date,
            "end_date": request.end_date,
            "csv_filename": csv_filename,
            "statistics": {
                "initial_capital": backtest.initial_capital,
                "final_capital": final_capital,
                "total_return": round(total_return, 2),
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 1),
                "max_drawdown": round(max_drawdown, 2)
            },
            "parameters": {
                "leverage": backtest.leverage,
                "position_size_ratio": backtest.position_size_ratio,
                "buy_surge_threshold": backtest.buy_surge_threshold,
                "buy_surge_max": backtest.buy_surge_max,
                "take_profit_pct": backtest.take_profit_pct,
                "add_position_trigger_pct": backtest.add_position_trigger_pct,
                "stop_loss_pct": backtest.stop_loss_pct,
                "max_hold_hours": backtest.max_hold_hours,
                "wait_timeout_hours": backtest.wait_timeout_hours,
                "max_daily_positions": backtest.max_daily_positions,
                "enable_trader_filter": backtest.enable_trader_filter,
                "min_account_ratio": backtest.min_account_ratio,
                "account_ratio_stop_threshold": backtest.account_ratio_stop_threshold
            },
            "trade_records": backtest.trade_records[:100],  # 返回前100条交易记录
            "daily_capital": backtest.daily_capital,
            "signal_records": backtest.signal_records
        }
    except Exception as e:
        logging.error(f"BuySurgeV3 回测失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")



@app.get("/api/database-stats", tags=["系统信息"])
async def get_database_stats():
    """获取数据库统计信息"""
    try:
        with engine.connect() as conn:
            # 获取所有表名
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            all_tables = [row[0] for row in result.fetchall()]
            
            # 筛选K线表（以K开头）
            kline_tables = [t for t in all_tables if t.startswith('K')]
            
            # 按 interval 分类统计
            interval_stats = {}
            total_tables = 0
            total_rows = 0
            
            # 常见的 interval 前缀
            intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
            
            for interval in intervals:
                prefix = f'K{interval}'
                interval_tables = [t for t in kline_tables if t.startswith(prefix)]
                
                if interval_tables:
                    table_rows = []
                    interval_total_rows = 0
                    latest_dates = []  # 存储每个表的最新日期
                    
                    # 获取每个表的行数（限制查询数量，避免太慢）
                    for table in interval_tables[:100]:  # 最多查询100个表
                        try:
                            safe_table_name = f'"{table}"'
                            count_result = conn.execute(text(f'SELECT COUNT(*) FROM {safe_table_name}'))
                            row_count = count_result.fetchone()[0]
                            
                            # 获取该表的最新日期
                            latest_date = None
                            try:
                                date_result = conn.execute(text(f'SELECT MAX(trade_date) FROM {safe_table_name}'))
                                latest_date_row = date_result.fetchone()
                                if latest_date_row and latest_date_row[0]:
                                    latest_date = str(latest_date_row[0])
                                    if latest_date:
                                        latest_dates.append(latest_date)
                            except Exception as e:
                                logging.debug(f"获取表 {table} 最新日期失败: {e}")
                            
                            table_rows.append({
                                'table_name': table,
                                'row_count': row_count
                            })
                            interval_total_rows += row_count
                        except Exception as e:
                            logging.warning(f"获取表 {table} 行数失败: {e}")
                            table_rows.append({
                                'table_name': table,
                                'row_count': 0
                            })
                    
                    # 如果有超过100个表，估算剩余表的行数
                    if len(interval_tables) > 100:
                        # 计算平均行数
                        if len(table_rows) > 0:
                            avg_rows = interval_total_rows / len(table_rows)
                            estimated_total = interval_total_rows + (len(interval_tables) - 100) * avg_rows
                        else:
                            estimated_total = interval_total_rows
                    else:
                        estimated_total = interval_total_rows
                    
                    # 计算所有表中最新的日期
                    latest_date_overall = None
                    if latest_dates:
                        # 将日期字符串转换为datetime进行比较
                        try:
                            parsed_dates = []
                            for date_str in latest_dates:
                                if not date_str:
                                    continue
                                try:
                                    # 处理PostgreSQL返回的datetime对象或字符串
                                    if isinstance(date_str, datetime):
                                        parsed_dates.append(date_str)
                                    elif isinstance(date_str, str):
                                        # 尝试解析不同的日期格式
                                        if ' ' in date_str:
                                            parsed_dates.append(datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S'))
                                        else:
                                            parsed_dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                                except Exception as parse_err:
                                    logging.debug(f"解析日期 {date_str} 失败: {parse_err}")
                                    pass
                            
                            if parsed_dates:
                                max_date = max(parsed_dates)
                                # 格式化日期，如果有时间部分则显示完整时间，否则只显示日期
                                if max_date.hour == 0 and max_date.minute == 0 and max_date.second == 0:
                                    latest_date_overall = max_date.strftime('%Y-%m-%d')
                                else:
                                    latest_date_overall = max_date.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logging.debug(f"解析最新日期失败: {e}")
                            # 如果解析失败，使用字符串比较（仅作为后备方案）
                            if latest_dates:
                                latest_date_overall = max([str(d) for d in latest_dates if d])
                    
                    interval_stats[interval] = {
                        'table_count': len(interval_tables),
                        'total_rows': int(estimated_total),
                        'sampled_tables': len(table_rows),
                        'latest_date': latest_date_overall,
                        'tables': table_rows[:20]  # 只返回前20个表的详细信息
                    }
                    
                    total_tables += len(interval_tables)
                    total_rows += int(estimated_total)
            
            # 获取其他表（非K线表）
            other_tables = [t for t in all_tables if not t.startswith('K')]
            other_table_info = []
            other_total_rows = 0
            
            for table in other_tables[:50]:  # 最多查询50个其他表
                try:
                    safe_table_name = f'"{table}"'
                    count_result = conn.execute(text(f'SELECT COUNT(*) FROM {safe_table_name}'))
                    row_count = count_result.fetchone()[0]
                    other_table_info.append({
                        'table_name': table,
                        'row_count': row_count
                    })
                    other_total_rows += row_count
                except Exception as e:
                    logging.warning(f"获取表 {table} 行数失败: {e}")
            
            return {
                "total_tables": total_tables + len(other_tables),
                "total_rows": total_rows + other_total_rows,
                "kline_tables": total_tables,
                "kline_rows": total_rows,
                "by_interval": interval_stats,
                "other_tables": {
                    "count": len(other_tables),
                    "total_rows": other_total_rows,
                    "tables": other_table_info
                },
                "database_name": PG_DB,
                "host": PG_HOST
            }
    except Exception as e:
        logging.error(f"获取数据库统计信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "回测服务",
        "port": BACKTEST_SERVICE_PORT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=BACKTEST_SERVICE_PORT)

