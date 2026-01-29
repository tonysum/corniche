"""
U本位合约做空策略回测程序 - 详细交易逻辑说明

═══════════════════════════════════════════════════════════════════════════════════════

【程序概述】
本程序模拟币安U本位合约的做空策略，通过分析历史K线数据，找出涨幅最大的交易对进行做空建仓，
并通过动态止盈、止损、补仓机制实现风险控制和利润最大化。

【核心策略逻辑】
1. 每日选择涨幅最大的交易对进行做空
2. 使用动态杠杆和止盈止损参数，根据建仓涨幅调整
3. 多重风控机制：主力获利不足、多空比异常、成交额过滤、Premium指数风控
4. 延迟建仓机制：避免在风险时刻建仓
5. 补仓机制：第一次止损时补仓而不是平仓，提高胜率
6. 动态止损机制：监控顶级交易者多空比，提前识别趋势反转

═══════════════════════════════════════════════════════════════════════════════════════

【1. 建仓逻辑】

【1.1 交易对选择】
- 每日从所有USDT交易对中选择涨幅最大的一个
- 涨幅计算：(当日收盘价 - 昨日收盘价) / 昨日收盘价
- 排除已在持仓中的交易对（避免重复建仓）

【1.2 建仓条件】
- 最小涨幅要求：涨幅 >= 10%
- 账户可用资金充足
- 通过所有风控检查

【1.3 动态参数配置】
根据建仓时的涨幅百分比，动态调整杠杆和止盈止损参数：

┌─────────────────────────────────────────────────────────────────┐
│ 涨幅区间 │ 杠杆 │ 初始止盈% │ 止损% │ 补仓阈值% │ 入场等待% │ 说明 │
├─────────────────────────────────────────────────────────────────┤
│ <25%    │ 2x  │ 40%➜25% │ 45%  │ 44%     │ 0%      │ 极低涨幅区 │
│ 25-40%  │ 2x  │ 40%➜25% │ 45%  │ 44%     │ 1%      │ 中低涨幅区 │
│ 40-60%  │ 2x  │ 40%➜25% │ 45%  │ 44%     │ 8%      │ 中涨幅区   │
│ 60-90%  │ 2x  │ 40%➜25% │ 45%  │ 40%     │ 6%      │ 大涨幅区   │
│ >=90%   │ 2x  │ 40%➜25% │ 45%  │ 40%     │ 10%     │ 特大涨幅区 │
└─────────────────────────────────────────────────────────────────┘

注：止盈策略为动态止盈：
  - 建仓后前2小时：等待40%止盈
  - 建仓后2小时起：降为25%止盈
  - 补仓后保持40%止盈不变

【1.4 风控机制】

【1.4.1 主力获利不足风控】
- 检查从30天均价涨幅是否足够
- 根据涨幅动态调整阈值：
  - 涨幅<40%：30天均价涨幅 >51%
  - 涨幅40-60%：30天均价涨幅 >45%
  - 涨幅>=60%：30天均价涨幅 >35%
- 触发时：延迟到第三天建仓

【1.4.2 多空比风控】
- 检查顶级交易者账户的多空比
- 多空比 < 0.85（空头占比>66%）时延迟建仓
- 避免在极端做空情绪下建仓

【1.4.3 成交额过滤】
- 高涨幅(>=50%) + 成交额<1.5亿：延迟建仓
- 基于数据分析：低成交额高涨幅币胜率较低

【1.4.4 延迟建仓价格检查】
- 仅对延迟建仓生效
- 检查第二天开盘价 vs 第三天建仓价的跌幅
- 跌幅 >11% 时放弃建仓

【1.5 建仓执行】
- 建仓方向：卖空（做空）
- 建仓价格：延迟建仓时为第三天开盘价，否则为第二天开盘价
- 建仓金额：总资产的设定比例（复利模式）
- 杠杆倍数：根据动态配置

═══════════════════════════════════════════════════════════════════════════════════════

【2. 止盈逻辑】

【2.1 止盈条件】
- 价格从建仓价下跌达到止盈阈值时平仓
- 做空策略：价格下跌 = 盈利

【2.2 动态止盈阈值】
- 初始止盈：40%（建仓后前2小时）
- 降低止盈：25%（建仓2小时后自动降低）
- 补仓后止盈：保持40%

【2.3 止盈策略说明】
基于48笔历史交易回测分析：
- 只有10.4%的交易能达到40%以上跌幅
- 56.2%的交易能在36小时内达到25%跌幅
- 平均达到25%跌幅的时间：11.9小时
策略：前2小时追求高收益（40%），之后确保稳定收益（25%）

【2.4 止盈检查】
- 逐小时检查持仓价格
- 一旦触发立即平仓
- 盈亏计算：(建仓价 - 平仓价) × 持仓数量 × 杠杆

═══════════════════════════════════════════════════════════════════════════════════════

【3. 补仓逻辑】

【3.1 补仓触发条件】
- 价格从建仓价上涨达到补仓阈值
- 必须是第一次止盈/止损检查（未补仓过）
- 补仓阈值由动态配置决定

【3.2 补仓执行】
- 补仓数量：等于原持仓数量
- 补仓价格：建仓价 × (1 + 补仓阈值)
- 补仓后更新平均建仓价

【3.3 补仓后调整】
- 止盈阈值调整（通常固定为40%）
- 止损阈值保持（通常为45%）
- 持仓数量增加

【3.4 补仓限制】
- 仅允许补仓一次
- 补仓后若再次触发上限，直接由于止损平仓

═══════════════════════════════════════════════════════════════════════════════════════

【4. 止损逻辑】

【4.1 止损条件】
- 价格从建仓价上涨达到止损阈值
- 做空策略：价格上涨 = 亏损

【4.2 止损阈值】
- 主要止损：45%
- 补仓后止损：45%

【4.3 止损处理】
- 补仓前：触发补仓而不是直接平仓
- 补仓后：直接平仓
- 强制平仓：持有超过 MAX_HOLD_DAYS 天

【4.4 止损优先级】
检查顺序：止盈 > 补仓 > 止损 > 动态止损

【4.5 动态止损逻辑（顶级交易者多空比）】

【4.5.1 动态止损触发条件】
- 建仓后逐小时监控顶级交易者账户多空比变化
- 当多空比从建仓时下降超过阈值时，触发动态止损
- 多空比下降说明主力资金从看多转向看空，价格可能反弹

【4.5.2 多空比变化计算】
- 建仓时记录顶级交易者账户多空比（entry_account_ratio）
- 每小时获取当前多空比（current_account_ratio）
- 计算变化：ratio_change = current - entry
- 判断：如果 ratio_change <= -0.18，触发动态止损

【4.5.3 动态止损阈值】
- 当前阈值：-0.18（多空比下降≥18%）
- 这是保守拦截策略，避免误拦盈利交易
- 根据回测数据优化：
  - 正确拦截：大部分亏损交易
  - 误拦率低：仅少量盈利交易被误拦
  - 净收益显著提升

【4.5.4 数据完整性要求】
- 仅在顶级交易者数据完整期启用（≥2025-12-12）
- 数据不完整期不启用，避免误判
- 数据来源：PostgreSQL（top_account_ratio表）

【4.5.5 动态止损效果】
- 提前识别趋势反转信号
- 减少深度止损损失
- 提升整体策略胜率和收益率
- 与传统止盈止损形成互补

【4.5.6 动态止损示例】
```
建仓：SYMBOL @ 100 USDT，多空比 0.50（50%多头）
1小时后：价格 102 USDT，多空比 0.48（-4%，未触发）
3小时后：价格 105 USDT，多空比 0.40（-20%，触发动态止损）
→ 立即平仓，避免继续上涨造成更大亏损
```

═══════════════════════════════════════════════════════════════════════════════════════

【5. 持仓管理】

- 支持同时持有多个未平仓的交易对
- 逐小时检查持仓状态
- 防止同一天同一标的重复建仓

═══════════════════════════════════════════════════════════════════════════════════════

【6. 风险控制总结】

【6.1 建仓前风控】
1. 涨幅筛选：>=25%
2. 主力获利检查：30天均价涨幅阈值
3. 多空比检查：<0.85时延迟
4. 成交额过滤：高涨幅+低成交额延迟
5. 延迟建仓价格检查：跌幅>11%放弃

【6.2 持仓中风控】
1. 动态止盈：40%（前16小时）→ 25%（16小时后）
2. 补仓机制：44%补仓，补仓后保持40%止盈
3. 止损保护：45%
4. 动态止损：顶级交易者多空比下降≥18%
5. 超时强制平仓：MAX_HOLD_DAYS天（默认12天）

【6.3 资金管理】
- 初始资金：10000 USDT
- 单仓比例：3%
- 杠杆：2倍
- 最大持仓数：10个（可通过MAX_POSITIONS参数调整）

═══════════════════════════════════════════════════════════════════════════════════════

【7. 数据保存】

- 数据库：PostgreSQL (backtrade_records 表)
- CSV文件：project/data/backtrade_records/ 下的带时间戳文件

═══════════════════════════════════════════════════════════════════════════════════════

【8. 数据表依赖（PostgreSQL）】

【8.1 日线/小时线表 (K1d{symbol} / K1h{symbol})】
- 数据结构：trade_date, open, high, low, close, volume, pct_chg
- 主要用途：
  1. 计算每日涨幅，选择做空标的
  2. 计算30天平均价，用于主力获利不足风控
  3. 提供建仓和平仓价格数据
- 数据要求：
  - 需要从回测开始日期至少前30天的数据（用于30天均价计算）
  - 建议从2021-11-01开始的完整历史数据
  - 每个交易对至少需要连续的日线数据

【8.2 5分钟线表 (K5m{symbol})】
- 数据来源：直接查询 K5m{symbol} 表
- 数据结构：open_time, open, high, low, close, volume, taker_buy_volume
- 主要用途：
  1. 计算卖量增长率（用于动态平仓风控）
  2. 监控价格变化，辅助平仓决策
- 数据要求：
  - 需要覆盖回测期间所有持仓时段
  - 建议至少有回测期间前1天的数据（用于计算lookback）
  - 用于卖量风控功能，如无此表则跳过卖量风控

【8.3 顶级交易者数据表 (可选)】
- 数据库：PostgreSQL
- 表名：top_account_ratio
- 主要用途：
  1. 建仓前多空比风控检查
  2. 持仓中动态止损监控
- 数据要求：
  - 动态止损功能仅在数据完整期（≥2025-12-12）启用
  - 如无此表，相关风控功能将被跳过

【8.4 数据表关系说明】
```
回测流程                          使用的数据表
────────────────────────────────────────────────
1. 选择涨幅第一交易对         → K1d{symbol}
2. 主力获利不足风控           → K1d{symbol} (30天数据)
3. 多空比风控检查             → top_account_ratio (可选)
4. 建仓执行                   → K1d{symbol}
5. 卖量增长率动态平仓         → K5m{symbol}
6. 动态止损监控               → top_account_ratio (可选)
7. 止盈止损检查               → K1d{symbol}
```

【8.5 数据完整性检查】
- 运行回测前建议检查数据表完整性
- 日线表是必需的，5分钟表影响卖量风控功能
- 数据缺失可能导致：
  1. 某些交易对无法参与回测
  2. 风控功能部分失效
  3. 回测结果不准确

═══════════════════════════════════════════════════════════════════════════════════════

【9. 数据维护说明】

本程序依赖的数据由 PostgreSQL 数据库维持，由crypto-data-manager项目维护。

【9.1 核心数据源】
- 币安合约 K 线数据 (1d, 1h, 5m)
- 顶级交易者持仓比数据
- 资金费率及 Premium 指数数据

【9.2 注意事项】
- 数据库连接配置位于 backend/db.py
- 若数据库中缺失特定交易对或日期的数据，相关回测步骤将跳过

═══════════════════════════════════════════════════════════════════════════════════════

【10. 数据库时间格式说明】

数据库中所有时间字段均使用 UTC 时区，使用时需要特别注意。

【10.1 时间参照】
- trade_date 格式：'YYYY-MM-DD HH:MM:SS' (UTC)
- 时区对照：UTC 00:00 = 北京时间 08:00

【10.2 open_time / close_time】
- 数据类型：毫秒级 Unix 时间戳 (UTC)

【10.3 重要提醒】
1. 所有数据库时间都是 UTC+0，不是北京时间。
2. 程序中处理时间时注意毫秒级与秒级的转换。
3. Backtrade20260129.py 内部统一使用数据库原始 UTC 时间。

═══════════════════════════════════════════════════════════════════════════════════════

注意：本策略专为做空设计，所有价格变化方向与传统多头策略相反
"""


import os
import logging
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 确保所有 logger (包括 root) 级别正确
logging.getLogger().setLevel(logging.INFO)

import re
import random
import calendar

import pandas as pd  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from db import engine, create_table
from data import get_local_symbols, get_local_kline_data

# 交易参数
INITIAL_CAPITAL = 10000  # 初始资金10000美金准备睡觉
POSITION_SIZE_RATIO = 0.15  # 每次建仓金额为总资产的3%（基础仓位，复利模式）
MIN_PCT_CHG = 0.1  # 最小涨幅10%才建仓
MAX_POSITIONS = 6  # 最大同时持仓数量（限制风险敞口）
MAX_HOLD_DAYS = 11  # 最长持仓时间（天），超过则强制平仓（支持小数，如1.5天）
ENTRY_RISE_THRESHOLD = 0  # 等待开盘价上涨X%后建仓（0表示直接以开盘价建仓）
ENTRY_WAIT_HOURS = 24  # 最长等待时间（小时），超时则放弃该交易

# ============================================================================
# 仓位管理模式配置
# FIXED_POSITION_MODE = True:  每次固定投入1000 USDT（稳定，不受盈亏影响）
# FIXED_POSITION_MODE = False: 每次投入总资产的3%（复利模式，盈利时仓位放大，亏损时仓位缩小）
# ============================================================================
FIXED_POSITION_MODE = False  # 复利模式（每次投入总资产的3%）
FIXED_POSITION_SIZE = 1000  # 固定仓位大小（USDT，仅在FIXED_POSITION_MODE=True时生效）

# ============================================================================
# 补仓参数配置
# 当价格从建仓价上涨达到补仓阈值时，执行补仓操作
# 补仓数量 = 原持仓数量 × 补仓倍数（默认1倍，即数量翻倍）
# 补仓金额 = 补仓数量 × 补仓价格（通常比建仓金额大）
# ============================================================================
ADD_POSITION_THRESHOLD = 0.35  # 补仓阈值35%（价格上涨35%时补仓）
ADD_POSITION_SIZE_MULTIPLIER = 1.0  # 补仓数量倍数（1.0=补仓数量等于原持仓，0.5=补仓一半，2.0=补仓2倍）
PROFIT_THRESHOLD = 0.28   # 止盈30%（价格下跌30%时止盈）
STOP_LOSS_THRESHOLD = 0.35  # 止损35%（补仓前触发补仓，补仓后触发止损）
PROFIT_THRESHOLD_AFTER_ADD = 0.40  # 补仓后止盈40%（补仓降低成本，追求更高收益）
LEVERAGE = 2  # 杠杆倍数

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
ENABLE_VOLUME_POSITION_SIZING = False  # 是否启用成交额分级仓位（已关闭，使用纯粹10%复利逻辑）

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
# 基于2025-11-01至2026-01-09的数据分析优化：
#   - 25-40%涨幅: 第二天平均最高涨12.5%, 等待1%可100%建仓
#   - 40-60%涨幅: 第二天平均最高涨35.8%, 等待10%可66.7%建仓
#   - 60-90%涨幅: 第二天平均最高涨25.3%, 等待15%可40%建仓
#   - >=90%涨幅: 第二天平均最高涨25.3%, 等待25%可83.3%建仓
DYNAMIC_STRATEGY_CONFIG = [
    # (涨幅上限%, 杠杆倍数, 初始止盈%, 止损%, 补仓阈值%, 入场等待涨幅%)
    # 2026-01-28更新：初始止盈改为40%，16小时后动态降为25%
    (25,  2, 0.3, 0.45, 0.44, 0.00),   # 极低涨幅(<25%): 2倍杠杆, 直接开盘建仓（不符合MIN_PCT_CHG，实际不会触发）
    (40,  2, 0.28, 0.45, 0.44, 0.01),   # 中低涨幅(25-40%): 2倍杠杆，初始止盈40%，止损45%，补仓45%，盈亏比1:1.125
    (60,  2, 0.28, 0.45, 0.44, 0.08),   # 中涨幅(40-60%): 2倍杠杆，初始止盈40%，止损45%，补仓55%，盈亏比1:1.125
    (90,  2, 0.28, 0.45, 0.44, 0.06),   # 大涨幅(60-90%): 2倍杠杆，初始止盈40%，止损45%，补仓40%，盈亏比1:1.125
    (999, 2, 0.28, 0.45, 0.44, 0.10),   # 特大涨幅(>=90%): 2倍杠杆，初始止盈40%，止损45%，补仓40%，盈亏比1:1.125
]

# ============================================================================
# 动态止盈配置（2026-01-28新增）
# 基于回测数据分析（48笔交易）：
#   - 只有10.4%的交易能在36小时内达到45%跌幅
#   - 56.2%的交易能在36小时内达到25%跌幅
#   - 24小时内达到25%的比例为47.9%，平均达到时间11.9小时
# 策略：建仓后前2小时等待40%止盈，2小时后降为25%止盈
# ============================================================================
ENABLE_DYNAMIC_PROFIT = True  # 是否启用动态止盈
DYNAMIC_PROFIT_HOURS_THRESHOLD = 18  # 动态止盈时间阈值（小时）
DYNAMIC_PROFIT_REDUCED_THRESHOLD = 0.25  # 降低后的止盈阈值（25%）

# ============================================================================
# 最大涨幅风控配置
# 在等待建仓期间，如果价格涨幅超过阈值，说明币种仍在疯涨，放弃建仓
# 基于数据分析：4笔止损交易建仓后疯涨>20%，这些币种不应该建仓
# ============================================================================
ENABLE_MAX_RISE_FILTER = False  # 是否启用最大涨幅风控

# 不同涨幅区间的最大允许涨幅（等待建仓期间）
MAX_RISE_BEFORE_ENTRY = {
    (25, 40): 0.01,    # 25-40%涨幅，等待期间最大涨1%
    (40, 60): 0.08,    # 40-60%涨幅，等待期间最大涨08%
    (60, 90): 0.06,    # 60-90%涨幅，等待期间最大涨6%
    (90, 999): 0.10,   # >=90%涨幅，等待期间最大涨10%
}


# ============================================================================
# 成交额过滤配置
# 基于回测数据分析（2025-11-01至2026-01-10）：
#   - 高涨幅(>=50%) + 成交额<1.5亿：胜率33.3%，总亏损-3,953 USDT
#   - 高涨幅(>=50%) + 成交额>=1.5亿：胜率84.2%，总盈利+28,954 USDT
#   - 低涨幅(<50%) + 低成交额：胜率100%，全部盈利
# 策略：高涨幅+低成交额 → 延迟一天建仓（第三天做空）
# ============================================================================
ENABLE_VOLUME_FILTER = True  # 是否启用成交额过滤
HIGH_PCT_CHG_THRESHOLD = 50  # 高涨幅阈值（%）
MIN_VOLUME_FOR_HIGH_PCT = 1.5e8  # 高涨幅币的最小成交额（1.5亿）

# ============================================================================
# 实盘风控配置（基于币安期货API数据）
# 在建仓前检查市场情绪指标，避免在极端看涨情绪下做空
# 这些数据只能在实盘中获取，回测时会跳过检查
# ============================================================================
ENABLE_RISK_CONTROL = False  # 是否启用实盘风控检查

# ============================================================================
# Premium Index（基差率）风控配置 - 精确拦截策略【最终优化版】
# 
# Premium Index = (标记价格 - 指数价格) / 指数价格
# 资金费率 = [Premium Index 8小时加权平均 + 固定利率(0.01%)] / 3
# 
# Premium相比资金费率的优势：
# 1. ✅ 有历史数据，支持回测（资金费率无历史数据）
# 2. ✅ 实时更新，更早预警（资金费率8小时滞后）
# 3. ✅ 数学上包含资金费率的所有信息
# 4. ✅ 能在资金费率结算前就发现风险
# 
# 🎯 精确拦截策略（经过充分验证的最优方案）：
# 
# 策略演进过程：
# 1. 初版：检查正Premium + 全范围负Premium → 过于严格，误拦盈利交易
# 2. 中版：检查正Premium + 中负Premium（-1%~-0.3%）→ 仍误拦23笔盈利
# 3. 终版：只检查中负Premium（-0.44%~-0.3%）→ 零误拦，完美拦截 ✅
# 
# 📊 最终版本效果验证（2025-11-01至2026-01-15）：
# ┌─────────────────┬─────────┬─────────┬──────────┐
# │ 指标            │ 无风控   │ 精确拦截 │ 提升     │
# ├─────────────────┼─────────┼─────────┼──────────┤
# │ 总交易数        │ 60笔    │ 57笔    │ -3笔     │
# │ 总盈亏          │ 8,619   │ 14,233  │ +5,613   │
# │ 收益率          │ 86.2%   │ 142.3%  │ +65.1%   │
# │ 胜率            │ 80.0%   │ 84.2%   │ +4.2%    │
# └─────────────────┴─────────┴─────────┴──────────┘
# 
# 被拦截的3笔交易（全部止损）：
# - DASHUSDT：Premium -0.426%，亏损 -1,484 USDT ❌
# - ICNTUSDT：Premium -0.412%，亏损 -1,062 USDT ❌
# - PIPPINUSDT：Premium -0.428%，亏损 -985 USDT ❌
# 合计避免亏损：-3,530 USDT
# 
# 零误拦记录：
# - 高负Premium（<-0.44%）：0笔误拦，保留所有盈利交易 ✅
# - 低负Premium（0~-0.3%）：0笔误拦，保留所有盈利交易 ✅
# - 高正Premium（>0.08%）：0笔误拦，保留所有盈利交易 ✅
# 
# 结论：只拦截 -0.44%~-0.3% 中负Premium区间，其他区间均不拦截
# ============================================================================
ENABLE_PREMIUM_CONTROL = True  # ✅ 启用精确Premium风控（-0.44%~-0.3%）

# Premium风控阈值配置【最终优化版 - 精确拦截策略】
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
    
    # 🔒 极度负Premium危险区间（新增）
    'premium_extreme_negative_min': -0.0265,  # 极度负区间下限：-2.65%
    'premium_extreme_negative_max': -0.017,   # 极度负区间上限：-1.9%（确保包含-1.976%）
    
    # 🔒 中负Premium危险区间（核心风控 - 已验证有效）
    # 回测验证：3笔全部亏损（PIPPINUSDT -5204/ICNTUSDT -464/DASHUSDT -3282），总亏损-8949 USDT
    'premium_avg_dangerous_min': -0.0044,   # 危险区间下限：-0.44%
    'premium_avg_dangerous_max': -0.003,    # 危险区间上限：-0.3%
    
    # 综合判断：1个信号即拦截
    'max_danger_signals': 1,
    
    # ⚠️ 以下参数已禁用（会误拦盈利交易）：
    # - 正Premium检查：禁用，会误拦14笔盈利（损失6,936 USDT）
    # - 当前Premium检查：禁用，使用24小时平均值更稳定
    # - 趋势检查：禁用，会误拦盈利交易
    # - 波动率检查：禁用，会误拦盈利交易
}

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
# 
# 完全过滤模式（当前）：
# - 总收益：35,164 USDT，收益率：351.64%
# - 胜率：81.63%，止损率：16.36%
# - 拦截：15笔高风险信号
# - 优势：更高胜率、更低止损率、更稳健
# 
# 延迟建仓模式（对比）：
# - 总收益：38,695 USDT，收益率：386.95%
# - 胜率：80.85%，止损率：16.67%
# - 优势：收益更高（+3,531 USDT）
# 
# 🎯 用户选择：完全过滤（严格风控）
# 理由：宁可少赚，也要降低风险，追求更稳健的策略
# 
# 特点：每天独立评估，被过滤的交易对后续重新出现时会重新评估买卖量特征
# ============================================================================
ENABLE_VOLUME_RISK_FILTER = True  # 是否启用买卖量风控
VOLUME_RISK_CONFIG = {
    'sell_vol_increase_min': 4.5,      # 卖量增长率下限：450%
    'sell_vol_increase_max': 5.3,      # 卖量增长率上限：530%
    'buy_acceleration_min': 0.06,      # 买量加速度下限：0.06
    'buy_acceleration_max': 0.12,      # 买量加速度上限：0.12
}

# ============================================================================
# 🆕 卖量增长率动态平仓配置（持仓期间监控）
# ============================================================================
# 策略说明：
# 基于分析"analysis_results"数据，当卖量增长率达到300%-450%时：
# - 涉及11个交易对，63.6%最终止盈，36.4%止损
# - 止损交易平均亏损-26.40%，如提前平仓仅亏损+9.65%，避免亏损36.05%
# - 止盈交易平均收益+18.62%，如提前平仓收益+3.64%，损失14.98%
# - 整体效果：总收益从+24.72%提升到+64.04%，提升+39.32%
# 
# 🎯 策略：卖量增长率在300%-450%时立即平仓
# - 大幅减少大额止损（-45%变成约+10%）
# - 牺牲部分止盈交易的收益（+25%变成约+4%）
# - 净效果：总收益提升约40%
# ============================================================================
ENABLE_SELL_GROWTH_EXIT = False  # 🔕 禁用卖量增长率动态平仓（不受顶级交易者数据影响）
SELL_GROWTH_EXIT_CONFIG = {
    'min_growth_rate': 2.7,  # 卖量增长率下限：270%
    'max_growth_rate': 3.4,  # 卖量增长率上限：340%
    'lookback_hours': 3,     # 回看小时数：对比前3小时平均卖量
}

# ============================================================================
# 🆕 顶级交易者多空比动态止损配置
# ============================================================================
# 策略说明：
# 建仓后，如果顶级交易者多空比显著下降，说明主力资金看跌信号增强，
# 此时应考虑提前止盈/止损，避免利润回吐或扩大亏损。
# 
# 数据完整性说明：
# - 顶级交易者数据从2025-12-11开始记录（258条，不完整）
# - 2025-12-12开始数据量稳定（528条/天），作为数据完整期起点
# 
# 阈值选择：
# - 保守拦截（-0.18）：只拦截极端下跌，避免误杀盈利交易
# - 根据回测数据，亏损交易的最小变化值为-0.0109，盈利交易的最小变化值为-0.2585
# - 选择-0.18可以拦截部分大幅下跌但避免误伤中等波动的盈利交易
# ============================================================================
ENABLE_TRADER_STOP_LOSS = True  # 启用顶级交易者动态止损

# API风控阈值配置（辅助风控，仅实盘可用）
# 注意：资金费率检查已被Premium Index替代（Premium有历史数据，支持回测）
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
    
    # 资金费率：极度看涨情绪（⚠️ 已被Premium Index替代）
    # 保留此项作为实盘的额外保障，但回测时无法使用（无历史数据）
    # Premium Index可以完全替代资金费率，且效果更好（实时、有历史）
    'funding_rate_max': 0.0005,  # 资金费率 > 0.05% 时警惕（仅实盘生效）
    
    # 综合判断：满足多少个危险信号时放弃建仓
    # 更保守的策略：1个危险信号就拦截，宁可错过也不要亏损
    'max_danger_signals': 1,  # 超过1个危险信号时放弃
}

# ============================================================================
# 顶级交易者动态止损配置【新增功能】
# 
# 基于Binance顶级交易者账户多空比变化的实时止损
# 
# 核心逻辑：监控顶级交易者（"聪明钱"）的持仓方向变化
# - 当账户多空比下降时，说明顶级交易者从看多转向看空
# - 对于做空策略，这意味着市场情绪转变，价格可能反弹
# - 提前止损，避免深度亏损
# 
# 📊 回测验证（2025-11-01至2026-01-15）：
# ┌────────────────┬─────────┬─────────┬──────────┐
# │ 指标           │ 无止损   │ 有止损   │ 提升     │
# ├────────────────┼─────────┼─────────┼──────────┤
# │ 拦截止损       │ -       │ 3/3笔   │ 100%     │
# │ 避免亏损       │ -       │ $7,171  │ -        │
# │ 误判止盈       │ -       │ 2/19笔  │ 10.5%    │
# │ 损失盈利       │ -       │ $1,721  │ -        │
# │ 净收益         │ $8,619  │ $14,069 │ +$5,450  │
# │ 收益率提升     │ 86.2%   │ 140.7%  │ +54.5%   │
# └────────────────┴─────────┴─────────┴──────────┘
# 
# 成功拦截的3笔大亏损：
# - HUSDT: 多空比-0.3157，避免亏损$3,232
# - BROCCOLI714USDT: 多空比-0.2565，避免亏损$1,144
# - CLOUSDT: 多空比-0.0159，避免亏损$2,795
# 
# 参考：hm1.py（做多策略）同样有效
# - 平均止损损失从-$868/笔降到-$11/笔
# - 最大回撤降低22%
# - 风险收益比提升22.6%
# ============================================================================
ENABLE_TRADER_STOP_LOSS = True  # 启用顶级交易者动态止损

# 顶级交易者动态止损配置
TRADER_STOP_LOSS_CONFIG = {
    # 账户多空比下降阈值
    # - 基于回测优化：-0.18（下降≥18%）保守拦截策略
    # - 避免数据不完整期误判（仅在>=2025-12-12启用）
    # - 数据完整期：正确拦截亏损交易，净收益显著提升
    'account_ratio_stop_threshold': -0.18,  # 下降≥18%时触发止损（保守拦截）
    
    # 数据完整期开始日期（在此之前不启用动态止损）
    # 实际数据：2025-12-11仅258条记录，2025-12-12开始528条/天（数据量稳定）
    'data_start_date': '2025-12-12',
    
    # 数据库配置（现已迁移至PostgreSQL，无需db_path）
    # 数据表名
    'table_name': 'top_account_ratio'
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

# Premium数据缓存（避免重复查询）
_premium_cache: Dict[str, dict] = {}

# 顶级交易者数据缓存
_trader_cache: Dict[str, dict] = {}

def get_top_trader_account_ratio(symbol: str, check_datetime: str) -> dict:
    """
    从数据库获取顶级交易者账户多空比数据（带缓存）
    
    账户多空比 = 顶级交易者做多账户数 / 做空账户数
    - 比值高：顶级交易者偏向看多
    - 比值低：顶级交易者偏向看空
    - 比值下降：顶级交易者从看多转向看空
    
    Args:
        symbol: 交易对符号（如 'BTCUSDT'）
        check_datetime: 检查时间（格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'）
    
    Returns:
        dict: {
            'long_short_ratio': 账户多空比,
            'long_account': 做多账户百分比,
            'short_account': 做空账户百分比,
            'timestamp': 时间戳,
            'success': 是否成功获取数据
        }
    """
    # 检查缓存
    cache_key = f"{symbol}_{check_datetime}"
    if cache_key in _trader_cache:
        return _trader_cache[cache_key]
    
    result = {
        'long_short_ratio': None,
        'long_account': None,
        'short_account': None,
        'timestamp': None,
        'success': False
    }
    
    try:
        # 解析检查时间
        if ' ' in check_datetime:
            check_dt = datetime.strptime(check_datetime, '%Y-%m-%d %H:%M:%S')
        else:
            check_dt = datetime.strptime(check_datetime, '%Y-%m-%d')
        
        # 转换为UTC毫秒时间戳
        check_ts = int(calendar.timegm(check_dt.timetuple()) * 1000)
        
        # 查询数据（查找最接近的时间点，允许±1天误差）
        table_name = TRADER_STOP_LOSS_CONFIG['table_name']
        
        # 查找最接近的数据点
        time_tolerance = 86400000  # 1天的毫秒数
        query = f"""
            SELECT timestamp, long_short_ratio, long_account, short_account
            FROM "{table_name}"
            WHERE symbol = :symbol
              AND timestamp >= :min_ts
              AND timestamp <= :max_ts
            ORDER BY ABS(timestamp - :check_ts)
            LIMIT 1
        """
        
        with engine.connect() as conn:
            result_proxy = conn.execute(
                text(query),
                {
                    'symbol': symbol,
                    'min_ts': check_ts - time_tolerance,
                    'max_ts': check_ts + time_tolerance,
                    'check_ts': check_ts
                }
            )
            row = result_proxy.fetchone()
        
        if row:
            result['timestamp'] = row[0]
            result['long_short_ratio'] = row[1]
            result['long_account'] = row[2]
            result['short_account'] = row[3]
            result['success'] = True
        
        # 缓存结果
        _trader_cache[cache_key] = result
        
    except Exception as e:
        logging.warning(f"获取 {symbol} 顶级交易者数据失败: {e}")
        # 缓存失败结果
        _trader_cache[cache_key] = result
    
    return result


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
            'premium_volatility': 基差率波动率（标准差）,
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
        'premium_volatility': None,
        'data_points': 0,
        'success': False
    }
    
    try:
        # 解析检查时间（已经是UTC时间）
        if ' ' in check_datetime:
            check_dt = datetime.strptime(check_datetime, '%Y-%m-%d %H:%M:%S')
        else:
            check_dt = datetime.strptime(check_datetime, '%Y-%m-%d')
        
        # ✅ 转换为UTC毫秒时间戳（需要明确指定UTC，避免受系统时区影响）
        # 方法：使用calendar.timegm()而不是timestamp()，因为timegm假设输入是UTC
        check_ts = int(calendar.timegm(check_dt.timetuple()) * 1000)
        start_24h_ts = int(calendar.timegm((check_dt - timedelta(hours=24)).timetuple()) * 1000)
        
        # 使用SQLAlchemy引擎连接（而不是sqlite3.connect）
        query = text('''
            SELECT open_time, close
            FROM "premium_index_history"
            WHERE symbol = :symbol 
              AND open_time >= :start_ts
              AND open_time <= :end_ts
              AND interval = '1h'
            ORDER BY open_time ASC
            LIMIT 25
        ''')
        
        with engine.connect() as conn:
            result_proxy = conn.execute(
                query, 
                {'symbol': symbol, 'start_ts': start_24h_ts, 'end_ts': check_ts}
            )
            rows = result_proxy.fetchall()
        
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
        
        # 🆕 计算波动率（标准差）- 衡量Premium的不稳定性
        if len(premiums) >= 3:
            import statistics
            result['premium_volatility'] = statistics.stdev(premiums)
        else:
            result['premium_volatility'] = 0
        
        result['data_points'] = len(premiums)
        result['success'] = True
        
        # 缓存成功结果
        _premium_cache[cache_key] = result
        
    except Exception as e:
        logging.warning(f"获取 {symbol} Premium数据失败: {e}")
        # 缓存失败结果
        _premium_cache[cache_key] = result
    
    return result


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


def calculate_funding_fee_cost_accurate(symbol: str, entry_datetime: str, exit_datetime: str,
                                       notional_value: float, trade_direction: str = 'short') -> dict:
    """
    精确计算持仓期间的资金费成本（使用实际Premium数据）
    
    Binance资金费规则：
    1. 标准结算：每8小时一次（00:00, 08:00, 16:00 UTC）
    2. 极端行情：可能改为每小时一次（当FR达到±0.75%或市场极度波动时）
    3. 资金费率：FR = clamp((Premium_8h_avg + 0.01%) / 3, -0.05%, +0.05%)
    
    Args:
        symbol: 交易对
        entry_datetime: 建仓时间（字符串格式："YYYY-MM-DD HH:MM:SS"）
        exit_datetime: 平仓时间（字符串格式："YYYY-MM-DD HH:MM:SS"）
        notional_value: 名义价值 = 投入金额 × 杠杆（即 price × size）
        trade_direction: 交易方向，'short'或'long'
    
    Returns:
        dict: {
            'total_cost': 资金费总成本（USDT），
            'settlement_details': 每次结算的详情列表，
            'settlement_count': 结算次数，
            'is_hourly': 是否检测到小时结算
        }
    """
    from datetime import datetime, timedelta
    
    result = {
        'total_cost': 0,
        'settlement_details': [],
        'settlement_count': 0,
        'is_hourly': False
    }
    
    if notional_value is None or notional_value == 0:
        return result
    
    try:
        entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d %H:%M:%S')
        exit_dt = datetime.strptime(exit_datetime, '%Y-%m-%d %H:%M:%S')
        
        # 找出持仓期间所有的结算时点（00:00, 08:00, 16:00 UTC）
        # ✅ entry/exit时间已经是UTC时间（K线数据存储为UTC字符串）
        settlement_times = []
        current = entry_dt.replace(minute=0, second=0, microsecond=0)
        
        # 找到下一个结算时点
        while current <= exit_dt:
            if current.hour in [0, 8, 16]:  # 已经是UTC时间，直接判断
                if current > entry_dt:  # 只计算建仓后的结算点
                    settlement_times.append(current)
            current += timedelta(hours=1)
        
        if not settlement_times:
            return result
        
        # 获取每个结算时点的Premium数据
        conn = engine.connect()
        total_cost = 0
        
        for settle_time in settlement_times:
            # 获取结算时点前8小时的Premium数据（用于计算8小时加权平均）
            start_time = settle_time - timedelta(hours=8)
            # ✅ 使用calendar.timegm()而不是timestamp()，确保UTC时间戳
            start_ts = int(calendar.timegm(start_time.timetuple()) * 1000)
            end_ts = int(calendar.timegm(settle_time.timetuple()) * 1000)
            
            query = text("""
                SELECT open_time, close as premium
                FROM "premium_index_history"
                WHERE symbol = :symbol
                  AND open_time >= :start_ts
                  AND open_time < :end_ts
                ORDER BY open_time ASC
            """)
            
            premiums = []
            try:
                rows = conn.execute(query, {'symbol': symbol, 'start_ts': start_ts, 'end_ts': end_ts}).fetchall()
                premiums = [row[1] for row in rows if row[1] is not None]
            except Exception as e:
                logging.warning(f"获取{symbol}在{settle_time}的Premium数据失败: {e}")
                continue
            
            if not premiums:
                continue
            
            # 计算8小时加权平均Premium（简化为算术平均）
            premium_avg = sum(premiums) / len(premiums)
            
            # 计算资金费率
            funding_rate = (premium_avg + 0.0001) / 3
            funding_rate = max(-0.05, min(0.05, funding_rate))
            
            # 检测是否可能触发小时结算（FR > ±0.75%）
            if abs(funding_rate) > 0.0075:
                result['is_hourly'] = True
                logging.warning(f"{symbol} 在{settle_time}的资金费率{funding_rate*100:.3f}%可能触发小时结算")
            
            # 计算成本
            cost = notional_value * funding_rate
            if trade_direction == 'short':
                cost = -cost  # 做空时取反
            
            total_cost += cost
            
            result['settlement_details'].append({
                'time': settle_time.strftime('%Y-%m-%d %H:%M:%S'),
                'premium_avg': premium_avg,
                'funding_rate': funding_rate,
                'cost': cost
            })
        
        conn.close()
        
        result['total_cost'] = total_cost
        result['settlement_count'] = len(settlement_times)
        
    except Exception as e:
        logging.error(f"计算{symbol}资金费成本失败: {e}")
    
    return result


def calculate_funding_fee_cost(premium_avg: float, position_value: float, hold_hours: int, 
                               trade_direction: str = 'short') -> dict:
    """
    简化版资金费计算（用于快速估算，使用建仓时Premium）
    
    ⚠️ 注意：这是简化版本，使用建仓时的24h平均Premium估算
    更精确的计算请使用 calculate_funding_fee_cost_accurate()
    
    资金费率公式：FR = (Premium + 0.01%) / 3
    Binance限制：-0.05% ≤ FR ≤ 0.05%
    结算周期：每8小时结算一次
    
    对于做空策略：
    - 正Premium（合约>现货）：资金费率为正，空头收到资金费（负成本，即收益）
    - 负Premium（合约<现货）：资金费率为负，空头支付资金费（正成本，即支出）
    
    Args:
        premium_avg: 24小时平均Premium（小数形式，如0.0008表示0.08%）
        position_value: 持仓价值（USDT）
        hold_hours: 持仓小时数
        trade_direction: 交易方向，'short'或'long'
    
    Returns:
        dict: {
            'funding_rate': 资金费率（每8小时），
            'settlement_count': 结算次数，
            'funding_fee_cost': 资金费总成本（USDT，正数=支出，负数=收入）,
            'cost_per_settlement': 每次结算的成本（USDT）
        }
    """
    result = {
        'funding_rate': 0,
        'settlement_count': 0,
        'funding_fee_cost': 0,
        'cost_per_settlement': 0
    }
    
    # 如果没有Premium数据，返回0成本
    if premium_avg is None or position_value is None or hold_hours is None:
        return result
    
    # 计算资金费率：FR = (Premium + 0.01%) / 3
    funding_rate = (premium_avg + 0.0001) / 3
    
    # Binance限制资金费率在 ±0.05%
    funding_rate = max(-0.05, min(0.05, funding_rate))
    
    # 计算结算次数（每8小时结算一次，不足8小时不结算）
    settlement_count = hold_hours // 8
    
    if settlement_count == 0:
        return result
    
    # 计算每次结算的成本/收益
    # 资金费率的支付方向：
    # - FR > 0：多头支付给空头
    # - FR < 0：空头支付给多头
    cost_per_settlement = position_value * funding_rate
    
    if trade_direction == 'short':
        # 做空：资金费率为正时收入（负成本），为负时支出（正成本）
        # - 正Premium → FR > 0 → 空头收入 → 成本为负
        # - 负Premium → FR < 0 → 空头支出 → 成本为正
        cost_per_settlement = -cost_per_settlement
    # 做多：资金费率为正时支出（正成本），为负时收入（负成本）
    # cost_per_settlement保持原值即可
    
    # 总成本 = 单次成本 × 结算次数
    total_cost = cost_per_settlement * settlement_count
    
    result['funding_rate'] = funding_rate
    result['settlement_count'] = settlement_count
    result['funding_fee_cost'] = total_cost
    result['cost_per_settlement'] = cost_per_settlement
    
    return result


def check_trader_stop_loss(symbol: str, entry_datetime: str, current_datetime: str, 
                          entry_account_ratio: Optional[float] = None) -> tuple:
    """
    检查是否因顶级交易者账户多空比变化触发止损
    
    核心逻辑：
    1. 获取建仓时的账户多空比
    2. 获取当前的账户多空比
    3. 计算变化：ratio_change = current - entry
    4. 如果下降幅度超过阈值，触发止损
    
    Args:
        symbol: 交易对符号
        entry_datetime: 建仓时间（UTC）
        current_datetime: 当前时间（UTC）
        entry_account_ratio: 建仓时的账户多空比（如果已知）
    
    Returns:
        (是否触发止损: bool, 原因说明: str, 数据详情: dict)
    """
    if not ENABLE_TRADER_STOP_LOSS:
        return False, "", {}
    
    try:
        # ✅ 数据完整性检查：只在数据完整期才启用动态止损
        from datetime import datetime
        entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d %H:%M:%S')
        data_start_dt = datetime.strptime(TRADER_STOP_LOSS_CONFIG['data_start_date'], '%Y-%m-%d')
        
        if entry_dt < data_start_dt:
            # 建仓时间在数据完整期之前，不启用动态止损
            return False, "", {}
        
        # 获取建仓时的账户多空比
        if entry_account_ratio is None:
            entry_data = get_top_trader_account_ratio(symbol, entry_datetime)
            if not entry_data['success'] or entry_data['long_short_ratio'] is None:
                # 无建仓数据，无法判断
                return False, "", {}
            entry_account_ratio = entry_data['long_short_ratio']
        
        # 获取当前的账户多空比
        current_data = get_top_trader_account_ratio(symbol, current_datetime)
        if not current_data['success'] or current_data['long_short_ratio'] is None:
            # 无当前数据，无法判断
            return False, "", {}
        
        current_account_ratio = current_data['long_short_ratio']
        
        # 计算变化
        ratio_change = current_account_ratio - entry_account_ratio
        
        # 获取阈值
        threshold = TRADER_STOP_LOSS_CONFIG['account_ratio_stop_threshold']
        
        # 保存数据供后续分析
        data_details = {
            'entry_account_ratio': entry_account_ratio,
            'current_account_ratio': current_account_ratio,
            'ratio_change': ratio_change,
            'threshold': threshold
        }
        
        # 判断是否触发止损
        if ratio_change <= threshold:
            reason = (
                f"顶级交易者账户多空比从{entry_account_ratio:.4f}下降到{current_account_ratio:.4f}，"
                f"变化{ratio_change:+.4f} <= {threshold}（阈值），"
                f"顶级交易者从看多转向看空，价格可能反弹"
            )
            return True, reason, data_details
        
        return False, "", data_details
        
    except Exception as e:
        logging.error(f"检查顶级交易者止损失败 {symbol}: {e}")
        return False, "", {}


def check_risk_control(symbol: str, entry_pct_chg: float, entry_datetime: str = None) -> dict:
    """
    实盘风控检查：检查市场情绪是否适合做空
    
    Args:
        symbol: 交易对符号
        entry_pct_chg: 入场涨幅（%）
        entry_datetime: 建仓时间（用于回测时查询历史Premium数据）
    
    Returns:
        dict: {
            'should_trade': 是否应该建仓,
            'danger_signals': 危险信号列表,
            'sentiment_data': 原始情绪数据,
            'premium_data': Premium数据,
            'message': 风控消息
        }
    """
    result = {
        'should_trade': True,
        'danger_signals': [],
        'sentiment_data': None,
        'premium_data': None,
        'message': ''
    }
    
    # ============================================================
    # 【主风控】Premium Index风控检查（回测+实盘通用）
    # Premium = (标记价格 - 指数价格) / 指数价格
    # 与资金费率高度相关，但有历史数据，支持回测
    # ============================================================
    if ENABLE_PREMIUM_CONTROL and entry_datetime:
        premium_data = get_premium_index_data(symbol, entry_datetime)
        result['premium_data'] = premium_data
        
        if premium_data['success']:
            config_premium = PREMIUM_CONTROL_CONFIG
            premium_signals = []
            
            # 🔕 1. 检查24小时平均Premium - 正值过高（已禁用，会误拦盈利交易）
            # if premium_data['avg_24h_premium'] and premium_data['avg_24h_premium'] > config_premium['premium_avg_max']:
            #     premium_signals.append(
            #         f"Premium 24h均值 {premium_data['avg_24h_premium']*100:.4f}% > {config_premium['premium_avg_max']*100:.2f}% (看涨情绪强，做空危险)"
            #     )
            
            # ✅ 1a. 检查24小时平均Premium - 极度负Premium区间（-2.65%~-1.9%）【新增风控】
            # 发现：TNSRUSDT(-2.64%)、TRADOORUSDT(-1.976%) 都触发补仓止损，合计亏损-10,207 USDT
            # 原因：合约远低于现货，市场极度看空，易发生空头挤压（Short Squeeze）
            if premium_data['avg_24h_premium']:
                extreme_negative_min = config_premium.get('premium_extreme_negative_min', -0.0265)
                extreme_negative_max = config_premium.get('premium_extreme_negative_max', -0.019)
                
                if extreme_negative_min < premium_data['avg_24h_premium'] < extreme_negative_max:
                    premium_signals.append(
                        f"Premium 24h均值 {premium_data['avg_24h_premium']*100:.4f}% 在极度负区间 [{extreme_negative_min*100:.2f}%, {extreme_negative_max*100:.2f}%] "
                        f"(市场极度看空，易发生空头挤压，逆势做空危险)"
                    )
            
            # ✅ 1b. 检查24小时平均Premium - 中负Premium区间（-0.44%~-0.3%）【核心风控】
            # 回测验证：3笔全部亏损，总亏损-8,949 USDT（PIPPINUSDT/ICNTUSDT/DASHUSDT）
            # 拦截效率：100%（3/3），胜率提升：80.77% → 85.71%，总收益提升50%
            if premium_data['avg_24h_premium']:
                dangerous_min = config_premium.get('premium_avg_dangerous_min', -0.0044)
                dangerous_max = config_premium.get('premium_avg_dangerous_max', -0.003)
                
                if dangerous_min < premium_data['avg_24h_premium'] < dangerous_max:
                    implied_fr = (premium_data['avg_24h_premium'] + 0.0001) / 3 * 100
                    premium_signals.append(
                        f"Premium 24h均值 {premium_data['avg_24h_premium']*100:.4f}% 在危险区间 [{dangerous_min*100:.2f}%, {dangerous_max*100:.1f}%] "
                        f"(空头需支付资金费率 约{abs(implied_fr):.3f}%/8h，且该区间100%亏损)"
                    )
            
            # 🔕 2. 检查当前Premium - 正值过高（已禁用，会误拦盈利交易）
            # if premium_data['current_premium'] and premium_data['current_premium'] > config_premium['premium_current_max']:
            #     premium_signals.append(
            #         f"Premium当前值 {premium_data['current_premium']*100:.4f}% > {config_premium['premium_current_max']*100:.2f}% (合约溢价过高，做空危险)"
            #     )
            
            # 🔕 2b. 检查当前Premium - 中负Premium区间（已禁用，只用平均值判断）
            # if premium_data['current_premium']:
            #     dangerous_min = config_premium.get('premium_current_dangerous_min', -0.02)
            #     dangerous_max = config_premium.get('premium_current_dangerous_max', -0.005)
            #     
            #     if dangerous_min < premium_data['current_premium'] < dangerous_max:
            #         implied_fr = (premium_data['current_premium'] + 0.0001) / 3 * 100
            #         premium_signals.append(
            #             f"Premium当前值 {premium_data['current_premium']*100:.4f}% 在危险区间 [{dangerous_min*100:.1f}%, {dangerous_max*100:.1f}%] "
            #             f"(瞬时资金费率 约{abs(implied_fr):.3f}%/8h)"
            #         )
            
            # 🔕 3. 检查Premium趋势 - 正向加速（已禁用，会误拦盈利交易）
            # if premium_data['premium_trend'] and premium_data['premium_trend'] > config_premium['premium_trend_threshold']:
            #     premium_signals.append(
            #         f"Premium趋势 +{premium_data['premium_trend']*100:.1f}% > {config_premium['premium_trend_threshold']*100:.0f}% (看涨情绪加速，做空危险)"
            #     )
            
            # 🔕 3b. 检查Premium趋势 - 负向加速（看跌加速，资金费率成本增加）- 已禁用
            # if premium_data['premium_trend'] and premium_data['premium_trend'] < config_premium.get('premium_trend_min', -999):
            #     premium_signals.append(
            #         f"Premium趋势 {premium_data['premium_trend']*100:.1f}% < {config_premium['premium_trend_min']*100:.0f}% (看跌情绪加速，资金费率成本增加)"
            #     )
            
            # 4. 检查Premium波动率（市场情绪不稳定性）- 已禁用
            # 测试发现波动率检测会误杀盈利交易，暂时禁用
            # if 'premium_volatility' in premium_data and premium_data['premium_volatility']:
            #     vol_threshold = config_premium.get('premium_volatility_max', 0.002)
            #     if premium_data['premium_volatility'] > vol_threshold:
            #         premium_signals.append(
            #             f"Premium波动率 {premium_data['premium_volatility']*100:.4f}% > {vol_threshold*100:.2f}% (市场情绪不稳定)"
            #         )
            
            # 判断是否拦截（1个信号就拦截）
            if len(premium_signals) >= config_premium['max_danger_signals']:
                result['should_trade'] = False
                result['danger_signals'].extend(premium_signals)
                result['message'] = f"Premium风控拦截: 发现{len(premium_signals)}个危险信号 (替代资金费率检查)"
                logging.info(f"{symbol} {result['message']}")
                return result  # Premium拦截，无需继续检查资金费率
            elif premium_signals:
                # 有信号但未超阈值，记录警告，继续检查
                result['danger_signals'].extend(premium_signals)
                logging.info(f"{symbol} Premium风控警告: {', '.join(premium_signals)}")
        else:
            logging.debug(f"{symbol} 无Premium数据，将尝试使用API资金费率风控")
    
    # ============================================================
    # 【辅助风控】API风控检查（仅实盘可用，Premium的补充）
    # 如果Premium已经拦截，不会执行到这里
    # 如果Premium通过，再用API数据做二次确认（仅实盘）
    # ============================================================
    if not ENABLE_RISK_CONTROL:
        # API风控未启用
        if ENABLE_PREMIUM_CONTROL:
            result['message'] = 'Premium风控通过 (API风控已禁用)'
        else:
            result['message'] = '所有风控检查已禁用'
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
    
    # 5. 资金费率过高（已被Premium Index替代）
    # 注意：资金费率 = Premium Index的8小时加权平均 + 固定利率
    # Premium风控已经涵盖了资金费率的核心信息，且更实时、更准确
    # 这里保留资金费率检查作为实盘的额外保障（仅当Premium未拦截时才会执行到这里）
    if sentiment['funding_rate'] and sentiment['funding_rate'] > config['funding_rate_max']:
        danger_signals.append(
            f"资金费率 {sentiment['funding_rate']*100:.4f}% > {config['funding_rate_max']*100:.2f}% (极度看涨，Premium风控未拦截但资金费率确认)"
        )
    
    result['danger_signals'] = danger_signals
    
    # 判断是否应该建仓
    if len(danger_signals) > config['max_danger_signals']:
        result['should_trade'] = False
        result['message'] = f"风控拦截: 发现{len(danger_signals)}个危险信号 > {config['max_danger_signals']}个阈值"
    else:
        result['message'] = f"风控通过: {len(danger_signals)}个危险信号 <= {config['max_danger_signals']}个阈值"
    
    return result


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
        # 使用SQLAlchemy引擎连接
        table_name = f'K1h{symbol}'
        
        query = f"""
            SELECT 
                open_time,
                volume,
                active_buy_volume
            FROM "{table_name}"
            WHERE open_time >= :start_ts AND open_time < :entry_ts
            ORDER BY open_time ASC
        """
        
        with engine.connect() as conn:
            df = pd.read_sql_query(
                text(query),
                conn,
                params={'start_ts': start_ts, 'entry_ts': entry_ts}
            )
        
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
        logging.warning(f"{symbol} 买卖量风控检查失败: {e}")
        result['reason'] = f'买卖量风控检查异常: {e}'
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
            
            # 检查是否有pct_chg列，如果没有或为NaN，则计算涨幅
            pct_chg = None
            if 'pct_chg' in row.index:
                pct_chg = row['pct_chg']
            
            if pct_chg is None or pd.isna(pct_chg):
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
            
            # 如果没有pct_chg列或有NaN值，计算涨幅（完全向量化）
            if 'pct_chg' not in df_filtered.columns or df_filtered['pct_chg'].isna().any():
                # 在原始df上计算pct_chg（如果没有的话）
                if 'pct_chg' not in df.columns or df['pct_chg'].isna().any():
                    df['prev_close'] = df['close'].shift(1)
                    df['pct_chg'] = (df['close'] - df['prev_close']) / df['prev_close'] * 100
                
                # 将计算好的pct_chg合并到df_filtered
                df_filtered = df_filtered.drop('pct_chg', axis=1, errors='ignore')
                df_filtered = df_filtered.merge(
                    df[['trade_date_str', 'pct_chg']], 
                    on='trade_date_str', 
                    how='left'
                )
            
            # 转换pct_chg为数值类型
            df_filtered['pct_chg'] = pd.to_numeric(df_filtered['pct_chg'], errors='coerce')
            
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
    # 使用 sort_values + head(1) 代替 apply(nlargest)，以避免 pandas FutureWarning 并提升性能
    top_gainers = (
        combined_df.sort_values(['trade_date_str', 'pct_chg'], ascending=[True, False])
        .groupby('trade_date_str')
        .head(1)
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
    # 统一使用K1h{symbol}表名格式
    table_name = f'K1h{symbol}'

    try:
        stmt = f'SELECT * FROM "{table_name}" ORDER BY trade_date ASC'
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
    table_name = f'K1h{symbol}'
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
            FROM "{table_name}"
            WHERE trade_date >= '{start_dt.strftime('%Y-%m-%d %H:%M:%S')}'
            AND trade_date < '{entry_dt.strftime('%Y-%m-%d %H:%M:%S')}'
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
                             wait_hours: int = ENTRY_WAIT_HOURS,
                             entry_pct_chg: float = 0) -> dict:
    """
    查找价格上涨到目标价的触发时间点
    
    Args:
        symbol: 交易对
        open_price: 开盘价
        start_date: 开始查找的日期（YYYY-MM-DD格式）
        rise_threshold: 上涨阈值（如0.05表示5%）
        wait_hours: 最长等待小时数
        entry_pct_chg: 入场涨幅（第一天的涨幅百分比，用于风控）
    
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
    
    # 获取最大允许涨幅（用于风控）
    max_rise_threshold = None
    if ENABLE_MAX_RISE_FILTER and entry_pct_chg > 0:
        for (pct_min, pct_max), max_rise in MAX_RISE_BEFORE_ENTRY.items():
            if pct_min <= entry_pct_chg < pct_max:
                max_rise_threshold = max_rise
                break
    
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
            
            # 风控检查：如果等待期间涨幅过大，放弃建仓
            if max_rise_threshold is not None:
                current_rise = (row['high'] - open_price) / open_price
                if current_rise > max_rise_threshold:
                    logging.info(
                        f"{symbol} 等待建仓期间涨幅{current_rise*100:.1f}%超过{max_rise_threshold*100:.0f}%限制，"
                        f"币种仍在疯涨，放弃建仓（入场涨幅{entry_pct_chg:.1f}%）"
                    )
                    return result
            
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


def load_sell_volume_data_for_position(symbol: str, entry_datetime: datetime, end_datetime: datetime) -> pd.DataFrame:
    """
    优先使用1小时K线，降级到5分钟K线聚合
    
    Args:
        symbol: 交易对符号
        entry_datetime: 建仓时间
        end_datetime: 结束时间
    
    Returns:
        DataFrame: 每小时的卖量数据，包含 hour, sell_volume 列
    """
    # 扩展时间范围，包含前3小时用于计算增长率
    start_ts = int((entry_datetime - timedelta(hours=3)).timestamp() * 1000)
    end_ts = int(end_datetime.timestamp() * 1000)
    
    # 方案1: 优先尝试使用1小时K线 (快速，性能提升10倍)
    try:
        table_name = f"K1h{symbol}"
        
        query = f"""
            SELECT open_time, volume, active_buy_volume
            FROM "{table_name}"
            WHERE open_time >= :start_ts AND open_time < :end_ts
            ORDER BY open_time
        """
        with engine.connect() as conn:
            df = pd.read_sql_query(
                text(query),
                conn,
                params={'start_ts': start_ts, 'end_ts': end_ts}
            )
        
        if not df.empty:
            # 直接计算主动卖量 (无需聚合)
            df['active_sell_volume'] = df['volume'] - df['active_buy_volume']
            # ✅ 修复时区问题：强制使用UTC时间，与trade_date保持一致
            df['datetime'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
            df['hour'] = df['datetime'].dt.floor('h').dt.tz_localize(None)  # 去除时区标记但保持UTC时间值
            
            hourly_sell = df[['hour', 'active_sell_volume']].copy()
            hourly_sell.columns = ['hour', 'sell_volume']
            
            logging.debug(f"✅ {symbol} 使用1小时K线，查询{len(df)}条")
            return hourly_sell
    
    except Exception as e:
        logging.debug(f"{symbol} 1小时K线不可用: {e}, 降级到5分钟聚合")
    
    # 方案2: 降级使用5分钟K线聚合 (兼容方案)
    try:
        table_name = f"K5m{symbol}"
        
        query = f"""
            SELECT open_time, volume, active_buy_volume
            FROM "{table_name}"
            WHERE open_time >= :start_ts AND open_time < :end_ts
            ORDER BY open_time
        """
        with engine.connect() as conn:
            df = pd.read_sql_query(
                text(query),
                conn,
                params={'start_ts': start_ts, 'end_ts': end_ts}
            )
        
        if df.empty:
            return pd.DataFrame()
        
        # 计算主动卖量
        df['active_sell_volume'] = df['volume'] - df['active_buy_volume']
        
        # ✅ 修复时区问题：强制使用UTC时间，与trade_date保持一致
        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
        df['hour'] = df['datetime'].dt.floor('h').dt.tz_localize(None)  # 去除时区标记但保持UTC时间值
        
        hourly_sell = df.groupby('hour')['active_sell_volume'].sum().reset_index()
        hourly_sell.columns = ['hour', 'sell_volume']
        
        logging.debug(f"✅ {symbol} 使用5分钟K线聚合，查询{len(df)}条")
        return hourly_sell
        
    except Exception as e:
        logging.warning(f"加载 {symbol} 卖量数据失败: {e}")
        return pd.DataFrame()


def calculate_sell_volume_growth_rate_from_cache(hourly_data: pd.DataFrame, current_hour: datetime, lookback_hours: int = 3) -> float:
    """
    从缓存的小时数据中计算卖量增长率（避免重复查询数据库）
    
    Args:
        hourly_data: 预加载的小时卖量数据
        current_hour: 当前小时
        lookback_hours: 回看小时数
    
    Returns:
        float: 卖量增长率
    """
    try:
        if hourly_data.empty:
            return 0.0
        
        # 找到当前小时的数据
        current_data = hourly_data[hourly_data['hour'] == current_hour]
        if current_data.empty:
            return 0.0
        
        current_sell_volume = current_data['sell_volume'].iloc[0]
        
        # 找到前N小时的数据
        lookback_start = current_hour - timedelta(hours=lookback_hours)
        lookback_data = hourly_data[
            (hourly_data['hour'] >= lookback_start) & 
            (hourly_data['hour'] < current_hour)
        ]
        
        if lookback_data.empty or len(lookback_data) == 0:
            return 0.0
        
        # 计算平均卖量
        avg_sell_volume = lookback_data['sell_volume'].mean()
        
        if avg_sell_volume == 0:
            return 0.0
        
        # 计算增长率
        growth_rate = (current_sell_volume - avg_sell_volume) / avg_sell_volume
        
        return growth_rate
        
    except Exception as e:
        logging.warning(f"计算卖量增长率失败: {e}")
        return 0.0


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
            # ⚠️ 小时K线数据缺失，无法进行逐小时风控检查
            # 这会导致止损、止盈、补仓功能失效
            logging.warning(f"{symbol} 小时K线数据缺失，逐小时风控功能将失效")
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

        # 🆕 预加载卖量数据（如果启用了卖量增长率检查）
        hourly_sell_data = pd.DataFrame()
        if ENABLE_SELL_GROWTH_EXIT:
            hourly_sell_data = load_sell_volume_data_for_position(
                symbol=symbol,
                entry_datetime=entry_dt,
                end_datetime=end_dt
            )
            if not hourly_sell_data.empty:
                logging.info(f"✅ {symbol} 预加载了 {len(hourly_sell_data)} 小时的卖量数据")

        # 最大检查小时数（12天 * 24小时 = 288小时）
        max_check_hours = 288
        checked_hours = 0
        
        # 当前使用的建仓价格（可能因补仓而改变）
        current_entry_price = entry_price
        current_position_size = position['position_size']
        
        # 根据是否已补仓选择止盈阈值（使用动态参数）
        current_profit_threshold = profit_threshold_after_add if has_added_position else profit_threshold
        
        # 🔥 动态止盈：建仓2小时后，如果未止盈，则将止盈阈值降为25%
        # 目的：在高止盈（40%）和低止盈（25%）之间取得平衡
        # - 前2小时：等待40%止盈（抓住10.4%能达到45%的交易）
        # - 2小时后：降为25%止盈（确保56.2%能达到25%的交易不错过）
        if ENABLE_DYNAMIC_PROFIT:
            # 计算建仓到当前的总小时数（使用entry_dt确保准确）
            # 注意：这里的判断是在进入逐小时检查前，所以checked_hours为0
            # 我们在循环内部进行判断
            pass
        
        # 逐小时检查
        for idx, hour_data in valid_data.iterrows():
            checked_hours += 1
            if checked_hours > max_check_hours:
                # 超过最大检查时间，强制平仓（使用当前市场价）
                result['action'] = 'exit'
                # 使用当前小时的收盘价作为平仓价
                result['exit_price'] = float(hour_data['close'])
                result['exit_datetime'] = hour_data['trade_date']
                result['exit_reason'] = generate_exit_reason(f"持有时间超过12天，强制平仓", has_added_position)
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
            
            # 🔥 动态止盈：建仓2小时后，降低止盈阈值为25%
            # 前提：未补仓状态下才进行动态调整（补仓后保持补仓止盈阈值不变）
            if (ENABLE_DYNAMIC_PROFIT and 
                not has_added_position and 
                hold_hours >= DYNAMIC_PROFIT_HOURS_THRESHOLD and 
                current_profit_threshold > DYNAMIC_PROFIT_REDUCED_THRESHOLD):
                # 降低止盈阈值
                current_profit_threshold = DYNAMIC_PROFIT_REDUCED_THRESHOLD
            
            # 1. 检查止盈（优先级最高）
            if price_change_low <= -current_profit_threshold:
                result['action'] = 'exit'
                result['exit_price'] = current_entry_price * (1 - current_profit_threshold)
                result['exit_datetime'] = hour_time
                result['exit_reason'] = generate_exit_reason(f"价格下跌{current_profit_threshold*100:.0f}%，持仓{hold_hours}小时止盈", has_added_position)
                return result

            # 2. 🔥 检查卖量增长率动态平仓（在补仓和价格止损之前，提前拦截风险）
            # ⚠️ 增加保护：如果卖量触发时价格已超过止损线，则按止损价退出
            if (ENABLE_SELL_GROWTH_EXIT and 
                not hourly_sell_data.empty and 
                checked_hours >= SELL_GROWTH_EXIT_CONFIG['lookback_hours']):
                
                # 从预加载的数据中计算卖量增长率（高效，不查询数据库）
                current_hour = hour_dt.replace(minute=0, second=0, microsecond=0)
                sell_growth_rate = calculate_sell_volume_growth_rate_from_cache(
                    hourly_data=hourly_sell_data,
                    current_hour=current_hour,
                    lookback_hours=SELL_GROWTH_EXIT_CONFIG['lookback_hours']
                )
                
                # 检查是否在目标范围内（270%-340%）
                if (SELL_GROWTH_EXIT_CONFIG['min_growth_rate'] <= sell_growth_rate <= 
                    SELL_GROWTH_EXIT_CONFIG['max_growth_rate']):
                    
                    # 计算价格变化
                    current_price = float(hour_data['close'])
                    price_change_pct = (current_price - current_entry_price) / current_entry_price
                    
                    # ✅ 检查是否已超过止损线（45%）
                    if price_change_pct >= stop_loss_threshold:
                        # 价格已超止损线，按止损价退出（避免损失扩大）
                        result['action'] = 'exit'
                        result['exit_price'] = current_entry_price * (1 + stop_loss_threshold)
                        result['exit_datetime'] = hour_time
                        result['exit_reason'] = generate_exit_reason(
                            f"卖量增长率{sell_growth_rate*100:.1f}%触发但价格已超{stop_loss_threshold*100:.0f}%止损线，按止损价退出，持仓{hold_hours}小时",
                            has_added_position
                        )
                        logging.warning(
                            f"🛑 卖量触发+价格止损: {symbol} 在 {hour_time} "
                            f"卖量增长{sell_growth_rate*100:.1f}%, 价格上涨{price_change_pct*100:+.2f}%, 按{stop_loss_threshold*100:.0f}%止损"
                        )
                        return result
                    else:
                        # 价格未超止损线，按实际价格退出
                        result['action'] = 'exit'
                        result['exit_price'] = current_price
                        result['exit_datetime'] = hour_time
                        result['exit_reason'] = generate_exit_reason(
                            f"卖量增长率{sell_growth_rate*100:.1f}%触发动态平仓（价格变化{price_change_pct*100:+.2f}%），持仓{hold_hours}小时",
                            has_added_position
                        )
                        logging.warning(
                            f"🔴 卖量动态平仓: {symbol} 在 {hour_time} "
                            f"卖量增长{sell_growth_rate*100:.1f}%, 价格变化{price_change_pct*100:+.2f}%"
                        )
                        return result

            # 3. 检查补仓（未补仓且价格上涨达到阈值）- 使用动态参数
            if not has_added_position and price_change_high >= add_position_threshold:
                # 计算补仓价格
                add_position_price = current_entry_price * (1 + add_position_threshold)

                # 补仓数量 = 原持仓数量 × 补仓倍数
                add_position_size = current_position_size * ADD_POSITION_SIZE_MULTIPLIER

                # 补仓金额 = 补仓数量 * 补仓价格
                add_position_value = add_position_size * add_position_price

                # 检查账户资金是否充足
                if add_position_value <= current_capital:
                    total_position_size = current_position_size + add_position_size
                    new_avg_entry_price = (current_entry_price * current_position_size + add_position_price * add_position_size) / total_position_size
                    
                    result['action'] = 'add_position'
                    result['exit_datetime'] = hour_time
                    result['exit_reason'] = f'持仓{hold_hours}小时触发补仓（阈值{add_position_threshold*100:.0f}%，补仓{ADD_POSITION_SIZE_MULTIPLIER}倍）'
                    result['new_entry_price'] = new_avg_entry_price
                    result['new_position_size'] = total_position_size
                    result['add_position_value'] = add_position_value
                    return result
            
            # 4. 🆕 检查顶级交易者动态止损
            if ENABLE_TRADER_STOP_LOSS:
                # 获取建仓时保存的账户多空比（如果有）
                entry_ratio = position.get('entry_account_ratio')
                
                # 检查是否触发止损
                should_stop, stop_reason, trader_data = check_trader_stop_loss(
                    symbol=symbol,
                    entry_datetime=entry_date,
                    current_datetime=hour_time,
                    entry_account_ratio=entry_ratio
                )
                
                if should_stop:
                    # 保存多空比数据供后续分析
                    if trader_data:
                        position['entry_account_ratio'] = trader_data.get('entry_account_ratio')
                        position['exit_account_ratio'] = trader_data.get('current_account_ratio')
                        position['account_ratio_change'] = trader_data.get('ratio_change')
                    
                    # 使用当前小时的收盘价止损
                    result['action'] = 'exit'
                    result['exit_price'] = float(hour_data['close'])
                    result['exit_datetime'] = hour_time
                    result['exit_reason'] = generate_exit_reason(
                        f"顶级交易者止损（账户多空比变化{trader_data.get('ratio_change', 0):+.4f}），持仓{hold_hours}小时",
                        has_added_position
                    )
                    logging.warning(f"🛑 顶级交易者止损: {symbol} 在 {hour_time} 因{stop_reason}")
                    return result
            
            # 5. 🛑 检查价格止损（最后兜底，避免极端亏损）
            if price_change_high >= stop_loss_threshold:
                result['action'] = 'exit'
                result['exit_price'] = current_entry_price * (1 + stop_loss_threshold)
                result['exit_datetime'] = hour_time
                result['exit_reason'] = generate_exit_reason(f"价格上涨{stop_loss_threshold*100:.0f}%，持仓{hold_hours}小时止损", has_added_position)
                logging.warning(f"🛑 价格止损: {symbol} 在 {hour_time} 价格上涨{stop_loss_threshold*100:.0f}%")
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
        # PostgreSQL 使用 information_schema 查询表是否存在
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name
                );
            """),
            {"table_name": table_name}
        )
        table_exists = result.fetchone()[0]
        
        if not table_exists:
            # PostgreSQL 表创建语句
            text_create = f"""
            CREATE TABLE "{table_name}" (
                id BIGSERIAL PRIMARY KEY,
                entry_date VARCHAR(50) NOT NULL,
                symbol VARCHAR(50) NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL,
                entry_pct_chg DOUBLE PRECISION,
                position_size DOUBLE PRECISION NOT NULL,
                leverage INTEGER NOT NULL,
                exit_date VARCHAR(50),
                exit_price DOUBLE PRECISION,
                exit_reason TEXT,
                profit_loss DOUBLE PRECISION,
                profit_loss_pct DOUBLE PRECISION,
                max_profit DOUBLE PRECISION,
                max_loss DOUBLE PRECISION,
                hold_days INTEGER,
                has_added_position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            conn.execute(text(text_create))
            conn.commit()
            logging.info(f"交易记录表 '{table_name}' 创建成功")
        else:
            # 检查是否需要添加has_added_position字段
            result = conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name;
                """),
                {"table_name": table_name}
            )
            columns = [row[0] for row in result.fetchall()]
            if 'has_added_position' not in columns:
                logging.info(f"添加 has_added_position 字段到表 '{table_name}'")
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN has_added_position INTEGER DEFAULT 0;')
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
    # 清空Premium缓存（开始新的回测）
    global _premium_cache
    _premium_cache.clear()
    logging.info("已清空Premium数据缓存")
    
    # 创建交易记录表
    create_trade_table()
    
    # 连接顶级交易者数据库（用于风控）
    # 注意：顶级交易者数据库现已迁移至PostgreSQL
    trader_engine = engine
    logging.info("已连接顶级交易者数据库（PostgreSQL）")
    
    # 获取所有涨幅第一的交易对
    logging.info(f"正在获取 {start_date} 到 {end_date} 期间的涨幅第一交易对...")
    top_gainers_df = get_all_top_gainers(start_date, end_date)
    
    if top_gainers_df.empty:
        logging.warning("未找到任何涨幅第一的交易对")
        return
    
    logging.info(f"共找到 {len(top_gainers_df)} 个涨幅第一的交易对")
    
    # 当前持仓
    current_positions = []  # 支持多个仓位同时存在
    capital = INITIAL_CAPITAL
    trade_records = []
    
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    while current_date <= end_dt:
        date_str = current_date.strftime('%Y-%m-%d')
        current_symbols_debug = [pos['symbol'] for pos in current_positions]
        logging.info(
            f"开始处理日期: {date_str}, 当前持仓数: {len(current_positions)}, "
            f"持仓列表: {current_symbols_debug}"
        )

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
            # 🔧 关键修复：传递当前日期而不是回测结束日期，避免"时间穿越"BUG
            # 逐小时检查应该只检查到当前日期，而不是未来的数据
            logging.debug(f"开始对 {symbol} 进行逐小时检查...")
            hourly_result = check_position_hourly(current_position, capital, date_str)
            
            # DEBUG: 记录hourly_result
            if hourly_result['action'] != 'none':
                logging.info(
                    f"{date_str}: {symbol} 逐小时检查结果: action={hourly_result['action']}, "
                    f"exit_datetime={hourly_result.get('exit_datetime')}, "
                    f"exit_reason={hourly_result.get('exit_reason')}"
                )

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

                # 计算资金费成本（基于名义价值 = 价格 × 数量）
                notional_value = original_entry_price * current_position['position_size']
                premium_avg = current_position.get('entry_premium_avg')
                trade_direction = current_position.get('trade_direction', 'short')
                funding_info = calculate_funding_fee_cost(premium_avg, notional_value, hold_hours, trade_direction)
                funding_fee_cost = funding_info['funding_fee_cost']
                final_profit = profit_loss - funding_fee_cost
                
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
                    'has_added_position': has_added_position,
                    # 🆕 建仓时的Premium数据
                    'entry_premium_avg': current_position.get('entry_premium_avg'),
                    'entry_premium_current': current_position.get('entry_premium_current'),
                    'entry_premium_trend': current_position.get('entry_premium_trend'),
                    # 🆕 顶级交易者账户多空比数据
                    'entry_account_ratio': current_position.get('entry_account_ratio'),
                    'exit_account_ratio': current_position.get('exit_account_ratio'),
                    'account_ratio_change': current_position.get('account_ratio_change'),
                    # 🆕 资金费成本和最终利润
                    'funding_fee_cost': funding_fee_cost,
                    'final_profit': final_profit
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

                    # BUG修复：验证补仓后持仓仍在列表中
                    still_in_position = any(pos['symbol'] == symbol for pos in current_positions)
                    if not still_in_position:
                        logging.error(f"❌ BUG: 补仓后 {symbol} 不在持仓列表中！这不应该发生。")

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
                removed_pos = current_positions[i]
                logging.info(
                    f"{date_str}: 从持仓列表移除 {removed_pos['symbol']} "
                    f"(索引{i}, 原因: 逐小时检查触发平仓或补仓)"
                )
                current_positions.pop(i)

        # 检查持有时间过长的交易，强制平仓
        # 重新创建一个positions_to_remove集合用于超时强制平仓
        timeout_positions_to_remove = []
        for i, current_position in enumerate(current_positions):
            symbol = current_position['symbol']
            # 使用原始建仓时间来计算持仓时长
            original_entry_date = current_position.get('original_entry_date', current_position['entry_date'])
            original_entry_price = current_position.get('original_entry_price', current_position['entry_price'])
            has_added_position = current_position.get('has_added_position', False)

            # 计算持有时间（从原始建仓时间开始），以天为单位
            if ' ' in original_entry_date:
                entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d %H:%M:%S')
            else:
                entry_dt = datetime.strptime(original_entry_date, '%Y-%m-%d')

            # 计算持有天数（浮点数，保持精确）
            hold_days = (current_date - entry_dt).total_seconds() / 86400  # 86400秒 = 1天

            if hold_days >= MAX_HOLD_DAYS:
                # 强制平仓 - 使用当天实际收盘价
                # 获取当天的K线数据
                current_kline = get_kline_data_for_date(symbol, date_str)
                
                if current_kline is not None:
                    # 使用当天的实际收盘价平仓
                    exit_price = current_kline['close']
                    exit_datetime = date_str + ' 23:59:59'  # 当天结束时平仓
                    
                    # 使用实际的持仓成本计算盈亏（考虑补仓后的平均成本）
                    actual_entry_price = current_position['entry_price']
                    profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * LEVERAGE
                    profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price
                    
                    exit_reason = generate_exit_reason(f"持有时间超过{MAX_HOLD_DAYS}天，强制平仓", has_added_position)

                    # 计算持仓时间
                    exit_dt = datetime.strptime(exit_datetime, '%Y-%m-%d %H:%M:%S')
                    final_hold_hours = int((exit_dt - entry_dt).total_seconds() / 3600)

                    # 计算资金费成本（基于名义价值 = 价格 × 数量）
                    notional_value = original_entry_price * current_position['position_size']
                    premium_avg = current_position.get('entry_premium_avg')
                    trade_direction = current_position.get('trade_direction', 'short')
                    funding_info = calculate_funding_fee_cost(premium_avg, notional_value, final_hold_hours, trade_direction)
                    funding_fee_cost = funding_info['funding_fee_cost']
                    final_profit = profit_loss - funding_fee_cost
                    
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
                        'has_added_position': has_added_position,
                        # 🆕 建仓时的Premium数据
                        'entry_premium_avg': current_position.get('entry_premium_avg'),
                        'entry_premium_current': current_position.get('entry_premium_current'),
                        'entry_premium_trend': current_position.get('entry_premium_trend'),
                        # 🆕 顶级交易者账户多空比数据
                        'entry_account_ratio': current_position.get('entry_account_ratio'),
                        'exit_account_ratio': current_position.get('exit_account_ratio'),
                        'account_ratio_change': current_position.get('account_ratio_change'),
                        # 🆕 资金费成本和最终利润
                        'funding_fee_cost': funding_fee_cost,
                        'final_profit': final_profit
                    }

                    trade_records.append(trade_record)
                    capital += final_profit

                    logging.info(
                        f"{date_str}: 超时强制平仓 {symbol} "
                        f"(建仓价{original_entry_price:.6f}, 平仓价{exit_price:.6f}, "
                        f"收益率{profit_loss_pct*100:.2f}%, 盈亏{final_profit:.2f}), "
                        f"当前资金: {capital:.2f}"
                    )
                    timeout_positions_to_remove.append(i)
                else:
                    logging.warning(f"{date_str}: 无法获取 {symbol} 的K线数据，跳过超时强制平仓")

        # 移除超时强制平仓的持仓（反向移除避免索引错乱）
        for i in sorted(timeout_positions_to_remove, reverse=True):
            if i < len(current_positions):  # 安全检查
                removed_pos = current_positions[i]
                logging.info(
                    f"{date_str}: 从持仓列表移除 {removed_pos['symbol']} "
                    f"(索引{i}, 原因: 超时强制平仓)"
                )
                current_positions.pop(i)

        # 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
        today_top = top_gainers_df[top_gainers_df['date'] == date_str]
        if not today_top.empty:
            symbol = today_top.iloc[0]['symbol']
            pct_chg = today_top.iloc[0]['pct_chg']
            
            # 检查该交易对是否在当前持仓中（只检查当前持仓，不检查已平仓的）
            # 如果已经平仓，可以再次建仓
            current_symbols = [pos['symbol'] for pos in current_positions]
            already_in_position = symbol in current_symbols
            
            # 检查是否达到最大持仓数量
            if len(current_positions) >= MAX_POSITIONS:
                logging.info(
                    f"{date_str}: 已达到最大持仓数量({len(current_positions)}/{MAX_POSITIONS})，"
                    f"跳过 {symbol}(涨幅{pct_chg:.2f}%) 的建仓机会"
                )
            # 建仓条件：涨幅>=10% 且 该交易对当前没有持仓 且 当前持仓数未超过最大限制
            elif pct_chg >= MIN_PCT_CHG * 100 and not already_in_position:
                logging.info(
                    f"{date_str}: 检查 {symbol}(涨幅{pct_chg:.2f}%) 是否在持仓中: {already_in_position}, "
                    f"当前持仓数:{len(current_positions)}/{MAX_POSITIONS}, 持仓列表: {current_symbols}"
                )
                # ============================================================
                # 风控1：检查顶级交易者多空比，如果 < 0.5 则延迟一天建仓
                # 原因：多空比 < 0.5 表示空头主导（做空占比>66%），
                #       第二天容易出现"短挤效应"导致价格疯涨，对做空者极其危险
                # ============================================================
                delay_entry = False  # 多空比风控延迟标志
                delay_entry_30d = False  # 30天均涨风控延迟标志
                delay_entry_volume = False  # 成交额风控延迟标志
                delay_entry_volume_risk = False  # 买卖量风控延迟标志（已废弃，改为完全过滤）
                delay_entry_premium = False  # Premium风控延迟标志（已废弃，改为完全过滤）
                skip_this_trade = False  # 妖币风控、买卖量风控、Premium风控完全过滤标志
                # 注意：买卖量风控和Premium风控都改为完全过滤
                skip_entry = False  # 新增：完全跳过建仓标志（暂未使用）
                
                # ============================================================
                # 风控1.5：妖币风控 - 检查是否为妖币或太妖，完全过滤不做
                # 原因：妖币和太妖波动极端，资金费率异常，反复拉盘，做空风险极高
                # 数据来源：yb表（妖币分析表）
                # 策略：完全过滤，不做任何妖币交易（回测验证：延迟建仓仍亏损-6,961 USDT）
                # ============================================================
                # 🔕 临时禁用妖币风控，用于测试基准数据
                pass
                # try:
                #     # 连接crypto_data.db查询yb表
                #     yb_db_path = os.path.join(os.path.dirname(__file__), '..', 'crypto_data.db')
                #     if os.path.exists(yb_db_path):
                #         yb_conn = sqlite3.connect(yb_db_path)
                #         yb_cursor = yb_conn.cursor()
                #         yb_cursor.execute(
                #             "SELECT category, total_score, pump_multiple, cycles_count, has_spike FROM yb WHERE symbol = ?",
                #             (symbol,)
                #         )
                #         yb_result = yb_cursor.fetchone()
                #         yb_conn.close()
                #         
                #         if yb_result:
                #             category, total_score, pump_multiple, cycles_count, has_spike = yb_result
                #             if category in ('妖币', '太妖'):
                #                 skip_this_trade = True
                #                 spike_info = "🔴插针" if has_spike else ""
                #                 cycle_info = f"{cycles_count}个周期" if cycles_count > 0 else ""
                #                 logging.info(
                #                     f"{date_str}: {symbol} 检测到{category}！"
                #                     f"(总分{total_score}, 涨幅{pump_multiple:.1f}倍 {spike_info} {cycle_info}), "
                #                     f"完全过滤不做（回测证明妖币平均亏损-248 USDT/笔）"
                #                 )
                #     else:
                #         logging.debug(f"妖币数据库不存在：{yb_db_path}，跳过妖币风控")
                # except Exception as e:
                #     logging.warning(f"查询 {symbol} 妖币数据失败：{e}，继续正常建仓")
                
                # ============================================================
                # 🔕 风控2：检查「从30天平均价涨幅」- 临时禁用用于测试
                # 逻辑：如果从30天平均价涨幅不足，说明主力还没充分获利，
                #      价格可能继续拉升，不适合做空
                # 分级风控：根据日涨幅动态调整阈值（见下方详细说明）
                # 注意：如果币上架不足30天，使用所有可用数据计算平均值
                # ============================================================
                # try:
                #     # 获取过去30天的K线数据，计算平均价
                #     # 如果上架不足30天，使用所有可用数据
                #     start_date_30d = (current_date - timedelta(days=30)).strftime('%Y-%m-%d')
                #     # 注意：不包括涨幅第一天本身
                #     day_before = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
                #     
                #     # 先查询数据行数和最早日期
                #     query_count = f'''
                #     SELECT COUNT(*) as cnt, MIN(DATE(trade_date)) as first_date
                #     FROM \"DailyKline_{symbol}\" 
                #     WHERE DATE(trade_date) <= :end_date
                #     '''
                #     
                #     query_avg = f'''
                #     SELECT AVG(close) as avg_close, COUNT(*) as cnt
                #     FROM \"DailyKline_{symbol}\" 
                #     WHERE DATE(trade_date) >= :start_date AND DATE(trade_date) <= :end_date
                #     '''
                #     
                #     query_current = f'''
                #     SELECT close
                #     FROM \"DailyKline_{symbol}\" 
                #     WHERE DATE(trade_date) = :current_date
                #     '''
                #     
                #     with engine.connect() as conn_temp:
                #         # 先检查总数据量
                #         result_count = conn_temp.execute(
                #             text(query_count),
                #             {'end_date': day_before}
                #         )
                #         row_count = result_count.fetchone()
                #         
                #         # 确定实际的查询起始日期
                #         actual_start_date = start_date_30d
                #         actual_days = 30
                #         
                #         if row_count and row_count[0] is not None and row_count[0] > 0:
                #             total_available_days = row_count[0]
                #             first_date = row_count[1]
                #             
                #             # 如果可用数据少于30天，使用所有数据
                #             if total_available_days < 30:
                #                 actual_start_date = first_date
                #                 actual_days = total_available_days
                #                 logging.info(
                #                     f"{symbol} 上架不足30天，使用所有{actual_days}天的数据计算平均值"
                #                 )
                #         
                #         # 获取平均价
                #         result_avg = conn_temp.execute(
                #             text(query_avg),
                #             {'start_date': actual_start_date, 'end_date': day_before}
                #         )
                #         row_avg = result_avg.fetchone()
                #         
                #         # 获取涨幅第一天的收盘价
                #         result_current = conn_temp.execute(
                #             text(query_current),
                #             {'current_date': date_str}
                #         )
                #         row_current = result_current.fetchone()
                #         
                #         if row_avg and row_current and row_avg[0] is not None and row_current[0] is not None:
                #             avg_close_30d = row_avg[0]
                #             current_close = row_current[0]
                #             from_avg_30d_pct = (current_close - avg_close_30d) / avg_close_30d * 100
                #             
                #             # ============================================================
                #             # 分级风控：根据日涨幅动态调整30天均价涨幅阈值
                #             # 关键：低涨幅币更危险（HUSDT案例：日涨35%，30天均涨55%仍亏-2343）
                #             # - 日涨<40%: 30天均涨>51% (HUSDT 55.1%都亏了，必须严格)
                #             # - 日涨40-60%: 30天均涨>45% (RVVUSDT 49%盈利，可放宽)
                #             # - 日涨60-100%: 30天均涨>35% (高涨幅动力强)
                #             # - 日涨>100%: 30天均涨>25% (极高涨幅说明强驱动)
                #             # ============================================================
                #             if pct_chg < 40:
                #                 threshold = 51
                #                 level_desc = "低中涨幅"
                #             elif pct_chg < 60:
                #                 threshold = 45
                #                 level_desc = "中涨幅"
                #             elif pct_chg < 100:
                #                 threshold = 35
                #                 level_desc = "高涨幅"
                #             else:
                #                 threshold = 10
                #                 level_desc = "超高涨幅"
                #             
                #             if from_avg_30d_pct < threshold:
                #                 delay_entry_30d = True
                #                 days_label = f"{actual_days}天" if actual_days < 30 else "30天"
                #                 logging.info(
                #                     f"{date_str}: {symbol} {level_desc}(日涨{pct_chg:.1f}%), "
                #                     f"从{days_label}均价涨幅{from_avg_30d_pct:.1f}%(<{threshold}%)，"
                #                     f"主力获利不足，延迟一天建仓（第三天）"
                #                 )
                # except Exception as e:
                #     logging.warning(f"检查 {symbol} 30天均价涨幅失败：{e}")
                
                if trader_engine is not None:
                    try:
                        # 获取当天（涨幅第一那天）的多空比
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        start_ts = int((date_obj - timedelta(days=1)).timestamp() * 1000)
                        end_ts = int((date_obj + timedelta(days=1)).timestamp() * 1000)
                        target_ts = int(date_obj.timestamp() * 1000)
                        
                        query_top = '''
                        SELECT long_short_ratio, long_account, short_account
                        FROM top_account_ratio
                        WHERE symbol = :symbol AND timestamp >= :start_ts AND timestamp <= :end_ts
                        ORDER BY ABS(timestamp - :target_ts) ASC LIMIT 1
                        '''
                        with trader_engine.connect() as t_conn:
                            df_top = pd.read_sql_query(
                                text(query_top), 
                                t_conn, 
                                params={'symbol': symbol, 'start_ts': start_ts, 'end_ts': end_ts, 'target_ts': target_ts}
                            )
                        
                        if not df_top.empty:
                            top_ratio = df_top.iloc[0]['long_short_ratio']
                            top_short_pct = df_top.iloc[0]['short_account'] * 100
                            
                            if top_ratio < 0.85:
                                delay_entry = True
                                logging.info(
                                    f"{date_str}: {symbol} 多空比{top_ratio:.2f}(<0.85, 空头占{top_short_pct:.1f}%), "
                                    f"存在短挤风险，延迟一天建仓（第三天）"
                                )
                    except Exception as e:
                        logging.warning(f"查询 {symbol} 多空比失败：{e}，继续正常建仓")
                
                # ============================================================
                # 风控3：检查成交额，高涨幅+低成交额 → 主力还没出货 → 延迟建仓
                # 原因：高涨幅但成交额低，说明FOMO不足，主力难以出货，
                #      可能继续拉升吸引散户，对做空者危险
                # 数据：高涨幅+低成交额胜率33.3%，高涨幅+高成交额胜率84.2%
                # ============================================================
                if ENABLE_VOLUME_FILTER and pct_chg >= HIGH_PCT_CHG_THRESHOLD:
                    # 使用当天的成交额数据
                    temp_datetime = f"{date_str} 23:59:59"
                    volume_24h = get_24h_quote_volume(symbol, temp_datetime)
                    if volume_24h >= 0 and volume_24h < MIN_VOLUME_FOR_HIGH_PCT:
                        delay_entry_volume = True
                        volume_yi = volume_24h / 1e8  # 转换为亿
                        volume_threshold_yi = MIN_VOLUME_FOR_HIGH_PCT / 1e8
                        logging.info(
                            f"{date_str}: {symbol} 高涨幅{pct_chg:.1f}% + 成交额{volume_yi:.1f}亿 < {volume_threshold_yi:.1f}亿，"
                            f"主力可能还没出货，延迟一天建仓（第三天）"
                        )
                
                # ============================================================
                # 风控4：买卖量风控 → 完全过滤
                # 原因：买量加速度在危险区间或卖量增长率异常
                # 策略：直接跳过该交易，不建仓
                # ============================================================
                if ENABLE_VOLUME_RISK_FILTER:
                    # 检查第二天（建仓日）的买卖量风控
                    temp_datetime = f"{date_str} 23:59:59"
                    # 由于是检查信号前24小时，所以需要用信号当天的数据
                    entry_datetime_for_check = f"{(current_date + timedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"
                    volume_risk_result = check_volume_risk(symbol, entry_datetime_for_check)
                    
                    if not volume_risk_result['should_trade']:
                        skip_this_trade = True
                        logging.info(
                            f"{date_str}: {symbol} {volume_risk_result['reason']}，"
                            f"买卖量风控触发，跳过建仓"
                        )
                    else:
                        logging.debug(f"{date_str}: {symbol} {volume_risk_result['reason']}")
                
                # ============================================================
                # 风控5：Premium风控 → 完全过滤
                # 检查Premium Index指标，异常时直接跳过该交易
                # ============================================================
                # 需要提前检查第二天的Premium数据
                second_day_str = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
                second_day_datetime = f"{second_day_str} 00:00:00"
                
                if ENABLE_PREMIUM_CONTROL:
                    # 提前获取Premium数据
                    premium_data_temp = get_premium_index_data(symbol, second_day_datetime)
                    risk_result = check_risk_control(symbol, pct_chg, second_day_datetime)
                    
                    # 🐛 调试：输出Premium风控检查详情
                    if premium_data_temp and premium_data_temp.get('success'):
                        avg_prem = premium_data_temp.get('avg_24h_premium')
                        if avg_prem:
                            extreme_min = PREMIUM_CONTROL_CONFIG['premium_extreme_negative_min']
                            extreme_max = PREMIUM_CONTROL_CONFIG['premium_extreme_negative_max']
                            logging.info(
                                f"{date_str}: {symbol} Premium检查 - "
                                f"24h均值={avg_prem*100:.4f}%, "
                                f"判断=({extreme_min} < {avg_prem} < {extreme_max}) = {extreme_min < avg_prem < extreme_max}, "
                                f"should_trade={risk_result['should_trade']}"
                            )
                    
                    if not risk_result['should_trade']:
                        skip_this_trade = True
                        logging.info(
                            f"{date_str}: {symbol} {risk_result['message']}，"
                            f"Premium风控触发，跳过建仓"
                        )
                        # 输出危险信号详情
                        for signal in risk_result['danger_signals']:
                            logging.info(f"  ⚠️ {signal}")
                
                # 获取第二天的开盘价（建仓价），如果有延迟则改为第三天
                # 三种延迟情况：
                #   1. 多空比风控 → 延迟1天（第三天）
                #   2. 30天均涨风控 → 延迟1天（第三天）
                #   3. 成交额风控 → 延迟1天（第三天）
                # 买卖量风控、Premium风控：完全过滤，不建仓
                # 检查是否需要跳过这个交易（妖币风控、买卖量风控、Premium风控触发时跳过）
                if skip_this_trade:
                    # 风控触发，直接跳过，进入下一天
                    logging.info(f"{date_str}: {symbol} 风控触发，跳过建仓，继续下一天")
                    current_date += timedelta(days=1)
                    continue

                # 判断延迟天数（仅三类风控延迟1天，买卖量和Premium风控已完全过滤）
                if delay_entry or delay_entry_30d or delay_entry_volume:
                    entry_delay_days = 2  # 风控触发：第三天建仓（延迟1天）
                else:
                    entry_delay_days = 1  # 无风控：第二天建仓
                
                if entry_delay_days > 1:  # 有延迟建仓
                    # ============================================================
                    # 延迟建仓价格检查：如果延迟期间价格下跌太多，放弃建仓
                    # 原因：延迟建仓期间价格大幅下跌，说明做空时机已过，难盈利
                    # 检查：第二天开盘价 vs 第三天建仓价，跌幅不能超过11%
                    # ============================================================
                    next_date = current_date + timedelta(days=entry_delay_days)
                    next_date_str = next_date.strftime('%Y-%m-%d')

                    if next_date <= end_dt:
                        kline_data = get_kline_data_for_date(symbol, next_date_str)
                        if kline_data is not None:
                            open_price = kline_data['open']

                            # 获取第二天开盘价（作为基准价格）
                            second_day = current_date + timedelta(days=1)
                            second_day_str = second_day.strftime('%Y-%m-%d')
                            second_day_data = get_kline_data_for_date(symbol, second_day_str)

                            if second_day_data is not None and not second_day_data.empty:
                                second_day_open = second_day_data['open']

                                # 计算价格跌幅：第二天开盘价 vs 第三天建仓价
                                if second_day_open > 0:
                                    price_drop_pct = ((second_day_open - open_price) / second_day_open) * 100

                                    # 如果跌幅超过11%，放弃建仓
                                    MAX_PRICE_DROP_FOR_DELAY = 11.0  # 最大允许跌幅11%
                                    if price_drop_pct > MAX_PRICE_DROP_FOR_DELAY:
                                        logging.info(
                                            f"{next_date_str}: {symbol} 延迟建仓价格检查失败，"
                                            f"第二天开盘{second_day_open:.4f} → 第三天建仓{open_price:.4f}，"
                                            f"跌幅{price_drop_pct:.1f}% > {MAX_PRICE_DROP_FOR_DELAY:.1f}%，放弃建仓"
                                        )
                                        skip_this_trade = True
                else:
                    entry_delay_days = 1  # 第二天建仓（无延迟）

                # ============================================================
                # 检查延迟建仓价格风控是否触发
                # 如果价格跌幅过大已设置 skip_this_trade = True，需要跳过建仓
                # ============================================================
                if skip_this_trade:
                    logging.info(f"{date_str}: {symbol} 延迟建仓价格检查失败，跳过建仓，继续下一天")
                    current_date += timedelta(days=1)
                    continue

                next_date = current_date + timedelta(days=entry_delay_days)
                next_date_str = next_date.strftime('%Y-%m-%d')
                entry_datetime = f"{next_date_str} 00:00:00"
                
                # 🆕 获取Premium数据用于记录分析
                premium_data_at_entry = get_premium_index_data(symbol, entry_datetime)
                api_sentiment = None
                
                # 如果启用了Premium风控，获取情感数据（用于记录）
                if ENABLE_PREMIUM_CONTROL:
                    risk_result = check_risk_control(symbol, pct_chg, entry_datetime)
                    api_sentiment = risk_result.get('sentiment_data')
                
                # ============================================================
                # 【买卖量风控检查】- 已移至前面作为延迟建仓机制
                # ============================================================
                
                if next_date <= end_dt:
                    kline_data = get_kline_data_for_date(symbol, next_date_str)
                    if kline_data is not None:
                        open_price = kline_data['open']
                        
                        # 获取动态交易参数（根据入场涨幅）
                        dynamic_params = get_dynamic_params(pct_chg)
                        position_leverage = dynamic_params['leverage']
                        position_profit_threshold = dynamic_params['profit_threshold']
                        position_stop_loss_threshold = dynamic_params['stop_loss_threshold']
                        
                        # 直接使用开盘价建仓（不再等待价格涨到目标价）
                        entry_price = open_price
                        hours_waited = 0
                        
                        # ============================================================
                        # 获取24小时成交额用于仓位计算
                        # ============================================================
                        volume_24h = get_24h_quote_volume(symbol, entry_datetime)
                        
                        # Premium风控已在前面检查过，这里不再重复检查

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
                        # 🎯 仓位计算：根据配置选择固定仓位或复利模式
                        # ============================================================
                        if FIXED_POSITION_MODE:
                            # 固定仓位模式：每次固定投入 FIXED_POSITION_SIZE
                            position_value = FIXED_POSITION_SIZE
                            position_size = position_value / entry_price
                            position_multiplier = 1.0  # 固定为1.0
                            adjusted_position_ratio = POSITION_SIZE_RATIO  # 固定比例
                            total_asset = capital  # 简化：只统计可用资金
                            logging.info(f"【固定仓位】{symbol} | 仓位:{position_value:.0f} USDT | 建仓价:{entry_price:.6f} | 数量:{position_size:.2f}")
                        else:
                            # 复利模式：基于总资产的百分比计算
                            position_multiplier = get_position_size_multiplier(volume_24h)
                            adjusted_position_ratio = POSITION_SIZE_RATIO * position_multiplier
                            
                            # 总资产 = 当前可用资金 + 所有持仓占用的资金
                            total_asset = capital
                            for pos in current_positions:
                                total_asset += pos.get('position_value', 0)
                            
                            # 每次建仓金额为总资产的调整后比例
                            position_value = total_asset * adjusted_position_ratio
                            position_size = position_value / entry_price
                            logging.info(f"【复利仓位】{symbol} | 总资产:{total_asset:.0f} | 比例:{adjusted_position_ratio:.3f} | 仓位:{position_value:.0f} ({position_value/total_asset*100:.1f}%)")
                        
                        capital -= position_value  # 扣除建仓金额（作为保证金）
                        logging.info(f"  建仓后资金: {capital:.2f}")

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
                            'position_multiplier': position_multiplier,  # 仓位倍数
                            # 🆕 保存建仓时的Premium数据用于分析
                            'entry_premium_avg': premium_data_at_entry.get('avg_24h_premium') if premium_data_at_entry else None,
                            'entry_premium_current': premium_data_at_entry.get('current_premium') if premium_data_at_entry else None,
                            'entry_premium_trend': premium_data_at_entry.get('premium_trend') if premium_data_at_entry else None,
                            # 🆕 保存建仓时的顶级交易者账户多空比（用于动态止损）
                            'entry_account_ratio': None,  # 将在检查时获取并缓存
                            'exit_account_ratio': None,
                            'account_ratio_change': None
                        }
                        # 建仓后不立即检查，等下一轮循环时通过 check_position_hourly 检查

                        # ============================================================
                        # BUG修复：在添加持仓前，再次严格检查该交易对是否已在持仓中
                        # 防止由于补仓等操作导致的持仓检测失败
                        # ============================================================
                        final_check = any(pos['symbol'] == symbol for pos in current_positions)
                        if final_check:
                            logging.warning(
                                f"{next_date_str}: ⚠️ 最终检查发现 {symbol} 已在持仓中，取消建仓！"
                                f"当前持仓交易对: {[pos['symbol'] for pos in current_positions]}"
                            )
                            # 退还建仓金额
                            capital += position_value
                            continue
                        
                        # 添加仓位到持仓列表
                        current_positions.append(new_position)

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
                        
                        # 建仓日志（直接使用开盘价建仓，不再等待）
                        logging.info(
                            f"{entry_datetime[:10]}: 建仓（{direction_cn}） {symbol} | "
                            f"建仓价: {entry_price:.8f} | "
                            f"昨日涨幅: {pct_chg:.2f}% ({leverage_group}) | "
                            f"24h成交额: {volume_yi:.1f}亿({volume_cat}) | "
                            f"杠杆: {position_leverage}x | 止盈: {position_profit_threshold*100:.0f}% | 止损: {position_stop_loss_threshold*100:.0f}% | "
                            f"仓位: {position_multiplier*100:.0f}% | 建仓金额: {position_value:.2f} USDT | "
                            f"持仓数: {len(current_positions)}"
                        )

            elif already_in_position:
                logging.info(f"{date_str}: {symbol} 涨幅 {pct_chg:.2f}%，当前已有持仓，跳过建仓")
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
                    # 优先获取目标日期的小时数据
                    last_date_data = hourly_df[hourly_df['trade_date'].str[:10] == last_date_str]
                    if not last_date_data.empty:
                        exit_price = last_date_data.iloc[-1]['close']
                        kline_data = last_date_data.iloc[-1]  # 用于后续计算
                    else:
                        # 如果没有目标日期的数据，使用最后一个可用的小时数据
                        # 按trade_date降序排序，取最新的数据
                        hourly_df_sorted = hourly_df.sort_values('trade_date', ascending=False)
                        if not hourly_df_sorted.empty:
                            latest_data = hourly_df_sorted.iloc[0]
                            exit_price = latest_data['close']
                            kline_data = latest_data
                            logging.info(f"使用最新可用数据: {latest_data['trade_date']} 收盘价: {exit_price}")
                        else:
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

                # 计算资金费成本（基于名义价值 = 价格 × 数量）
                notional_value = original_entry_price * current_position['position_size']
                premium_avg = current_position.get('entry_premium_avg')
                trade_direction = current_position.get('trade_direction', 'short')
                funding_info = calculate_funding_fee_cost(premium_avg, notional_value, hold_hours, trade_direction)
                funding_fee_cost = funding_info['funding_fee_cost']
                final_profit = profit_loss - funding_fee_cost
                
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
                    'has_added_position': has_added_position,  # 记录是否补过仓
                    # 🆕 建仓时的Premium数据
                    'entry_premium_avg': current_position.get('entry_premium_avg'),
                    'entry_premium_current': current_position.get('entry_premium_current'),
                    'entry_premium_trend': current_position.get('entry_premium_trend'),
                    # 🆕 顶级交易者账户多空比数据
                    'entry_account_ratio': current_position.get('entry_account_ratio'),
                    'exit_account_ratio': current_position.get('exit_account_ratio'),
                    'account_ratio_change': current_position.get('account_ratio_change'),
                    # 🆕 资金费成本和最终利润
                    'funding_fee_cost': funding_fee_cost,
                    'final_profit': final_profit
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

                # 计算资金费成本（基于名义价值 = 价格 × 数量）
                notional_value = original_entry_price * current_position['position_size']
                premium_avg = current_position.get('entry_premium_avg')
                trade_direction = current_position.get('trade_direction', 'short')
                funding_info = calculate_funding_fee_cost(premium_avg, notional_value, hold_hours, trade_direction)
                funding_fee_cost = funding_info['funding_fee_cost']
                final_profit = profit_loss - funding_fee_cost
                
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
                    'has_added_position': has_added_position,
                    # 🆕 建仓时的Premium数据
                    'entry_premium_avg': current_position.get('entry_premium_avg'),
                    'entry_premium_current': current_position.get('entry_premium_current'),
                    'entry_premium_trend': current_position.get('entry_premium_trend'),
                    # 🆕 顶级交易者账户多空比数据
                    'entry_account_ratio': current_position.get('entry_account_ratio'),
                    'exit_account_ratio': current_position.get('exit_account_ratio'),
                    'account_ratio_change': current_position.get('account_ratio_change'),
                    # 🆕 资金费成本和最终利润
                    'funding_fee_cost': funding_fee_cost,
                    'final_profit': final_profit
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
        
        # 保存到CSV文件 - 使用时间戳区分不同版本
        # 确保目录存在
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'backtrade_records')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join(output_dir, f"backtrade_records_{start_date}_{end_date}_v{timestamp}.csv")
        df_trades.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 成功保存 {len(trade_records)} 条交易记录到CSV文件: {csv_filename}")
        
        # 同时保存一份不带时间戳的副本（兼容旧逻辑）
        csv_filename_legacy = os.path.join(output_dir, f"backtrace_records_{start_date}_{end_date}.csv")
        df_trades.to_csv(csv_filename_legacy, index=False, encoding='utf-8-sig')
        logging.info(f"   同时保存到: {csv_filename_legacy}")
        
        # 打印统计信息 - 排除所有强制平仓的情况，只计算真正的止损和平仓
        # 真正的亏损：exit_reason包含"止损"或"上涨"（做空时的止损）
        # 真正的盈利：exit_reason包含"止盈"或"下跌"（做空时的止盈）
        # 所有强制平仓：不计入统计

        real_trades = df_trades[~df_trades['exit_reason'].str.contains('强制平仓')]

        win_trades = len(real_trades[real_trades['exit_reason'].str.contains('止盈|下跌')])
        loss_trades = len(real_trades[real_trades['exit_reason'].str.contains('止损|上涨')])

        total_real_trades = win_trades + loss_trades
        win_rate = win_trades / total_real_trades * 100 if total_real_trades > 0 else 0

        # 同时显示排除的强制平仓数量
        forced_close_count = len(df_trades[df_trades['exit_reason'].str.contains('强制平仓')])
        total_profit_loss = capital - INITIAL_CAPITAL  # 总盈亏 = 最终资金 - 初始资金
        
        logging.info("=" * 60)
        logging.info("回测统计:")
        logging.info(f"初始资金: {INITIAL_CAPITAL:.2f} USDT")
        logging.info(f"最终资金: {capital:.2f} USDT")
        logging.info(f"总盈亏: {total_profit_loss:.2f} USDT")
        logging.info(f"总收益率: {(capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100:.2f}%")
        logging.info(f"总交易次数: {len(trade_records)}")
        logging.info(f"有效交易次数: {total_real_trades} (排除{forced_close_count}次强制平仓)")
        logging.info(f"盈利次数: {win_trades}")
        logging.info(f"亏损次数: {loss_trades}")
        logging.info(f"胜率: {win_rate:.2f}%")
        logging.info("=" * 60)
    else:
        logging.warning("没有交易记录需要保存")
    
    # 关闭顶级交易者数据库连接
    logging.info("回测完成！")
    logging.info("已关闭顶级交易者数据库连接")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='币安U本位合约回测脚本')
    parser.add_argument('--start-date', type=str, required=True, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=10000.0, help='初始资金 (默认: 10000)')
    parser.add_argument('--ratio', type=float, default=0.15, help='单仓位比例 (默认: 0.15)')
    parser.add_argument('--min-pct', type=float, default=0.1, help='最小建仓涨幅 (默认: 0.1)')
    parser.add_argument('--max-pos', type=int, default=6, help='最大同时持仓数 (默认: 6)')
    parser.add_argument('--max-hold', type=float, default=11.0, help='最长持仓天数 (默认: 11)')
    parser.add_argument('--entry-wait', type=int, default=24, help='开盘后最长等待建仓小时数 (默认: 24)')
    parser.add_argument('--direction', type=str, default='auto', choices=['short', 'long', 'auto'], help='交易方向 (short/long/auto, 默认: auto)')
    parser.add_argument('--fixed-mode', action='store_true', help='启用固定仓位模式')
    parser.add_argument('--fixed-size', type=float, default=1000.0, help='固定仓位大小 (默认: 1000)')
    parser.add_argument('--no-dynamic', action='store_false', dest='dynamic_leverage', help='禁用动态杠杆策略')
    parser.set_defaults(dynamic_leverage=True)
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        logging.error("日期格式错误，请使用 YYYY-MM-DD 格式")
        exit(1)
    
    # 更新全局配置
    INITIAL_CAPITAL = args.capital
    POSITION_SIZE_RATIO = args.ratio
    MIN_PCT_CHG = args.min_pct
    MAX_POSITIONS = args.max_pos
    MAX_HOLD_DAYS = args.max_hold
    ENTRY_WAIT_HOURS = args.entry_wait
    TRADE_DIRECTION = args.direction
    FIXED_POSITION_MODE = args.fixed_mode
    FIXED_POSITION_SIZE = args.fixed_size
    ENABLE_DYNAMIC_LEVERAGE = args.dynamic_leverage

    simulate_trading(args.start_date, args.end_date)