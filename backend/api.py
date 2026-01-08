import os
import logging
import re

import pandas as pd  # pyright: ignore[reportMissingImports]

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (  # pyright: ignore[reportMissingImports]
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (  # pyright: ignore[reportMissingImports]
    KlineCandlestickDataIntervalEnum,
    TopTraderLongShortRatioPositionsPeriodEnum
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create configuration for the REST API
configuration_rest_api = ConfigurationRestAPI(
    api_key="66aLkztQkQFuyUQuM83oqYx9ENuZH1SFFbuTSP3ClcGYa9Vqwy5cmQan9QfK7Gzd",
    # api_key= "O0ambiAxVnDs0pDAtlwVs3uiLR7uH2kh5B12WWWmEersKD9uHipkJZ80I90enw4o",
    # api_secret="",
    api_secret="V4lTk3PUCa7jwGAxPybBFzE7fN2Ob09FZR9BbchLOiGtssRnH9cnkfL2O8C7aoQW",
    base_path=os.getenv(
        "BASE_PATH",  DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL)
)

# Initialize DerivativesTradingUsdsFutures client
client = DerivativesTradingUsdsFutures(config_rest_api=configuration_rest_api)

# 获取币安交易所所有合约交易对函数
def in_exchange_trading_symbols():
    try:
        response = client.rest_api.exchange_information()

        rate_limits = response.rate_limits
        # logging.info(f"exchange_info() rate limits: {rate_limits}")

        data = response.data()
        pattern =  r"usdt$"
        usdt_symbols= [
            t.symbol for t in data.symbols
            if re.search(pattern, t.symbol, flags=re.IGNORECASE) and t.status=="TRADING"
        ]
        return usdt_symbols
        logging.info(f"exchange_info() response: {data}")
    except Exception as e:
        logging.error(f"exchange_info() error: {e}")

# 获取K线数据
def kline_candlestick_data(symbol,interval,starttime,endtime,limit):
    try:
        response = client.rest_api.kline_candlestick_data(
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
        logging.info(f"kline_candlestick_data() response: {data}")
    except Exception as e:
        logging.error(f"kline_candlestick_data() error: {e}")

# K线数据转换为DataFrame        
def kline2df(data):
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
    
    #计算涨跌幅
    df["diff"] = df["close"]-df["close"].shift(1)
    df["pct_chg"] = (df["close"]-df["close"].shift(1))/df["close"].shift(1)*100
    
    # 时间戳转换为可读日期（毫秒级→秒级→datetime）
    df["trade_date"] = pd.to_datetime(df["open_time"] // 1000, unit="s")
    # df["open_time"] = pd.to_datetime(df["open_time"] // 1000, unit="s")
    # df["close_time"] = pd.to_datetime(df["close_time"] // 1000, unit="s")
    # df2 = df.set_index([df["trade_date"],df["symbol"]])
        
    return df