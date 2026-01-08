"""
计算建仓价格、止损价格、止盈价格

Usage: python order.py <price> <entry_pct_chg> <loss_threshold> <profit_threshold>
Example: python order.py 10000 0.04 0.019 0.04

"""
import sys

def calculate_short_exit_price(price, entry_pct_chg,loss_threshold, profit_threshold):
    entry_price = price * (1 + entry_pct_chg)
    stop_loss_price = entry_price * (1 + loss_threshold)
    take_profit_price = entry_price * (1 - profit_threshold)
    return entry_price, stop_loss_price, take_profit_price

def calculate_long_exit_price(price, entry_pct_chg,loss_threshold, profit_threshold):
    entry_price = price * (1 - entry_pct_chg)
    stop_loss_price = entry_price * (1 - loss_threshold)
    take_profit_price = entry_price * (1 + profit_threshold)
    return entry_price, stop_loss_price, take_profit_price

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) != 4:
        print("Usage: python order.py <price> <entry_pct_chg> <loss_threshold> <profit_threshold>")
        sys.exit(1)
    price = float(args[0])
    entry_pct_chg = float(args[1]) / 100
    loss_threshold = float(args[2]) / 100
    profit_threshold = float(args[3]) / 100
    entry_price, stop_loss_price, take_profit_price = calculate_short_exit_price(price, entry_pct_chg, loss_threshold, profit_threshold)
    print(f"Entry Price: {entry_price}, Stop Loss Price: {stop_loss_price}, Take Profit Price: {take_profit_price}")