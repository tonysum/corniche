import sys
import logging
from binance_api import BinanceAPI

# 配置日志
logging.basicConfig(level=logging.INFO)

def test_api():
    print("=== 开始测试 BinanceAPI 实盘接口 (增强版) ===")
    
    try:
        api = BinanceAPI()
        
        # 1. 测试获取余额
        print("\n[1/5] 测试获取账户余额...")
        balance = api.get_account_balance()
        print(f"USDT 余额: {balance}")
        
        # 2. 测试获取持仓
        print("\n[2/5] 测试获取当前持仓...")
        positions = api.get_position_risk()
        open_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        print(f"当前持仓数量: {len(open_positions)}")
        for pos in open_positions:
            print(f"  - {pos['symbol']}: {pos['positionAmt']} (未实现盈亏: {pos['unRealizedProfit']})")
            
        # 3. 测试获取多空比
        print("\n[3/5] 测试获取 BTCUSDT 多空比...")
        ratio = api.get_top_long_short_ratio("BTCUSDT", period="5m")
        print(f"BTCUSDT 5m 多空比: {ratio}")
        
        # 4. 测试获取交易对过滤器 (新增)
        print("\n[4/5] 测试获取 BTCUSDT 过滤器信息...")
        tick_size, step_size = api.get_symbol_filters("BTCUSDT")
        print(f"BTCUSDT -> tick_size: {tick_size}, step_size: {step_size}")
        
        # 测试精度调整
        test_price = 12345.6789
        adj_price = api.adjust_precision(test_price, tick_size)
        print(f"价格精度调整: {test_price} -> {adj_price} (应为 {round(test_price // tick_size * tick_size, 2)})")
        
        test_qty = 0.123456
        adj_qty = api.adjust_precision(test_qty, step_size)
        print(f"数量精度调整: {test_qty} -> {adj_qty} (应为 {round(test_qty // step_size * step_size, 3)})")

        # 5. 测试获取涨幅榜
        print("\n[5/5] 测试获取涨幅榜...")
        top3 = api.get_top3_gainers()
        if not top3.empty:
            print(top3[['symbol', 'price_change_percent', 'last_price']])
        else:
            print("涨幅榜为空")
            
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()
