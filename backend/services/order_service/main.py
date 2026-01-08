"""
订单服务 (Order Service)
端口: 8003

职责:
- 订单价格计算
- 建仓价格、止损价格、止盈价格计算
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from decimal import Decimal, ROUND_HALF_UP
import logging

from order import calculate_short_exit_price, calculate_long_exit_price
from services.shared.config import ORDER_SERVICE_PORT, ALLOWED_ORIGINS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="订单服务",
    description="提供订单价格计算API",
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


class OrderCalculateRequest(BaseModel):
    """订单计算请求模型"""
    price: float = Field(description="当前价格")
    entry_pct_chg: float = Field(description="建仓涨幅（百分比，如4表示4%）")
    loss_threshold: float = Field(description="止损阈值（百分比，如1.9表示1.9%）")
    profit_threshold: float = Field(description="止盈阈值（百分比，如4表示4%）")
    order_type: str = Field(description="订单类型：'short'（做空）或 'long'（做多）")


@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "service": "订单服务",
        "version": "1.0.0",
        "port": ORDER_SERVICE_PORT,
        "docs": "/docs",
        "endpoints": {
            "计算订单价格": "/api/calculate-order",
            "健康检查": "/api/health"
        }
    }


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


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "订单服务",
        "port": ORDER_SERVICE_PORT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORDER_SERVICE_PORT)

