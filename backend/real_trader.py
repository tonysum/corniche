import time
import json
import logging
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from binance_api import BinanceAPI, kline2df

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("real_trading.log"),
        logging.StreamHandler()
    ]
)

class RealTimeBuySurgeStrategy:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RealTimeBuySurgeStrategy, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.api = BinanceAPI()
        self.state_file = Path("trading_state.json")
        self.positions = self.load_state()
        
        # === 策略参数 (与 hm1sy20260125.py V2 保持一致) ===
        self.leverage = 4
        self.position_size_ratio = 0.01  # 1%
        self.buy_surge_threshold = 2.0
        self.buy_surge_max = 3.0
        self.max_positions = 20
        self.min_account_ratio = 0.84
        self.take_profit_pct = 0.33      # 33%
        self.stop_loss_pct = -0.18       # -18%
        self.add_position_trigger_pct = -0.18 # -18% (虚拟补仓)
        self.max_hold_hours = 72
        self.wait_timeout_hours = 37
        
        # 运行时状态
        self.last_scan_hour = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.thread = None
        self._initialized = True

    def start(self):
        """启动策略线程"""
        if self.is_running:
            logging.warning("策略已经在运行中")
            return

        logging.info("启动实盘策略线程...")
        self.is_running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止策略线程"""
        if not self.is_running:
            return

        logging.info("正在停止实盘策略线程...")
        self.is_running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        logging.info("实盘策略线程已停止")

    def get_status(self) -> Dict:
        """获取运行状态"""
        return {
            "is_running": self.is_running,
            "positions_count": len(self.positions),
            "last_scan_hour": self.last_scan_hour,
            "config": {
                "leverage": self.leverage,
                "position_size_ratio": self.position_size_ratio,
                "max_positions": self.max_positions
            }
        }

    def _run_loop(self):
        """后台运行循环"""
        logging.info("实盘交易引擎启动...")
        logging.info(f"配置: 杠杆={self.leverage}x, 仓位={self.position_size_ratio*100}%, 最大持仓={self.max_positions}")
        
        while not self.stop_event.is_set():
            try:
                now = datetime.now()
                
                # 每小时第 2 分钟执行扫描 (给 K 线生成留出 2 分钟缓冲)
                # 避免重复扫描
                if now.minute == 2 and self.last_scan_hour != now.hour:
                    self.scan_market()
                    self.last_scan_hour = now.hour
                
                # 每分钟监控持仓
                self.monitor_positions()
                
                # 休眠 60 秒 (使用 wait 以便能响应 stop 事件)
                self.stop_event.wait(60)
                
            except Exception as e:
                logging.error(f"主循环出错: {e}")
                self.stop_event.wait(60)

    def load_state(self) -> Dict:
        """加载持仓状态"""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                logging.info(f"已加载持仓状态: {len(data)} 个持仓")
                return data
            except Exception as e:
                logging.error(f"加载状态文件失败: {e}")
                return {}
        return {}

    def save_state(self):
        """保存持仓状态"""
        try:
            self.state_file.write_text(json.dumps(self.positions, indent=2))
        except Exception as e:
            logging.error(f"保存状态文件失败: {e}")

    def get_kline_data(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        """获取K线数据并转换为DataFrame"""
        raw_data = self.api.kline_candlestick_data(symbol=symbol, interval=interval, limit=limit)
        if not raw_data:
            return pd.DataFrame()
        return kline2df(raw_data)

    def scan_market(self):
        """扫描全市场寻找交易机会"""
        logging.info("开始全市场扫描...")
        
        # 1. 获取所有 USDT 交易对
        symbols = self.api.in_exchange_trading_symbols(symbol_pattern=r"USDT$")
        logging.info(f"获取到 {len(symbols)} 个交易对")
        
        current_time = datetime.now()
        
        for symbol in symbols:
            if self.stop_event.is_set(): break

            # 如果达到最大持仓限制，停止开仓
            if len(self.positions) >= self.max_positions:
                logging.warning("已达到最大持仓数量限制，停止扫描")
                break
                
            # 如果已经持仓，跳过
            if symbol in self.positions:
                continue
                
            try:
                # 2. 获取 K1h 数据 (过去 48 小时，足够计算昨日平均)
                df_1h = self.get_kline_data(symbol, "1h", limit=48)
                if df_1h.empty or len(df_1h) < 25:
                    continue
                
                # 3. 计算指标
                # 取上一根已完成的 K 线（索引 -2，因为 -1 是当前未完成的）
                # 注意：实盘扫描通常在整点过一点进行，此时 -1 刚开始，-2 是刚结束的完整小时
                # 如果是在整点运行，last_closed_candle 应该是 -2 (假设 api 返回包含了当前正在进行的 candle)
                # 实际上 binance api 返回的最后一条通常是当前未结束的 candle
                
                last_closed_candle = df_1h.iloc[-2]
                current_buy_volume = last_closed_candle['active_buy_volume']
                
                # 确定昨日的时间范围
                # 假设 last_closed_candle 的时间是 T，昨日就是 T 的日期 - 1天
                last_candle_time = last_closed_candle['trade_date']
                yesterday_date = (last_candle_time - timedelta(days=1)).date()
                
                # 筛选昨日的 K 线
                yesterday_df = df_1h[df_1h['trade_date'].dt.date == yesterday_date]
                if yesterday_df.empty:
                    continue
                    
                daily_avg_buy_volume = yesterday_df['active_buy_volume'].mean()
                
                if daily_avg_buy_volume == 0:
                    continue
                    
                buy_surge_ratio = current_buy_volume / daily_avg_buy_volume
                
                # 4. 检查买量暴涨信号
                if self.buy_surge_threshold <= buy_surge_ratio <= self.buy_surge_max:
                    logging.info(f"发现信号: {symbol} 买量倍数={buy_surge_ratio:.2f}")
                    
                    # 5. 风控检查：顶级交易者多空比
                    long_short_ratio = self.api.get_top_long_short_ratio(symbol, period="1h") # 使用 1h 周期匹配
                    if long_short_ratio < self.min_account_ratio:
                        logging.info(f"忽略信号 {symbol}: 多空比 {long_short_ratio} < {self.min_account_ratio}")
                        continue
                    
                    # 6. 执行开仓
                    self.open_position(symbol, last_closed_candle['close'], buy_surge_ratio)
                    
            except Exception as e:
                logging.error(f"扫描 {symbol} 时出错: {e}")
                continue

    def open_position(self, symbol: str, signal_price: float, buy_surge_ratio: float):
        """执行开仓"""
        try:
            # 1. 设置杠杆和保证金模式
            self.api.change_leverage(symbol, self.leverage)
            # 强制使用逐仓模式 (ISOLATED)
            self.api.change_margin_type(symbol, "ISOLATED") 

            # 2. 计算仓位大小
            balance = self.api.get_account_balance()
            if balance <= 0:
                logging.error("账户余额不足")
                return
                
            position_amount_usdt = balance * self.position_size_ratio * self.leverage
            quantity = position_amount_usdt / signal_price
            
            logging.info(f"准备开仓: {symbol} 价格={signal_price} 数量={quantity:.4f} 杠杆={self.leverage}")
            
            # 3. 发送下单请求 (市价单)
            # 利用增强版 post_order 自动处理精度
            response = self.api.post_order(
                symbol=symbol,
                side="BUY",
                ord_type="MARKET",
                quantity=quantity
            )
            
            # 4. 记录持仓状态
            # 实盘成交均价
            avg_price = float(response.get('avgPrice', signal_price)) 
            if avg_price == 0: avg_price = signal_price # 防止市价单未立即返回均价
            
            self.positions[symbol] = {
                "symbol": symbol,
                "entry_time": datetime.now().isoformat(),
                "entry_price": avg_price,
                "quantity": float(response.get('executedQty', quantity)),
                "buy_surge_ratio": buy_surge_ratio,
                "virtual_entry_price": avg_price, # 用于虚拟补仓
                "is_virtual_added": False,
                "max_pnl_pct": 0.0
            }
            self.save_state()
            logging.info(f"开仓成功: {symbol} 均价={avg_price}")
            
        except Exception as e:
            logging.error(f"开仓失败 {symbol}: {e}")

    def close_position(self, symbol: str, reason: str):
        """平仓"""
        if symbol not in self.positions:
            return
            
        try:
            logging.info(f"准备平仓 {symbol}: 原因={reason}")
            
            # 使用自动平仓功能
            self.api.post_order(
                symbol=symbol,
                side="SELL", # 这里传入 SELL 只是占位，post_order 会根据持仓自动判断
                ord_type="MARKET",
                quantity=0, # 数量为0，让 API 自动获取
                close_position=True
            )
            
            del self.positions[symbol]
            self.save_state()
            logging.info(f"平仓成功 {symbol}")
            
        except Exception as e:
            logging.error(f"平仓失败 {symbol}: {e}")

    def monitor_positions(self):
        """监控持仓 (止盈止损)"""
        if not self.positions:
            return
            
        logging.info(f"监控持仓: {len(self.positions)} 个")
        
        for symbol in list(self.positions.keys()):
            if self.stop_event.is_set(): break
            
            try:
                pos = self.positions[symbol]
                
                # 获取当前价格 (使用 K1m 或 ticker)
                # 这里简化使用 ticker 获取最新价
                ticker = self.api.client.rest_api.symbol_price_ticker(symbol=symbol).data()
                current_price = float(ticker.price)
                
                # 计算持仓时间
                entry_time = datetime.fromisoformat(pos['entry_time'])
                hold_hours = (datetime.now() - entry_time).total_seconds() / 3600
                
                # 计算收益率
                # 注意：这里计算的是相对于 virtual_entry_price 的收益率，用于策略判断
                # 实际 PnL 应该是 (current - entry) / entry
                
                virtual_entry_price = pos['virtual_entry_price']
                pnl_pct = (current_price - virtual_entry_price) / virtual_entry_price
                
                # 更新最大收益率
                if pnl_pct > pos['max_pnl_pct']:
                    pos['max_pnl_pct'] = pnl_pct
                    self.positions[symbol]['max_pnl_pct'] = pnl_pct # 更新内存
                    # 不频繁保存，仅在关键变动时保存
                
                # === 策略逻辑移植 ===
                
                # 1. 动态止盈
                # 简单版：如果收益 > 止盈阈值，平仓
                # 复杂版（参考 hm1sy）：根据 hold_hours 和 buy_surge_ratio 调整阈值
                
                dynamic_tp = self.take_profit_pct
                if hold_hours <= 2:
                    dynamic_tp = max(0.11, dynamic_tp * 0.8) # 前2小时降低要求
                
                if pnl_pct >= dynamic_tp:
                    self.close_position(symbol, "take_profit")
                    continue
                
                # 2. 虚拟补仓 (Trigger)
                if not pos['is_virtual_added'] and pnl_pct <= self.add_position_trigger_pct:
                    logging.info(f"{symbol} 触发虚拟补仓: 当前跌幅 {pnl_pct*100:.2f}%")
                    # 调整虚拟均价 = (原价 + 当前价) / 2
                    new_virtual_price = (virtual_entry_price + current_price) / 2
                    self.positions[symbol]['virtual_entry_price'] = new_virtual_price
                    self.positions[symbol]['is_virtual_added'] = True
                    self.save_state()
                    continue # 补仓后重新计算 PnL，本次循环先跳过平仓检查
                
                # 3. 止损
                if pnl_pct <= self.stop_loss_pct:
                    self.close_position(symbol, "stop_loss")
                    continue
                
                # 4. 时间止损
                if hold_hours >= self.max_hold_hours:
                    self.close_position(symbol, "timeout")
                    continue
                    
                # 5. 弱势平仓 (24小时涨幅不足)
                if hold_hours >= 24 and pnl_pct < 0.08:
                    self.close_position(symbol, "weak_trend_24h")
                    continue
                    
            except Exception as e:
                logging.error(f"监控 {symbol} 出错: {e}")

if __name__ == "__main__":
    # 简单的启动入口
    trader = RealTimeBuySurgeStrategy()
    trader.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        trader.stop()
