#!/usr/bin/env python3
"""
建仓分析程序 (PostgreSQL版) - 每日北京时间8点运行

功能：
1. 基于日K线数据，统计UTC 0:00时刻的24小时涨幅第一的交易对
2. 提供详细的建仓建议和风控数据（止损、止盈、补仓价格建议）
3. 多维度风控拦截：
   - Premium Index (基差率): 精确拦截危险区间 (-0.44% ~ -0.3%)
   - 买卖量加速度: 过滤最后2小时卖量激增项目
   - 顶级交易者多空比: 过滤主力观望或不合时宜的项目
   - 成交额过滤: 过滤由于小市值导致的虚高涨幅

数据源 (PostgreSQL):
- K1d{symbol}: 日K线数据 (用于计算24h涨幅)
- K1h{symbol}: 小时K线数据 (用于买卖量风控分析)
- premium_index_history: 历史基差数据
- top_account_ratio: 顶级交易者持仓比例

统计方式：昨日UTC 0:00 → 今日UTC 0:00（使用日K线开盘价计算24小时涨幅）
计算公式：(今日开盘价 - 昨日开盘价) / 昨日开盘价

使用说明:
- 北京时间8:00 = UTC 0:00（日K线的开盘时刻）
- python3 jcfx20260129.py --date YYYY-MM-DD (分析历史或指定日期)
- python3 jcfx20260129.py (自动分析今日最新数据)
"""

import os
import sys
import logging
import argparse
import pandas as pd
from sqlalchemy import text  # pyright: ignore[reportMissingImports]
from db import engine
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests
import time
import json
import calendar
try:
    from binance.client import Client as BinanceClient
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 数据库配置（使用PostgreSQL）
# DB_PATH 已移除，统一使用 db.py 中的 engine

# Binance API配置（用于获取实时数据）
API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# 策略参数（与backtrade8.py保持一致）
MIN_PCT_CHG = 0.25  # 最小涨幅25%
ENABLE_VOLUME_FILTER = True
HIGH_PCT_CHG_THRESHOLD = 50
MIN_VOLUME_FOR_HIGH_PCT = 1.5e8

# 动态策略配置（2026-01-28更新：初始止盈改为40%）
DYNAMIC_STRATEGY_CONFIG = [
    (25,  2, 0.40, 0.45, 0.44, 0.00),   # 极低涨幅(<25%): 2倍杠杆，初始止盈40%
    (40,  2, 0.40, 0.45, 0.44, 0.01),   # 中低涨幅(25-40%): 2倍杠杆，初始止盈40%
    (60,  2, 0.40, 0.45, 0.44, 0.08),   # 中涨幅(40-60%): 2倍杠杆，初始止盈40%
    (90,  2, 0.40, 0.45, 0.40, 0.06),   # 大涨幅(60-90%): 2倍杠杆，初始止盈40%
    (999, 2, 0.40, 0.45, 0.40, 0.10),   # 特大涨幅(>=90%): 2倍杠杆，初始止盈40%
]

# ============================================================================
# Premium Index（基差率）精确拦截配置【最终优化版】
# 
# 回测验证（2025-11-01至2026-01-15）：
# - 只拦截中负Premium区间（-0.44% ~ -0.3%），零误拦
# - 成功拦截3笔止损交易（DASHUSDT/ICNTUSDT/PIPPINUSDT），避免亏损-3,530 USDT
# - 收益率从86.2%提升到142.3%（+65.1%），胜率从80.0%提升到84.2%
# ============================================================================
ENABLE_PREMIUM_CONTROL = True  # ✅ 启用精确Premium风控

# Premium风控配置【精确拦截策略】
PREMIUM_CONTROL_CONFIG = {
    # ============================================================================
    # 🎯 Premium Index 精确拦截策略（回测验证有效）
    # ============================================================================
    # 
    # 📊 核心发现：负Premium呈现"U型"风险曲线
    # 
    # 区间表现（2025-11-01 至 2026-01-28，49笔交易）：
    # ┌────────────────────────────────────────────────────────────────┐
    # │ Premium区间          │ 样本 │ 胜率  │ 平均收益 │ 风险等级       │
    # ├────────────────────────────────────────────────────────────────┤
    # │ < -2.65%  超极端区间 │ 2笔  │ 100% │ +2667   │ ✅ 安全（反向）│
    # │ -2.65%~-1.7% 极度负  │ 1笔  │ 100% │ +2691   │ ⚠️ 保守拦截   │
    # │ -1.7%~-0.44% 间隙    │ 10笔 │ 90%  │ +2593   │ ✅ 安全       │
    # │ -0.44%~-0.3% 中负    │ 3笔  │ 0%   │ -2983   │ 🔴 危险！     │
    # │ -0.3%~0% 轻微负      │ 16笔 │ 81%  │ +2274   │ ✅ 安全       │
    # │ >= 0% 正常/正        │ 19笔 │ 84%  │ +1704   │ ✅ 安全       │
    # └────────────────────────────────────────────────────────────────┘
    # 
    # 🔴 为什么中负区间（-0.44%~-0.3%）最危险？
    # 
    # 1. **空头积累的危险区**：
    #    - 市场看跌但不极端 → 空头开始积累
    #    - 空头不算拥挤 → 容易被小型空头挤压
    #    - 资金费率成本：1.17%/3天（需支付）
    #    - 持仓时间长 → 累积损失大
    # 
    # 2. **三大失败案例**：
    #    - PIPPINUSDT: Premium -0.43%, 持仓96h, 亏损-5204 (45%止损)
    #    - ICNTUSDT: Premium -0.41%, 持仓13h, 亏损-464 (顶级交易者止损)
    #    - DASHUSDT: Premium -0.43%, 持仓11h, 亏损-3282 (顶级交易者止损)
    # 
    # 3. **本质原因**：错误的介入时机
    #    - 空头"半路出家"的陷阱
    #    - 市场共识尚未形成
    #    - 既要支付资金费率，又容易被反向
    # 
    # 🟢 为什么超极端区间（< -2.65%）反而安全？
    # 
    # 1. **反向指标效应**：
    #    - Premium超负 = 市场极度恐慌
    #    - 空头极度拥挤 = 可能"跌过头了"
    #    - 资金费率超高（7.5%/3天）→ 空头不敢加仓
    # 
    # 2. **快速止盈特征**：
    #    - RIVERUSDT: Premium -4.68%, 15小时止盈 +3259
    #    - BEATUSDT: Premium -4.03%, 11小时止盈 +2075
    #    - 平均持仓：13小时（vs 中负区间40小时）
    # 
    # 3. **交易智慧**：
    #    "不要在市场半信半疑时做空，要在极度恐慌或正常时做空"
    # 
    # ✅ 风控验证（对比测试）：
    # - 有中负区间风控：总收益 108,718 USDT, 胜率 85.71%, 盈亏比 1.41
    # - 无中负区间风控：总收益 72,559 USDT, 胜率 80.77%, 盈亏比 1.02
    # - 保护收益：+36,160 USDT (+50%)
    # ============================================================================
    
    # 🔒 极度负Premium危险区间（与backtrade8.py保持一致）
    'premium_extreme_negative_min': -0.0265,  # 极度负区间下限：-2.65%
    'premium_extreme_negative_max': -0.017,   # 极度负区间上限：-1.7%
    
    # 🔒 中负Premium危险区间（核心风控 - 已验证有效）
    # 回测验证：3笔全部亏损（PIPPINUSDT -5204/ICNTUSDT -464/DASHUSDT -3282），总亏损-8949 USDT
    'premium_avg_dangerous_min': -0.0044,   # 危险区间下限：-0.44%
    'premium_avg_dangerous_max': -0.003,    # 危险区间上限：-0.3%
    
    # 综合判断：1个信号即拦截
    'max_danger_signals': 1,
}

# Premium数据缓存（避免重复查询）
_premium_cache: Dict[str, dict] = {}

# ============================================================================
# 🆕 买卖量风控配置 - 完全过滤模式（严格风控）
# ============================================================================
# 策略说明：
# 基于对回测数据的分析，发现满足以下任意一个条件时，止损概率较高：
# 1. 最后2小时卖量增长率在 [450%, 530%) 区间
# 2. 买量加速度在 [0.06, 0.12) 区间
# 
# 风控逻辑：满足任意一个条件即完全过滤（OR 关系）
# 
# 📊 回测数据验证（2025-11-01 至 2026-01-17）：
# - 总收益：35,164 USDT，收益率：351.64%
# - 胜率：81.63%，止损率：16.36%
# - 拦截：15笔高风险信号
# - 优势：更高胜率、更低止损率、更稳健
# 
# 🎯 用户选择：完全过滤（严格风控）
# 理由：宁可少赚，也要降低风险，追求更稳健的策略
# ============================================================================
ENABLE_VOLUME_RISK_FILTER = True  # 是否启用买卖量风控
VOLUME_RISK_CONFIG = {
    'sell_vol_increase_min': 4.5,      # 卖量增长率下限：450%
    'sell_vol_increase_max': 5.3,      # 卖量增长率上限：530%
    'buy_acceleration_min': 0.06,      # 买量加速度下限：0.06
    'buy_acceleration_max': 0.12,      # 买量加速度上限：0.12
}

def format_price(price: float) -> str:
    """根据价格大小智能格式化显示"""
    if price == 0:
        return "0.00000000"
    elif price < 0.00001:
        return f"{price:.10f}"  # 超小价格显示10位
    elif price < 0.0001:
        return f"{price:.8f}"   # 极小价格显示8位
    elif price < 0.01:
        return f"{price:.6f}"   # 很小价格显示6位
    elif price < 1:
        return f"{price:.5f}"   # 小价格显示5位
    elif price < 100:
        return f"{price:.4f}"   # 中等价格显示4位
    elif price < 10000:
        return f"{price:.2f}"   # 大价格显示2位
    else:
        return f"{price:.1f}"   # 很大价格显示1位

def get_local_symbols() -> List[str]:
    """获取本地数据库中的交易对列表 (PostgreSQL)"""
    try:
        # 在 PostgreSQL 中查询 K1h_ 开头的表名
        query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name LIKE 'K1h%'
        """)
        with engine.connect() as conn:
            result = conn.execute(query)
            tables = result.fetchall()

        symbols = []
        for table, in tables:
            symbol = table.replace('K1h', '')
            symbols.append(symbol)

        return symbols
    except Exception as e:
        logging.error(f"获取交易对列表失败: {e}")
        return []

def get_hourly_kline_at_timestamp(symbol: str, target_timestamp: int) -> Optional[pd.Series]:
    """获取指定交易对在指定时间戳的小时K线数据 (PostgreSQL)"""
    try:
        table_name = f"K1h{symbol}"
        
        # 查询该时间戳的K线数据
        time_tolerance = 3600 * 1000  # 1小时的毫秒数
        query = text(f"""
            SELECT * FROM "{table_name}" 
            WHERE open_time >= :start AND open_time < :end
            ORDER BY ABS(open_time - :target)
            LIMIT 1
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql_query(
                query, 
                conn, 
                params={"start": target_timestamp - time_tolerance, "end": target_timestamp + time_tolerance, "target": target_timestamp}
            )

        if df.empty:
            return None

        return df.iloc[0]
    except Exception as e:
        return None

def get_kline_data_for_date(symbol: str, date: str) -> Optional[pd.Series]:
    """获取指定交易对在指定日期的日K线数据 (PostgreSQL)"""
    try:
        table_name = f"K1d{symbol}"
        
        # 尝试从日K线表读取
        query = text(f"SELECT * FROM \"{table_name}\" WHERE trade_date = :date OR trade_date LIKE :date_prefix")
        
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"date": date, "date_prefix": f'{date}%'})
        
        if not df.empty:
            return df.iloc[0]
        
        # 如果日K线表不存在或没有数据，从小时K线聚合
        hourly_table = f"K1h{symbol}"
        
        # 查询当天所有小时K线（UTC时间）
        hourly_query = text(f"""
            SELECT * FROM \"{hourly_table}\" 
            WHERE open_time >= :start AND open_time < :end
            ORDER BY open_time
        """)
        
        # 日期范围：UTC 00:00 到 24:00（毫秒时间戳）
        start_ts = int(pd.Timestamp(f"{date} 00:00:00", tz='UTC').timestamp() * 1000)
        end_ts = int(pd.Timestamp(f"{date} 23:59:59", tz='UTC').timestamp() * 1000)
        
        with engine.connect() as conn:
            hourly_df = pd.read_sql_query(hourly_query, conn, params={"start": start_ts, "end": end_ts})
        
        if hourly_df.empty:
            return None
        
        # 聚合成日K线
        daily_data = pd.Series({
            'open': hourly_df.iloc[0]['open'],
            'high': hourly_df['high'].max(),
            'low': hourly_df['low'].min(),
            'close': hourly_df.iloc[-1]['close'],
            'volume': hourly_df['volume'].sum(),
            'quote_volume': hourly_df['quote_volume'].sum(),
            'trade_date': date
        })
        
        return daily_data
        
    except Exception as e:
        logging.debug(f"获取 {symbol} 在 {date} 的K线数据失败: {e}")
        return None

def get_premium_index_data(symbol: str, check_datetime: str) -> dict:
    """
    从数据库获取Premium Index（基差率）数据（带缓存）
    
    Premium Index = (标记价格 - 指数价格) / 指数价格
    - 正值：合约价格 > 现货价格（看涨情绪）
    - 负值：合约价格 < 现货价格（看跌情绪）
    
    Args:
        symbol: 交易对符号（如 'BTCUSDT'）
        check_datetime: 检查时间（格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'）
    
    Returns:
        dict: {
            'current_premium': 当前基差率,
            'avg_24h_premium': 24小时平均基差率,
            'premium_trend': 基差率趋势（24h变化率）,
            'data_points': 数据点数量,
            'success': 是否成功获取数据
        }
    """
    # 检查缓存
    cache_key = f"{symbol}_{check_datetime}"
    if cache_key in _premium_cache:
        return _premium_cache[cache_key]
    
    result = {
        'current_premium': None,
        'avg_24h_premium': None,
        'premium_trend': None,
        'data_points': 0,
        'success': False
    }
    
    try:
        # 解析检查时间（已经是UTC时间）
        if ' ' in check_datetime:
            check_dt = datetime.strptime(check_datetime, '%Y-%m-%d %H:%M:%S')
        else:
            check_dt = datetime.strptime(check_datetime, '%Y-%m-%d')
        
        # ✅ 转换为UTC毫秒时间戳（使用calendar.timegm确保UTC）
        check_ts = int(calendar.timegm(check_dt.timetuple()) * 1000)
        start_24h_ts = int(calendar.timegm((check_dt - timedelta(hours=24)).timetuple()) * 1000)
        
        # 查询Premium历史数据
        query = text('''
            SELECT open_time, close
            FROM "premium_index_history"
            WHERE symbol = :symbol
              AND open_time >= :start
              AND open_time <= :end
              AND interval = '1h'
            ORDER BY open_time ASC
            LIMIT 25
        ''')
        
        with engine.connect() as conn:
            cursor = conn.execute(query, {"symbol": symbol, "start": start_24h_ts, "end": check_ts})
            rows = cursor.fetchall()
        
        if not rows:
            # 缓存失败结果，避免重复查询
            _premium_cache[cache_key] = result
            return result
        
        # 提取数据
        premiums = [float(row[1]) for row in rows]
        
        # 计算指标
        result['current_premium'] = premiums[-1]  # 最新值
        result['avg_24h_premium'] = sum(premiums) / len(premiums)  # 24h平均
        
        # 计算趋势（最近值 vs 24h前值）
        if len(premiums) >= 2:
            old_premium = premiums[0]
            new_premium = premiums[-1]
            if old_premium != 0:
                result['premium_trend'] = (new_premium - old_premium) / abs(old_premium)
            else:
                result['premium_trend'] = 0
        
        result['data_points'] = len(premiums)
        result['success'] = True
        
        # 缓存成功结果
        _premium_cache[cache_key] = result
        
    except Exception as e:
        logging.warning(f"获取 {symbol} Premium数据失败: {e}")
        # 缓存失败结果
        _premium_cache[cache_key] = result
    
    return result


def check_premium_risk(
    symbol: str,
    check_datetime: str
) -> dict:
    """
    Premium Index精确拦截风控检查
    
    基于回测验证的精确拦截策略：
    - 只拦截中负Premium区间（-0.44% ~ -0.3%）
    - 3笔目标区间交易全部止损（DASHUSDT/ICNTUSDT/PIPPINUSDT）
    - 零误拦，收益率提升65.1%
    
    Args:
        symbol: 交易对
        check_datetime: 检查时间（UTC时间）
    
    Returns:
        {
            'passed': bool,  # 是否通过风控
            'reason': str,   # 原因说明
            'premium_avg': float,  # 24h平均Premium
            'premium_current': float,  # 当前Premium
            'risk_level': str  # 风险等级
        }
    """
    # 获取Premium数据
    premium_data = get_premium_index_data(symbol, check_datetime)
    
    if not premium_data['success']:
        # 无法获取Premium数据，按正常流程（不阻断）
        return {
            'passed': True,
            'reason': '无法获取Premium数据，按正常流程',
            'premium_avg': None,
            'premium_current': None,
            'risk_level': 'unknown'
        }
    
    premium_avg = premium_data['avg_24h_premium']
    premium_current = premium_data['current_premium']
    
    if premium_avg is None:
        return {
            'passed': True,
            'reason': 'Premium数据不完整，按正常流程',
            'premium_avg': None,
            'premium_current': None,
            'risk_level': 'unknown'
        }
    
    # ✅ 1. 优先检查极度负Premium区间（-2.65% ~ -1.7%）
    extreme_negative_min = PREMIUM_CONTROL_CONFIG.get('premium_extreme_negative_min', -0.0265)
    extreme_negative_max = PREMIUM_CONTROL_CONFIG.get('premium_extreme_negative_max', -0.017)
    
    if extreme_negative_min < premium_avg < extreme_negative_max:
        # 触发极度负区间风控
        return {
            'passed': False,
            'reason': (
                f"🔴 Premium风控拦截：24h平均 {premium_avg*100:.4f}% 在极度负区间 "
                f"[{extreme_negative_min*100:.2f}%, {extreme_negative_max*100:.1f}%]\n"
                f"   （市场极度看空，易发生空头挤压，逆势做空危险）\n"
                f"   历史案例：TNSRUSDT/TRADOORUSDT 单笔亏损-2,000~-8,000 USDT"
            ),
            'premium_avg': premium_avg,
            'premium_current': premium_current,
            'risk_level': 'extreme_danger'
        }
    
    # ✅ 2. 检查中负Premium区间（-0.44% ~ -0.3%）【核心风控 - 已验证有效】
    # 回测验证：3笔全部亏损，总亏损-8,949 USDT（PIPPINUSDT/ICNTUSDT/DASHUSDT）
    # 拦截效率：100%（3/3），胜率提升：80.77% → 85.71%，总收益提升50%
    dangerous_min = PREMIUM_CONTROL_CONFIG['premium_avg_dangerous_min']
    dangerous_max = PREMIUM_CONTROL_CONFIG['premium_avg_dangerous_max']
    
    if dangerous_min < premium_avg < dangerous_max:
        # 触发中负区间风控
        implied_fr = (premium_avg + 0.0001) / 3 * 100
        return {
            'passed': False,
            'reason': (
                f"🔴 Premium风控拦截：24h平均 {premium_avg*100:.4f}% 在危险区间 "
                f"[{dangerous_min*100:.2f}%, {dangerous_max*100:.1f}%]\n"
                f"   （空头需支付资金费率约{abs(implied_fr):.3f}%/8h，且该区间100%亏损）\n"
                f"   历史数据：此区间3笔交易全部止损，总亏损-8,949 USDT"
            ),
            'premium_avg': premium_avg,
            'premium_current': premium_current,
            'risk_level': 'danger'
        }
    
    # 通过风控
    if premium_avg < extreme_negative_min:
        # 超高负Premium（<-2.65%）：更极端，需特别标注
        risk_level = 'safe'
        reason = (
            f"✅ Premium {premium_avg*100:.4f}% < {extreme_negative_min*100:.2f}% "
            f"（超高负Premium，市场极度看跌，利于做空）"
        )
    elif premium_avg < dangerous_min:
        # 高负Premium（-2.65% ~ -0.44%）：安全区间
        risk_level = 'safe'
        reason = (
            f"✅ Premium {premium_avg*100:.4f}% 在安全区间 "
            f"（市场看跌情绪，利于做空）"
        )
    elif premium_avg > dangerous_max:
        # 低负或正Premium（>-0.3%）：表现良好，安全
        risk_level = 'safe'
        reason = (
            f"✅ Premium {premium_avg*100:.4f}% > {dangerous_max*100:.1f}% "
            f"（正常区间，风控通过）"
        )
    else:
        risk_level = 'safe'
        reason = f"✅ Premium {premium_avg*100:.4f}% 正常"
    
    return {
        'passed': True,
        'reason': reason,
        'premium_avg': premium_avg,
        'premium_current': premium_current,
        'risk_level': risk_level
    }


def check_volume_risk(symbol: str, entry_datetime: str) -> dict:
    """
    买卖量风控检查：检查最后2小时卖量增长率和买量加速度
    
    Args:
        symbol: 交易对符号
        entry_datetime: 建仓时间 'YYYY-MM-DD HH:MM:SS'
    
    Returns:
        dict: {
            'should_trade': 是否应该建仓,
            'reason': 风控原因,
            'sell_vol_increase': 卖量增长率,
            'buy_acceleration': 买量加速度
        }
    """
    result = {
        'should_trade': True,
        'reason': '',
        'sell_vol_increase': None,
        'buy_acceleration': None
    }
    
    if not ENABLE_VOLUME_RISK_FILTER:
        result['reason'] = '买卖量风控已禁用'
        return result
    
    try:
        # 解析入场时间
        if ' ' in entry_datetime:
            entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d %H:%M:%S')
        else:
            entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d')
        
        # 计算24小时前的时间
        start_dt = entry_dt - timedelta(hours=24)
        entry_ts = int(entry_dt.timestamp() * 1000)
        start_ts = int(start_dt.timestamp() * 1000)
        
        # 获取24小时K线数据
        table_name = f'K1h{symbol}'
        
        query = text(f"""
            SELECT 
                open_time,
                volume,
                active_buy_volume
            FROM "{table_name}"
            WHERE open_time >= :start AND open_time < :entry
            ORDER BY open_time ASC
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"start": start_ts, "entry": entry_ts})
        
        if df.empty or len(df) < 12:
            result['reason'] = '数据不足，跳过风控检查'
            return result
        
        # 计算主动卖量
        df['active_sell_volume'] = df['volume'] - df['active_buy_volume']
        
        # 计算买卖比
        df['buy_sell_ratio'] = df['active_buy_volume'] / (df['active_sell_volume'] + 1e-10)
        
        # 1. 计算最后2小时卖量增长率
        last_2h = df.iloc[-2:]
        first_22h = df.iloc[:-2] if len(df) > 2 else df
        
        last_2h_sell_avg = last_2h['active_sell_volume'].mean()
        first_22h_sell_avg = first_22h['active_sell_volume'].mean()
        
        if first_22h_sell_avg > 0:
            sell_vol_increase_rate = (last_2h_sell_avg - first_22h_sell_avg) / first_22h_sell_avg
        else:
            sell_vol_increase_rate = 0
        
        result['sell_vol_increase'] = sell_vol_increase_rate
        
        # 2. 计算买量加速度（最后6小时 vs 前18小时）
        last_6h = df.iloc[-6:] if len(df) >= 6 else df
        first_18h = df.iloc[:-6] if len(df) > 6 else df.iloc[:len(df)//2]
        
        last_6h_buy_ratio = last_6h['buy_sell_ratio'].mean()
        first_18h_buy_ratio = first_18h['buy_sell_ratio'].mean()
        
        buy_acceleration = last_6h_buy_ratio - first_18h_buy_ratio
        result['buy_acceleration'] = buy_acceleration
        
        # 3. 检查是否满足风控条件（满足任意一个条件即拦截）
        config = VOLUME_RISK_CONFIG
        
        sell_in_danger_zone = (config['sell_vol_increase_min'] <= sell_vol_increase_rate < config['sell_vol_increase_max'])
        buy_in_danger_zone = (config['buy_acceleration_min'] <= buy_acceleration < config['buy_acceleration_max'])
        
        if sell_in_danger_zone or buy_in_danger_zone:
            result['should_trade'] = False
            danger_reasons = []
            if sell_in_danger_zone:
                danger_reasons.append(f"卖量增长率 {sell_vol_increase_rate*100:.1f}% 在危险区间 [{config['sell_vol_increase_min']*100:.0f}%, {config['sell_vol_increase_max']*100:.0f}%)")
            if buy_in_danger_zone:
                danger_reasons.append(f"买量加速度 {buy_acceleration:.4f} 在危险区间 [{config['buy_acceleration_min']:.2f}, {config['buy_acceleration_max']:.2f})")
            
            result['reason'] = f"买卖量风控拦截: {' 且 '.join(danger_reasons)}"
        else:
            result['reason'] = (
                f"买卖量风控通过: "
                f"卖量增长率 {sell_vol_increase_rate*100:.1f}%, "
                f"买量加速度 {buy_acceleration:.4f}"
            )
        
        return result
        
    except Exception as e:
        logging.warning(f"买卖量风控检查失败: {e}")
        result['reason'] = f'买卖量风控检查失败: {e}'
        return result


def get_real_time_funding_rate(symbol: str) -> dict:
    """
    实时获取资金费率（不依赖历史数据库）
    
    Args:
        symbol: 交易对（如'BTCUSDT'）
    
    Returns:
        {
            'funding_rate': float,
            'mark_price': float,
            'index_price': float,
            'next_funding_time': str
        }
        或 None（如果失败）
    """
    try:
        url = 'https://fapi.binance.com/fapi/v1/premiumIndex'
        params = {'symbol': symbol}
        response = requests.get(url, params=params, timeout=10)  # 🔧 增加超时时间到10秒
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        return {
            'funding_rate': float(data['lastFundingRate']),
            'mark_price': float(data['markPrice']),
            'index_price': float(data.get('indexPrice', 0)),
            'next_funding_time': data['nextFundingTime']
        }
    except Exception as e:
        logging.error(f"获取{symbol}资金费率失败: {e}")
        return None


def check_funding_rate_risk(
    symbol: str,
    entry_pct_chg: float,
    volume_amount: float = 0
) -> dict:
    """
    实时资金费率风控检查
    
    Args:
        symbol: 交易对
        entry_pct_chg: 建仓时的涨幅
        volume_amount: 成交额（可选）
    
    Returns:
        {
            'passed': bool,
            'delay_days': int,
            'reason': str,
            'funding_rate': float,
            'risk_level': str  # 'safe', 'warning', 'danger', 'extreme'
        }
    """
    
    # 获取实时资金费率
    funding_info = get_real_time_funding_rate(symbol)
    
    if not funding_info:
        # 无法获取资金费率，按正常流程（不阻断）
        return {
            'passed': True,
            'delay_days': 0,
            'reason': '无法获取资金费率，按正常流程',
            'funding_rate': None,
            'risk_level': 'unknown'
        }
    
    funding_rate = funding_info['funding_rate']
    
    # ===== 资金费率风控规则 =====
    
    # 🔕 规则1-4: 妖币判断相关规则（暂时禁用）
    # 原因：与backtrade8.py保持一致，暂不启用妖币风控
    
    # # 规则1: 极端负费率（<-0.5%）→ 强制跳过
    # if funding_rate < -0.005:
    #     return {
    #         'passed': False,
    #         'delay_days': 999,
    #         'reason': (
    #             f"🔴 极端负费率 {funding_rate*100:.3f}% < -0.5% "
    #             f"(期现严重失衡，妖币特征，强制避开)"
    #         ),
    #         'funding_rate': funding_rate,
    #         'risk_level': 'extreme'
    #     }
    # 
    # # 规则2: 严重负费率（<-0.3%）→ 强制跳过
    # if funding_rate < -0.003:
    #     return {
    #         'passed': False,
    #         'delay_days': 999,
    #         'reason': (
    #             f"🔴 负费率 {funding_rate*100:.3f}% < -0.3% "
    #             f"(妖币特征明显，强制避开)"
    #         ),
    #         'funding_rate': funding_rate,
    #         'risk_level': 'danger'
    #     }
    # 
    # # 规则3: 负费率 + 低成交额 → 强制跳过
    # if funding_rate < -0.001 and volume_amount > 0 and volume_amount < 3_00_000_000:
    #     return {
    #         'passed': False,
    #         'delay_days': 999,
    #         'reason': (
    #             f"🔴 负费率 {funding_rate*100:.3f}% + "
    #             f"低成交额 {volume_amount/1e8:.2f}亿 "
    #             f"(小市值妖币，极可能继续暴涨)"
    #         ),
    #         'funding_rate': funding_rate,
    #         'risk_level': 'danger'
    #     }
    # 
    # # 规则4: 负费率 + 超高涨幅 → 强制跳过
    # if funding_rate < -0.001 and entry_pct_chg > 100:
    #     return {
    #         'passed': False,
    #         'delay_days': 999,
    #         'reason': (
    #             f"🔴 负费率 {funding_rate*100:.3f}% + "
    #             f"超高涨幅 {entry_pct_chg:.1f}% "
    #             f"(妖币特征，避开)"
    #         ),
    #         'funding_rate': funding_rate,
    #         'risk_level': 'danger'
    #     }
    
    # 规则5: 轻度负费率（-0.3%到-0.1%）→ 延迟建仓（保留）
    if funding_rate < -0.001:
        return {
            'passed': True,
            'delay_days': 1,
            'reason': (
                f"⚠️ 负费率 {funding_rate*100:.3f}% "
                f"(期现价差大，延迟建仓观察)"
            ),
            'funding_rate': funding_rate,
            'risk_level': 'warning'
        }
    
    # 规则6: 费率正常或为正 → 正常执行
    if funding_rate >= -0.001:
        reason = f"✅ 资金费率 {funding_rate*100:.3f}% 正常"
        risk_level = 'safe'
        if funding_rate > 0.001:
            reason += "（多头付费，有利做空）"
            risk_level = 'very_safe'
        
        return {
            'passed': True,
            'delay_days': 0,
            'reason': reason,
            'funding_rate': funding_rate,
            'risk_level': risk_level
        }
    
    return {
        'passed': True,
        'delay_days': 0,
        'reason': '未知情况',
        'funding_rate': funding_rate,
        'risk_level': 'unknown'
    }


def get_funding_rate(symbol: str) -> Optional[float]:
    """获取当前资金费率（保留兼容性）"""
    funding_info = get_real_time_funding_rate(symbol)
    if funding_info:
        return funding_info['funding_rate']
    return None

def get_24h_quote_volume(symbol: str, date_str: str = None) -> float:
    """
    获取24小时成交额
    
    如果提供了日期，从数据库获取历史数据；否则从实时API获取
    
    Args:
        symbol: 交易对
        date_str: 日期字符串（可选，用于历史数据查询）
    
    Returns:
        24小时成交额（USDT）
    """
    try:
        # 🔧 修复：如果提供了日期，优先从数据库获取历史数据（不要用实时API）
        if date_str:
            table_name = f"K1d{symbol}"
            
            query = text(f"SELECT quote_volume FROM \"{table_name}\" WHERE trade_date LIKE :date_pattern")
            with engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params={"date_pattern": f"{date_str}%"})
            
            if not df.empty:
                quote_volume = float(df.iloc[0]['quote_volume'])
                logging.info(f"从数据库获取 {symbol} {date_str} 成交额: {quote_volume:,.0f} USDT")
                return quote_volume
            else:
                logging.warning(f"数据库中未找到 {symbol} {date_str} 的成交额数据")
        
        # 如果没有提供日期，或数据库查询失败，则从API获取实时数据
        try:
            url = 'https://fapi.binance.com/fapi/v1/ticker/24hr'
            params = {'symbol': symbol}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                quote_volume = float(data.get('quoteVolume', 0))
                if quote_volume > 0:
                    logging.info(f"从API获取 {symbol} 24h成交额: {quote_volume:,.0f} USDT")
                    return quote_volume
        except Exception as api_error:
            logging.warning(f"API获取 {symbol} 24h成交额失败: {api_error}")
        
        logging.warning(f"无法获取 {symbol} 的24h成交额数据")
        return 0.0
        
    except Exception as e:
        logging.error(f"获取 {symbol} 24h成交额失败: {e}")
        return 0.0

def get_top_trader_ratio(symbol: str, date_str: str) -> Optional[float]:
    """获取顶级交易者多空比 (PostgreSQL)"""
    try:
        # 将日期转换为时间戳范围
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        start_ts = int((date_obj - timedelta(days=1)).timestamp() * 1000)
        end_ts = int((date_obj + timedelta(days=1)).timestamp() * 1000)
        target_ts = int(date_obj.timestamp() * 1000)

        query = text('''
        SELECT long_short_ratio, long_account, short_account
        FROM "top_account_ratio"
        WHERE symbol = :symbol AND timestamp >= :start AND timestamp <= :end
        ORDER BY ABS(timestamp - :target) ASC LIMIT 1
        ''')

        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"symbol": symbol, "start": start_ts, "end": end_ts, "target": target_ts})

        if not df.empty:
            return float(df.iloc[0]['long_short_ratio'])
        return None
    except Exception as e:
        logging.error(f"获取 {symbol} 多空比失败: {e}")
        return None

def analyze_top_gainer(target_date: Optional[str] = None) -> Optional[Dict]:
    """
    分析涨幅第一的交易对（基于日K线UTC 0:00开盘价）
    
    Args:
        target_date: 要分析的日期（今天的日期），格式为 'YYYY-MM-DD'。如果为 None，则分析今天的数据
    
    Returns:
        分析结果的字典，如果失败返回None
    
    注意：
    - 使用日K线的开盘价计算24小时涨幅（UTC 0:00时刻）
    - 计算公式：(今日开盘价 - 昨日开盘价) / 昨日开盘价
    - 这样可以捕获到凌晨暴涨的币种
    - 例如：今天2026-01-23早上8点运行，分析2026-01-23 vs 2026-01-22的开盘价涨幅
    """
    print("=" * 80)
    print("🎯 建仓分析程序 - 涨幅第一交易对分析（日K线UTC 0:00时刻）")
    print("=" * 80)

    # 确定分析日期
    try:
        if target_date:
            # 使用指定的日期作为"今天"
            try:
                analyze_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            except ValueError:
                print(f"❌ 日期格式错误，请使用 YYYY-MM-DD 格式，例如: 2025-01-15")
                return
            
            analyze_date_str = analyze_date_obj.strftime('%Y-%m-%d')  # 今天
            prev_date_str = (analyze_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')  # 昨天
            entry_date_str = analyze_date_str  # 今天建仓
        else:
            # 自动分析今天的数据（UTC 0:00开盘价 vs 昨天UTC 0:00开盘价）
            now = datetime.now()
            analyze_date_obj = now  # 今天
            analyze_date_str = analyze_date_obj.strftime('%Y-%m-%d')
            prev_date_str = (analyze_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')  # 昨天
            entry_date_str = analyze_date_str  # 今天建仓

    except Exception as e:
        print(f"❌ 计算日期失败: {e}")
        return None

    if target_date:
        print(f"📅 分析日期: {analyze_date_str} (用户指定)")
    else:
        print(f"📅 分析日期: {analyze_date_str} (自动分析今天数据)")
    print(f"📊 统计方式: {prev_date_str} UTC 0:00开盘 vs {analyze_date_str} UTC 0:00开盘")
    print(f"🏗️  建仓日期: {entry_date_str}")
    print(f"ℹ️  说明: 使用日K线开盘价计算24小时涨幅（UTC 0:00时刻）")
    print()

    # 获取所有交易对
    symbols = get_local_symbols()
    if not symbols:
        print("❌ 无法获取交易对列表")
        return None

    print(f"🔍 正在分析 {len(symbols)} 个交易对...")

    # 计算每个交易对的涨幅（使用日K线开盘价）
    top_gainer = None
    max_pct_chg = float('-inf')

    for symbol in symbols:
        try:
            # 获取昨天的日K线数据（基准价格 = 昨天UTC 0:00开盘价）
            prev_day_data = get_kline_data_for_date(symbol, prev_date_str)
            if prev_day_data is None:
                continue

            prev_open = prev_day_data['open']  # 昨天UTC 0:00开盘价
            if pd.isna(prev_open) or prev_open <= 0:
                continue

            # 获取今天的日K线数据（今天UTC 0:00开盘价）
            analyze_day_data = get_kline_data_for_date(symbol, analyze_date_str)
            if analyze_day_data is None:
                continue

            analyze_open = analyze_day_data['open']  # 今天UTC 0:00开盘价
            analyze_high = analyze_day_data['high']
            analyze_low = analyze_day_data['low']
            analyze_close = analyze_day_data['close']
            
            if pd.isna(analyze_open) or analyze_open <= 0:
                continue

            # 计算涨幅（使用开盘价）
            # 公式：(今日开盘 - 昨日开盘) / 昨日开盘 * 100
            pct_chg = (analyze_open - prev_open) / prev_open * 100

            if pct_chg > max_pct_chg:
                max_pct_chg = pct_chg
                top_gainer = {
                    'symbol': symbol,
                    'pct_chg': pct_chg,
                    'prev_open': prev_open,  # 昨日开盘（UTC 0:00）
                    'analyze_open': analyze_open,  # 今日开盘（UTC 0:00）
                    'analyze_high': analyze_high,  # 今日最高
                    'analyze_low': analyze_low,  # 今日最低
                    'analyze_close': analyze_close,  # 今日收盘
                    'entry_date': entry_date_str  # 建仓日期
                }

        except Exception as e:
            logging.debug(f"分析 {symbol} 失败: {e}")
            continue

    if not top_gainer:
        print("❌ 未找到有效的涨幅数据")
        return None

    # 分析涨幅第一的交易对
    symbol = top_gainer['symbol']
    pct_chg = top_gainer['pct_chg']
    entry_date = top_gainer['entry_date']

    print("\n🏆 涨幅第一交易对分析")
    print("-" * 80)
    print(f"交易对: {symbol}")
    print(f"24小时涨幅: {pct_chg:.2f}% ({prev_date_str} UTC 0:00 → {analyze_date_str} UTC 0:00)")
    print(f"昨日开盘({prev_date_str} UTC 0:00): {format_price(top_gainer['prev_open'])}")
    print(f"今日开盘({analyze_date_str} UTC 0:00): {format_price(top_gainer['analyze_open'])}")
    print(f"今日最高: {format_price(top_gainer['analyze_high'])}")
    print(f"今日最低: {format_price(top_gainer['analyze_low'])}")
    print(f"当前价格(收盘): {format_price(top_gainer['analyze_close'])}")
    print(f"建仓日期: {entry_date}")
    print()

    # 风控分析
    print("🛡️ 风控分析")
    print("-" * 80)

    # ============================================================
    # 🔕 风控1：检查「从30天平均价涨幅」，避免主力获利不足继续拉升 (临时禁用用于测试)
    # ============================================================
    # 说明：与backtrade8.py同步，临时禁用此风控以测试其影响
    delay_entry_30d = False
    
    # # 动态阈值（与backtrade8.py保持一致）
    # # 关键：低涨幅币更危险（HUSDT案例：日涨35%，30天均涨55%仍亏-2343）
    # if pct_chg < 40:
    #     threshold = 51
    #     level_desc = "低中涨幅"
    # elif pct_chg < 60:
    #     threshold = 45
    #     level_desc = "中涨幅"
    # elif pct_chg < 100:
    #     threshold = 35
    #     level_desc = "高涨幅"
    # else:
    #     threshold = 10
    #     level_desc = "超高涨幅"
    #
    # try:
    #     # 计算30天平均价涨幅 (PostgreSQL)
    #     table_name = f"K1d{symbol}"
    #
    #     # 获取30天的数据（使用分析日前一天作为结束日期）
    #     end_date = prev_date_str
    #     start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
    #
    #     query = text(f'''
    #     SELECT AVG(close) as avg_close, MIN(trade_date) as first_date
    #     FROM "{table_name}"
    #     WHERE trade_date <= :end AND trade_date >= :start
    #     ''')
    #
    #     with engine.connect() as conn:
    #         df = pd.read_sql_query(query, conn, params={"end": end_date, "start": start_date})
    #
    #     if not df.empty and df.iloc[0]['avg_close']:
    #         avg_close_30d = df.iloc[0]['avg_close']
    #         prev_open = top_gainer['prev_open']  # 使用昨日开盘价
    #         from_avg_30d_pct = (prev_open - avg_close_30d) / avg_close_30d * 100
    #
    #         if from_avg_30d_pct < threshold:
    #             delay_entry_30d = True
    #             print(f"❌ 主力获利不足: {level_desc}(日涨{pct_chg:.1f}%), 30天均价涨幅{from_avg_30d_pct:.2f}% < {threshold}%")
    #         else:
    #             print(f"✅ 主力获利充足: {level_desc}(日涨{pct_chg:.1f}%), 30天均价涨幅{from_avg_30d_pct:.2f}% >= {threshold}%")
    #     else:
    #         print("⚠️  无法计算30天均价涨幅")
    # except Exception as e:
    #     print(f"⚠️  30天均价涨幅计算失败: {e}")
    
    print("ℹ️  30天均价涨幅风控已临时禁用（测试中）")

    # 2. 多空比检查（使用分析日前一天的数据）
    delay_entry = False
    top_ratio = get_top_trader_ratio(symbol, prev_date_str)
    if top_ratio is not None:
        if top_ratio < 0.85:
            delay_entry = True
            print(f"❌ 多空比过低: {top_ratio:.2f} < 0.85")
        else:
            print(f"✅ 多空比正常: {top_ratio:.2f} >= 0.85")
    else:
        print("⚠️  无法获取多空比数据")

    # 3. 成交额过滤（使用分析日前一天的数据）
    delay_entry_volume = False
    volume_24h = get_24h_quote_volume(symbol, prev_date_str)
    volume_yi = volume_24h / 1e8 if volume_24h > 0 else 0
    
    if ENABLE_VOLUME_FILTER and pct_chg >= HIGH_PCT_CHG_THRESHOLD:
        if volume_24h >= 0 and volume_24h < MIN_VOLUME_FOR_HIGH_PCT:
            delay_entry_volume = True
            # 根据成交额大小选择合适的显示格式
            if volume_yi < 0.1:
                print(f"❌ 成交额不足: {volume_yi:.4f}亿 ({volume_24h:,.0f} USDT) < 1.5亿")
            else:
                print(f"❌ 成交额不足: {volume_yi:.2f}亿 < 1.5亿")
            print(f"🔄 建议延迟建仓")
        else:
            print(f"✅ 成交额充足: {volume_yi:.2f}亿 >= 1.5亿")
    else:
        # 即使不触发成交额过滤，也显示成交额信息
        if volume_yi < 0.1:
            print(f"ℹ️  24h成交额: {volume_yi:.4f}亿 ({volume_24h:,.0f} USDT)")
        else:
            print(f"ℹ️  24h成交额: {volume_yi:.2f}亿")
    # 4. 延迟建仓价格检查
    should_delay = delay_entry or delay_entry_30d or delay_entry_volume
    
    # 确定实际建仓日期
    # - 如果不延迟：今天建仓（entry_date_str）
    # - 如果延迟：明天建仓（entry_date_str + 1天）
    if should_delay:
        actual_entry_date_obj = datetime.strptime(entry_date_str, '%Y-%m-%d') + timedelta(days=1)
        actual_entry_date_str = actual_entry_date_obj.strftime('%Y-%m-%d')
    else:
        actual_entry_date_str = entry_date_str

    if should_delay:
        print("\n🔄 延迟建仓检查")
        print("-" * 80)
        print(f"因风控触发，延迟到 {actual_entry_date_str} 建仓（第三天开盘）")

        # 尝试获取实际建仓日的数据（可能还没有）
        actual_entry_day_data = get_kline_data_for_date(symbol, actual_entry_date_str)
        if actual_entry_day_data is not None:
            entry_day_open = actual_entry_day_data['open']
            
            # 计算价格变化率（从涨幅日收盘价到建仓日开盘价）
            price_change_pct = ((entry_day_open - top_gainer['analyze_close']) / top_gainer['analyze_close']) * 100

            max_price_drop = 11.0  # 延迟建仓允许的最大跌幅阈值
            
            if price_change_pct < -max_price_drop:
                # 价格下跌超过11%，放弃建仓
                print(f"❌ 价格跌幅过大: 涨幅日收盘{format_price(top_gainer['analyze_close'])} → 建仓日开盘{format_price(entry_day_open)}")
                print(f"   跌幅{price_change_pct:.1f}% < -{max_price_drop:.1f}% (已开始大幅回调)")
                print("🚫 放弃建仓")
                should_delay = False  # 取消延迟，放弃建仓
            elif price_change_pct > 10:
                # 价格继续上涨超过10%，警告但仍可建仓
                print(f"⚠️  价格继续上涨: 涨幅日收盘{format_price(top_gainer['analyze_close'])} → 建仓日开盘{format_price(entry_day_open)}")
                print(f"   涨幅+{price_change_pct:.1f}% (价格继续走高)")
                print("🔄 可以延迟建仓，但注意价格已在高位")
            else:
                # 价格在合理区间内（-11%到+10%）
                if price_change_pct >= 0:
                    print(f"✅ 价格稳定上涨: 涨幅日收盘{format_price(top_gainer['analyze_close'])} → 建仓日开盘{format_price(entry_day_open)}")
                    print(f"   涨幅+{price_change_pct:.1f}% (价格走势正常)")
                else:
                    print(f"✅ 价格小幅回调: 涨幅日收盘{format_price(top_gainer['analyze_close'])} → 建仓日开盘{format_price(entry_day_open)}")
                    print(f"   跌幅{price_change_pct:.1f}% (回调幅度可接受)")
                print("🔄 可以延迟建仓")
        else:
            # 无法获取建仓日数据（通常是因为还没到那一天）
            print(f"ℹ️  建仓日 {actual_entry_date_str} 数据尚未生成，无法进行价格检查")
            print(f"💡 请在 {actual_entry_date_str} 再次运行本程序，检查建仓价格是否合适")
            print(f"📌 价格检查标准: 不能低于涨幅日收盘价 {format_price(top_gainer['analyze_close'])} 的11%")

    # 建仓建议
    print("\n💡 建仓建议")
    print("-" * 80)

    if pct_chg < MIN_PCT_CHG * 100:
        print(f"❌ 涨幅不足: {pct_chg:.1f}% < {MIN_PCT_CHG * 100:.0f}%")

        print(f"\n💡 涨幅最高的前5个交易对（在 {analyze_date_str}）")
        print("-" * 80)

        # 显示涨幅最高的几个交易对（使用开盘价计算）
        top_symbols = []
        for check_symbol in symbols[:200]:  # 检查前200个交易对
            try:
                check_prev_data = get_kline_data_for_date(check_symbol, prev_date_str)
                check_analyze_data = get_kline_data_for_date(check_symbol, analyze_date_str)
                if check_prev_data is not None and check_analyze_data is not None:
                    check_prev_open = check_prev_data['open']  # 昨日开盘价
                    check_analyze_open = check_analyze_data['open']  # 今日开盘价
                    if pd.isna(check_prev_open) or pd.isna(check_analyze_open) or check_prev_open <= 0:
                        continue
                    symbol_pct_chg = (check_analyze_open - check_prev_open) / check_prev_open * 100
                    # 过滤异常数据（涨幅绝对值超过1000%的可能是异常数据）
                    if abs(symbol_pct_chg) < 1000:
                        top_symbols.append((check_symbol, symbol_pct_chg))
            except:
                pass

        # 按涨幅排序并显示前5个
        top_symbols.sort(key=lambda x: x[1], reverse=True)
        for i, (check_symbol, pct) in enumerate(top_symbols[:5]):
            print(f"{i+1}. {check_symbol}: {pct:.2f}%")

        # 返回涨幅不足结果
        return {
            'timestamp': datetime.now().isoformat(),
            'analysis_date': analyze_date_str,
            'signal': {
                'symbol': symbol,
                'pct_chg': pct_chg,
                'yesterday_open': top_gainer['prev_open'],  # 昨日UTC 0:00开盘价
                'today_open': top_gainer['analyze_open'],  # 今日UTC 0:00开盘价
                'today_close': top_gainer['analyze_close'],
                'risk_level': 'low_gain',
                'insufficient_gain': True,
                'min_required': MIN_PCT_CHG * 100
            }
        }

    # 获取实际建仓日的开盘价（如果有）
    actual_entry_day_data = get_kline_data_for_date(symbol, actual_entry_date_str)
    if actual_entry_day_data is not None:
        entry_price = actual_entry_day_data['open']
        has_entry_data = True
    else:
        # 如果无法获取建仓日数据（数据还没生成），使用涨幅日开盘价作为参考
        entry_price = top_gainer['analyze_open']
        has_entry_data = False

    if should_delay:
        print("🔄 建议: 延迟一天建仓（第三天开盘）")
        entry_price_min = top_gainer['analyze_close'] * (1 - 0.11)  # 不能低于涨幅日收盘价的11%
        print(f"建仓日期: {actual_entry_date_str}")
        if has_entry_data:
            print(f"建仓价格: {format_price(entry_price)}")
        else:
            print(f"建仓价格: {format_price(entry_price)} (参考价，实际以{actual_entry_date_str}开盘价为准)")
        print(f"最低价格: {format_price(entry_price_min)} (不能低于此价格)")
    else:
        print("✅ 建议: 立即建仓（第二天开盘）")
        entry_price_min = entry_price  # 立即建仓没有最低价格限制
        print(f"建仓日期: {actual_entry_date_str}")
        if has_entry_data:
            print(f"建仓价格: {format_price(entry_price)}")
        else:
            print(f"建仓价格: {format_price(entry_price)} (参考价，实际以{actual_entry_date_str}开盘价为准)")
        print(f"最低价格: {format_price(entry_price_min)}")
    # 获取动态参数
    dynamic_params = get_dynamic_params(pct_chg)
    leverage = dynamic_params['leverage']
    profit_threshold = dynamic_params['profit_threshold']
    stop_loss_threshold = dynamic_params['stop_loss_threshold']
    add_position_threshold = dynamic_params['add_position_threshold']

    print("\n📊 交易参数")
    print("-" * 80)
    print(f"杠杆倍数: {leverage}x")
    print(f"止盈阈值: {profit_threshold*100:.0f}%")
    print(f"止损阈值: {stop_loss_threshold*100:.0f}%")
    print(f"补仓阈值: {add_position_threshold*100:.0f}%")
    # 计算具体价格
    if entry_price > 0:
        # 🔧 修复：做空策略需要考虑杠杆倍数
        # 实际价格变动 = 阈值 / 杠杆倍数
        stop_loss_price = entry_price * (1 + stop_loss_threshold / leverage)
        take_profit_price = entry_price * (1 - profit_threshold / leverage)
        add_position_price = entry_price * (1 + add_position_threshold / leverage)

        print("\n💰 关键价格")
        print("-" * 80)
        print(f"止损价格: {format_price(stop_loss_price)}")
        print(f"止盈价格: {format_price(take_profit_price)}")
        print(f"补仓价格: {format_price(add_position_price)}")
    # ============================================================================
    # Premium Index风控分析【优先检查，精确拦截】
    # ============================================================================
    if ENABLE_PREMIUM_CONTROL:
        print("\n🎯 Premium Index风控分析（精确拦截策略）")
        print("-" * 80)
        
        # 使用分析日前一天作为检查时间（与涨幅计算基准一致）
        check_datetime = prev_date_str
        
        premium_check = check_premium_risk(
            symbol=symbol,
            check_datetime=check_datetime
        )
        
        # 显示Premium数据
        if premium_check['premium_avg'] is not None:
            premium_avg_pct = premium_check['premium_avg'] * 100
            premium_current_pct = premium_check['premium_current'] * 100 if premium_check['premium_current'] else 0
            
            print(f"24小时平均Premium: {premium_avg_pct:+.4f}%")
            print(f"当前Premium: {premium_current_pct:+.4f}%")
            
            # 换算为资金费率（便于理解）
            implied_fr = (premium_check['premium_avg'] + 0.0001) / 3 * 100
            print(f"隐含资金费率: {implied_fr:+.4f}%/8h")
            
            # 风控判断
            risk_level = premium_check['risk_level']
            if risk_level == 'danger':
                print("\n🔴🔴 风险等级: 危险（中负Premium区间）")
                print(premium_check['reason'])
                print("\n⚠️  Premium精确拦截策略判定:")
                print("   ❌ 不通过 - 强制跳过此交易")
                print("   历史回测：此区间3笔交易全部止损，平均亏损-1,177 USDT/笔")
                print("   建议: 放弃此交易，等待更好机会")
                print("\n" + "=" * 80)
                print("🚫 分析结束 - Premium风控拦截，不建议建仓")
                print("=" * 80)
                
                # 返回风控拦截结果（获取动态参数）
                dynamic_params = get_dynamic_params(pct_chg)
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'analysis_date': analyze_date_str,
                    'signal': {
                        'symbol': symbol,
                        'pct_chg': pct_chg,
                        'yesterday_open': top_gainer['prev_open'],  # 昨日UTC 0:00开盘价
                        'today_open': top_gainer['analyze_open'],
                        'today_high': top_gainer['analyze_high'],
                        'today_low': top_gainer['analyze_low'],
                        'today_close': top_gainer['analyze_close'],
                        'entry_date': entry_date,
                        'risk_level': 'danger',
                        'premium_passed': False,
                        'premium_reason': premium_check['reason'],
                        'premium_avg': premium_check['premium_avg'],
                        'premium_current': premium_check['premium_current'],
                        'should_delay': False,  # Premium拦截时不延迟，直接不建仓
                        'dynamic_params': {
                            'leverage': dynamic_params['leverage'],
                            'profit_threshold': dynamic_params['profit_threshold'],
                            'stop_loss_threshold': dynamic_params['stop_loss_threshold'],
                            'add_position_threshold': dynamic_params['add_position_threshold']
                        }
                    }
                }
            elif risk_level == 'safe':
                print(f"\n🟢 风险等级: 安全")
                print(premium_check['reason'])
                print("✅ Premium风控通过，继续后续风控检查")
            else:
                print(f"\n⚪ 风险等级: 未知")
                print(premium_check['reason'])
        else:
            print("⚠️  无法获取Premium数据，按正常流程继续")
    
    # ============================================================================
    # 🆕 买卖量风控分析（严格风控）
    # ============================================================================
    print("\n📊 买卖量风控分析（主动买卖量特征检查）")
    print("-" * 80)
    
    # 检查时间设定为涨幅日的开盘时刻（建仓时刻）
    # 涨幅计算：(今日开盘 - 昨日开盘) / 昨日开盘
    # 所以买卖量应该检查：昨日开盘到今日开盘这24小时的数据
    entry_datetime_for_volume_check = f"{analyze_date_str} 00:00:00"
    
    volume_risk_check = check_volume_risk(
        symbol=symbol,
        entry_datetime=entry_datetime_for_volume_check
    )
    
    if volume_risk_check['sell_vol_increase'] is not None:
        sell_vol_pct = volume_risk_check['sell_vol_increase'] * 100
        buy_accel = volume_risk_check['buy_acceleration']
        
        print(f"最后2小时卖量增长率: {sell_vol_pct:+.1f}%")
        print(f"买量加速度: {buy_accel:+.4f}")
        
        config = VOLUME_RISK_CONFIG
        danger_zone_sell = f"[{config['sell_vol_increase_min']*100:.0f}%, {config['sell_vol_increase_max']*100:.0f}%)"
        danger_zone_buy = f"[{config['buy_acceleration_min']:.2f}, {config['buy_acceleration_max']:.2f})"
        
        print(f"\n风险阈值:")
        print(f"  - 卖量增长率危险区间: {danger_zone_sell}")
        print(f"  - 买量加速度危险区间: {danger_zone_buy}")
        
        # 判断是否通过风控
        if not volume_risk_check['should_trade']:
            print("\n🔴🔴 买卖量风控判定: 危险")
            print(f"⚠️  {volume_risk_check['reason']}")
            print("\n📊 回测验证（2025-11-01至2026-01-17）:")
            print("   - 此类特征交易止损率显著偏高")
            print("   - 拦截策略：胜率81.63%，总收益35,164 USDT")
            print("   - 建议：完全过滤，不建议建仓")
            print("\n" + "=" * 80)
            print("🚫 分析结束 - 买卖量风控拦截，不建议建仓")
            print("=" * 80)
            
            # 返回买卖量风控拦截结果
            return {
                'timestamp': datetime.now().isoformat(),
                'analysis_date': analyze_date_str,
                'signal': {
                    'symbol': symbol,
                    'pct_chg': pct_chg,
                    'yesterday_open': top_gainer['prev_open'],  # 昨日UTC 0:00开盘价
                    'today_open': top_gainer['analyze_open'],
                    'today_high': top_gainer['analyze_high'],
                    'today_low': top_gainer['analyze_low'],
                    'today_close': top_gainer['analyze_close'],
                    'entry_date': actual_entry_date_str,
                    'risk_level': 'danger',
                    'premium_passed': premium_check.get('passed', True) if ENABLE_PREMIUM_CONTROL else True,
                    'premium_avg': premium_check.get('premium_avg') if ENABLE_PREMIUM_CONTROL else None,
                    'premium_current': premium_check.get('premium_current') if ENABLE_PREMIUM_CONTROL else None,
                    'volume_risk_passed': False,
                    'volume_risk_reason': volume_risk_check['reason'],
                    'sell_vol_increase': volume_risk_check['sell_vol_increase'],
                    'buy_acceleration': volume_risk_check['buy_acceleration'],
                    'should_delay': should_delay,
                    'delay_30d': delay_entry_30d,
                    'delay_ratio': delay_entry,
                    'delay_volume': delay_entry_volume,
                    'dynamic_params': {
                        'leverage': leverage,
                        'profit_threshold': profit_threshold,
                        'stop_loss_threshold': stop_loss_threshold,
                        'add_position_threshold': add_position_threshold
                    }
                }
            }
        else:
            print("\n🟢 买卖量风控判定: 通过")
            print(f"✅ {volume_risk_check['reason']}")
            print("👍 主动买卖量特征正常，继续后续风控检查")
    else:
        print(f"⚠️  {volume_risk_check['reason']}")
    
    # ============================================================================
    # 🔕 资金费率风控分析（已禁用 - 与backtrade8.py保持一致）
    # ============================================================================
    # print("\n💸 资金费率风控分析")
    # print("-" * 80)
    #
    # # 获取成交额用于风控（使用分析日前一天的数据）
    # volume_24h = get_24h_quote_volume(symbol, prev_date_str)
    # 
    # # 执行资金费率风控检查
    # funding_check = check_funding_rate_risk(
    #     symbol=symbol,
    #     entry_pct_chg=pct_chg,
    #     volume_amount=volume_24h
    # )
    # 
    # if funding_check['funding_rate'] is not None:
    #     funding_rate = funding_check['funding_rate']
    #     funding_rate_pct = funding_rate * 100
    #     
    #     # 显示资金费率
    #     print(f"当前资金费率: {funding_rate_pct:.4f}%")
    #     
    #     # 风控判断
    #     risk_level = funding_check['risk_level']
    #     if risk_level == 'extreme':
    #         print("🔴🔴🔴 风险等级: 极端危险")
    #         print(f"⚠️  {funding_check['reason']}")
    #         print("💀 做空成本极高，可能每天支付6-48%的资金费！")
    #         print("🚫 强烈建议: 放弃此交易")
    #     elif risk_level == 'danger':
    #         print("🔴🔴 风险等级: 危险")
    #         print(f"⚠️  {funding_check['reason']}")
    #         print("💸 做空成本高，妖币特征明显")
    #         print("🚫 建议: 不要建仓")
    #     elif risk_level == 'warning':
    #         print("🟡 风险等级: 警告")
    #         print(f"⚠️  {funding_check['reason']}")
    #         print("🔄 建议: 延迟建仓，观察费率变化")
    #     elif risk_level == 'safe':
    #         print("🟢 风险等级: 安全")
    #         print(f"✅ {funding_check['reason']}")
    #         print("👍 可以正常执行做空策略")
    #     elif risk_level == 'very_safe':
    #         print("🟢🟢 风险等级: 非常安全")
    #         print(f"✅ {funding_check['reason']}")
    #         print("💰 多头付费给空头，做空成本低，最佳时机！")
    #     else:
    #         print("⚪ 风险等级: 未知")
    #         print(f"ℹ️  {funding_check['reason']}")
    #     
    #     # 计算做空成本（如果是负费率）
    #     if funding_rate < 0:
    #         # 假设每8小时结算一次
    #         cost_per_8h = abs(funding_rate) * 100
    #         cost_per_day = cost_per_8h * 3
    #         cost_per_3days = cost_per_day * 3
    #         
    #         print(f"\n📊 做空成本估算（2倍杠杆）:")
    #         print(f"   每次结算: {cost_per_8h:.2f}%")
    #         print(f"   每天成本: {cost_per_day:.2f}%")
    #         print(f"   3天成本: {cost_per_3days:.2f}%")
    #         
    #         if cost_per_3days > 10:
    #             print(f"   ⚠️  3天成本超过{cost_per_3days:.1f}%，风险极高！")
    #     
    #     # 最终判断
    #     print(f"\n🎯 资金费率风控结论:")
    #     if not funding_check['passed']:
    #         print("   ❌ 不通过 - 强制跳过此交易")
    #         print("   原因: 资金费率异常，妖币特征明显")
    #     elif funding_check['delay_days'] > 0:
    #         print(f"   🔄 建议延迟 {funding_check['delay_days']} 天观察")
    #         print("   原因: 资金费率有风险信号")
    #     else:
    #         print("   ✅ 通过 - 可以正常交易")
    # else:
    #     print("⚠️  无法获取资金费率数据")

    print("\n" + "=" * 80)
    print("🎯 分析完成 - 请根据上述信息决定是否建仓")
    print("=" * 80)
    
    # ============================================================================
    # 返回分析结果（用于保存和展示）
    # ============================================================================
    result_data = {
        'timestamp': datetime.now().isoformat(),
        'analysis_date': analyze_date_str,
        'signal': {
            'symbol': symbol,
            'pct_chg': pct_chg,
            'yesterday_open': top_gainer['prev_open'],  # 昨日UTC 0:00开盘价
            'today_open': top_gainer['analyze_open'],
            'today_high': top_gainer['analyze_high'],
            'today_low': top_gainer['analyze_low'],
            'today_close': top_gainer['analyze_close'],
            'entry_date': actual_entry_date_str,
            'risk_level': premium_check.get('risk_level', 'unknown') if ENABLE_PREMIUM_CONTROL else 'unknown',
            'premium_passed': premium_check.get('passed', True) if ENABLE_PREMIUM_CONTROL else True,
            'premium_avg': premium_check.get('premium_avg') if ENABLE_PREMIUM_CONTROL else None,
            'premium_current': premium_check.get('premium_current') if ENABLE_PREMIUM_CONTROL else None,
            'volume_risk_passed': volume_risk_check.get('should_trade', True),
            'sell_vol_increase': volume_risk_check.get('sell_vol_increase'),
            'buy_acceleration': volume_risk_check.get('buy_acceleration'),
            'funding_rate': funding_check.get('funding_rate') if 'funding_check' in locals() else None,
            'funding_passed': funding_check.get('passed', True) if 'funding_check' in locals() else True,
            'should_delay': should_delay,
            'delay_30d': delay_entry_30d,
            'delay_ratio': delay_entry,
            'delay_volume': delay_entry_volume,
            'dynamic_params': {
                'leverage': leverage,
                'profit_threshold': profit_threshold,
                'stop_loss_threshold': stop_loss_threshold,
                'add_position_threshold': add_position_threshold
            }
        }
    }
    
    return result_data

def get_dynamic_params(pct_chg: float) -> Dict:
    """获取动态交易参数"""
    for max_pct, leverage, profit_th, stop_loss_th, add_pos_th, entry_rise in DYNAMIC_STRATEGY_CONFIG:
        if pct_chg < max_pct:
            return {
                'leverage': leverage,
                'profit_threshold': profit_th,
                'stop_loss_threshold': stop_loss_th,
                'add_position_threshold': add_pos_th,
                'entry_rise_threshold': entry_rise
            }

    # 默认返回最后一档
    _, leverage, profit_th, stop_loss_th, add_pos_th, entry_rise = DYNAMIC_STRATEGY_CONFIG[-1]
    return {
        'leverage': leverage,
        'profit_threshold': profit_th,
        'stop_loss_threshold': stop_loss_th,
        'add_position_threshold': add_pos_th,
        'entry_rise_threshold': entry_rise
    }

def save_signals_to_json(signal_data: Dict, output_file: str = "jcfx_signals.json"):
    """
    将分析结果保存到JSON文件，供前端页面展示
    
    Args:
        signal_data: 分析结果数据（直接来自 analyze_top_gainer 的返回值）
        output_file: 输出文件路径
    """
    try:
        # signal_data 已经包含了 timestamp, analysis_date 和 signal
        # 直接保存即可，不需要再嵌套一层
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(signal_data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"✅ 分析结果已保存到: {output_file}")
    except Exception as e:
        logging.error(f"❌ 保存JSON文件失败: {e}")

def send_email_notification(signal_data: Dict, email_to: str = "13910306825@163.com"):
    """
    发送邮件通知
    
    Args:
        signal_data: 分析结果数据
        email_to: 接收邮箱
    """
    try:
        # 导入 notifier
        from notifier import Notifier
        
        notifier = Notifier()
        
        # 检查邮件是否配置
        if not notifier.config.get('email', {}).get('enabled', False):
            logging.warning("⚠️  邮件通知未启用，请在 notifier_config.json 中配置")
            return
        
        symbol = signal_data.get('symbol', 'UNKNOWN')
        pct_chg = signal_data.get('pct_chg', 0)
        current_price = signal_data.get('today_close', 0)
        risk_level = signal_data.get('risk_level', 'unknown')
        should_delay = signal_data.get('should_delay', False)
        premium_passed = signal_data.get('premium_passed', True)
        
        # 构建邮件标题
        if not premium_passed:
            title = f"⚠️ JCFX信号 - {symbol} (Premium风控拦截)"
        elif should_delay:
            title = f"🔄 JCFX信号 - {symbol} (建议延迟建仓)"
        else:
            title = f"🎯 JCFX信号 - {symbol} (涨幅第一做空)"
        
        # 构建邮件正文
        message = f"""
🎯 涨幅第一做空信号

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 基本信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
交易对: {symbol}
24小时涨幅: {pct_chg:.2f}%
当前价格: {current_price}
分析时间: {signal_data.get('analysis_date', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ 风控状态
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # 添加风控信息
        if not premium_passed:
            message += "❌ Premium风控: 未通过\n"
            message += f"   原因: {signal_data.get('premium_reason', 'N/A')}\n"
        else:
            message += "✅ Premium风控: 通过\n"
        
        if should_delay:
            message += "🔄 建仓建议: 延迟建仓\n"
            delay_reasons = []
            if signal_data.get('delay_60d'): delay_reasons.append("主力获利不足")
            if signal_data.get('delay_ratio'): delay_reasons.append("多空比过低")
            if signal_data.get('delay_volume'): delay_reasons.append("成交额不足")
            message += f"   原因: {', '.join(delay_reasons)}\n"
        else:
            message += "✅ 建仓建议: 可立即建仓\n"
        
        message += f"\n🎯 风险等级: {risk_level}\n"
        
        # 添加动态参数
        params = signal_data.get('dynamic_params', {})
        if params:
            message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ 动态参数建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
杠杆倍数: {params.get('leverage', 'N/A')}x
止盈阈值: {params.get('profit_threshold', 0)*100:.0f}%
止损阈值: {params.get('stop_loss_threshold', 0)*100:.0f}%
补仓阈值: {params.get('add_position_threshold', 0)*100:.0f}%
"""
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 查看详情
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Web页面: http://localhost:5001/index_multi.html
(点击"涨幅第一做空"标签查看)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # 发送邮件
        notifier.send_email(email_to, title, message)
        logging.info(f"✅ 邮件通知已发送到: {email_to}")
        
    except ImportError:
        logging.warning("⚠️  未找到 notifier 模块，跳过邮件通知")
    except Exception as e:
        logging.error(f"❌ 发送邮件失败: {e}")

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(
        description='建仓分析程序 - 分析涨幅第一的交易对',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 分析最新数据
  python jcfx.py
  
  # 分析指定日期
  python jcfx.py --date 2025-01-15
  python jcfx.py -d 2025-12-25
  
  # 分析并保存结果（用于定时任务）
  python jcfx.py --save-json --send-email
        '''
    )
    
    parser.add_argument(
        '-d', '--date',
        type=str,
        help='指定要分析的日期，格式为 YYYY-MM-DD (例如: 2025-01-15)'
    )
    
    parser.add_argument(
        '--save-json',
        action='store_true',
        help='保存分析结果到JSON文件（供前端展示）'
    )
    
    parser.add_argument(
        '--send-email',
        action='store_true',
        help='发送邮件通知到 13910306825@163.com'
    )
    
    args = parser.parse_args()
    
    # 运行分析并获取结果
    signal_data = analyze_top_gainer(target_date=args.date)
    
    # 保存到JSON文件（如果指定了 --save-json 或没有数据）
    if signal_data and (args.save_json or not args.date):
        # 自动模式（每天运行）或明确指定保存时，保存到JSON
        save_signals_to_json(signal_data)
    
    # 发送邮件通知
    if signal_data and args.send_email:
        send_email_notification(signal_data)

if __name__ == "__main__":
    main()
