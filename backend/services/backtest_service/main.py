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

from backtrade import simulate_trading
from smartmoney import simulate_trading as simulate_smartmoney_trading
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


class SmartMoneyBacktestRequest(BaseModel):
    """聪明钱回测请求模型"""
    start_date: str = Field(description="开始日期（格式: YYYY-MM-DD）")
    end_date: str = Field(description="结束日期（格式: YYYY-MM-DD）")


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
    
    注意：聪明钱策略使用全局配置参数，不支持自定义参数
    """
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 运行聪明钱回测（同步执行，因为需要返回结果）
        result = simulate_smartmoney_trading(
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

