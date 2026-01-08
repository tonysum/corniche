## url = https://www.binance.com/zh-CN/smart-money/signal/RIVERUSDT?timeRange=1h&side=BOTH&sortBy=TIME&sortOrder=DESC&page=1
## 获取当前地址的巨鲸总持仓、鲸鱼总数、名义多空比率，转换为DataFrame返回
## 使用crawl4ai框架
from crawl4ai  import *
import pandas as pd

async def crawl_binance_whale_data(url: str) -> pd.DataFrame:
    """
    爬取币安巨鲸数据页面，提取总持仓、鲸鱼总数、名义多空比率，转为DataFrame返回
    :param url: 币安巨鲸数据页面地址
    :return: 包含巨鲸核心数据的DataFrame
    """
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            
            url=url,
            # 启用浏览器渲染（关键：币安页面为动态加载，必须开启）
            browser=True,
            # 等待页面渲染完成（网络空闲后再爬取，确保数据加载完整）
            wait_until="networkidle",
            # 延长页面加载超时时间（避免因网络延迟导致爬取失败）
            timeout=30000,
            # 模拟真实浏览器请求头（避免被反爬）
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        # 3. 验证爬取结果是否成功
        if not result:
            raise Exception(f"页面爬取失败：{result.error_message}")
        
        # 4. 提取核心数据（通过 CSS 选择器定位，适配币安页面结构）
        # 注意：币安页面元素选择器可能随版本更新变化，若提取失败需刷新选择器
        page_content = result.html  # 获取爬取到的完整页面HTML
        selector = result.selector  # 使用 crawl4ai 内置的 Parsel 选择器（支持CSS/XPath）
        
        # 定义元素选择器（适配币安 zh-CN 页面结构，若失效需手动调试更新）
        selectors_map = {
            "巨鲸总持仓": 'div[class*="total-position"] span[class*="value"]::text',
            "鲸鱼总数": 'div[class*="whale-count"] span[class*="value"]::text',
            "名义多空比率": 'div[class*="long-short-ratio"] span[class*="ratio-value"]::text'
        }
        
        # 提取数据
        whale_data = {}
        for key, css_selector in selectors_map.items():
            # 提取文本并清理空格、换行符
            value = selector.css(css_selector).get(default="N/A").strip()
            whale_data[key] = [value]  # 转为列表格式，方便后续构建DataFrame
        
        # 5. 转换为 DataFrame
        df_whale = pd.DataFrame(whale_data)
        
        # 可选：数据格式清洗（将字符串数值转为浮点数，处理特殊字符）
        def clean_numeric_value(val):
            if val == "N/A":
                return None
            # 移除逗号、百分号等非数字字符
            val = val.replace(",", "").replace("%", "").replace("×", "")
            try:
                return float(val)
            except ValueError:
                return val
        
        for col in df_whale.columns:
            df_whale[col] = df_whale[col].apply(clean_numeric_value)
        
        return df_whale



# 主程序入口
if __name__ == "__main__":
    # 目标币安巨鲸数据页面地址
    target_url = "https://www.binance.com/zh-CN/smart-money/signal/RIVERUSDT?timeRange=1h&side=BOTH&sortBy=TIME&sortOrder=DESC&page=1"
    
    # 爬取数据并转为 DataFrame
    whale_df = crawl_binance_whale_data(target_url)
    
    # 打印结果
    print("币安巨鲸核心数据 DataFrame：")
    print(whale_df)
    print("\n数据类型：")
    print(whale_df)