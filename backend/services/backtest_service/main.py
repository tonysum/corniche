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

from backtrade import StandardBacktest
from smartmoney import SmartMoneyBacktest
from hm1 import BuySurgeBacktest
from backtrade4 import Backtrade4Backtest
from services.shared.config import BACKTEST_SERVICE_PORT, ALLOWED_ORIGINS

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
            "Backtrade4回测": "/api/backtest/backtrade4",
            "健康检查": "/api/health"
        }
    }


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

