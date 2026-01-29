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
from datetime import datetime
from typing import Optional
import logging
from sqlalchemy import text

from order import calculate_short_exit_price, calculate_long_exit_price
from services.shared.config import ORDER_SERVICE_PORT, ALLOWED_ORIGINS, PG_DB, PG_HOST
from db import engine

# 引入实盘交易模块
from real_trader import RealTimeBuySurgeStrategy
from binance_api import BinanceAPI

# 初始化实盘策略单例
trader_bot = RealTimeBuySurgeStrategy()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="订单与交易服务",
    description="提供订单计算、实盘交易与机器人控制API",
    version="1.1.0"
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

class TradeOrderRequest(BaseModel):
    """实盘下单请求模型"""
    symbol: str = Field(description="交易对 (e.g. BTCUSDT)")
    side: str = Field(description="方向: BUY 或 SELL")
    order_type: str = Field(default="MARKET", description="类型: MARKET 或 LIMIT")
    quantity: float = Field(description="数量 (币的数量)")
    price: float = Field(default=None, description="价格 (限价单必填)")

class ClosePositionRequest(BaseModel):
    """平仓请求模型"""
    symbol: str = Field(description="交易对")

@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "service": "订单与交易服务",
        "version": "1.1.0",
        "port": ORDER_SERVICE_PORT,
        "docs": "/docs",
        "endpoints": {
            "计算订单价格": "/api/calculate-order",
            "实盘-余额": "/api/account/balance",
            "实盘-持仓": "/api/account/positions",
            "实盘-下单": "/api/trade/order",
            "实盘-平仓": "/api/trade/close-position",
            "机器人-状态": "/api/bot/status",
            "机器人-启动": "/api/bot/start",
            "机器人-停止": "/api/bot/stop",
            "数据库统计": "/api/database-stats",
            "健康检查": "/api/health"
        }
    }


# === 实盘账户接口 ===

@app.get("/api/account/balance")
async def get_balance():
    """获取 USDT 可用余额"""
    try:
        balance = trader_bot.api.get_account_balance()
        return {"asset": "USDT", "available_balance": balance}
    except Exception as e:
        logging.error(f"获取余额失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/account/positions")
async def get_positions():
    """获取当前持仓"""
    try:
        # 获取所有持仓
        positions = trader_bot.api.get_position_risk()
        # 过滤掉数量为0的持仓
        active_positions = [
            p for p in positions 
            if float(p.get('positionAmt', 0)) != 0
        ]
        return active_positions
    except Exception as e:
        logging.error(f"获取持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/account/open-orders")
async def get_open_orders(symbol: Optional[str] = None):
    """获取当前挂单"""
    try:
        orders = trader_bot.api.get_open_orders(symbol=symbol)
        return orders
    except Exception as e:
        logging.error(f"获取挂单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === 实盘交易接口 ===

@app.post("/api/trade/order")
async def place_order(request: TradeOrderRequest):
    """发送实盘订单"""
    try:
        logging.info(f"收到下单请求: {request}")
        response = trader_bot.api.post_order(
            symbol=request.symbol,
            side=request.side,
            ord_type=request.order_type,
            quantity=request.quantity,
            price=request.price
        )
        return response
    except Exception as e:
        logging.error(f"下单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/trade/order")
async def cancel_order(symbol: str, order_id: int):
    """撤销订单"""
    try:
        response = trader_bot.api.cancel_order(symbol=symbol, order_id=order_id)
        return response
    except Exception as e:
        logging.error(f"撤单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trade/close-position")
async def close_position_api(request: ClosePositionRequest):
    """一键平仓 (市价全平)"""
    try:
        # 使用 binance_api 增强版的自动平仓功能
        response = trader_bot.api.post_order(
            symbol=request.symbol,
            side="SELL", # 占位，会自动根据持仓判断
            ord_type="MARKET",
            quantity=0,
            close_position=True
        )
        
        # 3. 如果机器人在管理该币种，移除管理状态
        if request.symbol in trader_bot.positions:
            logging.info(f"手动平仓 {request.symbol}，移除机器人管理状态")
            del trader_bot.positions[request.symbol]
            trader_bot.save_state()
            
        return response
    except Exception as e:
        logging.error(f"平仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === 机器人控制接口 ===

@app.get("/api/bot/status")
async def get_bot_status():
    """获取机器人状态"""
    return trader_bot.get_status()

@app.post("/api/bot/start")
async def start_bot():
    """启动机器人"""
    try:
        trader_bot.start()
        return {"status": "started", "message": "机器人已启动"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/stop")
async def stop_bot():
    """停止机器人"""
    try:
        trader_bot.stop()
        return {"status": "stopped", "message": "机器人已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bot/logs")
async def get_bot_logs(limit: int = 50):
    """获取机器人日志"""
    try:
        log_path = Path("real_trading.log")
        if not log_path.exists():
            return {"logs": []}
            
        # 读取最后 N 行
        with open(log_path, "r") as f:
            lines = f.readlines()
            return {"logs": lines[-limit:]}
    except Exception as e:
        logging.error(f"获取日志失败: {e}")
        return {"logs": []}


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
        "service": "订单服务",
        "port": ORDER_SERVICE_PORT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORDER_SERVICE_PORT)

