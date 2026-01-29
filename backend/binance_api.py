import os
import logging
import re
from pathlib import Path
from typing import Optional, List

import pandas as pd  # pyright: ignore[reportMissingImports]
from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (  # pyright: ignore[reportMissingImports]
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (  # pyright: ignore[reportMissingImports]
    KlineCandlestickDataIntervalEnum,
    TopTraderLongShortRatioPositionsPeriodEnum
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models.enums import (
    NewOrderTimeInForceEnum,
    NewOrderSideEnum,
    ChangeMarginTypeMarginTypeEnum
)

# 🔧 加载 .env 文件
# 从当前文件所在目录向上查找 .env 文件（支持 backend/ 目录和项目根目录）
backend_dir = Path(__file__).parent
project_root = backend_dir.parent
env_path = project_root / '.env'
if not env_path.exists():
    # 如果项目根目录没有 .env，尝试 backend 目录
    env_path = backend_dir / '.env'

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logging.info(f"已加载环境变量文件: {env_path}")
else:
    logging.warning(f"未找到 .env 文件，将使用环境变量或默认值。查找路径: {env_path}")

# Configure logging
# logging.basicConfig(level=logging.INFO)  # 被移除，由入口程序统一配置


import math

class BinanceAPI:
    """币安API客户端封装类"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_path: Optional[str] = None
    ):
        """
        初始化币安API客户端
        
        Args:
            api_key: API密钥（优先级：参数 > .env文件 > 环境变量 > 默认值）
            api_secret: API密钥（优先级：参数 > .env文件 > 环境变量 > 默认值）
            base_path: API基础路径（优先级：参数 > .env文件 > 环境变量 > 默认值）
        """
        # 🔧 从 .env 文件或环境变量获取配置（已通过 load_dotenv() 加载）
        # 优先级：函数参数 > .env文件/环境变量 > 默认值
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        self.base_path = base_path or os.getenv("BASE_PATH", DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL)
        
        # 🔧 验证必需的配置
        if not self.api_key:
            raise ValueError(
                "BINANCE_API_KEY 未设置。请创建 .env 文件并设置 BINANCE_API_KEY，"
                "或在环境变量中设置 BINANCE_API_KEY。"
            )
        if not self.api_secret:
            raise ValueError(
                "BINANCE_API_SECRET 未设置。请创建 .env 文件并设置 BINANCE_API_SECRET，"
                "或在环境变量中设置 BINANCE_API_SECRET。"
            )
        
        # 创建配置和客户端
        configuration_rest_api = ConfigurationRestAPI(
            api_key=self.api_key,
            api_secret=self.api_secret,
            base_path=self.base_path
        )
        self.client = DerivativesTradingUsdsFutures(config_rest_api=configuration_rest_api)
        self._exchange_info_cache = None

    def get_exchange_info(self) -> dict:
        """获取交易所信息（带简单缓存）"""
        if self._exchange_info_cache:
            return self._exchange_info_cache
        try:
            response = self.client.rest_api.exchange_information()
            self._exchange_info_cache = response.data()
            return self._exchange_info_cache
        except Exception as e:
            logging.error(f"获取交易所信息失败: {e}")
            return {}

    def get_symbol_filters(self, symbol: str) -> tuple:
        """获取交易对的精度过滤器"""
        exchange_info = self.get_exchange_info()
        if not exchange_info or not hasattr(exchange_info, 'symbols'):
            return None, None
            
        for s in exchange_info.symbols:
            if s.symbol == symbol:
                tick_size = None
                step_size = None
                for f in s.filters:
                    if f.filter_type == 'PRICE_FILTER':
                        tick_size = float(f.tick_size)
                    elif f.filter_type == 'LOT_SIZE':
                        step_size = float(f.step_size)
                return tick_size, step_size
        return None, None

    def adjust_precision(self, value: float, step_size: float) -> float:
        """调整精度"""
        if step_size <= 0 or value <= 0:
            return value
        
        # 计算精度位数
        step_str = f"{step_size:.10f}".rstrip('0').rstrip('.')
        if '.' in step_str:
            precision = len(step_str.split('.')[1])
        else:
            precision = 0
            
        # 向下取整
        adjusted = math.floor(value / step_size) * step_size
        return round(adjusted, precision)

    def change_leverage(self, symbol: str, leverage: int):
        """调整杠杆倍数"""
        try:
            self.client.rest_api.change_initial_leverage(symbol=symbol, leverage=leverage)
            logging.info(f"已设置 {symbol} 杠杆为 {leverage}x")
        except Exception as e:
            logging.error(f"设置杠杆失败: {e}")

    def change_margin_type(self, symbol: str, margin_type: str = "ISOLATED"):
        """调整保证金模式 (ISOLATED/CROSSED)"""
        try:
            # 使用 Enum 转换参数
            margin_type_enum = ChangeMarginTypeMarginTypeEnum(margin_type.upper())
            self.client.rest_api.change_margin_type(symbol=symbol, margin_type=margin_type_enum)
            logging.info(f"已设置 {symbol} 保证金模式为 {margin_type}")
        except ValueError:
             logging.error(f"无效的保证金模式: {margin_type}")
        except Exception as e:
            # 如果已经是该模式，API会报错 "No need to change margin type"，可以忽略
            if "No need to change" not in str(e):
                logging.error(f"设置保证金模式失败: {e}")

    def in_exchange_trading_symbols(
        self,
        symbol_pattern: str = r"usdt$",
        status: str = "TRADING"
    ) -> List[str]:
        """
        获取币安交易所所有合约交易对
        
        Args:
            symbol_pattern: 交易对符号匹配模式（默认匹配USDT结尾）
            status: 交易状态过滤（默认只返回TRADING状态的）
        
        Returns:
            符合条件的交易对符号列表
        """
        try:
            response = self.client.rest_api.exchange_information()
            rate_limits = response.rate_limits
            # logging.info(f"exchange_info() rate limits: {rate_limits}")

            data = response.data()
            usdt_symbols = [
                t.symbol for t in data.symbols
                if re.search(symbol_pattern, t.symbol, flags=re.IGNORECASE) and t.status == status
            ]
            return usdt_symbols
        except Exception as e:
            logging.error(f"exchange_info() error: {e}")
            return []
    
    def kline_candlestick_data(
        self,
        symbol: str,
        interval: str,
        starttime: Optional[int] = None,
        endtime: Optional[int] = None,
        limit: Optional[int] = None
    ):
        """
        获取K线数据
        
        Args:
            symbol: 交易对符号
            interval: K线间隔
            starttime: 开始时间（时间戳，毫秒）
            endtime: 结束时间（时间戳，毫秒）
            limit: 返回数据条数限制
        
        Returns:
            K线数据
        """
        try:
            response = self.client.rest_api.kline_candlestick_data(
                symbol=symbol,
                interval=interval,
                start_time=starttime,
                end_time=endtime,
                limit=limit,
            )

            rate_limits = response.rate_limits
            logging.info(f"kline_candlestick_data() rate limits: {rate_limits}")

            data = response.data()
            return data
        except Exception as e:
            logging.error(f"kline_candlestick_data() error: {e}")
            return None
    
    def ticker24hr_price_change_statistics(self):
        """
        获取24小时价格变动统计
        
        Returns:
            24小时价格变动统计数据
        """
        try:
            response = self.client.rest_api.ticker24hr_price_change_statistics()

            rate_limits = response.rate_limits
            logging.info(f"ticker24hr_price_change_statistics() rate limits: {rate_limits}")

            data = response.data()
            for t in data:
                if t[0] == "actual_instance":    
                    return t[1]
            return None
        except Exception as e:
            logging.error(f"ticker24hr_price_change_statistics() error: {e}", exc_info=True)
            return None
    
    def sort_tickers(
        self,
        symbol_pattern: str = r"usdt$",
        exclude_patterns: tuple = ("UP", "DOWN", "USDTM"),
        reverse: bool = True
    ) -> List:
        """
        按照涨幅降序排序交易对
        
        Args:
            symbol_pattern: 交易对符号匹配模式（默认匹配USDT结尾）
            exclude_patterns: 要排除的交易对后缀（默认排除杠杆/合约交易对）
            reverse: 是否降序排序（默认True，涨幅从高到低）
        
        Returns:
            排序后的交易对列表
        """
        tickers = self.ticker24hr_price_change_statistics()

        if not tickers or tickers is None:
            logging.warning("ticker24hr_price_change_statistics() 返回空或None")
            return []

        in_trading_symbols = self.in_exchange_trading_symbols(symbol_pattern=symbol_pattern)

        if not in_trading_symbols:
            return []

        usdt_tickers = [
            t for t in tickers
            if re.search(symbol_pattern, t.symbol, flags=re.IGNORECASE)
        ]

        in_trading_tickers = [
            t for t in usdt_tickers if t.symbol in in_trading_symbols
        ]
        
        valid_tickers = [
            t for t in in_trading_tickers
            if t.price_change_percent and not t.symbol.endswith(exclude_patterns)
        ]
        
        sorted_tickers = sorted(
            valid_tickers,
            key=lambda x: float(x.price_change_percent),
            reverse=reverse
        )
        
        return sorted_tickers
    
    def get_top_gainers(
        self,
        top_n: int = 3,
        symbol_pattern: str = r"usdt$",
        exclude_patterns: tuple = ("UP", "DOWN", "USDTM")
    ) -> pd.DataFrame:
        """
        获取涨幅前N的交易对
        
        Args:
            top_n: 返回前N个交易对（默认3）
            symbol_pattern: 交易对符号匹配模式（默认匹配USDT结尾）
            exclude_patterns: 要排除的交易对后缀（默认排除杠杆/合约交易对）
        
        Returns:
            包含前N个交易对信息的DataFrame
        """
        try:
            tickers = self.sort_tickers(
                symbol_pattern=symbol_pattern,
                exclude_patterns=exclude_patterns
            )
            
            if not tickers:
                logging.warning("sort_tickers() 返回空列表")
                return pd.DataFrame()
            
            tickers_list = [vars(ticker) for ticker in tickers[:top_n]]
            
            if not tickers_list:
                logging.warning("tickers_list 为空")
                return pd.DataFrame()

            df = pd.DataFrame(tickers_list)
            
            if df.empty:
                logging.warning("DataFrame 为空")
                return df
            
            # 处理时间列（如果存在）
            if 'open_time' in df.columns:
                df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True).dt.tz_localize(None)
            if 'close_time' in df.columns:
                df['close_time'] = pd.to_datetime(df['close_time'], unit='ms', utc=True).dt.tz_localize(None)
            
            # 数值列转换为浮点数
            numeric_columns = [
                'price_change', 'price_change_percent', 'last_price', 
                'open_price', 'volume', 'high_price', 'low_price'
            ]

            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
        except Exception as e:
            logging.error(f"get_top_gainers() 执行失败: {e}", exc_info=True)
            return pd.DataFrame()

    def get_top3_gainers(self, top_n: int = 3) -> pd.DataFrame:
        """
        获取涨幅前三的交易对（便捷函数，保持向后兼容）
        
        Args:
            top_n: 返回前N个交易对（默认3，保持向后兼容）
        
        Returns:
            包含前N个交易对信息的DataFrame
        """
        return self.get_top_gainers(top_n=top_n)

    def post_order(
        self,
        symbol: str,
        side: str,
        ord_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        close_position: bool = False
    ):
        """
        发送订单 (增强版：支持精度自动调整、自动平仓、风控检查)
        
        Args:
            symbol: 交易对符号 (e.g. "BTCUSDT")
            side: 方向 ("BUY", "SELL")
            ord_type: 订单类型 ("LIMIT", "MARKET", "STOP", "TAKE_PROFIT", etc.)
            quantity: 数量 (如果 close_position=True，此参数可为0，自动获取持仓)
            price: 价格 (LIMIT单必填)
            stop_price: 触发价 (STOP/TAKE_PROFIT单必填)
            time_in_force: 有效期 (默认 "GTC")
            reduce_only: 是否只减仓 (默认 False)
            close_position: 是否为平仓单 (默认 False，若为True则自动获取持仓数量并设置reduce_only)
        
        Returns:
            订单响应字典
        """
        try:
            # 1. 如果是平仓单，自动获取持仓数量
            if close_position:
                positions = self.get_position_risk(symbol=symbol)
                target_pos = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
                
                if not target_pos:
                    raise ValueError(f"未找到 {symbol} 的持仓，无法执行自动平仓")
                
                pos_amt = float(target_pos['positionAmt'])
                # 自动判断平仓方向：持多(>0)则卖出，持空(<0)则买入
                # 注意：如果外部传入了 side，这里会覆盖或校验。通常 close_position 时 side 应该由持仓决定。
                # 这里为了灵活性，如果外部传入的 side 与持仓平仓方向不符，抛出警告或错误？
                # 简化逻辑：直接覆盖 side
                side = "SELL" if pos_amt > 0 else "BUY"
                quantity = abs(pos_amt)
                reduce_only = True
                logging.info(f"自动平仓模式: {symbol} 持仓={pos_amt} -> 下单 {side} {quantity}")

            # 2. 获取交易对过滤器信息 (精度)
            tick_size, step_size = self.get_symbol_filters(symbol)
            
            # 3. 调整价格精度
            if price is not None and tick_size:
                original_price = price
                price = self.adjust_precision(price, tick_size)
                if price != original_price:
                    logging.info(f"价格精度调整: {original_price} -> {price}")
            
            if stop_price is not None and tick_size:
                stop_price = self.adjust_precision(stop_price, tick_size)

            # 4. 调整数量精度
            if quantity > 0 and step_size:
                original_qty = quantity
                quantity = self.adjust_precision(quantity, step_size)
                if quantity != original_qty:
                    logging.info(f"数量精度调整: {original_qty} -> {quantity}")
            
            if quantity <= 0:
                raise ValueError(f"下单数量无效: {quantity}")

            # 5. 构建参数
            params = {
                "symbol": symbol,
                "type": ord_type,
                "quantity": quantity,
            }

            # 处理订单方向 (Side)
            try:
                # 确保大写并转换为 Enum
                side_enum = NewOrderSideEnum(side.upper())
                params["side"] = side_enum
            except ValueError:
                logging.warning(f"无效的 Side: {side}, 尝试直接使用字符串")
                params["side"] = side
            
            # 处理价格和有效期 (适用于 LIMIT, STOP, TAKE_PROFIT 等需要价格的订单)
            if price is not None:
                params["price"] = price
                # 只有非市价单才需要 time_in_force
                if "MARKET" not in ord_type:
                    # 将字符串转换为 Enum
                    try:
                        tif_enum = NewOrderTimeInForceEnum(time_in_force)
                        params["time_in_force"] = tif_enum
                    except ValueError:
                        logging.warning(f"无效的 TimeInForce: {time_in_force}, 使用默认 GTC")
                        params["time_in_force"] = NewOrderTimeInForceEnum.GTC
            elif ord_type == "LIMIT":
                raise ValueError("LIMIT 订单必须指定 price")
            
            if stop_price is not None:
                params["stop_price"] = stop_price
                
            if reduce_only:
                params["reduce_only"] = "true"

            # 6. 发送订单
            response = self.client.rest_api.new_order(**params)
            logging.info(f"下单成功: {symbol} {side} {ord_type} {quantity}")
            return response.data()
            
        except Exception as e:
            logging.error(f"下单失败: {symbol} {side} {ord_type} {quantity} - {e}")
            raise

    def cancel_order(self, symbol: str, order_id: int):
        """
        撤销订单
        
        Args:
            symbol: 交易对符号
            order_id: 订单ID
        """
        try:
            response = self.client.rest_api.cancel_order(symbol=symbol, order_id=order_id)
            logging.info(f"撤单成功: {symbol} order_id={order_id}")
            return response.data()
        except Exception as e:
            logging.error(f"撤单失败: {symbol} order_id={order_id} - {e}")
            raise

    def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        获取当前挂单
        
        Args:
            symbol: 交易对符号 (可选)
            
        Returns:
            挂单列表
        """
        try:
            if symbol:
                response = self.client.rest_api.current_all_open_orders(symbol=symbol)
            else:
                response = self.client.rest_api.current_all_open_orders()
            
            data = response.data()
            # 转换为字典列表
            return [order.to_dict() for order in data]
        except Exception as e:
            logging.error(f"获取挂单失败: {e}")
            return []

    def get_account_balance(self) -> float:
        """
        获取 USDT 可用余额
        
        Returns:
            USDT 余额 (float)
        """
        try:
            response = self.client.rest_api.futures_account_balance_v2()
            data = response.data()
            for asset in data:
                if asset.asset == "USDT":
                    return float(asset.available_balance)
            return 0.0
        except Exception as e:
            logging.error(f"获取余额失败: {e}")
            return 0.0

    def get_position_risk(self, symbol: Optional[str] = None) -> List[dict]:
        """
        获取持仓风险信息
        
        Args:
            symbol: 交易对符号 (可选，不填返回所有持仓)
            
        Returns:
            持仓列表
        """
        try:
            # SDK 方法可能是 position_information_v2
            if symbol:
                response = self.client.rest_api.position_information_v2(symbol=symbol)
            else:
                response = self.client.rest_api.position_information_v2()
            
            data = response.data()
            # 转换为字典列表，方便使用
            return [pos.to_dict() for pos in data]
        except Exception as e:
            logging.error(f"获取持仓失败: {e}")
            return []

    def get_top_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 1) -> float:
        """
        获取顶级交易者账户多空比
        
        Args:
            symbol: 交易对符号
            period: 周期 (默认 "5m")
            limit: 限制条数 (默认 1)
            
        Returns:
            最新的多空比 (float)，如果获取失败返回 -1.0
        """
        try:
            response = self.client.rest_api.top_trader_long_short_ratio_accounts(
                symbol=symbol,
                period=period,
                limit=limit
            )
            data = response.data()
            if data and len(data) > 0:
                # SDK 返回的是 dict 列表，且 key 为 camelCase
                item = data[-1]
                if isinstance(item, dict):
                    return float(item.get('longShortRatio', -1.0))
                else:
                    # 兼容如果返回的是对象的情况
                    return float(getattr(item, 'long_short_ratio', -1.0))
            return -1.0
        except Exception as e:
            logging.error(f"获取多空比失败: {symbol} - {e}")
            return -1.0


# ============================================================================
# 全局默认实例（保持向后兼容）
# ============================================================================

# 创建默认的API客户端实例
_default_api = BinanceAPI()

# ============================================================================
# 便捷函数（保持向后兼容，内部使用默认实例）
# ============================================================================

def in_exchange_trading_symbols(symbol_pattern: str = r"usdt$", status: str = "TRADING") -> List[str]:
    """
    获取币安交易所所有合约交易对（便捷函数）
    
    Args:
        symbol_pattern: 交易对符号匹配模式（默认匹配USDT结尾）
        status: 交易状态过滤（默认只返回TRADING状态的）
    
    Returns:
        符合条件的交易对符号列表
    """
    return _default_api.in_exchange_trading_symbols(
        symbol_pattern=symbol_pattern,
        status=status
    )


def kline_candlestick_data(
    symbol: str,
    interval: str,
    starttime: Optional[int] = None,
    endtime: Optional[int] = None,
    limit: Optional[int] = None
):
    """
    获取K线数据（便捷函数）
    
    Args:
        symbol: 交易对符号
        interval: K线间隔
        starttime: 开始时间（时间戳，毫秒）
        endtime: 结束时间（时间戳，毫秒）
        limit: 返回数据条数限制
    
    Returns:
        K线数据
    """
    return _default_api.kline_candlestick_data(
        symbol=symbol,
        interval=interval,
        starttime=starttime,
        endtime=endtime,
        limit=limit
    )


def kline2df(data) -> pd.DataFrame:
    """
    K线数据转换为DataFrame
    
    Args:
        data: K线数据列表
    
    Returns:
        转换后的DataFrame
    """
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume", "trade_count",
        "active_buy_volume", "active_buy_quote_volume", "reserved_field"
    ])
   
    # 数据类型转换（字符串→数值/日期）
    df["open"] = pd.to_numeric(df["open"])
    df["high"] = pd.to_numeric(df["high"])
    df["low"] = pd.to_numeric(df["low"])
    df["close"] = pd.to_numeric(df["close"])
    df["volume"] = pd.to_numeric(df["volume"])
    df["quote_volume"] = pd.to_numeric(df["quote_volume"])
    df["trade_count"] = pd.to_numeric(df["trade_count"])
    df["active_buy_volume"] = pd.to_numeric(df["active_buy_volume"])
    df["active_buy_quote_volume"] = pd.to_numeric(df["active_buy_quote_volume"])
    
    # 计算涨跌幅
    df["diff"] = df["close"] - df["close"].shift(1)
    df["pct_chg"] = (df["close"] - df["close"].shift(1)) / df["close"].shift(1) * 100
    
    # 时间戳转换为可读日期（毫秒级→秒级→datetime）
    df["trade_date"] = pd.to_datetime(df["open_time"] // 1000, unit="s")
        
    return df


def ticker24hr_price_change_statistics():
    """
    获取24小时价格变动统计（便捷函数）
    
    Returns:
        24小时价格变动统计数据
    """
    return _default_api.ticker24hr_price_change_statistics()


def sort_tickers(
    symbol_pattern: str = r"usdt$",
    exclude_patterns: tuple = ("UP", "DOWN", "USDTM"),
    reverse: bool = True
) -> List:
    """
    按照涨幅降序排序交易对（便捷函数）
    
    Args:
        symbol_pattern: 交易对符号匹配模式（默认匹配USDT结尾）
        exclude_patterns: 要排除的交易对后缀（默认排除杠杆/合约交易对）
        reverse: 是否降序排序（默认True，涨幅从高到低）
    
    Returns:
        排序后的交易对列表
    """
    return _default_api.sort_tickers(
        symbol_pattern=symbol_pattern,
        exclude_patterns=exclude_patterns,
        reverse=reverse
    )


def get_top3_gainers(top_n: int = 3) -> pd.DataFrame:
    """
    获取涨幅前三的交易对（便捷函数，保持向后兼容）
    
    Args:
        top_n: 返回前N个交易对（默认3，保持向后兼容）
    
    Returns:
        包含前N个交易对信息的DataFrame
    """
    return _default_api.get_top_gainers(top_n=top_n)
