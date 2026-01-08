
import os
import logging
import re

from binance_sdk_spot.spot import Spot, ConfigurationRestAPI, SPOT_REST_API_PROD_URL

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create configuration for the REST API
configuration_rest_api = ConfigurationRestAPI(
    api_key=os.getenv("API_KEY", ""),
    api_secret=os.getenv("API_SECRET", ""),
    base_path=os.getenv("BASE_PATH", SPOT_REST_API_PROD_URL),
)

# Initialize Spot client
client = Spot(config_rest_api=configuration_rest_api)


def get_ticker24hr():
    try:
        response = client.rest_api.ticker24hr()

        rate_limits = response.rate_limits
        # logging.info(f"ticker24hr() rate limits: {rate_limits}")

        data = response.data()
        for t in data:
            if t[0] == "actual_instance":    
                return t[1]
    # logging.info(f"ticker24hr() response: {data}")
    except Exception as e:
        logging.error(f"ticker24hr() error: {e}")
        return []

def in_exchange_trading_symbols():
    try:
        response = client.rest_api.exchange_info()

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




        
def get_top3_gainers():
    """筛选当日涨幅前三的币种"""
    tickers = get_ticker24hr()

    if not tickers:
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
    
    return sorted_tickers[:3]

if __name__ == "__main__":
    tickers = get_top3_gainers()
    print("Top 3 Gainers:")
    for t in tickers:
        print(f"Symbol: {t.symbol}, Change: {t.price_change_percent}%, Open: {t.open_price}, Close: {t.last_price}")