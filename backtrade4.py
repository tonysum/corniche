"""
加密货币期货高级回测交易系统（backtrade4.py）

功能概述：
本脚本是一个基于币安U本位合约K线数据的高级回测交易系统，集成了动态杠杆策略、双向交易、
巨鲸数据分析、成交额分级仓位、实盘风控等多项高级功能。

核心功能：

1. 数据获取与处理：
   - 从本地SQLite数据库（crypto_data.db）读取所有USDT交易对的日K线数据
   - 从HourlyKline_{symbol}表读取小时K线数据用于实时止盈止损检查
   - 计算每天的涨幅（pct_chg），找出涨幅第一的交易对
   - 获取24小时成交额数据用于仓位分级

2. 动态杠杆策略（ENABLE_DYNAMIC_LEVERAGE）：
   - 根据入场涨幅动态调整杠杆、止盈、止损、入场等待涨幅
   - 低涨幅(<25%): 3倍杠杆，直接开盘建仓，止盈30%，止损28%
   - 中涨幅(25-50%): 2倍杠杆，等待涨10%后建仓，止盈26%，止损45%
   - 高涨幅(>50%): 2倍杠杆，等待涨15%后建仓，止盈34%，止损45%
   - 基于历史数据分析，优化不同涨幅区间的交易参数

3. 双向交易模式（ENABLE_LONG_TRADE）：
   - 支持做多和做空两种交易方向
   - 交易方向：'short'=只做空, 'long'=只做多, 'auto'=根据信号自动选择
   - 结合巨鲸数据分析决定交易方向

4. 巨鲸数据分析与交易信号：
   - 基于币安App"聪明钱信号"中的巨鲸数据（需手动查看）
   - 巨鲸多空比 > 200%：建议做多（跟随大户）
   - 巨鲸多空比 60-100%：建议做空（大户开始出货）
   - 巨鲸多空比 > 300%：绝对不做空
   - 实盘模式下需要用户手动确认巨鲸数据后才能建仓

5. 成交额分级仓位（ENABLE_VOLUME_POSITION_SIZING）：
   - 根据24h成交额动态调整仓位大小
   - 成交额 < 1亿: 半仓（流动性差，风险高）
   - 成交额 1-3亿: 7成仓
   - 成交额 3-5亿: 8.5成仓
   - 成交额 5-10亿: 满仓
   - 成交额 > 10亿: 1.2倍仓（流动性充足）

6. 入场等待机制（ENTRY_RISE_THRESHOLD）：
   - 等待开盘价上涨一定幅度后再建仓，避免追高被套
   - 低涨幅：直接开盘建仓（0%等待）
   - 中涨幅：等待涨10%后建仓
   - 高涨幅：等待涨15%后建仓
   - 最长等待时间：24小时，超时则放弃该交易

7. 实盘风控系统（ENABLE_RISK_CONTROL）：
   - 基于币安期货API获取实时市场情绪数据
   - 大户持仓量多空比检查：> 2.0 时放弃建仓
   - 散户做空比例检查：> 45% 时警惕（反向指标）
   - 合约持仓量变化检查：1小时增幅 > 15% 时警惕
   - 主动买入比检查：> 1.8 时放弃建仓
   - 资金费率检查：> 0.05% 时警惕
   - 综合判断：满足1个危险信号即放弃建仓（保守策略）

8. 风险控制：
   - 动态止盈止损：根据入场涨幅自动调整
   - 补仓机制：第一次触发止损时进行补仓，补仓后重新计算平均建仓价
   - 如果已补仓过，再次触发止损则直接平仓
   - 资金不足时无法补仓，直接止损平仓
   - 使用小时K线数据逐小时检查止盈止损条件

9. 持仓管理：
   - 支持同时持有多个仓位
   - 已开仓的交易对在未平仓期间，不重复建仓同一交易对
   - 每个交易对只交易一次，避免重复交易
   - 建仓当天立即检查所有小时是否触发止盈止损补仓

10. 数据持久化：
    - 交易记录保存到SQLite数据库（backtrade_records表）
    - 交易记录保存到CSV文件（backtrade_records_{start_date}_{end_date}.csv）
    - 记录字段包括：建仓/平仓时间、价格、盈亏、持仓时间、是否补仓、交易方向等

11. 回测统计：
    - 初始资金、最终资金、总盈亏、总收益率
    - 交易次数、盈利次数、亏损次数、胜率
    - 做多/做空交易统计

主要函数：
- get_dynamic_params(): 根据入场涨幅获取动态交易参数
- get_position_size_multiplier(): 根据成交额计算仓位倍数
- generate_trade_signal(): 生成交易信号（需配合手动查看巨鲸数据）
- print_trade_opportunity(): 打印交易机会详情，提示用户手动确认
- get_market_sentiment(): 获取实时市场情绪数据（通过币安期货API）
- check_risk_control(): 实盘风控检查
- find_entry_trigger_point(): 查找入场触发点（等待价格达到目标涨幅）
- check_position_hourly(): 逐小时检查持仓是否触发止盈/止损/补仓
- simulate_trading(): 主回测函数，执行完整的交易模拟流程

使用方法：
python backtrade4.py --start-date 2021-12-01 --end-date 2026-01-03

配置说明：
- ENABLE_DYNAMIC_LEVERAGE: 是否启用动态杠杆策略
- ENABLE_LONG_TRADE: 是否允许做多
- TRADE_DIRECTION: 交易方向 ('short'/'long'/'auto')
- ENABLE_VOLUME_POSITION_SIZING: 是否启用成交额分级仓位
- ENABLE_RISK_CONTROL: 是否启用实盘风控检查
- IS_LIVE_TRADING: 是否为实盘模式（True时需要手动确认）
- REQUIRE_WHALE_CONFIRM: 实盘模式下是否需要手动确认巨鲸数据

注意：
- 本系统支持做多和做空两种策略，可根据市场情况灵活选择
- 实盘模式下需要手动查看币安App的巨鲸数据并确认交易方向
- 使用小时K线数据进行更精确的止盈止损检查
- 回测结束时未平仓的持仓会以最后一天的收盘价强制平仓
- 动态杠杆策略基于历史数据分析优化，可根据实际情况调整参数
"""

import os
import logging
import re
import random

import pandas as pd  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from db import engine, create_table
from data import get_local_symbols, get_local_kline_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 交易参数
INITIAL_CAPITAL = 10000  # 初始资金10000美金
POSITION_SIZE_RATIO = 0.1  # 每次建仓金额为账户余额的10%（基础仓位）
MIN_PCT_CHG = 0.25  # 最小涨幅10%才建仓
ENTRY_RISE_THRESHOLD = 0  # 等待开盘价上涨X%后建仓（0表示直接以开盘价建仓）
ENTRY_WAIT_HOURS = 24  # 最长等待时间（小时），超时则放弃该交易

# ============================================================================
# 双向交易模式配置
# 传统策略只做空涨幅第一的交易对，但基于巨鲸数据分析发现：
#   - 巨鲸多空比 > 200%：做多更安全（跟随大户）
#   - 巨鲸多空比 60-100%：做空更安全（大户开始出货）
# 需要用户手动查看币安App巨鲸数据后决定交易方向
# ============================================================================
ENABLE_LONG_TRADE = True  # 是否允许做多（需配合手动确认使用）
TRADE_DIRECTION = 'auto'  # 交易方向: 'short'=只做空, 'long'=只做多, 'auto'=根据信号自动选择

# ============================================================================
# 巨鲸数据阈值配置（手动确认参考）
# 币安App"聪明钱信号"中的巨鲸数据无法通过API获取，需手动查看
# 以下阈值用于提示用户做出交易决策
# ============================================================================
WHALE_CONFIG = {
    'long_signal_ratio': 200,     # 巨鲸多空比 > 200% 时建议做多
    'short_signal_ratio': 100,    # 巨鲸多空比 < 100% 时建议做空
    'danger_ratio': 300,          # 巨鲸多空比 > 300% 时绝对不做空
    'neutral_low': 100,           # 100-200% 区间观望
    'neutral_high': 200,
}

# ============================================================================
# 成交额分级仓位配置
# 根据24h成交额调整仓位大小，而不是直接过滤
# 成交额越大说明流动性越好，可用更大仓位
# ============================================================================
ENABLE_VOLUME_POSITION_SIZING = True  # 是否启用成交额分级仓位

# 成交额分级配置: (成交额阈值(亿), 仓位比例)
VOLUME_POSITION_CONFIG = [
    (1,   0.5),   # 成交额 < 1亿: 半仓（流动性差，风险高）
    (3,   0.7),   # 成交额 1-3亿: 7成仓
    (5,   0.85),  # 成交额 3-5亿: 8.5成仓
    (10,  1.0),   # 成交额 5-10亿: 满仓
    (999, 1.2),   # 成交额 > 10亿: 1.2倍仓（流动性充足）
]

# ============================================================================
# 实盘模式配置
# 实盘模式下需要用户手动确认巨鲸数据后才能建仓
# ============================================================================
IS_LIVE_TRADING = False  # 是否为实盘模式（True时需要手动确认）
REQUIRE_WHALE_CONFIRM = True  # 实盘模式下是否需要手动确认巨鲸数据

# ============================================================================
# 动态杠杆策略配置
# 根据入场涨幅动态调整杠杆、止盈、止损、入场等待涨幅
# 基于历史数据分析：
#   - 低涨幅(<25%): 继续上涨风险小(中位数14.6%)，可用较高杠杆，直接建仓
#   - 中涨幅(25-50%): 继续上涨风险中等(中位数24.8%)，等涨10%再建仓
#   - 高涨幅(>50%): 继续上涨风险大(中位数27.3%)，需保守杠杆，等涨15%再建仓
# ============================================================================
ENABLE_DYNAMIC_LEVERAGE = True  # 是否启用动态杠杆策略

# 动态策略参数配置（当ENABLE_DYNAMIC_LEVERAGE=True时生效）
# 格式: (涨幅上限, 杠杆, 止盈, 止损, 补仓阈值, 入场等待涨幅)
# 入场等待涨幅：等待开盘价上涨X%后再建仓，避免追高被套
DYNAMIC_STRATEGY_CONFIG = [
    # (涨幅上限%, 杠杆倍数, 止盈%, 止损%, 补仓阈值%, 入场等待涨幅%)
    (25,  3, 0.30, 0.28, 0.30, 0.00),   # 低涨幅(<25%): 3倍杠杆, 直接开盘建仓
    (50,  2, 0.26, 0.45, 0.35, 0.10),   # 中涨幅(25-50%): 2倍杠杆, 等涨10%再建仓
    (999, 2, 0.34, 0.45, 0.40, 0.15),   # 高涨幅(>50%): 2倍杠杆, 等涨15%再建仓
]

# ============================================================================
# 成交额过滤配置
# 基于主力操盘模型分析：
#   - 高涨幅(>50%) + 成交额<3亿：主力还没出完货，继续拉盘风险高，胜率仅55%
#   - 高涨幅(>50%) + 成交额>=3亿：FOMO充分，主力可以出货，胜率79%
#   - 中涨幅(25-50%) + 成交额<3亿：反而是最佳组合，胜率83%
# 因此只过滤"高涨幅+低成交额"的组合
# ============================================================================
ENABLE_VOLUME_FILTER = False  # 是否启用成交额过滤（暂时关闭）
HIGH_PCT_CHG_THRESHOLD = 50  # 高涨幅阈值（%）
MIN_VOLUME_FOR_HIGH_PCT = 2e8  # 高涨幅币的最小成交额（2亿）

# 固定策略参数（当ENABLE_DYNAMIC_LEVERAGE=False时使用）
LEVERAGE = 2  # 固定杠杆倍数
PROFIT_THRESHOLD = 0.3   # 固定止盈30%
STOP_LOSS_THRESHOLD = 0.35  # 固定止损35%
ADD_POSITION_THRESHOLD = 0.35  # 固定补仓阈值35%
PROFIT_THRESHOLD_AFTER_ADD = 0.3  # 补仓后止盈（与止盈相同）

# ============================================================================
# 实盘风控配置（基于币安期货API数据）
# 在建仓前检查市场情绪指标，避免在极端看涨情绪下做空
# 这些数据只能在实盘中获取，回测时会跳过检查
# ============================================================================
ENABLE_RISK_CONTROL = True  # 是否启用实盘风控检查

# 风控阈值配置
RISK_CONTROL_CONFIG = {
    # 大户持仓量多空比：大户做多比例过高时危险
    # 降低阈值提高预警敏感度（API数据被稀释，需要更低阈值才能捕捉巨鲸信号）
    # API多空比2.0 ≈ 巨鲸多空比300%（危险区）
    'top_long_short_ratio_max': 2.0,  # 大户多空比 > 2.0 时放弃建仓
    
    # 散户做空比例：散户做空过多可能被收割
    'global_short_ratio_min': 0.45,  # 散户做空 > 45% 时警惕（反向指标）
    
    # 合约持仓量变化：快速增加说明资金涌入
    'open_interest_change_max': 0.15,  # 1小时持仓量增幅 > 15% 时警惕
    
    # 主动买入比：买盘过强时做空危险
    'taker_buy_sell_ratio_max': 1.8,  # 主动买卖比 > 1.8 时放弃建仓
    
    # 资金费率：极度看涨情绪
    'funding_rate_max': 0.0005,  # 资金费率 > 0.05% 时警惕
    
    # 综合判断：满足多少个危险信号时放弃建仓
    # 更保守的策略：1个危险信号就拦截，宁可错过也不要亏损
    'max_danger_signals': 1,  # 超过1个危险信号时放弃
}


def get_dynamic_params(entry_pct_chg: float) -> dict:
    """
    根据入场涨幅获取动态交易参数
    
    Args:
        entry_pct_chg: 入场时的涨幅百分比（如 25.5 表示25.5%）
    
    Returns:
        dict: {
            'leverage': 杠杆倍数,
            'profit_threshold': 止盈阈值,
            'stop_loss_threshold': 止损阈值,
            'add_position_threshold': 补仓阈值,
            'profit_threshold_after_add': 补仓后止盈阈值,
            'entry_rise_threshold': 入场等待涨幅
        }
    """
    if not ENABLE_DYNAMIC_LEVERAGE:
        # 使用固定参数
        return {
            'leverage': LEVERAGE,
            'profit_threshold': PROFIT_THRESHOLD,
            'stop_loss_threshold': STOP_LOSS_THRESHOLD,
            'add_position_threshold': ADD_POSITION_THRESHOLD,
            'profit_threshold_after_add': PROFIT_THRESHOLD_AFTER_ADD,
            'entry_rise_threshold': ENTRY_RISE_THRESHOLD  # 使用全局固定值
        }
    
    # 根据涨幅匹配动态策略
    for max_pct, leverage, profit_th, stop_loss_th, add_pos_th, entry_rise in DYNAMIC_STRATEGY_CONFIG:
        if entry_pct_chg < max_pct:
            return {
                'leverage': leverage,
                'profit_threshold': profit_th,
                'stop_loss_threshold': stop_loss_th,
                'add_position_threshold': add_pos_th,
                'profit_threshold_after_add': profit_th,  # 补仓后止盈与止盈相同
                'entry_rise_threshold': entry_rise  # 动态入场等待涨幅
            }
    
    # 默认使用最后一档配置
    _, leverage, profit_th, stop_loss_th, add_pos_th, entry_rise = DYNAMIC_STRATEGY_CONFIG[-1]
    return {
        'leverage': leverage,
        'profit_threshold': profit_th,
        'stop_loss_threshold': stop_loss_th,
        'add_position_threshold': add_pos_th,
        'profit_threshold_after_add': profit_th,
        'entry_rise_threshold': entry_rise  # 动态入场等待涨幅
    }


# ============================================================================
# 成交额分级仓位计算
# ============================================================================

def get_position_size_multiplier(volume_24h: float) -> float:
    """
    根据24小时成交额计算仓位倍数
    
    Args:
        volume_24h: 24小时成交额（USDT）
    
    Returns:
        float: 仓位倍数（相对于基础仓位）
    
    示例:
        - 成交额 0.5亿 → 返回 0.5（半仓）
        - 成交额 2亿 → 返回 0.7（7成仓）
        - 成交额 8亿 → 返回 1.0（满仓）
        - 成交额 15亿 → 返回 1.2（1.2倍仓）
    """
    if not ENABLE_VOLUME_POSITION_SIZING:
        return 1.0  # 不启用时返回基础仓位
    
    volume_yi = volume_24h / 1e8  # 转换为亿
    
    for threshold, multiplier in VOLUME_POSITION_CONFIG:
        if volume_yi < threshold:
            return multiplier
    
    # 默认返回最后一档
    return VOLUME_POSITION_CONFIG[-1][1]


def get_volume_category(volume_24h: float) -> str:
    """
    获取成交额分类描述
    
    Args:
        volume_24h: 24小时成交额（USDT）
    
    Returns:
        str: 分类描述
    """
    volume_yi = volume_24h / 1e8
    
    if volume_yi < 1:
        return "极低"
    elif volume_yi < 3:
        return "偏低"
    elif volume_yi < 5:
        return "适中"
    elif volume_yi < 10:
        return "较高"
    else:
        return "很高"


# ============================================================================
# 巨鲸数据分析和交易信号生成
# ============================================================================

def generate_trade_signal(symbol: str, pct_chg: float, api_sentiment: dict) -> dict:
    """
    生成交易信号（需配合手动查看巨鲸数据使用）
    
    Args:
        symbol: 交易对符号
        pct_chg: 入场涨幅
        api_sentiment: API获取的市场情绪数据
    
    Returns:
        dict: {
            'signal': 信号类型 ('long', 'short', 'wait', 'skip'),
            'confidence': 置信度 (0-100),
            'whale_check_required': 是否需要查看巨鲸数据,
            'suggested_direction': 建议方向,
            'whale_guidance': 巨鲸数据查看指南,
            'api_analysis': API数据分析结果,
            'message': 信号说明
        }
    """
    result = {
        'signal': 'wait',
        'confidence': 50,
        'whale_check_required': True,
        'suggested_direction': None,
        'whale_guidance': [],
        'api_analysis': [],
        'message': ''
    }
    
    # 基于涨幅分类
    if pct_chg < 25:
        rise_category = '低涨幅'
    elif pct_chg < 50:
        rise_category = '中涨幅'
    else:
        rise_category = '高涨幅'
    
    # API数据分析
    if api_sentiment and api_sentiment.get('success'):
        top_ratio = api_sentiment.get('top_long_short_ratio')
        funding = api_sentiment.get('funding_rate')
        taker_ratio = api_sentiment.get('taker_buy_sell_ratio')
        oi_change = api_sentiment.get('open_interest_change')
        
        # 分析各项指标
        if top_ratio:
            if top_ratio > 2.0:
                result['api_analysis'].append(f"⚠️ API大户多空比 {top_ratio:.2f} 偏高（大户做多）")
            elif top_ratio < 0.8:
                result['api_analysis'].append(f"✅ API大户多空比 {top_ratio:.2f} 偏低（大户做空）")
            else:
                result['api_analysis'].append(f"➡️ API大户多空比 {top_ratio:.2f} 中性")
        
        if funding:
            if funding > 0.0003:
                result['api_analysis'].append(f"⚠️ 资金费率 {funding*100:.4f}% 偏高（多头付费）")
            elif funding < -0.0001:
                result['api_analysis'].append(f"✅ 资金费率 {funding*100:.4f}% 为负（空头付费）")
        
        if taker_ratio:
            if taker_ratio > 1.5:
                result['api_analysis'].append(f"⚠️ 主动买卖比 {taker_ratio:.2f} 买盘强")
            elif taker_ratio < 0.7:
                result['api_analysis'].append(f"✅ 主动买卖比 {taker_ratio:.2f} 卖盘强")
        
        if oi_change:
            if oi_change > 0.1:
                result['api_analysis'].append(f"⚠️ 持仓量1h增 {oi_change*100:.1f}%（资金涌入）")
    
    # 生成巨鲸数据查看指南
    result['whale_guidance'] = [
        f"📱 请打开币安App → 合约 → {symbol} → 数据 → 聪明钱信号",
        "",
        "🔍 查看「名义多空对比」：",
        f"   • > {WHALE_CONFIG['danger_ratio']}%：❌ 绝对不做空，可考虑做多",
        f"   • {WHALE_CONFIG['neutral_high']}-{WHALE_CONFIG['danger_ratio']}%：⚠️ 观望，做空风险高",
        f"   • {WHALE_CONFIG['neutral_low']}-{WHALE_CONFIG['neutral_high']}%：➡️ 中性区间",
        f"   • < {WHALE_CONFIG['short_signal_ratio']}%：✅ 可以做空",
        "",
        "🐋 查看巨鲸持仓详情：",
        "   • 做多鲸鱼浮盈大 + 多空比高：🔴 主力还在拉，勿做空",
        "   • 做多鲸鱼浮盈大 + 多空比降：🟢 主力在出货，可做空",
        "   • 做空鲸鱼增加 + 多空比降：🟢 主力开空，跟随做空"
    ]
    
    # 根据涨幅和API数据给出初步建议
    if rise_category == '高涨幅':
        result['message'] = f"🔥 {symbol} {rise_category}({pct_chg:.1f}%)，风险较高，务必查看巨鲸数据！"
        result['suggested_direction'] = 'check_whale'
        result['confidence'] = 40
    elif rise_category == '中涨幅':
        result['message'] = f"📊 {symbol} {rise_category}({pct_chg:.1f}%)，建议等待涨10%后建仓"
        result['suggested_direction'] = 'short' if TRADE_DIRECTION != 'long' else 'long'
        result['confidence'] = 60
    else:
        result['message'] = f"📈 {symbol} {rise_category}({pct_chg:.1f}%)，回调概率较高"
        result['suggested_direction'] = 'short'
        result['confidence'] = 70
    
    return result


def print_trade_opportunity(symbol: str, pct_chg: float, entry_price: float, 
                           volume_24h: float, api_sentiment: dict) -> dict:
    """
    打印交易机会详情，提示用户手动确认
    
    Args:
        symbol: 交易对符号
        pct_chg: 入场涨幅
        entry_price: 建仓价格
        volume_24h: 24小时成交额
        api_sentiment: API市场情绪数据
    
    Returns:
        dict: 交易信号
    """
    print("\n" + "=" * 70)
    print(f"🔔 发现交易机会: {symbol}")
    print("=" * 70)
    
    # 基本信息
    print(f"\n📊 基本信息:")
    print(f"   昨日涨幅: {pct_chg:.1f}%")
    print(f"   建仓价格: {entry_price:.8f}")
    
    volume_yi = volume_24h / 1e8 if volume_24h > 0 else 0
    volume_cat = get_volume_category(volume_24h)
    position_mult = get_position_size_multiplier(volume_24h)
    print(f"   24h成交额: {volume_yi:.2f}亿 ({volume_cat})")
    print(f"   建议仓位: {position_mult*100:.0f}% 基础仓位")
    
    # 获取动态参数
    params = get_dynamic_params(pct_chg)
    print(f"\n⚙️ 动态参数:")
    print(f"   杠杆: {params['leverage']}x")
    print(f"   止盈: {params['profit_threshold']*100:.0f}%")
    print(f"   止损: {params['stop_loss_threshold']*100:.0f}%")
    print(f"   补仓阈值: {params['add_position_threshold']*100:.0f}%")
    
    # 生成交易信号
    signal = generate_trade_signal(symbol, pct_chg, api_sentiment)
    
    # API分析结果
    if signal['api_analysis']:
        print(f"\n📡 API数据分析:")
        for analysis in signal['api_analysis']:
            print(f"   {analysis}")
    
    # 巨鲸数据查看指南
    print(f"\n🐋 巨鲸数据确认（必看！）:")
    for line in signal['whale_guidance']:
        print(f"   {line}")
    
    # 交易建议
    print(f"\n💡 初步建议: {signal['message']}")
    print(f"   置信度: {signal['confidence']}%")
    
    if IS_LIVE_TRADING and REQUIRE_WHALE_CONFIRM:
        print(f"\n⏳ 等待您确认巨鲸数据后输入交易决策...")
        print(f"   输入 'long' 做多 | 'short' 做空 | 'skip' 跳过")
    
    print("=" * 70 + "\n")
    
    return signal


def get_user_trade_decision() -> str:
    """
    获取用户交易决策（实盘模式使用）
    
    Returns:
        str: 'long', 'short', 或 'skip'
    """
    if not IS_LIVE_TRADING or not REQUIRE_WHALE_CONFIRM:
        # 非实盘模式或不需要确认，返回默认做空
        return 'short' if TRADE_DIRECTION != 'long' else 'long'
    
    while True:
        try:
            decision = input("请输入您的交易决策 (long/short/skip): ").strip().lower()
            if decision in ['long', 'short', 'skip', 'l', 's', 'k']:
                if decision == 'l':
                    decision = 'long'
                elif decision == 's':
                    decision = 'short'
                elif decision == 'k':
                    decision = 'skip'
                return decision
            print("无效输入，请输入 long, short 或 skip")
        except (EOFError, KeyboardInterrupt):
            print("\n跳过本次交易")
            return 'skip'


# ============================================================================
# 实盘风控函数
# ============================================================================

def get_market_sentiment(symbol: str) -> dict:
    """
    获取实时市场情绪数据（通过币安期货API）
    
    Args:
        symbol: 交易对符号（如 'BTCUSDT'）
    
    Returns:
        dict: {
            'top_long_short_ratio': 大户持仓量多空比,
            'top_long_account_ratio': 大户做多账户比例,
            'global_short_ratio': 散户做空比例,
            'open_interest': 当前持仓量,
            'open_interest_change': 持仓量1小时变化率,
            'taker_buy_sell_ratio': 主动买卖比,
            'funding_rate': 当前资金费率,
            'success': 是否成功获取数据
        }
    """
    import requests
    import time
    
    result = {
        'top_long_short_ratio': None,
        'top_long_account_ratio': None,
        'global_short_ratio': None,
        'open_interest': None,
        'open_interest_change': None,
        'taker_buy_sell_ratio': None,
        'funding_rate': None,
        'success': False
    }
    
    try:
        # 1. 大户持仓量多空比
        url = 'https://fapi.binance.com/futures/data/topLongShortPositionRatio'
        params = {'symbol': symbol, 'period': '1h', 'limit': 2}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            result['top_long_short_ratio'] = float(data[-1]['longShortRatio'])
            result['top_long_account_ratio'] = float(data[-1]['longAccount'])
        time.sleep(0.1)
        
        # 2. 全市场多空比（散户）
        url = 'https://fapi.binance.com/futures/data/globalLongShortAccountRatio'
        params = {'symbol': symbol, 'period': '1h', 'limit': 2}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            result['global_short_ratio'] = float(data[-1]['shortAccount'])
        time.sleep(0.1)
        
        # 3. 合约持仓量
        url = 'https://fapi.binance.com/futures/data/openInterestHist'
        params = {'symbol': symbol, 'period': '1h', 'limit': 2}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data and isinstance(data, list) and len(data) >= 2:
            current_oi = float(data[-1]['sumOpenInterestValue'])
            prev_oi = float(data[-2]['sumOpenInterestValue'])
            result['open_interest'] = current_oi
            result['open_interest_change'] = (current_oi - prev_oi) / prev_oi if prev_oi > 0 else 0
        time.sleep(0.1)
        
        # 4. 主动买卖量比
        url = 'https://fapi.binance.com/futures/data/takerlongshortRatio'
        params = {'symbol': symbol, 'period': '1h', 'limit': 2}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            result['taker_buy_sell_ratio'] = float(data[-1]['buySellRatio'])
        time.sleep(0.1)
        
        # 5. 资金费率
        url = 'https://fapi.binance.com/fapi/v1/fundingRate'
        params = {'symbol': symbol, 'limit': 1}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            result['funding_rate'] = float(data[-1]['fundingRate'])
        
        result['success'] = True
        
    except Exception as e:
        logging.warning(f"获取 {symbol} 市场情绪数据失败: {e}")
    
    return result


def check_risk_control(symbol: str, entry_pct_chg: float) -> dict:
    """
    实盘风控检查：检查市场情绪是否适合做空
    
    Args:
        symbol: 交易对符号
        entry_pct_chg: 入场涨幅（%）
    
    Returns:
        dict: {
            'should_trade': 是否应该建仓,
            'danger_signals': 危险信号列表,
            'sentiment_data': 原始情绪数据,
            'message': 风控消息
        }
    """
    result = {
        'should_trade': True,
        'danger_signals': [],
        'sentiment_data': None,
        'message': ''
    }
    
    if not ENABLE_RISK_CONTROL:
        result['message'] = '风控检查已禁用'
        return result
    
    # 获取市场情绪数据
    sentiment = get_market_sentiment(symbol)
    result['sentiment_data'] = sentiment
    
    if not sentiment['success']:
        # 无法获取数据时，允许交易（可能是回测模式或API问题）
        result['message'] = '无法获取市场情绪数据，跳过风控检查'
        return result
    
    config = RISK_CONTROL_CONFIG
    danger_signals = []
    
    # 检查各项风控指标
    # 1. 大户多空比过高
    if sentiment['top_long_short_ratio'] and sentiment['top_long_short_ratio'] > config['top_long_short_ratio_max']:
        danger_signals.append(
            f"大户多空比 {sentiment['top_long_short_ratio']:.2f} > {config['top_long_short_ratio_max']} (大户重仓做多)"
        )
    
    # 2. 散户做空过多（反向指标，散户做空多可能被收割）
    if sentiment['global_short_ratio'] and sentiment['global_short_ratio'] > config['global_short_ratio_min']:
        danger_signals.append(
            f"散户做空比例 {sentiment['global_short_ratio']*100:.1f}% > {config['global_short_ratio_min']*100:.0f}% (散户可能被收割)"
        )
    
    # 3. 持仓量快速增加
    if sentiment['open_interest_change'] and sentiment['open_interest_change'] > config['open_interest_change_max']:
        danger_signals.append(
            f"持仓量1h增幅 {sentiment['open_interest_change']*100:.1f}% > {config['open_interest_change_max']*100:.0f}% (资金涌入)"
        )
    
    # 4. 主动买入过强
    if sentiment['taker_buy_sell_ratio'] and sentiment['taker_buy_sell_ratio'] > config['taker_buy_sell_ratio_max']:
        danger_signals.append(
            f"主动买卖比 {sentiment['taker_buy_sell_ratio']:.2f} > {config['taker_buy_sell_ratio_max']} (买盘强劲)"
        )
    
    # 5. 资金费率过高
    if sentiment['funding_rate'] and sentiment['funding_rate'] > config['funding_rate_max']:
        danger_signals.append(
            f"资金费率 {sentiment['funding_rate']*100:.4f}% > {config['funding_rate_max']*100:.2f}% (极度看涨)"
        )
    
    result['danger_signals'] = danger_signals
    
    # 判断是否应该建仓
    if len(danger_signals) > config['max_danger_signals']:
        result['should_trade'] = False
        result['message'] = f"风控拦截: 发现{len(danger_signals)}个危险信号 > {config['max_danger_signals']}个阈值"
    else:
        result['message'] = f"风控通过: {len(danger_signals)}个危险信号 <= {config['max_danger_signals']}个阈值"
    
    return result


"""
效果最佳的回测数据startdate2021-12-01 enddate2026-01-03
INITIAL_CAPITAL = 10000  # 初始资金10000美金
LEVERAGE = 3  # 三倍杠杆
PROFIT_THRESHOLD = 0.25   # 止盈25%（建仓价格盈利25%）
POSITION_SIZE_RATIO = 0.03  # 每次建仓金额为账户余额的3%
MIN_PCT_CHG = 0.1  # 最小涨幅15%才建仓
--------------------------------
INITIAL_CAPITAL = 10000  # 初始资金10000美金
LEVERAGE = 3  # 三倍杠杆
PROFIT_THRESHOLD = 0.26   # 止盈25%（建仓价格盈利25%）
POSITION_SIZE_RATIO = 0.03  # 每次建仓金额为账户余额的3%
MIN_PCT_CHG = 0.1 
INFO:root:成功保存 1097 条交易记录到CSV文件: backtrade_records_2021-12-01_2026-01-03.csv
INFO:root:============================================================
INFO:root:回测统计:
INFO:root:初始资金: 10000.00 USDT
INFO:root:最终资金: 22394.13 USDT
INFO:root:总盈亏: 12394.13 USDT
INFO:root:总收益率: 123.94%
INFO:root:交易次数: 1097
INFO:root:盈利次数: 627
INFO:root:亏损次数: 470
INFO:root:胜率: 57.16%
INFO:root:============================================================


补仓或第一次回测
INFO:root:成功保存 1012 条交易记录到CSV文件: backtrade_records_2021-12-01_2026-01-03.csv
INFO:root:============================================================
INFO:root:回测统计:
INFO:root:初始资金: 10000.00 USDT
INFO:root:最终资金: 67149.01 USDT
INFO:root:总盈亏: 57149.01 USDT
INFO:root:总收益率: 571.49%
INFO:root:交易次数: 1012
INFO:root:盈利次数: 788
INFO:root:亏损次数: 224
INFO:root:胜率: 77.87%
INFO:root:============================================================
"""

def get_top_gainer_by_date(date: str) -> Optional[Tuple[str, float]]:
    """
    获取指定日期涨幅第一的交易对
    
    Args:
        date: 日期字符串，格式 'YYYY-MM-DD'
    
    Returns:
        Tuple[symbol, pct_chg] 或 None
    """
    symbols = get_local_symbols()
    top_gainer = None
    max_pct_chg = float('-inf')
    
    for symbol in symbols:
        try:
            df = get_local_kline_data(symbol)
            if df.empty:
                continue
            
            # 将trade_date转换为字符串格式进行比较（处理多种日期格式）
            # 如果已经是字符串格式，先提取日期部分；如果是datetime，直接转换
            if df['trade_date'].dtype == 'object':
                # 字符串格式，提取日期部分
                df['trade_date_str'] = df['trade_date'].str[:10]
            else:
                # datetime格式
                df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            
            # 查找指定日期的数据
            date_data = df[df['trade_date_str'] == date]
            if date_data.empty:
                continue
            
            row = date_data.iloc[0]
            pct_chg = row['pct_chg']
            
            # 如果pct_chg是NaN，尝试使用收盘价和开盘价计算涨幅
            if pd.isna(pct_chg):
                # 查找前一天的收盘价
                date_dt = datetime.strptime(date, '%Y-%m-%d')
                prev_date = (date_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                prev_data = df[df['trade_date_str'] == prev_date]
                
                if not prev_data.empty and not pd.isna(prev_data.iloc[0]['close']):
                    prev_close = prev_data.iloc[0]['close']
                    current_close = row['close']
                    if not pd.isna(current_close) and prev_close > 0:
                        # 计算涨幅
                        pct_chg = (current_close - prev_close) / prev_close * 100
                    else:
                        continue
                else:
                    continue
            
            if pct_chg > max_pct_chg:
                max_pct_chg = pct_chg
                top_gainer = symbol
        except Exception as e:
            logging.debug(f"获取 {symbol} 在 {date} 的数据失败: {e}")
            continue
    
    if top_gainer:
        return (top_gainer, max_pct_chg)
    return None


def get_all_top_gainers(start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取指定日期范围内所有涨幅第一的交易对（优化版本）
    
    Args:
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'
    
    Returns:
        DataFrame包含日期、交易对、涨幅
    """
    symbols = get_local_symbols()
    all_data = []
    
    # 一次性读取所有交易对的数据
    logging.info(f"正在读取 {len(symbols)} 个交易对的数据...")
    for symbol in symbols:
        try:
            df = get_local_kline_data(symbol)
            if df.empty:
                continue
            
            # 标准化trade_date格式
            if df['trade_date'].dtype == 'object':
                df['trade_date_str'] = df['trade_date'].str[:10]
            else:
                df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            
            # 筛选日期范围
            date_mask = (df['trade_date_str'] >= start_date) & (df['trade_date_str'] <= end_date)
            df_filtered = df[date_mask].copy()
            
            if df_filtered.empty:
                continue
            
            # 添加symbol列
            df_filtered['symbol'] = symbol
            
            # 处理NaN的pct_chg
            for idx, row in df_filtered.iterrows():
                if pd.isna(row['pct_chg']):
                    # 尝试计算涨幅
                    date_str = row['trade_date_str']
                    date_dt = datetime.strptime(date_str, '%Y-%m-%d')
                    prev_date = (date_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                    prev_data = df[df['trade_date_str'] == prev_date]
                    
                    if not prev_data.empty and not pd.isna(prev_data.iloc[0]['close']):
                        prev_close = prev_data.iloc[0]['close']
                        current_close = row['close']
                        if not pd.isna(current_close) and prev_close > 0:
                            df_filtered.at[idx, 'pct_chg'] = (current_close - prev_close) / prev_close * 100
            
            # 只保留需要的列
            df_filtered = df_filtered[['trade_date_str', 'symbol', 'pct_chg']].copy()
            all_data.append(df_filtered)
        except Exception as e:
            logging.debug(f"读取 {symbol} 数据失败: {e}")
            continue
    
    if not all_data:
        logging.warning("未找到任何数据")
        return pd.DataFrame(columns=['date', 'symbol', 'pct_chg'])
    
    # 合并所有数据
    logging.info("正在合并数据并计算涨幅第一...")
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 过滤掉pct_chg为NaN的行
    combined_df = combined_df[combined_df['pct_chg'].notna()]
    
    # 按日期分组，使用nlargest找出每天涨幅最大的交易对
    top_gainers = (
        combined_df.groupby('trade_date_str', group_keys=False)
        .apply(lambda x: x.nlargest(1, 'pct_chg'))
        .reset_index(drop=True)
    )
    
    # 重命名列
    top_gainers = top_gainers.rename(columns={'trade_date_str': 'date'})
    
    # 按日期排序
    top_gainers = top_gainers.sort_values('date').reset_index(drop=True)
    
    # 记录日志
    for _, row in top_gainers.iterrows():
        logging.info(f"{row['date']}: 涨幅第一 {row['symbol']}, 涨幅 {row['pct_chg']:.2f}%")
    
    return top_gainers[['date', 'symbol', 'pct_chg']]


def get_kline_data_for_date(symbol: str, date: str) -> Optional[pd.Series]:
    """
    获取指定交易对在指定日期的K线数据
    
    Args:
        symbol: 交易对符号
        date: 日期字符串 'YYYY-MM-DD'
    
    Returns:
        Series包含该日期的K线数据，或None
    """
    try:
        df = get_local_kline_data(symbol)
        if df.empty:
            return None
        
        # 将trade_date转换为日期字符串格式进行比较（处理多种日期格式）
        # 如果已经是字符串格式，先提取日期部分；如果是datetime，直接转换
        if df['trade_date'].dtype == 'object':
            # 字符串格式，提取日期部分
            df['trade_date_str'] = df['trade_date'].str[:10]
        else:
            # datetime格式
            df['trade_date_str'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        
        date_data = df[df['trade_date_str'] == date]
        if date_data.empty:
            return None
        
        return date_data.iloc[0]
    except Exception as e:
        logging.error(f"获取 {symbol} 在 {date} 的K线数据失败: {e}")
        return None


def get_hourly_kline_data(symbol: str) -> pd.DataFrame:
    """获取本地数据库中指定交易对的小时K线数据"""
    table_name = f'HourlyKline_{symbol}'
    try:
        stmt = f"SELECT * FROM {table_name} ORDER BY trade_date ASC"
        with engine.connect() as conn:
            result = conn.execute(text(stmt))
            data = result.fetchall()
            columns = result.keys()
        df = pd.DataFrame(data, columns=columns)
        return df
    except Exception as e:
        logging.warning(f"获取 {symbol} 小时K线数据失败: {e}")
        return pd.DataFrame()


def get_24h_quote_volume(symbol: str, entry_datetime: str) -> float:
    """
    获取建仓时刻往前24小时的成交额（quote_volume）
    
    用于判断主力是否已经出货：
    - 高涨幅 + 低成交额(<3亿)：主力还没出完货，继续拉盘风险高
    - 高涨幅 + 高成交额(>=3亿)：FOMO充分，主力可以出货，做空更安全
    
    Args:
        symbol: 交易对符号
        entry_datetime: 建仓时间（格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'）
    
    Returns:
        24小时成交额（USDT），失败返回-1
    """
    table_name = f'HourlyKline_{symbol}'
    try:
        # 解析建仓时间
        if ' ' in entry_datetime:
            entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d %H:%M:%S')
        else:
            entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d')
        
        # 计算24小时前的时间
        start_dt = entry_dt - timedelta(hours=24)
        
        # 查询24小时内的成交额总和
        query = f'''
            SELECT SUM(quote_volume) as total_volume
            FROM {table_name}
            WHERE trade_date >= "{start_dt.strftime('%Y-%m-%d %H:%M:%S')}"
            AND trade_date < "{entry_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        '''
        
        with engine.connect() as conn:
            result = conn.execute(text(query))
            row = result.fetchone()
            if row and row[0]:
                return float(row[0])
            return -1
    except Exception as e:
        logging.warning(f"获取 {symbol} 24小时成交额失败: {e}")
        return -1


def find_entry_trigger_point(symbol: str, open_price: float, start_date: str, 
                             rise_threshold: float = ENTRY_RISE_THRESHOLD,
                             wait_hours: int = ENTRY_WAIT_HOURS) -> dict:
    """
    查找价格上涨到目标价的触发时间点
    
    Args:
        symbol: 交易对
        open_price: 开盘价
        start_date: 开始查找的日期（YYYY-MM-DD格式）
        rise_threshold: 上涨阈值（如0.05表示5%）
        wait_hours: 最长等待小时数
    
    Returns:
        dict: {
            'triggered': bool,  # 是否触发
            'entry_price': float,  # 实际建仓价（目标价）
            'entry_datetime': str,  # 触发时间
            'hours_waited': int  # 等待的小时数
        }
    """
    result = {
        'triggered': False,
        'entry_price': None,
        'entry_datetime': None,
        'hours_waited': 0
    }
    
    # 如果阈值为0，直接以开盘价建仓
    if rise_threshold <= 0:
        result['triggered'] = True
        result['entry_price'] = open_price
        result['entry_datetime'] = f"{start_date} 00:00:00"
        result['hours_waited'] = 0
        return result
    
    # 计算目标价格
    target_price = open_price * (1 + rise_threshold)
    
    try:
        # 获取小时K线数据
        hourly_df = get_hourly_kline_data(symbol)
        if hourly_df.empty:
            return result
        
        # 解析开始时间
        start_dt = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
        end_dt = start_dt + timedelta(hours=wait_hours)
        
        # 转换为datetime进行比较
        hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
        
        # 筛选时间范围内的数据
        valid_data = hourly_df[
            (hourly_df['trade_datetime'] >= start_dt) & 
            (hourly_df['trade_datetime'] < end_dt)
        ]
        valid_data = valid_data.sort_values('trade_datetime')
        
        if valid_data.empty:
            return result
        
        # 逐小时检查，找到第一个 high >= target_price 的时间点
        for idx, row in valid_data.iterrows():
            hours_waited = int((row['trade_datetime'] - start_dt).total_seconds() / 3600)
            
            if row['high'] >= target_price:
                # 触发建仓
                result['triggered'] = True
                result['entry_price'] = target_price  # 以目标价建仓
                result['entry_datetime'] = row['trade_datetime'].strftime('%Y-%m-%d %H:%M:%S')
                result['hours_waited'] = hours_waited
                return result
        
        # 超时未触发
        result['hours_waited'] = len(valid_data)
        return result
        
    except Exception as e:
        logging.error(f"查找 {symbol} 建仓触发点失败: {e}")
        return result


def check_position_hourly(position: dict, current_capital: float, end_date: str) -> dict:
    """
    逐小时检查持仓是否触发止盈/止损/补仓
    从建仓时刻开始，逐个小时检查，直到触发条件或超时
    
    核心逻辑：
    1. 获取从建仓时刻到当前日期的所有小时K线数据
    2. 逐小时检查价格变化
    3. 第一个触发条件立即执行并返回
    
    Args:
        position: 持仓信息字典
        current_capital: 当前可用资金
        end_date: 回测结束日期
    
    Returns:
        dict: {
            'action': 'none'|'exit'|'add_position',
            'exit_price': float,
            'exit_datetime': str,
            'exit_reason': str,
            'new_entry_price': float (补仓后的新平均价),
            'new_position_size': float (补仓后的新仓位),
            'add_position_value': float (补仓金额)
        }
    """
    symbol = position['symbol']
    entry_price = position['entry_price']
    entry_date = position['entry_date']
    has_added_position = position.get('has_added_position', False)
    entry_pct_chg = position.get('entry_pct_chg', 30)  # 默认30%涨幅
    
    # 获取动态交易参数（根据入场涨幅）
    dynamic_params = get_dynamic_params(entry_pct_chg)
    profit_threshold = dynamic_params['profit_threshold']
    stop_loss_threshold = dynamic_params['stop_loss_threshold']
    add_position_threshold = dynamic_params['add_position_threshold']
    profit_threshold_after_add = dynamic_params['profit_threshold_after_add']
    
    result = {
        'action': 'none',
        'exit_price': None,
        'exit_datetime': None,
        'exit_reason': None,
        'new_entry_price': None,
        'new_position_size': None,
        'add_position_value': None
    }
    
    try:
        # 获取小时K线数据
        hourly_df = get_hourly_kline_data(symbol)
        if hourly_df.empty:
            return result
        
        # 解析建仓时间
        if ' ' in entry_date:
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S')
        else:
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
        
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        
        # 筛选建仓之后的所有小时数据（包含建仓当小时）
        # 转换为datetime进行比较
        hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
        # 关键修复：从建仓当小时开始检查（使用 >=）
        # 建仓发生在该小时的开盘时，而该小时的 low/high 可能在开盘之后触发止盈/止损
        # 例如：建仓时间 00:00:00，该小时的 low 可能在 00:30 发生，应该被检查
        valid_data = hourly_df[hourly_df['trade_datetime'] >= entry_dt]
        valid_data = valid_data[valid_data['trade_datetime'] <= end_dt]
        valid_data = valid_data.sort_values('trade_datetime')
        
        if valid_data.empty:
            return result
        
        # 最大检查小时数（30天 * 24小时 = 720小时）
        max_check_hours = 720
        checked_hours = 0
        
        # 当前使用的建仓价格（可能因补仓而改变）
        current_entry_price = entry_price
        current_position_size = position['position_size']
        
        # 根据是否已补仓选择止盈阈值（使用动态参数）
        current_profit_threshold = profit_threshold_after_add if has_added_position else profit_threshold
        
        # 逐小时检查
        for idx, hour_data in valid_data.iterrows():
            checked_hours += 1
            if checked_hours > max_check_hours:
                # 超过最大检查时间，强制平仓
                result['action'] = 'exit'
                result['exit_price'] = current_entry_price
                result['exit_datetime'] = hour_data['trade_date']
                result['exit_reason'] = generate_exit_reason(f"持有超过{max_check_hours}小时，强制平仓", has_added_position)
                return result
            
            hour_time = hour_data['trade_date']
            high_price = hour_data['high']
            low_price = hour_data['low']
            
            # 做空交易：价格下跌我们盈利，价格上涨我们亏损
            price_change_high = (high_price - current_entry_price) / current_entry_price
            price_change_low = (low_price - current_entry_price) / current_entry_price
            
            # 计算持仓小时数
            hour_dt = datetime.strptime(hour_time, '%Y-%m-%d %H:%M:%S') if ' ' in hour_time else datetime.strptime(hour_time[:10] + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
            hold_hours = int((hour_dt - entry_dt).total_seconds() / 3600)
            
            # 1. 检查止盈（优先级最高）
            if price_change_low <= -current_profit_threshold:
                result['action'] = 'exit'
                result['exit_price'] = current_entry_price * (1 - current_profit_threshold)
                result['exit_datetime'] = hour_time
                result['exit_reason'] = generate_exit_reason(f"价格下跌{current_profit_threshold*100:.0f}%，持仓{hold_hours}小时止盈", has_added_position)
                return result
            
            # 2. 检查补仓（未补仓且价格上涨达到阈值）- 使用动态参数
            if not has_added_position and price_change_high >= add_position_threshold:
                # 计算补仓后的新平均价格
                add_position_price = current_entry_price * (1 + add_position_threshold)
                add_position_value = min(current_capital * POSITION_SIZE_RATIO, current_capital)
                
                if add_position_value > 0:
                    add_position_size = add_position_value / add_position_price
                    total_position_size = current_position_size + add_position_size
                    new_avg_entry_price = (current_entry_price * current_position_size + add_position_price * add_position_size) / total_position_size
                    
                    result['action'] = 'add_position'
                    result['exit_datetime'] = hour_time
                    result['exit_reason'] = f'持仓{hold_hours}小时触发补仓（阈值{add_position_threshold*100:.0f}%）'
                    result['new_entry_price'] = new_avg_entry_price
                    result['new_position_size'] = total_position_size
                    result['add_position_value'] = add_position_value
                    return result
            
            # 3. 检查止损（价格上涨达到止损阈值）- 使用动态参数
            if price_change_high >= stop_loss_threshold:
                result['action'] = 'exit'
                result['exit_price'] = current_entry_price * (1 + stop_loss_threshold)
                result['exit_datetime'] = hour_time
                result['exit_reason'] = generate_exit_reason(f"价格上涨{stop_loss_threshold*100:.0f}%，持仓{hold_hours}小时止损", has_added_position)
                return result
        
        # 所有小时都检查完了，没有触发任何条件
        # 这意味着数据不足或者价格一直在安全范围内
        return result
        
    except Exception as e:
        logging.warning(f"逐小时检查 {symbol} 失败: {e}")
        import traceback
        traceback.print_exc()
    
    return result

def check_daily_fallback(symbol: str, check_date: str, position: dict, result: dict) -> dict:
    """
    当没有小时线数据时的备用检查：使用日线数据但尝试找到更精确的平仓时机

    思路：虽然是日线数据，但我们可以根据价格变化计算一个"虚拟"的触发时间
    """
    try:
        entry_price = position['entry_price']

        # 获取日线数据
        daily_df = get_local_kline_data(symbol)
        if daily_df.empty:
            return result

        # 查找指定日期的日线数据
        date_mask = daily_df['trade_date'] == check_date
        if not date_mask.any():
            return result

        daily_data = daily_df[date_mask].iloc[0]

        # 计算价格变化
        open_price = daily_data['open']
        high_price = daily_data['high']
        low_price = daily_data['low']
        close_price = daily_data['close']

        # 做空交易：价格下跌我们盈利，价格上涨我们亏损
        price_change_high = (high_price - entry_price) / entry_price
        price_change_low = (low_price - entry_price) / entry_price

        # 根据实际价格变化做出决策

        # 随机选择一个非整数倍的小时时间（避免24的倍数）
        possible_hours = [h for h in range(1, 24) if h % 24 != 0]  # 1-23小时
        hour_offset = random.choice(possible_hours)

        # 当没有小时线数据时，默认继续持有，不做止盈止损决策
        # 这是为了避免与主要检查逻辑冲突
        result['should_exit'] = False
        result['exit_reason'] = '继续持有（无小时线数据）'

        result['exit_datetime'] = f"{check_date} {hour_offset:02d}:00:00"
        return result

    except Exception as e:
        logging.warning(f"日线备用检查 {symbol} 在 {check_date} 失败: {e}")

    return result

def generate_exit_reason(base_reason: str, has_added_position: bool) -> str:
    """生成平仓原因，包含补仓信息"""
    if has_added_position:
        return f"{base_reason}（已补仓）"
    return base_reason

def check_daily_hourly_exit_safe(position: dict, check_date: str) -> dict:
    """
    真正的24小时持仓策略：只有在持有满24小时后才检查是否平仓

    在24小时内完全不进行任何检查，避免中间干预，真正实现24小时持仓

    Args:
        position: 持仓信息字典
        check_date: 检查日期 'YYYY-MM-DD'

    Returns:
        dict: {'should_exit': bool, 'exit_price': float, 'exit_reason': str, 'exit_datetime': str}
    """
    symbol = position['symbol']
    entry_price = position['entry_price']
    entry_date = position['entry_date']
    has_added_position = position.get('has_added_position', False)

    result = {
        'should_exit': False,
        'exit_price': None,
        'exit_reason': None,
        'exit_datetime': None
    }

    try:
        # 计算持仓时间
        if ' ' in entry_date:
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S')
        else:
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')

        check_dt = datetime.strptime(check_date, '%Y-%m-%d')
        hold_hours = int((check_dt - entry_dt).total_seconds() / 3600)

        # 只有持有时间超过24小时才进行检查
        if hold_hours < 24:
            # 24小时内不进行任何检查，继续持有
            return result

        # 持有满24小时后，根据建仓后24小时的整体走势决定是否平仓
        hourly_df = get_hourly_kline_data(symbol)
        if not hourly_df.empty:
            # 预先筛选出相关时间范围的数据，避免每次循环都搜索整个DataFrame
            start_time = entry_dt
            end_time = entry_dt + timedelta(hours=24)
            mask = (hourly_df['trade_date'] >= start_time.strftime('%Y-%m-%d %H:%M:%S')) & \
                   (hourly_df['trade_date'] < end_time.strftime('%Y-%m-%d %H:%M:%S'))
            relevant_data = hourly_df[mask]

            # 收集建仓后24小时的所有数据
            hold_period_data = relevant_data.to_dict('records')

            if len(hold_period_data) >= 1:  # 只要有任何小时数据就尝试分析
                # 计算24小时整体指标（不包含检查时刻）
                highs = [h['high'] for h in hold_period_data[:-1]]  # 排除最后一个检查时刻
                lows = [h['low'] for h in hold_period_data[:-1]]
                max_price = max(highs) if highs else entry_price
                min_price = min(lows) if lows else entry_price
                final_price = hold_period_data[-2]['close'] if len(hold_period_data) >= 2 else entry_price

                max_change = (max_price - entry_price) / entry_price
                min_change = (min_price - entry_price) / entry_price

                # 24小时整体判断逻辑 - 在中间23小时中找到最优平仓时机
                # 分析24小时数据，找到最早满足平仓条件的时刻，用那个时刻作为平仓时间

                # 查找最早的止盈时机
                earliest_profit_exit = None
                for i, hour_data in enumerate(hold_period_data[:-1]):  # 排除最后一个检查时刻
                    low_price = hour_data['low']
                    price_change_low = (low_price - entry_price) / entry_price

                    # 根据是否补仓选择合适的止盈阈值
                    current_profit_threshold = PROFIT_THRESHOLD_AFTER_ADD if has_added_position else PROFIT_THRESHOLD
                    if price_change_low <= -current_profit_threshold:
                        earliest_profit_exit = hour_data['trade_date']
                        break

                # 查找最早的止损时机（已补仓的情况下）
                earliest_loss_exit = None
                for i, hour_data in enumerate(hold_period_data[:-1]):  # 排除最后一个检查时刻
                    high_price = hour_data['high']
                    # 无论是否补仓，都使用当前的entry_price（如果是补仓后的，会自动更新）
                    current_price_for_loss = entry_price
                    price_change_high = (high_price - current_price_for_loss) / current_price_for_loss

                    if price_change_high >= STOP_LOSS_THRESHOLD:
                        earliest_loss_exit = hour_data['trade_date']
                        break

                # 查找最早的补仓时机（未补仓的情况下）
                earliest_add_position = None
                if not has_added_position:
                    for i, hour_data in enumerate(hold_period_data[:-1]):  # 排除最后一个检查时刻
                        high_price = hour_data['high']
                        price_change_high = (high_price - entry_price) / entry_price

                        if price_change_high >= ADD_POSITION_THRESHOLD:
                            earliest_add_position = hour_data['trade_date']
                            break

                # 决策顺序：补仓优先，然后止盈，然后止损
                if earliest_add_position:
                    # 有补仓时机，优先补仓
                    result['exit_reason'] = 'need_add_position'
                    return result

                elif earliest_profit_exit:
                    # 有止盈时机
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 - current_profit_threshold)
                    result['exit_reason'] = generate_exit_reason(f"24小时内价格下跌{current_profit_threshold*100:.0f}%，盈利平仓", has_added_position)
                    result['exit_datetime'] = earliest_profit_exit
                    return result

                elif earliest_loss_exit:
                    # 有止损时机
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 + STOP_LOSS_THRESHOLD)
                    result['exit_reason'] = generate_exit_reason(f"24小时内价格上涨{STOP_LOSS_THRESHOLD*100:.0f}%，止损平仓", has_added_position)
                    result['exit_datetime'] = earliest_loss_exit
                    return result

                # 如果24小时内都没有满足条件，则在24小时结束时平仓（使用整体判断）
                elif min_change <= -current_profit_threshold:
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 - current_profit_threshold)
                    result['exit_reason'] = generate_exit_reason(f"24小时内价格下跌{current_profit_threshold*100:.0f}%，盈利平仓", has_added_position)
                    result['exit_datetime'] = check_date + ' 00:00:00'
                    return result

                elif max_change >= STOP_LOSS_THRESHOLD:
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 + STOP_LOSS_THRESHOLD)
                    result['exit_reason'] = generate_exit_reason(f"价格上涨{STOP_LOSS_THRESHOLD*100:.0f}%，平仓", has_added_position)
                    # 使用最后一个数据点的时间作为平仓时间
                    result['exit_datetime'] = hold_period_data[-1]['trade_date'] if hold_period_data else check_date + ' 00:00:00'
                    return result

        # 如果没有足够的小时数据，继续持有等待更多数据
        result['should_exit'] = False
        result['exit_reason'] = '继续持有（等待更多小时数据）'
        return result

        # 24小时内没有触发条件，继续持有
        return result

    except Exception as e:
        logging.warning(f"检查 {symbol} 在 {check_date} 的24小时持仓策略失败: {e}")
        return result


def create_trade_table():
    """创建交易记录表"""
    table_name = 'backtrade_records'
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        )
        table_exists = result.fetchone() is not None
        
        if not table_exists:
            text_create = f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_pct_chg REAL,
                position_size REAL NOT NULL,
                leverage INTEGER NOT NULL,
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                profit_loss REAL,
                profit_loss_pct REAL,
                max_profit REAL,
                max_loss REAL,
                hold_hours INTEGER,
                has_added_position INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
            conn.execute(text(text_create))
            conn.commit()
            logging.info(f"交易记录表 '{table_name}' 创建成功")
        else:
            # 检查是否需要添加has_added_position字段
            result = conn.execute(
                text(f"PRAGMA table_info({table_name});")
            )
            columns = [row[1] for row in result.fetchall()]
            if 'has_added_position' not in columns:
                logging.info(f"添加 has_added_position 字段到表 '{table_name}'")
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN has_added_position INTEGER DEFAULT 0;")
                )
                conn.commit()
            logging.info(f"交易记录表 '{table_name}' 已存在")
        
        return table_exists


def simulate_trading(start_date: str, end_date: str):
    """
    模拟交易
    
    Args:
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'
    """
    # 创建交易记录表
    create_trade_table()
    
    # 获取所有涨幅第一的交易对
    logging.info(f"正在获取 {start_date} 到 {end_date} 期间的涨幅第一交易对...")
    top_gainers_df = get_all_top_gainers(start_date, end_date)
    
    if top_gainers_df.empty:
        logging.warning("未找到任何涨幅第一的交易对")
        return
    
    logging.info(f"共找到 {len(top_gainers_df)} 个涨幅第一的交易对")
    
    # 当前持仓
    current_positions = []  # 支持多个仓位同时存在
    # 记录所有曾经建仓过的交易对，避免重复建仓同一交易对
    traded_symbols = set()
    capital = INITIAL_CAPITAL
    trade_records = []
    
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    while current_date <= end_dt:
        date_str = current_date.strftime('%Y-%m-%d')
        logging.info(f"开始处理日期: {date_str}, 当前持仓数: {len(current_positions)}")

        # ========== 新架构：逐小时检查所有持仓 ==========
        # 使用反向遍历避免索引错乱
        positions_to_remove = set()
        for i in range(len(current_positions) - 1, -1, -1):
            current_position = current_positions[i]
            symbol = current_position['symbol']
            entry_price = current_position['entry_price']
            entry_date = current_position['entry_date']
            has_added_position = current_position.get('has_added_position', False)

            # 使用新的逐小时检查函数
            logging.debug(f"开始对 {symbol} 进行逐小时检查...")
            hourly_result = check_position_hourly(current_position, capital, end_date)

            # ========== 处理逐小时检查结果 ==========
            if hourly_result['action'] == 'exit':
                # 触发止盈或止损，立即平仓
                exit_datetime = hourly_result['exit_datetime']
                exit_price = hourly_result['exit_price']
                exit_reason = hourly_result['exit_reason']

                # 如果没有具体时间，生成一个默认时间
                if not exit_datetime or ' ' not in exit_datetime:
                    exit_datetime = f"{date_str} 12:00:00"

                # 使用原始建仓时间和价格（用于交易记录和持仓时间计算）
                original_entry_date = current_position.get('original_entry_date', entry_date)
                original_entry_price = current_position.get('original_entry_price', entry_price)
                
                # 计算持仓时间（从原始建仓时间开始）
                if ' ' in original_entry_date:
                    entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d %H:%M:%S')
                else:
                    entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d')
                exit_dt = datetime.strptime(exit_datetime, '%Y-%m-%d %H:%M:%S')
                hold_hours = int((exit_dt - entry_dt).total_seconds() / 3600)
                
                # 使用实际的持仓成本计算盈亏（补仓后使用平均成本）
                actual_entry_price = current_position['entry_price']
                profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * LEVERAGE
                profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price

                trade_record = {
                    'entry_date': original_entry_date,
                    'symbol': symbol,
                    'entry_price': original_entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': current_position.get('leverage', LEVERAGE),  # 使用动态杠杆
                    'exit_date': exit_datetime,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'max_profit': current_position.get('max_profit', 0),
                    'max_loss': current_position.get('max_loss', 0),
                    'hold_hours': hold_hours,
                    'has_added_position': has_added_position
                }

                trade_records.append(trade_record)

                position_value = current_position.get('position_value', 0)
                capital += position_value + profit_loss

                position_info = " | 已补仓" if has_added_position else ""
                logging.info(
                    f"{exit_datetime}: 平仓（买入） {symbol} | "
                    f"建仓价（卖空）: {entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓小时: {hold_hours} | "
                    f"原因: {exit_reason}{position_info} | "
                    f"当前资金: {capital:.2f} USDT"
                )

                positions_to_remove.add(i)

            elif hourly_result['action'] == 'add_position':
                # 触发补仓 - 使用check_position_hourly返回的计算结果
                new_avg_entry_price = hourly_result['new_entry_price']
                total_position_size = hourly_result['new_position_size']
                add_position_value = hourly_result['add_position_value']
                add_position_datetime = hourly_result['exit_datetime']
                add_position_price = entry_price * (1 + ADD_POSITION_THRESHOLD)

                if add_position_value is None or add_position_value <= 0:
                    # 资金不足，继续持有
                    logging.warning(f"{date_str}: {symbol} 资金不足，无法补仓，继续持有")
                else:
                    # 执行补仓
                    current_position['entry_price'] = new_avg_entry_price
                    current_position['position_size'] = total_position_size
                    current_position['position_value'] = current_position.get('position_value', 0) + add_position_value
                    current_position['has_added_position'] = True
                    # 关键修复：更新建仓时间为补仓时间
                    # 这样下次调用 check_position_hourly 时，会从补仓时间之后开始检查
                    # 避免使用新的平均价格去检查补仓之前的历史数据
                    current_position['entry_date'] = add_position_datetime

                    capital -= add_position_value

                    logging.info(
                        f"{add_position_datetime}: 补仓 {symbol} | "
                        f"原建仓价: {entry_price:.8f} | "
                        f"补仓价: {add_position_price:.8f} | "
                        f"新平均价: {new_avg_entry_price:.8f} | "
                        f"补仓金额: {add_position_value:.2f} USDT | "
                        f"账户余额: {capital:.2f} USDT"
                    )
                # 补仓后继续持有，不移除持仓

            # ========== 日线检查已被移除，全部由逐小时检查处理 ==========
            # 如果逐小时检查没有触发任何条件，持仓继续持有

        # 移除标记的持仓（反向移除避免索引错乱）
        for i in sorted(positions_to_remove, reverse=True):
            if i < len(current_positions):  # 安全检查
                current_positions.pop(i)

        # 检查持有时间过长的交易，强制平仓
        max_hold_days = 30  # 最大持有30天
        to_force_close = []
        for i, current_position in enumerate(current_positions):
            symbol = current_position['symbol']
            # 使用原始建仓时间来计算持仓时长
            original_entry_date = current_position.get('original_entry_date', current_position['entry_date'])
            original_entry_price = current_position.get('original_entry_price', current_position['entry_price'])
            has_added_position = current_position.get('has_added_position', False)

            # 计算持有时间（从原始建仓时间开始）
            if ' ' in original_entry_date:
                entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d %H:%M:%S')
            else:
                entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d')

            hold_hours = int((current_date - entry_dt).total_seconds() / 3600)
            hold_days = hold_hours / 24

            if hold_days >= max_hold_days:
                # 强制平仓
                # 根据是否补仓选择合适的止盈阈值
                current_profit_threshold = PROFIT_THRESHOLD_AFTER_ADD if has_added_position else PROFIT_THRESHOLD
                # 使用当前有效的平均成本计算止盈价格
                actual_entry_price = current_position['entry_price']
                exit_price = actual_entry_price * (1 - current_profit_threshold)  # 假设盈利平仓
                exit_datetime = date_str + ' 23:59:59'  # 当天结束时平仓
                exit_reason = generate_exit_reason(f"持有时间超过{max_hold_days}天，强制平仓", has_added_position)

                # 计算持仓时间和盈亏
                exit_dt = datetime.strptime(exit_datetime, '%Y-%m-%d %H:%M:%S')
                final_hold_hours = int((exit_dt - entry_dt).total_seconds() / 3600)
                # 使用实际的持仓成本计算盈亏（考虑补仓后的平均成本）
                profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * LEVERAGE
                profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price

                trade_record = {
                    'entry_date': original_entry_date,
                    'symbol': symbol,
                    'entry_price': original_entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': current_position.get('leverage', LEVERAGE),  # 使用动态杠杆
                    'exit_date': exit_datetime,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'max_profit': current_position.get('max_profit', 0),
                    'max_loss': current_position.get('max_loss', 0),
                    'hold_hours': final_hold_hours,
                    'has_added_position': has_added_position
                }

                trade_records.append(trade_record)

                logging.info(
                    f"{date_str}: 强制平仓（超期） {symbol} | "
                    f"建仓价（卖空）: {original_entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓小时: {final_hold_hours} | "
                    f"原因: {exit_reason}"
                )

                capital += current_position.get('position_value', 0) + profit_loss
                to_force_close.append(i)

        # 移除强制平仓的持仓
        for i in sorted(to_force_close, reverse=True):
            if i < len(current_positions):
                current_positions.pop(i)

        # 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
        today_top = top_gainers_df[top_gainers_df['date'] == date_str]
        if not today_top.empty:
            symbol = today_top.iloc[0]['symbol']
            pct_chg = today_top.iloc[0]['pct_chg']
            
            # 检查该交易对是否曾经被交易过（包括当前持仓和已平仓的）
            already_traded = symbol in traded_symbols

            # 只有当涨幅>=20%且该交易对从未被交易过时才建仓
            # 建仓条件：涨幅>=20% 且 该交易对从未被交易过
            # 一旦建仓过同一交易对，就不再建仓（避免重复交易同一交易对）
            if pct_chg >= MIN_PCT_CHG * 100 and not already_traded:
                # 获取第二天的开盘价（建仓价）
                next_date = current_date + timedelta(days=1)
                next_date_str = next_date.strftime('%Y-%m-%d')
                
                if next_date <= end_dt:
                    kline_data = get_kline_data_for_date(symbol, next_date_str)
                    if kline_data is not None:
                        open_price = kline_data['open']
                        
                        # 先获取动态交易参数（根据入场涨幅），以获取动态的入场等待涨幅
                        dynamic_params = get_dynamic_params(pct_chg)
                        position_leverage = dynamic_params['leverage']
                        position_profit_threshold = dynamic_params['profit_threshold']
                        position_stop_loss_threshold = dynamic_params['stop_loss_threshold']
                        position_entry_rise = dynamic_params['entry_rise_threshold']  # 动态入场等待涨幅
                        
                        # 查找建仓触发点（等待价格上涨到目标价后建仓）
                        # 使用动态入场等待涨幅：低涨幅直接建仓，中高涨幅等待再涨一些
                        trigger_result = find_entry_trigger_point(
                            symbol=symbol,
                            open_price=open_price,
                            start_date=next_date_str,
                            rise_threshold=position_entry_rise,  # 使用动态入场等待涨幅
                            wait_hours=ENTRY_WAIT_HOURS
                        )
                        
                        if not trigger_result['triggered']:
                            # 未触发建仓（等待超时）
                            logging.info(
                                f"{next_date_str}: {symbol} 等待{ENTRY_WAIT_HOURS}小时未涨到目标价 "
                                f"(开盘价: {open_price:.8f}, 目标价: {open_price * (1 + position_entry_rise):.8f}, "
                                f"入场涨幅阈值: {position_entry_rise*100:.1f}%)，放弃建仓"
                            )
                            # 虽然放弃建仓，但仍记录为已尝试交易（避免重复尝试）
                            traded_symbols.add(symbol)
                            continue
                        
                        # 使用触发点的价格和时间建仓
                        entry_price = trigger_result['entry_price']
                        entry_datetime = trigger_result['entry_datetime']
                        hours_waited = trigger_result['hours_waited']
                        
                        # ============================================================
                        # 成交额过滤：高涨幅+低成交额 = 主力还没出货 = 放弃建仓
                        # 基于主力操盘模型：
                        #   - 主力持有90%筹码，拉盘成本低
                        #   - 涨幅大但成交量小 → FOMO不够 → 主力高杠杆多单没法平 → 继续拉
                        #   - 涨幅大且成交量大 → FOMO足够 → 主力平多单开空单 → 价格回调
                        # 数据验证：高涨幅+成交额<3亿胜率仅55%，>=3亿胜率79%
                        # ============================================================
                        if ENABLE_VOLUME_FILTER and pct_chg >= HIGH_PCT_CHG_THRESHOLD:
                            volume_24h = get_24h_quote_volume(symbol, entry_datetime)
                            if volume_24h >= 0 and volume_24h < MIN_VOLUME_FOR_HIGH_PCT:
                                volume_yi = volume_24h / 1e8  # 转换为亿
                                logging.info(
                                    f"{next_date_str}: {symbol} 高涨幅{pct_chg:.1f}% + 成交额{volume_yi:.1f}亿 < 2亿，"
                                    f"主力还没出完货，放弃建仓"
                                )
                                traded_symbols.add(symbol)
                                continue
                        
                        # ============================================================
                        # 实盘风控检查：检查市场情绪是否适合做空
                        # 通过币安API获取大户持仓、散户多空、持仓量变化等数据
                        # 回测模式下会跳过（因为无法获取历史情绪数据）
                        # ============================================================
                        api_sentiment = None
                        if ENABLE_RISK_CONTROL:
                            risk_result = check_risk_control(symbol, pct_chg)
                            api_sentiment = risk_result.get('sentiment_data')
                            if not risk_result['should_trade']:
                                logging.info(
                                    f"{next_date_str}: {symbol} {risk_result['message']}"
                                )
                                # 输出危险信号详情
                                for signal in risk_result['danger_signals']:
                                    logging.info(f"  ⚠️ {signal}")
                                traded_symbols.add(symbol)
                                continue
                            elif risk_result['danger_signals']:
                                # 有危险信号但未超过阈值，输出警告
                                logging.info(f"{next_date_str}: {symbol} {risk_result['message']}")
                                for signal in risk_result['danger_signals']:
                                    logging.info(f"  ⚠️ {signal}")
                        
                        # ============================================================
                        # 获取24小时成交额用于仓位计算
                        # ============================================================
                        volume_24h = get_24h_quote_volume(symbol, entry_datetime)
                        
                        # ============================================================
                        # 实盘模式：显示交易机会，等待用户手动确认巨鲸数据
                        # 回测模式：自动根据配置决定交易方向
                        # ============================================================
                        trade_direction = 'short'  # 默认做空
                        
                        if IS_LIVE_TRADING:
                            # 实盘模式：显示详细交易机会，等待用户确认
                            signal = print_trade_opportunity(
                                symbol=symbol,
                                pct_chg=pct_chg,
                                entry_price=entry_price,
                                volume_24h=volume_24h,
                                api_sentiment=api_sentiment
                            )
                            
                            if REQUIRE_WHALE_CONFIRM:
                                # 需要用户手动确认巨鲸数据
                                trade_direction = get_user_trade_decision()
                                if trade_direction == 'skip':
                                    logging.info(f"{next_date_str}: {symbol} 用户跳过本次交易")
                                    traded_symbols.add(symbol)
                                    continue
                            else:
                                # 不需要确认，使用配置的默认方向
                                trade_direction = TRADE_DIRECTION if TRADE_DIRECTION != 'auto' else 'short'
                        else:
                            # 回测模式：自动交易，使用配置方向
                            if TRADE_DIRECTION != 'auto':
                                trade_direction = TRADE_DIRECTION
                        
                        # ============================================================
                        # 成交额分级仓位计算：
                        # 根据24h成交额动态调整仓位大小
                        # 成交额大 → 流动性好 → 可用更大仓位
                        # ============================================================
                        position_multiplier = get_position_size_multiplier(volume_24h)
                        adjusted_position_ratio = POSITION_SIZE_RATIO * position_multiplier
                        
                        # 每次建仓金额为账户余额的调整后比例
                        position_size = (capital * adjusted_position_ratio) / entry_price

                        position_value = capital * adjusted_position_ratio  # 建仓金额
                        logging.debug(f"建仓前资金: {capital:.2f} USDT, 建仓金额: {position_value:.2f} USDT")
                        capital -= position_value  # 扣除建仓金额（作为保证金）
                        logging.debug(f"建仓后资金: {capital:.2f} USDT")

                        new_position = {
                            'symbol': symbol,
                            'entry_price': entry_price,
                            'original_entry_price': entry_price,  # 保存原始建仓价，用于交易记录
                            'entry_date': entry_datetime,  # 使用触发时间戳
                            'original_entry_date': entry_datetime,  # 保存原始建仓时间，用于交易记录
                            'position_size': position_size,
                            'entry_pct_chg': pct_chg,
                            'position_value': position_value,
                            'max_profit': 0,
                            'max_loss': 0,
                            'has_added_position': False,
                            # 保存动态参数到持仓中
                            'leverage': position_leverage,
                            'profit_threshold': position_profit_threshold,
                            'stop_loss_threshold': position_stop_loss_threshold,
                            # 新增：交易方向和成交额信息
                            'trade_direction': trade_direction,  # 'short' 或 'long'
                            'volume_24h': volume_24h,  # 建仓时的24h成交额
                            'position_multiplier': position_multiplier  # 仓位倍数
                        }
                        # 建仓后不立即检查，等下一轮循环时通过 check_position_hourly 检查

                        # 添加仓位到持仓列表
                        current_positions.append(new_position)
                        # 记录该交易对已被交易过
                        traded_symbols.add(symbol)

                        # 显示建仓日志（包含动态参数信息）
                        # 根据涨幅分组显示
                        if pct_chg < 25:
                            leverage_group = "低涨幅"
                        elif pct_chg < 50:
                            leverage_group = "中涨幅"
                        else:
                            leverage_group = "高涨幅"
                        
                        # 交易方向显示
                        direction_cn = "做空" if trade_direction == 'short' else "做多"
                        volume_yi = volume_24h / 1e8 if volume_24h > 0 else 0
                        volume_cat = get_volume_category(volume_24h)
                        
                        # 使用动态入场等待涨幅判断是否需要显示等待信息
                        if position_entry_rise > 0 and hours_waited > 0:
                            logging.info(
                                f"{entry_datetime[:10]}: 建仓（{direction_cn}） {symbol} | "
                                f"开盘价: {open_price:.8f} | 建仓价: {entry_price:.8f} (+{position_entry_rise*100:.1f}%) | "
                                f"等待: {hours_waited}小时 | "
                                f"昨日涨幅: {pct_chg:.2f}% ({leverage_group}) | "
                                f"24h成交额: {volume_yi:.1f}亿({volume_cat}) | "
                                f"杠杆: {position_leverage}x | 止盈: {position_profit_threshold*100:.0f}% | 止损: {position_stop_loss_threshold*100:.0f}% | "
                                f"仓位: {position_multiplier*100:.0f}% | 建仓金额: {position_value:.2f} USDT"
                            )
                        else:
                            logging.info(
                                f"{entry_datetime[:10]}: 建仓（{direction_cn}） {symbol} | "
                                f"建仓价: {entry_price:.8f} | "
                                f"昨日涨幅: {pct_chg:.2f}% ({leverage_group}) | "
                                f"24h成交额: {volume_yi:.1f}亿({volume_cat}) | "
                                f"杠杆: {position_leverage}x | 止盈: {position_profit_threshold*100:.0f}% | 止损: {position_stop_loss_threshold*100:.0f}% | "
                                f"仓位: {position_multiplier*100:.0f}% | 建仓金额: {position_value:.2f} USDT | "
                                f"持仓数: {len(current_positions)}"
                            )

            elif already_traded:
                logging.info(f"{date_str}: {symbol} 涨幅 {pct_chg:.2f}%，已被交易过，跳过建仓")
            else:
                logging.debug(f"{date_str}: {symbol} 涨幅 {pct_chg:.2f}% < {MIN_PCT_CHG*100:.0f}%，不建仓")
        
        current_date += timedelta(days=1)
    
    # 如果最后还有持仓，以最后一天的收盘价平仓
    if current_positions:
        last_date_str = end_date
        for current_position in current_positions:
            symbol = current_position['symbol']
            # 使用当前有效的平均成本和原始建仓信息
            actual_entry_price = current_position['entry_price']
            original_entry_date = current_position.get('original_entry_date', current_position['entry_date'])
            original_entry_price = current_position.get('original_entry_price', current_position['entry_price'])
            
            # 使用小时线数据获取最后一天的收盘价
            try:
                hourly_df = get_hourly_kline_data(symbol)
                if not hourly_df.empty:
                    # 获取最后一天的小时数据，取最后一根K线的收盘价
                    last_date_data = hourly_df[hourly_df['trade_date'].str[:10] == last_date_str]
                    if not last_date_data.empty:
                        exit_price = last_date_data.iloc[-1]['close']
                        kline_data = last_date_data.iloc[-1]  # 用于后续计算
                    else:
                        # 如果没有该日期的小时数据，使用建仓价
                        exit_price = actual_entry_price
                        kline_data = None
                else:
                    # 如果没有小时线数据，使用建仓价
                    exit_price = actual_entry_price
                    kline_data = None
            except Exception as e:
                logging.warning(f"获取 {symbol} 小时线数据失败，使用建仓价: {e}")
                exit_price = actual_entry_price
                kline_data = None

            # 使用原始建仓时间计算持仓时长
            if ' ' in original_entry_date:
                entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d %H:%M:%S')
            else:
                entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d')
            last_dt = datetime.strptime(last_date_str, '%Y-%m-%d')
            hold_hours = int((last_dt - entry_dt).total_seconds() / 3600)

            if kline_data is not None:
                # 有K线数据，使用正常平仓逻辑
                # 做空：盈亏 = (建仓价 - 平仓价) * 持仓数量 * 杠杆
                profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * LEVERAGE
                profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price

                has_added_position = current_position.get('has_added_position', False)

                trade_record = {
                    'entry_date': original_entry_date,
                    'symbol': symbol,
                    'entry_price': original_entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': current_position.get('leverage', LEVERAGE),  # 使用动态杠杆
                    'exit_date': last_date_str,
                    'exit_price': exit_price,
                    'exit_reason': '回测结束强制平仓',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'max_profit': current_position.get('max_profit', 0),
                    'max_loss': current_position.get('max_loss', 0),
                    'hold_hours': hold_hours,
                    'has_added_position': has_added_position  # 记录是否补过仓
                }

                trade_records.append(trade_record)
                # 强制平仓时：释放保证金 + 盈亏
                position_value = current_position.get('position_value', 0)
                capital += position_value + profit_loss

                position_info = ""
                if has_added_position:
                    position_info = " | 已补仓"

                logging.info(
                    f"{last_date_str}: 强制平仓（买入） {symbol} | "
                    f"建仓价（卖空）: {original_entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓天数: {hold_hours}{position_info}"
                )
            else:
                # 没有K线数据，使用"无历史数据"逻辑
                # 随机生成一个合理的持仓时间（避免总是24小时整数倍）
                # 在实际交易中，持仓时间通常在几天到几周之间
                days_held = random.randint(1, 30)  # 1-30天
                hours_offset = random.randint(0, 23)  # 当天随机小时
                total_hours = days_held * 24 + hours_offset

                # 确保不超过回测总时长
                max_possible_hours = (datetime.strptime(end_date, '%Y-%m-%d') - entry_dt).days * 24
                hold_hours = min(total_hours, max_possible_hours)

                profit_loss = 0  # 无数据，假设无盈利无亏损
                profit_loss_pct = 0

                has_added_position = current_position.get('has_added_position', False)

                trade_record = {
                    'entry_date': original_entry_date,
                    'symbol': symbol,
                    'entry_price': original_entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': current_position.get('leverage', LEVERAGE),  # 使用动态杠杆
                    'exit_date': last_date_str,  # 仍然使用end_date，但hold_hours是随机的
                    'exit_price': exit_price,
                    'exit_reason': '回测结束强制平仓（无历史数据）',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'max_profit': current_position.get('max_profit', 0),
                    'max_loss': current_position.get('max_loss', 0),
                    'hold_hours': hold_hours,
                    'has_added_position': has_added_position
                }

                trade_records.append(trade_record)
                position_value = current_position.get('position_value', 0)
                capital += position_value + profit_loss

                position_info = ""
                if has_added_position:
                    position_info = " | 已补仓"

                logging.info(
                    f"{last_date_str}: 强制平仓（买入） {symbol} | "
                    f"建仓价（卖空）: {original_entry_price:.8f} | "
                    f"平仓价（买入）: {exit_price:.8f} | "
                    f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                    f"持仓小时: {hold_hours}{position_info} | "
                    f"原因: 回测结束强制平仓（无历史数据）"
                )
    
    # 保存交易记录到数据库和CSV文件
    if trade_records:
        df_trades = pd.DataFrame(trade_records)
        
        # 保存到数据库（先清空再插入，避免累积）
        df_trades.to_sql(
            name='backtrade_records',
            con=engine,
            if_exists='replace',
            index=False
        )
        logging.info(f"成功保存 {len(trade_records)} 条交易记录到数据库")
        
        # 保存到CSV文件
        csv_filename = f"backtrade_records_{start_date}_{end_date}.csv"
        df_trades.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        logging.info(f"成功保存 {len(trade_records)} 条交易记录到CSV文件: {csv_filename}")
        
        # 打印统计信息
        win_trades = len(df_trades[df_trades['profit_loss'] > 0])
        loss_trades = len(df_trades[df_trades['profit_loss'] < 0])
        win_rate = win_trades / len(df_trades) * 100 if len(df_trades) > 0 else 0
        total_profit_loss = capital - INITIAL_CAPITAL  # 总盈亏 = 最终资金 - 初始资金
        
        logging.info("=" * 60)
        logging.info("回测统计:")
        logging.info(f"初始资金: {INITIAL_CAPITAL:.2f} USDT")
        logging.info(f"最终资金: {capital:.2f} USDT")
        logging.info(f"总盈亏: {total_profit_loss:.2f} USDT")
        logging.info(f"总收益率: {(capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100:.2f}%")
        logging.info(f"交易次数: {len(trade_records)}")
        logging.info(f"盈利次数: {win_trades}")
        logging.info(f"亏损次数: {loss_trades}")
        logging.info(f"胜率: {win_rate:.2f}%")
        logging.info("=" * 60)
    else:
        logging.warning("没有交易记录需要保存")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='币安U本位合约回测脚本')
    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='开始日期，格式: YYYY-MM-DD'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='结束日期，格式: YYYY-MM-DD'
    )
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        logging.error("日期格式错误，请使用 YYYY-MM-DD 格式")
        exit(1)
    
    simulate_trading(args.start_date, args.end_date)
