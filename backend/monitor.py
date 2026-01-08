from typing import List, Dict
from .top10 import get_top_gainers
import time
import logging

def get_top5_gainers() -> List[Dict]:
    """
    筛选当日涨幅前三的币种
    
    Returns:
        List[Dict]: 涨幅前三的交易对信息列表
    """
    top10 = get_top_gainers()
    return top10[:5]


# 定义一个数据结构，包含：日期、时间、前五的货币涨幅信息
class GainerRecord:
    def __init__(self, date: str, time: str, gainers: List[Dict]):
        self.date = date
        self.time = time
        self.gainers = gainers

# 定义一个上述数据的集合
class GainerRecordSet:
    def __init__(self):
        self.records: List[GainerRecord] = []

    def add_record(self, record: GainerRecord):
        self.records.append(record)

# 将get_top5_gainers获取的数据添加到上述数据结构中，
def record_top5_gainers(record_set: GainerRecordSet):
    from datetime import datetime
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    top5 = get_top5_gainers()
    record = GainerRecord(date=date_str, time=time_str, gainers=top5)
    record_set.add_record(record)            



# 这段是一个定时监控程序
# 它每个小时运行一次，获取涨幅前5的币种并记录日志

def schedule_task(task_func, interval_hours: int):
    interval_seconds = interval_hours * 3600
    while True:
        task_func()
        time.sleep(interval_seconds)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def monitor_top5_gainers():
    top5 = get_top5_gainers()
    logging.info("Top 5 Gainers:")
    for t in top5:
        logging.info(f"Symbol: {t['symbol']}, Change: {t['priceChangePercent']}%, Open: {t['openPrice']}, Close: {t['lastPrice']}") 

schedule_task(monitor_top5_gainers, interval_hours=1)


    