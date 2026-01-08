import requests
import re
import logging
from typing import List, Dict, Set, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 常量定义
BINANCE_API_BASE = "https://data-api.binance.vision/api/v3"
REQUEST_TIMEOUT = 10
USDT_PATTERN = re.compile(r"usdt$", re.IGNORECASE)
EXCLUDED_SUFFIXES = ("UP", "DOWN", "USDTM")


def get_trading_usdt_symbols() -> Set[str]:
    """
    获取所有处于交易状态的 USDT 交易对
    
    Returns:
        Set[str]: USDT 交易对符号集合
    """
    url = f"{BINANCE_API_BASE}/exchangeInfo"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        usdt_symbols = {
            symbol['symbol'] 
            for symbol in data['symbols']
            if USDT_PATTERN.search(symbol['symbol']) and symbol['status'] == 'TRADING'
        }
        
        logging.info(f"成功获取 {len(usdt_symbols)} 个 USDT 交易对")
        return usdt_symbols
        
    except requests.RequestException as e:
        logging.error(f"获取交易所信息失败: {e}")
        return set()
    except (KeyError, ValueError) as e:
        logging.error(f"解析交易所信息失败: {e}")
        return set()


def get_ticker24hr() -> List[Dict]:
    """
    获取 24 小时价格变动统计
    
    Returns:
        List[Dict]: 24小时行情数据列表
    """
    url = f"{BINANCE_API_BASE}/ticker/24hr"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() 
        data = response.json()
        logging.info(f"成功获取 {len(data)} 个交易对的行情数据")
        return data

    except requests.RequestException as e:
        logging.error(f"获取24小时行情失败: {e}")
        return []
    except ValueError as e:
        logging.error(f"解析24小时行情失败: {e}")
        return []


def get_top3_gainers() -> List[Dict]:
    """
    筛选当日涨幅前三的币种
    
    Returns:
        List[Dict]: 涨幅前三的交易对信息列表
    """
    tickers = get_ticker24hr()
    if not tickers:
        logging.warning("未获取到行情数据")
        return []
    
    trading_symbols = get_trading_usdt_symbols()
    if not trading_symbols:
        logging.warning("未获取到交易对列表")
        return []

    # 筛选有效的交易对
    valid_tickers = [
        ticker for ticker in tickers
        if (
            ticker.get('symbol') in trading_symbols and
            USDT_PATTERN.search(ticker.get('symbol', '')) and
            ticker.get("priceChangePercent") and
            not ticker.get("symbol", "").endswith(EXCLUDED_SUFFIXES)
        )
    ]
    
    # 按涨幅排序
    try:
        sorted_tickers = sorted(
            valid_tickers,
            key=lambda x: float(x["priceChangePercent"]),
            reverse=True
        )
        logging.info(f"成功筛选出 {len(sorted_tickers)} 个有效交易对")
        return sorted_tickers[:3]
    except (ValueError, TypeError) as e:
        logging.error(f"排序交易对失败: {e}")
        return []


if __name__ == "__main__":

    tickers = get_top3_gainers()
    logging.info("Top 3 Gainers:")
    for t in tickers:
        logging.info(f"Symbol: {t['symbol']}, Change: {t['priceChangePercent']}%, Open: {t['openPrice']}, Close: {t['lastPrice']}")