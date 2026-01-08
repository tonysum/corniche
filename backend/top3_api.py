import os
import logging
import re
import pandas as pd 

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
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

def ticker24hr_price_change_statistics():
    try:
        response = client.rest_api.ticker24hr_price_change_statistics()

        rate_limits = response.rate_limits
        logging.info(f"ticker24hr_price_change_statistics() rate limits: {rate_limits}")

        data = response.data()
        for t in data:
            if t[0] == "actual_instance":    
                return t[1]
        # return data
        # logging.info(f"ticker24hr_price_change_statistics() response: {data}")
        return None
    except Exception as e:
        logging.error(f"ticker24hr_price_change_statistics() error: {e}", exc_info=True)
        return None

#
def in_exchange_trading_symbols():
    try:
        response = client.rest_api.exchange_information()

        rate_limits = response.rate_limits
        # logging.info(f"exchange_info() rate limits: {rate_limits}")

        data = response.data()
        pattern =  r"usdt$"
        usdt_symbols= [
            t.symbol for t in data.symbols
            if re.search(pattern, t.symbol, flags=re.IGNORECASE) and t.status=='TRADING'
        ]
        return usdt_symbols
        logging.info(f"exchange_info() response: {data}")
    except Exception as e:
        logging.error(f"exchange_info() error: {e}")

def sort_tickers():
    """按照涨幅降序排序"""
    tickers = ticker24hr_price_change_statistics()

    if not tickers or tickers is None:
        logging.warning("ticker24hr_price_change_statistics() 返回空或None")
        return []

    in_trading_symbols = in_exchange_trading_symbols()

    if not in_trading_symbols:
        return []


    pattern =  r"usdt$"
    
    usdt_tickers= [
        t for t in tickers
        if re.search(pattern, t.symbol, flags=re.IGNORECASE)
    ]

    in_trading_tickers = [
        t for t in usdt_tickers if t.symbol in in_trading_symbols
    ]
    
    valid_tickers = [
        t for t in  in_trading_tickers
        if t.price_change_percent and not t.symbol.endswith(("UP", "DOWN", "USDTM"))  # 排除杠杆/合约交易对
    ]
    
    sorted_tickers = sorted(
        valid_tickers,
        key=lambda x: float(x.price_change_percent),
        reverse=True
    )
    
    return sorted_tickers

def get_top3_gainers():
    try:
        tickers = sort_tickers()
        
        if not tickers:
            logging.warning("sort_tickers() 返回空列表")
            return pd.DataFrame()
        
        tickers_list = [vars(ticker) for ticker in tickers[:3]]
        
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
        
        # 同时优化数值列和时间列
        numeric_columns = ['price_change', 'price_change_percent', 'last_price', 'open_price', 'volume', 'high_price', 'low_price']

        # 数值列转换为浮点数
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df
    except Exception as e:
        logging.error(f"get_top3_gainers() 执行失败: {e}", exc_info=True)
        return pd.DataFrame()