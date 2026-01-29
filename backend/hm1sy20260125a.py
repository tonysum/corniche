#!/usr/bin/env python3
"""
买量暴涨策略回测程序 - 小时线版本（优化版 + 顶级交易者风控）
基于小时主动买量暴涨信号的快进快出量化策略
新增：基于Binance顶级交易者持仓数据的智能风控系统

═══════════════════════════════════════════════════════════════════════════════
📊 核心策略逻辑（根据实际代码整理）
═══════════════════════════════════════════════════════════════════════════════

【1️⃣ 信号发现与建仓】

  📡 信号扫描逻辑（get_hourly_buy_surge_signals函数）：
    • 数据源：扫描所有USDT永续合约的小时K线数据
    • 扫描范围：每个交易日内的所有小时K线（0:00-23:00）
    • 触发条件：小时主动买量 >= 昨日24小时平均买量 × 2倍
    • 倍数限制：默认仅接受2-3倍信号（可通过--max-multiple参数放宽到10倍）
      - <2倍：正常波动，不触发
      - 2-3倍：稳健信号，默认接受 ✅
      - >3倍：高波动，默认过滤（可放宽）
    • 记录内容：信号时间、信号价格、暴涨倍数、小时买量、昨日平均小时买量
  
  🎯 顶级交易者筛选（check_trader_signal_filter函数）：
    • 启用条件：默认启用（可通过--disable-trader-filter禁用）
    • 数据来源：top_trader_data.db（每日00:00采集）
    • 筛选标准：账户多空比(longShortRatio) >= 0.70
    • 查询窗口：信号时间±24小时（匹配采集频率）
    • 筛选逻辑：
      ✓ 有数据且比值>=0.70 → 放行
      ✓ 无数据 → 放行（容错机制）
      ✗ 有数据但比值<0.70 → 过滤
    • 效果：约过滤15-20%信号，降低低质量交易
  
  📉 等待回调建仓（get_wait_drop_pct + execute_trade函数）：
    • 回调策略（根据买量倍数动态调整）：
      - 2-3倍：等待-5%回调（低倍数，回调空间小）
      - 3-5倍：等待-4%回调
      - 5-10倍：等待-3%回调（高倍数，波动大）
    • 建仓触发：小时K线最低价触及目标回调价时建仓
    • 超时机制：信号触发后48小时内未回调到位则放弃
    • 建仓价格：触及目标回调价的小时K线收盘价
  
  💰 资金管理（execute_trade函数）：
    • 杠杆倍数：4倍（固定）
    • 单次建仓：当前资金 × 5%（position_size_ratio）
    • 复利模式：每次盈利后资金增长，下次建仓金额随之增长
    • 爆仓保护：资金亏损超过80%时停止交易
    • 最大同时持仓：无硬性限制（实测最多13个）
  
  🎁 虚拟补仓补偿机制：
    • 触发条件：上一笔交易发生虚拟补仓平仓后
    • 补偿系数：1.5倍（VIRTUAL_ADD_COMPENSATION_MULTIPLIER）
    • 补偿次数：最多累积1次（最高1.5倍建仓金额）
    • 上限保护：单笔建仓不超过总资金30%
    • 消耗机制：建仓成功后消耗1次补偿机会
    • 设计理念：用下次交易的适度增加仓位（+50%）来补偿虚拟补仓的损失

【2️⃣ 动态止盈机制】

  🎯 基础止盈（take_profit_pct参数）：
    • 默认值：33%（代码中self.take_profit_pct = 0.33）
    • 触发方式：小时K线最高价达到止盈价时平仓
    • 平仓价格：止盈阈值价格（avg_price × (1 + take_profit_pct)）
  
  📊 弱势币动态降低止盈（_calculate_dynamic_take_profit函数）：
    ① 第一阶段判定（建仓后2小时）：
       • 数据源：5分钟K线（理论24根）
       • 判定条件：涨幅>1.5%的K线占比<60%
       • 触发效果：止盈从33%降低到20%
       • 标记字段：dynamic_tp_weak=True, dynamic_tp_trigger='2h_weak'
    
    ② 第二阶段判定（建仓后12小时）：
       • 数据源：小时K线
       • 判定条件：12小时涨幅<2.5%
       • 触发效果：止盈从33%或20%降低到11%
       • 标记字段：dynamic_tp_weak=True, dynamic_tp_trigger='12h_weak'
    
    ③ 强势币保持：
       • 条件：不满足上述任一弱势判定
       • 效果：保持33%基础止盈
       • 标记字段：dynamic_tp_strong=False, dynamic_tp_trigger='none'
  
  🔄 缓存机制：
    • 首次计算后缓存到position['dynamic_tp_pct']
    • 避免重复计算，提升回测效率
    • 确保止盈阈值在整个持仓期间保持一致

【3️⃣ 补仓机制】

  🆕 虚拟补仓模式（默认启用，use_virtual_add_position=True）：
    
    触发条件（check_exit_conditions函数）：
      • 小时K线最低价触及：avg_price × (1 - 0.18) = -18%
      • 首次建仓后才能触发（has_add_position=False）
      • 最多触发1次
    
    执行逻辑（add_position函数）：
      ✓ 不实际扣除资金（self.capital不变）
      ✓ 计算虚拟新平均成本：
        new_avg_price = (原成本×原数量 + 当前价×虚拟数量) / (原数量+虚拟数量)
      ✓ 返还首仓本金到资金账户（释放资金）
      ✓ 仓位显示值翻倍（视觉上看起来补仓了）
      ✓ 实际持仓数量不变（position_size不变）
      ✓ 标记：is_virtual_add_position=True, capital_already_returned=True
      ✓ 仍占用仓位槽（保留节流阀效应）
    
    后续影响：
      • 止损/止盈基准：使用虚拟新平均成本计算
      • 实际盈亏：基于原始成本和数量（不增加风险）
      • 虚拟补仓补偿：平仓后产生1次1.05x补偿机会（更保守的增仓）
    
    战略价值：
      ① 避免实际追加资金 → 单笔最大亏损固定在首仓
      ② 调整止损基准 → 给失败交易"虚拟救活"机会
      ③ 占用仓位槽 → 防止冒进建立新仓（节流阀）
      ④ 产生补偿机会 → 下次交易用更大仓位弥补亏损
  
  传统补仓模式（可选，use_virtual_add_position=False）：
    • 实际扣除资金：当前资金 × 5%
    • 重算平均成本：真实追加数量
    • 更新持仓信息：position_size增加
    • 补仓后立即检查止盈止损

【4️⃣ 止损机制】

  ① 价格止损（check_exit_conditions函数）：
    • 启用条件：补仓后才启用（has_add_position=True）
    • 止损阈值：avg_price × (1 - 0.18) = -18%
    • 监控方式：小时K线最低价
    • 触发价格：止损阈值价格（不用最低价，避免过度乐观）
    • 平仓类型：
      - 虚拟补仓：虚拟平仓（virtual_stop_loss）
      - 传统补仓：真实平仓（stop_loss）
    • 设计理念：
      * 首仓不止损 → 允许回调进行补仓
      * 补仓后止损 → 防止继续扩大亏损
  
  ② 顶级交易者动态止损（check_exit_conditions函数）：
    • 启用条件：enable_trader_stop_loss=True（默认）
    • 监控指标：账户多空比(longShortRatio)
    • 数据采集：每小时查询一次最新数据
    • 触发条件：
      current_ratio - entry_ratio <= -0.10（下降>=0.10）
    • 触发价格：当前小时收盘价
    • 平仓原因：stop_loss_trader
    • 优先级：高于价格止损（先检查）
    • 典型效果：
      - 平均损失：-$11/笔
      - 提前止损：避免深度回撤
      - 典型案例：JELLYJELLYUSDT比值从1.98降到1.77，-8%止损

【5️⃣ 观察模式与动态平仓】

  🔍 24小时弱势观察模式（check_exit_conditions函数）：
    
    启用条件：
      • enable_weak_24h_exit=True（可选，默认禁用）
      • 建仓满24小时
      • 仓位状态为normal
    
    触发条件：
      • 24小时涨幅 < 8%（weak_24h_threshold）
    
    观察逻辑：
      ① 进入观察状态（observing）：
         • 返还首仓本金（释放资金）
         • 记录观察建仓价（当前价）
         • 仍占用仓位槽（保持风控）
         • 记录weak_24h_pnl（观察时盈亏）
      
      ② 观察期三条出路：
         🔴 路径A：跌到-18% → 虚拟补仓
            • 转为virtual_tracking状态
            • 记录虚拟建仓价
            • 产生1次虚拟补偿机会
            • 继续等待±18%或72小时
         
         🟢 路径B：涨到+11% → 止盈离场
            • 平仓原因：observing_take_profit
            • 释放仓位槽
            • 实际盈亏 = 原建仓价到当前价
         
         ⏰ 路径C：72小时超时 → 强制离场
            • 平仓原因：observing_timeout
            • 释放仓位槽
      
      ③ 虚拟跟踪阶段（virtual_tracking）：
         • 等待涨回+18%（从虚拟建仓价计）
         • 或等待72小时总持仓超时
         • 平仓时产生1次虚拟补偿机会
    
    ⚠️ 当前状态：已禁用（enable_weak_24h_exit=False）
    • 原因：24小时弱势平仓效果不佳
    • 数据证明：依赖动态止盈和止损效果更好

【6️⃣ 强制平仓】

  ⏰ 最大持仓时间（check_exit_conditions函数）：
    • 时间限制：72小时（max_hold_hours=72）
    • 计算方式：从建仓小时时间戳开始精确计算
    • 检查优先级：最高（最先检查）
    • 触发价格：当前小时收盘价
    • 平仓原因：
      - normal状态：max_hold_time
      - observing状态：observing_timeout
      - virtual_tracking状态：virtual_max_hold_time
    • 设计理念：
      * 避免长期占用资金
      * 提升资金周转效率
      * 防止死仓问题

═══════════════════════════════════════════════════════════════════════════════
📈 策略特点总结
═══════════════════════════════════════════════════════════════════════════════

【核心优势】
  ✅ 复利模式：盈利后资金增长，下次建仓金额随之增长，实现指数增长
  ✅ 虚拟补仓：不实际追加资金，避免补仓亏损，但保留战略价值
  ✅ 虚拟补偿：上次虚拟补仓后，下次用1.05倍仓位适度补偿（更保守风控）
  ✅ 动态止盈：弱势币降低止盈（20%→11%），提高胜率
  ✅ 多重止损：价格止损 + 交易者止损，双重保护
  ✅ 智能风控：观察模式 + 强制平仓，避免死仓

【风险控制】
  🛡️ 仓位控制：单笔5%，最高30%（补偿时）
  🛡️ 杠杆固定：4倍，风险可控
  🛡️ 止损保护：补仓后-18%强制止损
  🛡️ 时间限制：72小时强制平仓
  🛡️ 爆仓保护：资金<20%停止交易

【实测表现（2025-11-01 至 2026-01-20）】
  📊 总交易次数：309笔
  💰 初始资金：$10,000
  💵 最终资金：$633,307
  📈 总收益率：+6,233%
  🎯 最大同时持仓：13个
  ⏰ 平均持仓时间：约24小时
  
  平仓原因分布（示例）：
    • 止盈(take_profit)：约40-60%
    • 交易者止损(stop_loss_trader)：约10-15%
    • 超时平仓(max_hold_time)：约20-30%
    • 价格止损(stop_loss)：约5-10%
    • 虚拟平仓(virtual_*)：约10-20%

═══════════════════════════════════════════════════════════════════════════════
⚠️ 风险提示
═══════════════════════════════════════════════════════════════════════════════

1. 杠杆风险：4倍杠杆放大收益的同时也放大风险
2. 补仓风险：部分交易需要补仓，占用额外资金
3. 止损风险：虽然顶级交易者止损大幅降低单笔损失，但价格止损仍可能造成较大亏损
4. 数据依赖：顶级交易者数据来自Binance，需确保数据采集稳定（每日00:00采集）
5. 市场风险：策略基于历史数据回测，实盘表现可能不同
6. 最大回撤：虽然风控版本降低了最大回撤，但仍有30%的回撤风险
7. 风控限制：顶级交易者风控会过滤15-20%的信号，可能错过部分机会

🔧 技术实现细节
═══════════════════════════════════════════════════════════════════════════════

• 数据精度：使用小时K线数据（HourlyKline表）进行精确监控
• 时间戳：精确到小时级别，确保动态止盈计算准确
• 价格监控：
  - 止盈：使用每小时最高价(high)
  - 补仓：使用每小时最低价(low)
  - 止损：使用每小时最低价(low)
• 持仓时间：基于建仓小时时间戳精确计算，而非简单的日期差
• 无缓存设计：避免量化回测中的数据不一致问题，每次实时查询数据库

═══════════════════════════════════════════════════════════════════════════════

作者：量化交易助手
创建时间：2026-01-11
最后更新：2026-01-16
版本：v3.0（新增顶级交易者风控系统，优化风险控制）

主要更新：
  • v3.0 (2026-01-16): 新增基于Binance顶级交易者持仓数据的智能风控系统
    - 信号筛选：账户多空比过滤
    - 动态止损：基于账户多空比变化的实时止损
    - 效果显著：最大回撤降低22%，止损损失减少66%
  • v2.0 (2026-01-14): 优化信号过滤，接受2-10倍信号
  • v1.0 (2026-01-11): 初始版本
"""

import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import pandas as pd
from sqlalchemy import text
from db import engine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ════════════════════════════════════════════════════════════════
# 🔧 可调整参数配置区（方便测试修改）
# ════════════════════════════════════════════════════════════════

# 虚拟补仓补偿倍数（用于补偿虚拟补仓损失）
# 说明：当上一笔交易发生虚拟补仓平仓后，下一笔交易建仓金额会乘以此倍数
# 范围：1.0-2.0 建议值：1.2-1.5
VIRTUAL_ADD_COMPENSATION_MULTIPLIER = 1.5  # 🔧 当前设置：1.5倍

# ════════════════════════════════════════════════════════════════


class BuySurgeBacktest:
    """买量暴涨策略回测器"""

    def __init__(self):
        # 使用 PostgreSQL 引擎
        self.engine = engine
        logging.info("✅ 已连接 PostgreSQL 数据库")
        
        # 🆕 添加：顶级交易者风控参数
        self.enable_trader_filter = True  # 是否启用顶级交易者信号筛选（默认开启）
        self.enable_trader_stop_loss = True  # 是否启用顶级交易者动态止损（默认开启）
        self.min_account_ratio = 0.70  # 最小账户多空比（信号筛选）
        self.account_ratio_stop_threshold = 0.1  # 账户多空比绝对值止损阈值（当前多空比 < 此值时止损）

        # 回测参数
        self.initial_capital = 10000.0  # 初始资金
        self.leverage = 4.0  # 杠杆倍数（4倍）
        self.position_size_ratio = 0.08  # 单次建仓占资金比例（6%）
        self.add_position_size_ratio = 0.05  # 补仓占资金比例（5%，可以设置为首仓的倍数）
        self.max_daily_positions = 6  # 并发持仓上限（保守设置，留出缓冲空间）
        self.buy_surge_threshold = 2  # 小时主动买量比昨日暴涨阈值（2倍）
        self.buy_surge_max = 3.0  # 买量暴涨倍数上限（默认接受2-3倍，可通过参数放宽）
        self.take_profit_pct = 0.33  # 止盈比例 (8.5%)
        
        # 🆕 资金管理：追踪可用资金余额（扣除已锁定在持仓中的资金）
        self.available_capital = self.initial_capital  # 可用资金（初始等于总资金）

        # 🔧 动态止盈参数（"弱势币"梯度降低止盈阈值）
        # - 判定条件（满足任一即降低）：
        #   1. 2小时内60%的5分钟K线收盘价涨幅<1.5%（弱势） → 降到20%
        #   2. 12小时涨幅 < 2.5%（弱势） → 降到11%
        # - 降低逻辑：30% → 20% → 11%（梯度下调）
        #   强势币（2h满足 & 12h满足）：保持30%
        #   中等币（仅2h不满足）：降到20%
        #   弱势币（12h也不满足）：降到11%
        # - dynamic_tp_boost_pct：备用参数（暂不使用）
        self.dynamic_tp_boost_pct = 0.11
        self.dynamic_tp_boost_config = [
            (3, 0.09),     # 2-3倍：9%总止盈
            (6, 0.08),     # 3-6倍：16.5%
            (10, 0.05),    # 6-10倍：13.5%
            (9999, 0.05),  # 10倍以上
        ]
        # 🆕 改为12小时窗口（720分钟），基于数据分析的最佳判定时机
        # 分析显示：能涨19.5%的币在12h涨3.56%，只涨8.5%的币12h涨0.11%，区分度极高
        self.dynamic_tp_lookback_minutes = 720
        # 🆕 调整强势币判定阈值为2.5%（而非原来的1%）
        self.dynamic_tp_close_up_pct = 0.025  # 12小时涨幅 >= 2.5%
        self.dynamic_tp_ratio = 0.60
        self.dynamic_tp_min_5m_bars = 8
        
        # ⚠️ 量化回测中不使用K线缓存，避免数据不一致
        # 只缓存交易对列表（回测期间不会变化）
        self._all_symbols_cache = None  # 交易对列表缓存
        
        # 补仓设置
        self.enable_add_position = True  # 补仓开关
        self.add_position_trigger_pct = -0.18  # 补仓触发比例（跌18%触发补仓）
        self.add_position_size_ratio = 0.05  # ✅ 补仓占5%资金
        self.use_virtual_add_position = True  # 🆕 虚拟补仓模式：不实际追加资金，只调整止损/止盈基准，保留仓位占用效应
        
        # 🆕 虚拟补仓补偿机制
        self.virtual_add_compensation_multiplier = VIRTUAL_ADD_COMPENSATION_MULTIPLIER  # 🔧 从文件开头配置区读取
        self.pending_virtual_compensations = 0  # 待补偿的虚拟补仓次数
        
        # 风控参数人情往来
        self.stop_loss_pct = -0.18  # 止损比例
        self.max_hold_hours = 72  # 最大持仓小时数
        
        # 24小时弱势平仓
        self.enable_weak_24h_exit = True  # ✅ 启用24小时弱势平仓
        self.weak_24h_threshold = 0.08  # 24小时涨幅阈值（8%）
        
        self.wait_timeout_hours = 37  # 等待超时时间（小时）- 优化为36小时
        self.wait_min_hours = 0  # 最早建仓时间（信号后立即可建仓）- 充分利用0-6h黄金窗口
        
        # 🚨🚨🚨 启动时打印关键参数（用于调试）
        logging.info("="*80)
        logging.info("🔧 【关键参数确认 - 请检查是否为最新值】")
        logging.info(f"   max_daily_positions = {self.max_daily_positions} (应该是6)")
        logging.info(f"   virtual_add_compensation_multiplier = {self.virtual_add_compensation_multiplier} (应该是{VIRTUAL_ADD_COMPENSATION_MULTIPLIER})")
        logging.info(f"   wait_timeout_hours = {self.wait_timeout_hours} (应该是37)")
        logging.info(f"   wait_min_hours = {self.wait_min_hours} (应该是0)")
        logging.info("="*80)
        
        # 等待跌幅策略（根据买量倍数）
        # 🎯 基于实际等待时间数据优化的配置
        # 低倍数信号价格快速上涨，等待反而买贵；高倍数信号波动大，可等待回调
        self.wait_drop_pct_config = [
            (3, -0.07),     # 2-3倍：等待9%回调（已修改）
            (5, -0.04),     # 3-5倍：等待4%回调（66.7%立即成交，仅1%回调空间）
            (10, -0.03),   # 5-10倍：等待3%回调（64.9%立即成交，适度等待）
            (9999, -0.01), # 10倍以上：等待2%回调（31.8%立即成交，实际获得1.91%回调）
        ]
        
        # 待建仓信号列表（等待回调中的信号）
        self.pending_signals = []  # 存储 {symbol, signal_date, signal_close, buy_surge_ratio, timeout_datetime}
        # 🆕 信号记录（用于输出“发现信号但未成交”的反馈表）
        # 每条记录：信号时间、目标价、是否成交、未成交原因等
        self.signal_records = []

        # 交易记录
        self.capital = self.initial_capital
        self.positions = []  # 当前持仓
        self.trade_records = []  # 交易记录
        self.daily_capital = []  # 每日资金记录

    def __del__(self):
        """析构函数"""
        pass

    def get_wait_drop_pct(self, buy_surge_ratio: float) -> float:
        """根据买量暴涨倍数获取等待跌幅
        
        Args:
            buy_surge_ratio: 买量暴涨倍数
        
        Returns:
            等待跌幅百分比（负数）
        """
        for max_ratio, drop_pct in self.wait_drop_pct_config:
            if buy_surge_ratio < max_ratio:
                return drop_pct
        return self.wait_drop_pct_config[-1][1]

    def get_dynamic_tp_boost_pct(self, buy_surge_ratio) -> float:
        """根据买量暴涨倍数获取动态止盈加成幅度（仅在“强势币”触发时使用）"""
        if buy_surge_ratio is None:
            return float(self.dynamic_tp_boost_pct)
        try:
            r = float(buy_surge_ratio)
        except Exception:
            return float(self.dynamic_tp_boost_pct)

        for max_ratio, boost_pct in getattr(self, 'dynamic_tp_boost_config', []) or []:
            if r < max_ratio:
                return float(boost_pct)
        return float(self.dynamic_tp_boost_pct)
    
    def get_top_trader_account_ratio(self, symbol: str, timestamp: datetime) -> Optional[Dict]:
        """获取顶级交易者账户多空比数据
        
        Args:
            symbol: 交易对
            timestamp: 查询时间
        
        Returns:
            包含账户多空比数据的字典，如果没有数据则返回None
        """
        try:
            # 转换为毫秒时间戳
            target_ts = int(timestamp.timestamp() * 1000)
            
            # 🔧 修正：顶级交易者数据是每天采集一次，需要更大的查询窗口
            # 查询前后24小时范围内最接近的数据
            time_tolerance = 24 * 3600 * 1000  # 24小时容差
            start_ts = target_ts - time_tolerance
            end_ts = target_ts + time_tolerance
            
            query = text("""
                SELECT timestamp, long_short_ratio, long_account, short_account
                FROM top_account_ratio
                WHERE symbol = :symbol AND timestamp BETWEEN :start_ts AND :end_ts
                ORDER BY ABS(timestamp - :target_ts)
                LIMIT 1
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {
                    "symbol": symbol,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "target_ts": target_ts
                })
                row = result.fetchone()
            
            if row:
                return {
                    'timestamp': row[0],
                    'long_short_ratio': row[1],
                    'long_account': row[2],
                    'short_account': row[3],
                    'datetime': datetime.fromtimestamp(row[0] / 1000)
                }
            
            return None
            
        except Exception as e:
            logging.debug(f"获取顶级交易者数据失败 {symbol}: {e}")
            return None

    def check_trader_signal_filter(self, symbol: str, signal_datetime: datetime) -> tuple:
        """检查信号是否通过顶级交易者数据筛选
        
        Args:
            symbol: 交易对
            signal_datetime: 信号时间
        
        Returns:
            (是否通过, 账户多空比值, 过滤原因)
        """
        if not self.enable_trader_filter:
            return True, None, ""
        
        try:
            trader_data = self.get_top_trader_account_ratio(symbol, signal_datetime)
            
            if trader_data is None:
                # 🆕 优化策略：没有顶级交易者数据时，放行开仓
                # 原因：不应该因为数据缺失而错失机会，只对"有数据但不符合条件"的进行风控
                logging.debug(f"⚠️  {symbol} 无顶级交易者数据，放行")
                return True, None, ""
            
            account_ratio = trader_data['long_short_ratio']
            
            if account_ratio < self.min_account_ratio:
                return False, account_ratio, f"账户多空比{account_ratio:.4f} < {self.min_account_ratio}"
            
            return True, account_ratio, ""
            
        except Exception as e:
            logging.error(f"检查顶级交易者过滤失败 {symbol}: {e}")
            # 🆕 优化：出错时也放行，避免因技术问题错失机会
            return True, None, f"检查异常，放行"

    def check_trader_stop_loss(self, position: Dict, current_datetime: datetime) -> tuple:
        """检查是否因顶级交易者数据触发止损
        
        新逻辑：直接判断当前账户多空比绝对值
        如果当前账户多空比 < 阈值（默认0.1），说明做空力量过强，触发止损
        
        Args:
            position: 持仓信息
            current_datetime: 当前时间
        
        Returns:
            (是否触发止损, 原因说明)
        """
        if not self.enable_trader_stop_loss:
            return False, ""
        
        try:
            symbol = position['symbol']
            
            # 获取建仓时的账户多空比（用于记录）
            entry_account_ratio = position.get('entry_account_ratio')
            if entry_account_ratio is None:
                entry_datetime = position.get('entry_datetime')
                if entry_datetime:
                    entry_trader_data = self.get_top_trader_account_ratio(symbol, entry_datetime)
                    if entry_trader_data:
                        entry_account_ratio = entry_trader_data['long_short_ratio']
                        position['entry_account_ratio'] = entry_account_ratio
            
            # 获取当前的账户多空比
            current_trader_data = self.get_top_trader_account_ratio(symbol, current_datetime)
            
            if current_trader_data is None:
                # 数据不足，无法判断
                return False, ""
            
            current_account_ratio = current_trader_data['long_short_ratio']
            
            # 保存当前值供后续分析
            position['current_account_ratio'] = current_account_ratio
            if entry_account_ratio is not None:
                position['account_ratio_change'] = current_account_ratio - entry_account_ratio
            
            # 🔧 新逻辑：直接判断当前账户多空比绝对值
            # 如果当前账户多空比 < 阈值，说明做空力量过强，触发止损
            if current_account_ratio < self.account_ratio_stop_threshold:
                reason = (f"当前账户多空比{current_account_ratio:.4f} < {self.account_ratio_stop_threshold}，"
                         f"做空力量过强")
                if entry_account_ratio is not None:
                    reason += f"（建仓时为{entry_account_ratio:.4f}）"
                return True, reason
            
            return False, ""
            
        except Exception as e:
            logging.error(f"检查顶级交易者止损失败 {symbol}: {e}")
            return False, ""
    
    def check_signal_surge(self, symbol: str, signal_date: str, signal_close: float) -> tuple:
        """检查信号触发前1小时是否暴涨
        
        Args:
            symbol: 交易对
            signal_date: 信号日期
            signal_close: 信号日收盘价
        
        Returns:
            (是否通过检查, 涨幅百分比)
        """
        try:
            # 获取信号日的时间戳
            signal_dt = datetime.strptime(signal_date, '%Y-%m-%d')
            signal_ts = int(signal_dt.timestamp() * 1000)
            
            # 获取信号日之前的最后一个小时K线
            table_name = f'K1h{symbol}'
            
            query = text(f"""
                SELECT close
                FROM "{table_name}"
                WHERE open_time < :signal_ts
                ORDER BY open_time DESC
                LIMIT 1
            """)
            
            with self.engine.connect() as conn:
                # 检查表是否存在（可选，或者捕获异常）
                try:
                    result = conn.execute(query, {"signal_ts": signal_ts}).fetchone()
                except Exception as e:
                    logging.debug(f"查询表 {table_name} 失败: {e}")
                    return True, 0.0
            
            if not result:
                # 如果没有小时数据，默认通过检查
                return True, 0.0
            
            prev_1h_close = result[0]
            
            # 计算1小时内的涨幅
            surge_pct = ((signal_close - prev_1h_close) / prev_1h_close * 100)
            
            # 如果1小时内涨幅<5%，拒绝信号（涨幅太低）
            if surge_pct < 5.0:
                return False, surge_pct
            
            # 如果1小时内暴涨超过48.5%，拒绝信号（追高风险）
            if surge_pct > 48.5:
                return False, surge_pct
            
            return True, surge_pct
            
        except Exception as e:
            logging.debug(f"检查信号暴涨失败 {symbol}: {e}")
            # 出错时默认通过检查
            return True, 0.0
    
    def calculate_dynamic_take_profit(
        self,
        position: Dict,
        hourly_df: pd.DataFrame,
        entry_datetime: datetime,
        current_datetime: datetime,
    ) -> float:
        """🔧 计算动态止盈阈值（弱势币梯度降低）
        
        双重判断机制（弱势币梯度降低止盈）：
        1. 2小时判断：2小时内<60%的5分钟K线涨幅>1.5% → 降低止盈到20%
        2. 12小时判断：12小时涨幅<2.5% → 降低止盈到11%
        
        梯度下调逻辑：
        - 强势币（2h强 & 12h强）：保持30%
        - 中等币（2h弱 & 12h强）：降到20%
        - 弱势币（12h弱）：降到11%
        
        Args:
            position: 持仓信息
            hourly_df: 小时K线数据
            entry_datetime: 建仓时间（完整的datetime对象，包含小时）
            current_datetime: 当前回测推进到的时间点（避免用未来数据做"强势判定"）
        
        Returns:
            动态止盈阈值（0.30=30%, 0.20=20%, 0.11=11%）
        """
        symbol = position.get('symbol', 'UNKNOWN')
        logging.info(f"🎯 开始计算 {symbol} 动态止盈，entry_datetime={entry_datetime}, current_datetime={current_datetime}")
        try:
            # 缓存：如果已经判定过，直接返回
            cached = position.get('dynamic_tp_pct')
            if isinstance(cached, (int, float)) and cached > 0:
                result = float(cached)
                logging.info(f"🎯 {symbol} 使用缓存止盈={result}")
                return result

            # 获取建仓价格
            avg_price = position['avg_entry_price']
            symbol = position['symbol']
            
            # 🔧 安全检查：确保entry_datetime是有效的datetime对象
            if entry_datetime is None or (hasattr(entry_datetime, '__class__') and entry_datetime.__class__.__name__ == 'NaTType'):
                result = self.take_profit_pct
                logging.warning(f"{symbol} entry_datetime无效，使用默认止盈={result}")
                return result
            
            # ============ 判断1：2小时内60%的5分钟K线涨幅>1.5% ============
            window_2h_end = entry_datetime + timedelta(hours=2)
            if current_datetime >= window_2h_end:
                # 2小时已过，检查5分钟K线表现
                try:
                    kline_5m_table = f'K5m{symbol}'
                    
                    # 获取建仓后2小时内的5分钟K线（24根）
                    start_ts = int(entry_datetime.timestamp() * 1000)
                    end_ts = int(window_2h_end.timestamp() * 1000)
                    
                    query = text(f"""
                    SELECT close
                    FROM "{kline_5m_table}"
                    WHERE open_time >= :start_ts AND open_time < :end_ts
                    ORDER BY open_time
                    """)
                    with self.engine.connect() as conn:
                        result = conn.execute(query, {"start_ts": start_ts, "end_ts": end_ts})
                        closes = [row[0] for row in result.fetchall()]
                    
                    if len(closes) >= 24:  # 确保有足够的K线数据
                        # 计算每根K线相对建仓价的涨幅
                        returns = [(close - avg_price) / avg_price for close in closes[:24]]
                        
                        # 统计涨幅超过1.5%的K线数量
                        count_above_threshold = sum(1 for r in returns if r > 0.015)
                        pct_above = count_above_threshold / 24
                        
                        position['dynamic_tp_2h_pct_above'] = pct_above * 100
                        
                        # 🔧 如果60%以上的K线涨幅低于1.5%（弱势币）→ 降低止盈到20%
                        if pct_above < 0.60:
                            adjusted_tp = 0.20  # 从30%降到20%
                            
                            position['dynamic_tp_pct'] = adjusted_tp
                            position['dynamic_tp_weak'] = True  # 标记为弱势
                            position['dynamic_tp_trigger'] = '2h_weak'
                            
                            buy_surge_ratio = position.get('buy_surge_ratio')
                            ratio_str = f"{float(buy_surge_ratio):.2f}" if buy_surge_ratio else "NA"
                            logging.info(
                                f"📉 {symbol} 弱势币(买量{ratio_str}x)：2小时内{pct_above*100:.0f}%的K线涨<1.5%，"
                                f"止盈降低到{adjusted_tp*100:.1f}%"
                            )
                            logging.info(f"🎯 {symbol} 返回2h弱势止盈={adjusted_tp}")
                            return adjusted_tp
                except Exception as e:
                    logging.debug(f"查询2小时平均价格失败 {symbol}: {e}")

            # ============ 判断2：12小时涨幅 ============
            window_12h_end = entry_datetime + timedelta(minutes=self.dynamic_tp_lookback_minutes)
            if current_datetime >= window_12h_end:
                # 12小时已过，检查12小时涨幅
                try:
                    hourly_table = f'K1h{symbol}'
                    
                    # 获取12小时后附近的K线（允许前后1小时的误差）
                    window_start_ts = int(window_12h_end.timestamp() * 1000)
                    window_end_ts = int((window_12h_end + timedelta(hours=1)).timestamp() * 1000)
                    
                    query = text(f"""
                    SELECT close
                    FROM "{hourly_table}"
                    WHERE open_time >= :start_ts AND open_time < :end_ts
                    ORDER BY open_time ASC
                    LIMIT 1
                    """)
                    with self.engine.connect() as conn:
                        result = conn.execute(query, {"start_ts": window_start_ts, "end_ts": window_end_ts}).fetchone()
                    
                    if result:
                        price_12h = result[0]
                        return_12h = (price_12h - avg_price) / avg_price
                        
                        position['dynamic_tp_12h_return'] = return_12h * 100
                        
                        # 🔧 如果12小时涨幅 < 2.5%（弱势币）→ 降低止盈到11%
                        if return_12h < self.dynamic_tp_close_up_pct:
                            adjusted_tp = 0.11  # 从30%或20%降到11%（最终止盈）
                            
                            position['dynamic_tp_pct'] = adjusted_tp
                            position['dynamic_tp_weak'] = True  # 标记为弱势
                            position['dynamic_tp_trigger'] = '12h_weak'
                            
                            buy_surge_ratio = position.get('buy_surge_ratio')
                            ratio_str = f"{float(buy_surge_ratio):.2f}" if buy_surge_ratio else "NA"
                            logging.info(
                                f"📉 {symbol} 弱势币(买量{ratio_str}x)：12小时涨幅{return_12h*100:.2f}% < {self.dynamic_tp_close_up_pct*100:.1f}%，"
                                f"止盈降低到{adjusted_tp*100:.1f}%"
                            )
                            logging.info(f"🎯 {symbol} 返回12h弱势止盈={adjusted_tp}")
                            return adjusted_tp
                except Exception as e:
                    logging.debug(f"查询12小时价格失败 {symbol}: {e}")

            # ============ 两个判断都不满足（强势币保持高止盈）============
            # 如果12小时窗口还没走完，返回当前止盈（可能是30%或2小时降低后的20%）
            if current_datetime < window_12h_end:
                # 返回之前可能已经降低的止盈，或者默认的30%
                # 🔧 关键修复：如果值是None，使用默认值
                current_tp = position.get('dynamic_tp_pct') or self.take_profit_pct
                logging.info(f"🎯 {symbol} 12小时窗口未到，当前止盈={current_tp}")
                return current_tp
            
            # 12小时已过且强势（涨幅>=2.5%），保持当前止盈（可能是30%或20%）
            # 🔧 关键修复：如果值是None，使用默认值
            current_tp = position.get('dynamic_tp_pct') or self.take_profit_pct
            position['dynamic_tp_pct'] = current_tp
            position['dynamic_tp_strong'] = False
            position['dynamic_tp_boost_used'] = 0.0
            position['dynamic_tp_trigger'] = 'none'
            result = self.take_profit_pct
            logging.info(f"🎯 {symbol} 强势币，保持默认止盈={result}")
            return result
                
        except Exception as e:
            logging.error(f"❌❌❌ {symbol} 计算动态止盈异常: {e}")
            import traceback
            logging.error(f"异常堆栈:\n{traceback.format_exc()}")
            result = self.take_profit_pct if self.take_profit_pct is not None else 0.3
            position['dynamic_tp_pct'] = result
            position['dynamic_tp_strong'] = False
            logging.error(f"使用默认止盈={result}")
            return result

    def get_daily_buy_surge_coins(self, date_str: str) -> List[Dict]:
        """获取指定日期主动买量暴涨的合约
        
        Args:
            date_str: 日期字符串
        
        Returns:
            主动买量暴涨的合约列表
        """
        try:
            with self.engine.connect() as conn:
                # 获取所有交易对
                tables_query = text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'K1d%USDT'")
                tables = conn.execute(tables_query).fetchall()
                
                surge_contracts = []
                
                for table_name_row in tables:
                    table_name = table_name_row[0]
                    symbol = table_name.replace('K1d', '')
                    
                    if not symbol.endswith('USDT'):
                        continue
                    
                    try:
                        # 获取当日数据
                        query_today = text(f'''
                            SELECT trade_date, close, open, active_buy_volume
                            FROM "{table_name}"
                            WHERE trade_date = :date_str OR trade_date LIKE :date_like
                        ''')
                        
                        today_result = conn.execute(query_today, {"date_str": date_str, "date_like": f'{date_str}%'}).fetchone()
                        if not today_result or not today_result[3]:
                            continue
                        
                        today_date, close_price, open_price, today_buy_volume = today_result
                        
                        # 获取昨日数据
                        yesterday_dt = datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)
                        yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
                        
                        query_yesterday = text(f'''
                            SELECT active_buy_volume
                            FROM "{table_name}"
                            WHERE trade_date = :yesterday_str OR trade_date LIKE :yesterday_like
                        ''')
                        
                        yesterday_result = conn.execute(query_yesterday, {"yesterday_str": yesterday_str, "yesterday_like": f'{yesterday_str}%'}).fetchone()
                        if not yesterday_result or not yesterday_result[0]:
                            continue
                        
                        yesterday_buy_volume = yesterday_result[0]
                        
                        # 计算买量暴涨倍数
                        if yesterday_buy_volume > 0:
                            buy_surge_ratio = today_buy_volume / yesterday_buy_volume
                            
                            # 如果买量暴涨超过阈值
                            if buy_surge_ratio >= self.buy_surge_threshold:
                                # 🆕 检查信号触发前1小时是否暴涨
                                passed, surge_pct = self.check_signal_surge(symbol, date_str, close_price)
                                
                                if not passed:
                                    # 根据涨幅判断过滤原因
                                    if surge_pct < 5.0:
                                        logging.info(f"⚠️ 过滤信号: {symbol} 在 {date_str} 买量暴涨 {buy_surge_ratio:.1f}倍，但1小时内涨幅仅{surge_pct:.1f}%（涨幅太低）")
                                    else:
                                        logging.info(f"⚠️ 过滤信号: {symbol} 在 {date_str} 买量暴涨 {buy_surge_ratio:.1f}倍，但1小时内价格暴涨{surge_pct:.1f}%（追高风险）")
                                    continue
                                
                                surge_contracts.append({
                                    'symbol': symbol,
                                    'close': close_price,
                                    'open': open_price,
                                    'today_buy_volume': today_buy_volume,
                                    'yesterday_buy_volume': yesterday_buy_volume,
                                    'buy_surge_ratio': buy_surge_ratio
                                })
                                
                                logging.info(f"🔥 发现买量暴涨: {symbol} 在 {date_str} 买量暴涨 {buy_surge_ratio:.1f}倍 (1小时涨幅{surge_pct:+.1f}%)")
                    
                    except Exception as e:
                        continue
            
            # 按买量暴涨倍数降序排序
            surge_contracts.sort(key=lambda x: x['buy_surge_ratio'], reverse=True)
            
            return surge_contracts
        
        except Exception as e:
            logging.error(f"获取 {date_str} 买量暴涨合约失败: {e}")
            return []

    def get_all_symbols(self) -> List[str]:
        """获取所有USDT交易对列表（缓存，回测期间交易对列表不变）"""
        if self._all_symbols_cache is not None:
            return self._all_symbols_cache
        
        # 适配 PostgreSQL 表名规则：K1d{symbol}
        query = text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'K1d%USDT'")
        with self.engine.connect() as conn:
            tables = conn.execute(query).fetchall()
            
        symbols = [
            table_name[0].replace('K1d', '') 
            for table_name in tables 
        ]
        self._all_symbols_cache = symbols
        logging.info(f"🔍 找到 {len(symbols)} 个USDT交易对")
        return symbols
    
    def get_daily_1hour_surge_signals(self, check_date: str) -> List[Dict]:
        """🆕 优化版：检测某天内哪些小时的买量超过昨日平均小时买量
        
        检测逻辑：
        1. 获取昨日日K线的 active_buy_volume（总买量）
        2. 计算昨日平均小时买量 = 总买量 / 24（1天=24小时）
        3. 遍历今日24小时，找到第一个买量 >= 昨日平均小时买量 × 阈值的小时
        4. 那个小时就是信号时间
        
        Args:
            check_date: 检测日期 'YYYY-MM-DD'
        
        Returns:
            信号列表，包含symbol、信号时间、倍数等
        """
        try:
            with self.engine.connect() as conn:
                
                # 获取所有交易对列表
                all_symbols = self.get_all_symbols()
                total_symbols = len(all_symbols)
                
                signals = []
                threshold = 2.0  # 🔥 某小时买量 >= 昨日平均小时买量 × 2倍
                
                check_dt = datetime.strptime(check_date, '%Y-%m-%d')
                yesterday_date = (check_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                
                # 遍历所有交易对
                logging.info(f"🔍 开始扫描 {check_date} 的信号，共 {total_symbols} 个交易对...")
                for idx, symbol in enumerate(all_symbols, 1):
                    
                    try:
                        # 🚀 步骤1：获取昨日日K线总买量
                        daily_table = f'K1d{symbol}'
                        query_daily = text(f'''
                            SELECT active_buy_volume
                            FROM "{daily_table}"
                            WHERE trade_date = :yesterday_date OR trade_date LIKE :yesterday_like
                        ''')
                        
                        yesterday_row = conn.execute(query_daily, {"yesterday_date": yesterday_date, "yesterday_like": f'{yesterday_date}%'}).fetchone()
                        if not yesterday_row or not yesterday_row[0]:
                            continue
                        
                        yesterday_daily_volume = yesterday_row[0]
                        # 🔧 关键修复：计算昨日平均小时买量（1天 = 24小时）
                        yesterday_avg_hour_volume = yesterday_daily_volume / 24.0
                        
                        # 🚀 步骤2：获取今日所有小时K线（优化：使用LIKE更快）
                        hourly_table = f'K1h{symbol}'
                        query_hourly = text(f'''
                            SELECT trade_date, active_buy_volume, close
                            FROM "{hourly_table}"
                            WHERE trade_date LIKE :check_date_like
                            ORDER BY trade_date ASC
                        ''')
                        
                        today_hours = conn.execute(query_hourly, {"check_date_like": f'{check_date}%'}).fetchall()
                        if not today_hours:
                            continue
                        
                        # 🚀 步骤3：找到第一个满足条件的小时
                        for hour_data in today_hours:
                            hour_time, hour_volume, hour_price = hour_data
                            
                            if not hour_volume or not hour_price:
                                continue
                            
                            # 🔧 修复后：某小时买量 vs 昨日平均小时买量
                            surge_ratio = hour_volume / yesterday_avg_hour_volume
                            
                            # 满足阈值，记录信号（只保留2-3倍的稳健信号）
                            if surge_ratio >= threshold and surge_ratio <= self.buy_surge_max:
                                signal_datetime = pd.to_datetime(hour_time)
                                
                                signals.append({
                                    'symbol': symbol,
                                    'signal_datetime': signal_datetime,
                                    'signal_price': hour_price,
                                    'surge_ratio': surge_ratio,
                                    'signal_hour_volume': hour_volume,
                                    'yesterday_avg_hour_volume': yesterday_avg_hour_volume
                                })
                                
                                logging.info(f"🔥 发现信号: {symbol} @{signal_datetime.strftime('%H:00')} 倍数{surge_ratio:.2f}x 价格{hour_price:.6f}")
                                break  # 只记录第一个满足条件的小时
                            elif surge_ratio > self.buy_surge_max:
                                logging.debug(f"⚠️ 过滤高倍数信号: {symbol} @{hour_time} 倍数{surge_ratio:.2f}x (>{self.buy_surge_max}倍)")
                                break  # 超过上限也跳过该交易对后续小时（保持原逻辑：只关心最早触发的小时）
                    
                    except Exception as e:
                        continue
                    
                    # 每扫描100个交易对显示一次进度
                    if idx % 100 == 0 or idx == total_symbols:
                        logging.info(f"  扫描进度: {idx}/{total_symbols} ({idx*100//total_symbols}%) | 已找到信号: {len(signals)} 个")
                
                # 按倍数降序排序
                signals.sort(key=lambda x: x['surge_ratio'], reverse=True)
                
                logging.info(f"✅ {check_date} 扫描完成，共发现 {len(signals)} 个买量暴涨信号")
                return signals
        
        except Exception as e:
            logging.error(f"获取 {check_date} 买量暴涨信号失败: {e}")
            return []

    def get_hourly_kline_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取小时K线数据（安全版：不使用缓存，只查询需要的日期范围）
        
        Args:
            symbol: 交易对
            start_date: 开始日期（可选，格式：YYYY-MM-DD）
            end_date: 结束日期（可选，格式：YYYY-MM-DD）
        
        Note:
            量化回测中不使用缓存，确保数据准确性
        """
        table_name = f'K1h{symbol}'
        
        try:
            # 构建带日期范围的查询（优化：只查询需要的数据）
            if start_date and end_date:
                query = text(f'SELECT * FROM "{table_name}" WHERE trade_date >= :start_date AND trade_date <= :end_date ORDER BY trade_date ASC')
                params = {"start_date": start_date, "end_date": end_date + ' 23:59:59'}
            elif start_date:
                query = text(f'SELECT * FROM "{table_name}" WHERE trade_date >= :start_date ORDER BY trade_date ASC')
                params = {"start_date": start_date}
            elif end_date:
                query = text(f'SELECT * FROM "{table_name}" WHERE trade_date <= :end_date ORDER BY trade_date ASC')
                params = {"end_date": end_date + ' 23:59:59'}
            else:
                # 没有指定范围时，查询全部（但会很慢）
                logging.warning(f"查询 {symbol} 全部小时K线数据，可能较慢")
                query = text(f'SELECT * FROM "{table_name}" ORDER BY trade_date ASC')
                params = {}
            
            with self.engine.connect() as conn:
                return pd.read_sql(query, conn, params=params)
                
        except Exception as e:
            logging.warning(f"获取 {symbol} 小时K线数据失败: {e}")
            return pd.DataFrame()

    def execute_trade(self, symbol: str, entry_price: float, entry_date: str, 
                     signal_date: str, buy_surge_ratio: float, position_type: str = "long", entry_datetime=None):
        """执行交易
        
        Args:
            entry_datetime: 完整的建仓时间戳（datetime对象或字符串），用于精确记录建仓时刻
        """
        try:
            # 🔧 持仓数量限制（双重保险：避免同一天内建仓过多）
            if len(self.positions) >= self.max_daily_positions:
                logging.warning(
                    f"⚠️ 持仓数量已达上限{self.max_daily_positions}个，无法建仓: {symbol} "
                    f"当前持仓{len(self.positions)}个"
                )
                return
            
            # 🔧 爆仓保护：如果资金亏损超过80%，停止交易
            if self.capital <= self.initial_capital * 0.2:
                logging.warning(f"⚠️ 资金不足，停止交易: {symbol} 当前资金${self.capital:.2f} < 初始资金20%")
                return
            
            # 💰 复利模式：基于当前资金余额的比例建仓（实现复利增长）
            base_position_value = self.capital * self.position_size_ratio
            
            # 🆕 虚拟补仓补偿机制：如果有待补偿的虚拟补仓，增加建仓金额
            if self.pending_virtual_compensations > 0:
                # 🔧 保守补偿：限制补偿倍数上限为1.05倍（更低风险）
                # 最多累积1次补偿：1 + (1.05-1)*1 = 1.05倍
                effective_compensations = min(self.pending_virtual_compensations, 1)  # 🔧 改为最多累积1次（1.05倍上限）
                compensation_multiplier = 1 + (self.virtual_add_compensation_multiplier - 1) * effective_compensations
                position_value = base_position_value * compensation_multiplier
                
                # 🔧 限制单笔建仓上限：不超过总资金的30%
                max_position_value = self.capital * 0.3
                if position_value > max_position_value:
                    position_value = max_position_value
                    logging.warning(
                        f"⚠️ 补偿后建仓金额${position_value:.2f}超限，限制为总资金30%: ${max_position_value:.2f}"
                    )
                
                logging.info(
                    f"🔄 虚拟补仓补偿: {symbol} 基础建仓${base_position_value:.2f} "
                    f"× {compensation_multiplier:.2f} = ${position_value:.2f} "
                    f"(待补偿{self.pending_virtual_compensations}次，实际使用{effective_compensations}次)"
                )
            else:
                position_value = base_position_value
            
            # 🆕 检查可用资金余额是否足够建仓（扣除已锁定在持仓中的资金）
            if self.available_capital < position_value:
                locked_capital = self.capital - self.available_capital
                logging.warning(
                    f"⚠️ 可用资金不足，无法建仓: {symbol} "
                    f"需要${position_value:.2f}，可用${self.available_capital:.2f} "
                    f"(总资金${self.capital:.2f}，已锁定${locked_capital:.2f})"
                )
                return
            
            # 计算建仓数量 (考虑杠杆)
            position_size = (position_value * self.leverage) / entry_price
            
            # 🔧 转换 entry_datetime 为字符串格式（如果是 pandas Timestamp 或 datetime 对象）
            if entry_datetime is not None:
                if hasattr(entry_datetime, 'strftime'):
                    entry_datetime_str = entry_datetime.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    entry_datetime_str = str(entry_datetime)
            else:
                entry_datetime_str = None
            
            # 记录交易
            trade_record = {
                'entry_date': entry_date,
                'entry_datetime': entry_datetime_str,  # 🆕 保存完整的建仓时间戳（字符串格式）
                'symbol': symbol,
                'entry_price': entry_price,
                'position_size': position_size,
                'position_value': position_value,
                'base_position_value': base_position_value,  # 🆕 记录未补偿的基础金额（用于计算real_pnl）
                'leverage': self.leverage,
                'position_type': position_type,
                'exit_date': None,
                'exit_price': None,
                'exit_reason': None,
                'pnl': 0,
                'pnl_pct': 0,
                'status': 'normal',  # 🆕 仓位状态：normal / observing / virtual_tracking
                'observing_since': None,  # 🆕 进入观察状态的时间
                'observing_entry_price': None,  # 🆕 观察状态的建仓价
                'weak_24h_exit_price': None,  # 🆕 weak_24h平仓时的价格
                'weak_24h_pnl': None,  # 🆕 weak_24h平仓时的盈亏
                'avg_entry_price': entry_price,
                'signal_date': signal_date,
                'buy_surge_ratio': buy_surge_ratio,  # 买量暴涨倍数
                
                # 🆕 添加：顶级交易者数据字段
                'entry_account_ratio': None,  # 建仓时账户多空比
                'current_account_ratio': None,  # 当前账户多空比
                'account_ratio_change': None,  # 账户多空比变化
                
                'has_add_position': False,
                'add_position_price': None,
                'add_position_size': None,
                'max_drawdown': 0,
                'max_up_2h': None,  # 🆕 建仓后2小时最大涨幅（ratio，用于分析）
                'max_up_24h': None,  # 🆕 建仓后24小时最大涨幅（ratio，用于分析）
                'hold_days': 0,

                # 动态止盈相关（用于后续分析 + CSV输出）
                # - dynamic_tp_pct: 本次交易“最终使用的动态止盈阈值”（会缓存：8.5% 或 18.5%）
                # - dynamic_tp_strong: 是否被判定为“强势币”（True/False）
                # - dynamic_tp_boost_used: 强势时实际使用的加成幅度（按买量暴涨倍数分档）
                # - tp_pct_used: 本次实际触发止盈时使用的阈值（仅在 take_profit 平仓时写入）
                'dynamic_tp_pct': None,
                'dynamic_tp_strong': None,
                'dynamic_tp_boost_used': None,
                'dynamic_tp_above_cnt': None,
                'dynamic_tp_total_cnt': None,
                'tp_pct_used': None
            }
            
            # 🆕 添加：获取并保存建仓时的账户多空比
            if hasattr(self, 'enable_trader_filter') and self.enable_trader_filter:
                trader_data = self.get_top_trader_account_ratio(symbol, entry_datetime)
                if trader_data:
                    trade_record['entry_account_ratio'] = trader_data['long_short_ratio']
                    logging.info(f"📊 {symbol} 建仓时账户多空比: {trader_data['long_short_ratio']:.4f}")
            
            self.positions.append(trade_record)
            self.trade_records.append(trade_record)
            
            # 🆕 虚拟补仓补偿：建仓成功后，消耗一次补偿机会
            if self.pending_virtual_compensations > 0:
                self.pending_virtual_compensations -= 1
                logging.info(f"✅ 消耗1次虚拟补仓补偿，剩余待补偿: {self.pending_virtual_compensations}次")
            
            # 💰 复利模式：建仓时扣除投入资金（从可用资金中扣除）
            self.available_capital -= position_value
            locked_capital = self.capital - self.available_capital
            
            logging.info(
                f"🚀 建仓: {symbol} {entry_date} 价格:{entry_price:.4f} 买量暴涨:{buy_surge_ratio:.1f}倍 "
                f"杠杆:{self.leverage}x 仓位:${position_value:.2f} "
                f"可用资金:${self.available_capital:.2f} 已锁定:${locked_capital:.2f} 总资金:${self.capital:.2f}"
            )
        except Exception as e:
            logging.error(f"执行交易失败: {e}")

    def check_exit_conditions(self, position: Dict, current_price: float, current_date: str) -> bool:
        """使用小时线数据检查是否满足平仓条件
        
        支持虚拟跟踪模式：
        - is_virtual_tracking=True时，使用virtual_entry_price判断止盈/止损
        - 虚拟平仓不影响资金（真实仓位已经止损清仓）
        - 虚拟平仓后，释放槽位
        """
        try:
            symbol = position['symbol']
            logging.info(f"🔍🔍🔍 检查 {symbol} 平仓条件，当前日期={current_date}, max_hold_hours={self.max_hold_hours}")
            
            # 🆕 虚拟跟踪模式：使用虚拟建仓价计算止盈止损
            # ⚠️ 但时间相关计算仍使用原始entry_date（首次建仓日期）
            if position.get('is_virtual_tracking', False):
                entry_price = position['virtual_entry_price']
            else:
                entry_price = position['avg_entry_price']
            
            # 所有模式下都使用原始建仓日期（用于查询小时线数据）
            entry_date = position['entry_date']
            
            # 获取小时线数据（优化：只查询建仓日到当前日的数据）
            hourly_df = self.get_hourly_kline_data(symbol, start_date=entry_date, end_date=current_date)
            if hourly_df.empty:
                logging.warning(f"无小时线数据，使用日线数据检查: {symbol}")
                # 备用：使用日线数据（无法使用动态止盈，使用默认阈值）
                price_change_pct = (current_price - entry_price) / entry_price
                if price_change_pct >= self.take_profit_pct:
                    position['tp_pct_used'] = self.take_profit_pct
                    self.exit_position(position, current_price, current_date, "take_profit")
                    return True
                return False
            
            # 筛选建仓时刻之后的所有小时数据
            # 🔧 修复：使用保存的完整建仓时间戳，而不是只用日期
            # ⚠️ 关键修复：虚拟跟踪模式下，仍使用原始entry_datetime计算持仓时长、动态止盈等
            # 只有止盈止损价格使用virtual_entry_price
            if position.get('entry_datetime'):
                # 如果有完整的建仓时间戳，使用它
                entry_datetime_temp = pd.to_datetime(position['entry_datetime'])
                if pd.isna(entry_datetime_temp):
                    # 如果转换失败，使用日期
                    entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
                else:
                    entry_datetime = entry_datetime_temp.to_pydatetime() if hasattr(entry_datetime_temp, 'to_pydatetime') else entry_datetime_temp
            else:
                # 向后兼容：如果没有时间戳，使用日期（旧数据）
                entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
            
            # 🔧 关键修复：将 current_date 设置为当天23:59:59，避免排除当天的小时数据
            current_datetime = datetime.strptime(current_date, '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
            
            # 将trade_date转换为datetime进行筛选
            hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
            # 🔧 关键修复：只看建仓时刻及之后的数据
            mask = hourly_df['trade_datetime'] >= entry_datetime
            mask = mask & (hourly_df['trade_datetime'] <= current_datetime)
            hold_period_data = hourly_df[mask].copy()
            logging.info(f"📊 {symbol} hold_period_data获取完成: {len(hold_period_data)}行 (建仓:{entry_datetime}, 当前:{current_datetime})")

            # 🆕 计算“建仓后2小时最大涨幅%”（用于分析：为何动态止盈触发少）
            # 口径：2小时内最高价(high)相对“建仓价(entry_price)”的涨幅
            # - 用建仓价而不是补仓后平均价
            # - 若2小时内最高价未高于建仓价，则记为0
            if position.get('max_up_2h') is None:
                try:
                    entry_price0 = float(position.get('entry_price') or position.get('avg_entry_price') or 0)
                    if entry_price0 > 0:
                        window_end_dt = entry_datetime + timedelta(hours=2)
                        wmask = (hourly_df['trade_datetime'] >= entry_datetime) & (hourly_df['trade_datetime'] < window_end_dt)
                        wdf = hourly_df[wmask]
                        if not wdf.empty and 'high' in wdf.columns:
                            max_high = wdf['high'].max()
                            if pd.notna(max_high):
                                up_ratio = (float(max_high) - entry_price0) / entry_price0
                                position['max_up_2h'] = max(0.0, float(up_ratio))
                            else:
                                position['max_up_2h'] = None
                        else:
                            position['max_up_2h'] = None
                    else:
                        position['max_up_2h'] = None
                except Exception:
                    position['max_up_2h'] = None

            # 🆕 计算“建仓后24小时最大涨幅%”
            # 口径：24小时内最高价(high)相对“建仓价(entry_price)”的涨幅
            # - 用建仓价而不是补仓后平均价
            # - 若24小时内最高价未高于建仓价，则记为0
            if position.get('max_up_24h') is None:
                try:
                    entry_price0 = float(position.get('entry_price') or position.get('avg_entry_price') or 0)
                    if entry_price0 > 0:
                        window_end_dt = entry_datetime + timedelta(hours=24)
                        wmask = (hourly_df['trade_datetime'] >= entry_datetime) & (hourly_df['trade_datetime'] < window_end_dt)
                        wdf = hourly_df[wmask]
                        if not wdf.empty and 'high' in wdf.columns:
                            max_high = wdf['high'].max()
                            if pd.notna(max_high):
                                up_ratio = (float(max_high) - entry_price0) / entry_price0
                                position['max_up_24h'] = max(0.0, float(up_ratio))
                            else:
                                position['max_up_24h'] = None
                        else:
                            position['max_up_24h'] = None
                    else:
                        position['max_up_24h'] = None
                except Exception:
                    position['max_up_24h'] = None
            
            # 获取建仓时的具体小时时间戳（用于精确计算持仓小时数）
            entry_hour_timestamp = None
            if not hold_period_data.empty:
                try:
                    entry_hour_timestamp = hold_period_data.iloc[0]['trade_datetime']
                    logging.info(f"🕒 {symbol} hold_period_data有{len(hold_period_data)}行，建仓时间={entry_hour_timestamp}, max_hold_hours={self.max_hold_hours}")
                except Exception as ex:
                    logging.error(f"获取entry_hour_timestamp失败: {ex}")
            
            # 检查每小时的价格是否满足止盈/补仓/止损条件
            if not hold_period_data.empty:
                for idx, row in hold_period_data.iterrows():
                    high_price = row['high']
                    low_price = row['low']
                    hour_datetime = row['trade_datetime']
                    hour_date = hour_datetime.strftime('%Y-%m-%d')
                    hour_datetime_str = hour_datetime.strftime('%Y-%m-%d %H:%M:%S')  # 🆕 完整的日期时间字符串
                    
                    # 🔧🔧🔧 最优先：72小时强制平仓（无论任何状态）
                    if entry_hour_timestamp:
                        total_hours_held = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                        if idx == 0:  # 第一个小时，打印日志
                            logging.info(f"🕒 {symbol} 第一小时检查: hour={hour_datetime}, entry={entry_hour_timestamp}, hours={total_hours_held:.1f}")
                        if total_hours_held >= self.max_hold_hours:
                            logging.warning(f"⏰⏰⏰ {symbol} 触发72小时检查! hours={total_hours_held:.1f}, max={self.max_hold_hours}")
                            exit_price = row['close']
                            exit_reason = "max_hold_time"
                            if position.get('status') == 'observing':
                                exit_reason = "observing_timeout"
                            elif position.get('status') == 'virtual_tracking':
                                exit_reason = "virtual_max_hold_time"
                            
                            self.exit_position(position, exit_price, hour_datetime_str, exit_reason)
                            logging.warning(f"⏰⏰⏰ 72小时强制平仓: {symbol} 持有{total_hours_held:.1f}h，状态={position.get('status')}")
                            return True
                    
                    # 🆕 观察状态的持续监控逻辑
                    if position.get('status') == 'observing':
                        observing_entry_price = position['observing_entry_price']
                        current_price = row['close']
                        price_change = (current_price - observing_entry_price) / observing_entry_price
                        leveraged_return = price_change * self.leverage
                        
                        observing_since = position['observing_since']
                        observing_hours = (hour_datetime - observing_since).total_seconds() / 3600
                        
                        # 🔧 优先检查总持仓时间（从最初建仓开始）
                        if entry_hour_timestamp:
                            total_hours_held = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                            if total_hours_held >= self.max_hold_hours:
                                logging.info(f"⏰ 观察模式超时（总持仓{total_hours_held:.1f}h）: {symbol}")
                                self.exit_position(position, current_price, hour_datetime_str, "observing_timeout")
                                return True
                        
                        # 🔍 调试日志
                        if observing_hours % 6 == 0:  # 每6小时打印一次
                            logging.debug(
                                f"📊 观察中: {symbol} 观察{observing_hours:.1f}h "
                                f"当前价{current_price:.6f} 观察价{observing_entry_price:.6f} "
                                f"变化{leveraged_return*100:.2f}% (需±18%或72h)"
                            )
                        
                        # 路径A：跌到-18% → 触发虚拟补仓
                        if leveraged_return <= -0.18:
                            logging.info(
                                f"📉 观察期跌破止损: {symbol} 相对观察建仓价{observing_entry_price:.6f}跌幅{leveraged_return*100:.2f}%，"
                                f"触发虚拟补仓，当前价{current_price:.6f}"
                            )
                            # 转为虚拟跟踪状态
                            position['status'] = 'virtual_tracking'
                            position['is_virtual_tracking'] = True
                            position['virtual_entry_price'] = current_price
                            position['virtual_entry_date'] = hour_date  # 🆕 添加虚拟建仓日期
                            # 🔧 修复：只有在real_pnl未设置时才使用weak_24h_pnl，避免覆盖
                            if 'real_pnl' not in position:
                                position['real_pnl'] = position.get('weak_24h_pnl', 0)  # 使用weak_24h的盈亏作为real_pnl
                            
                            # 🎁 产生1.05x补偿机会（更保守补偿，进一步降低风险）
                            self.pending_virtual_compensations += 1
                            logging.info(f"🎁 观察期虚拟补仓产生补偿机会，待补偿次数: {self.pending_virtual_compensations}")
                            
                            # 🔧 虚拟补仓后也要检查总持仓时间
                            if entry_hour_timestamp:
                                total_hours = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                                if total_hours >= self.max_hold_hours:
                                    logging.warning(f"⚠️ 虚拟跟踪超时: {symbol} 总持仓{total_hours:.1f}h >= {self.max_hold_hours}h")
                                    self.exit_position(position, current_price, hour_datetime_str, "virtual_max_hold_time")
                                    return True
                            
                            # 继续持有，不return
                            continue
                        
                        # 路径B：涨到11% → 释放仓位
                        elif leveraged_return >= 0.11:
                            logging.info(
                                f"📈 观察期触达止盈: {symbol} 相对观察建仓价{observing_entry_price:.6f}涨幅{leveraged_return*100:.2f}%，"
                                f"释放仓位，当前价{current_price:.6f}"
                            )
                            # 平仓并释放仓位
                            # 🔧 修复：让exit_position正常计算盈亏（从建仓价到当前价），不要覆盖
                            # 观察模式已经返还了本金并记录了weak_24h_pnl，但最终盈亏应该是实际的价格变化
                            self.exit_position(position, current_price, hour_datetime_str, "observing_take_profit")
                            return True
                        
                        # 路径C：超时 → 强制释放
                        elif observing_hours >= 72:
                            logging.info(
                                f"⏰ 观察期超时: {symbol} 观察{observing_hours:.1f}小时，"
                                f"释放仓位，当前价{current_price:.6f}"
                            )
                            # 平仓并释放仓位
                            # 🔧 修复：让exit_position正常计算盈亏（从建仓价到当前价），不要覆盖
                            self.exit_position(position, current_price, hour_datetime_str, "observing_timeout")
                            return True
                        
                        # 🔧 最后检查：无论如何，总持仓时间超过72小时必须平仓
                        if entry_hour_timestamp:
                            total_hours = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                            if total_hours >= self.max_hold_hours:
                                logging.warning(f"⚠️ 观察模式强制超时: {symbol} 总持仓{total_hours:.1f}h >= {self.max_hold_hours}h")
                                self.exit_position(position, current_price, hour_datetime_str, "observing_timeout")
                                return True
                        
                        # 继续观察，不触发其他逻辑
                        continue
                    
                    # 🔧 精确计算持仓小时数（基于小时时间戳）
                    if entry_hour_timestamp:
                        hours_held_precise = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                        
                        # ⏰ 在检查其他条件之前，先检查是否超过最大持仓时间
                        if hours_held_precise >= self.max_hold_hours:
                            # 使用当前小时的收盘价平仓
                            exit_price = row['close']
                            self.exit_position(position, exit_price, hour_datetime_str, "max_hold_time")
                            logging.info(f"⏰ {self.max_hold_hours:.0f}小时强制平仓: {symbol} 持有{hours_held_precise:.1f}小时，平仓价{exit_price:.6f}")
                            return True
                    
                    # 动态获取当前有效的平均价格（补仓后会更新）
                    # 🆕 虚拟跟踪模式：使用虚拟建仓价
                    if position.get('is_virtual_tracking', False):
                        current_avg_price = position['virtual_entry_price']
                    else:
                        current_avg_price = position['avg_entry_price']
                    
                    # 更新最大跌幅
                    drawdown_pct = (low_price - current_avg_price) / current_avg_price
                    if drawdown_pct < position['max_drawdown']:
                        position['max_drawdown'] = drawdown_pct

                    # ==========================
                    # 🧠 回测执行价与顺序（避免“未来函数/过度乐观”）
                    # - 同一根小时K线里，high/low 只用来判断“是否触发”，成交价使用“阈值价”而不是直接用 high/low
                    # - 当同一根K线同时触发止损与止盈时，按“先止损后止盈”（更保守）
                    # ==========================
                    # 🆕 动态止盈阈值（避免"偷看未来"：只有窗口走完才允许触发动态加成）
                    dynamic_tp_pct = self.calculate_dynamic_take_profit(position, hourly_df, entry_datetime, hour_datetime)
                    
                    # 计算止盈/止损价格（虚拟跟踪模式会使用virtual_entry_price作为current_avg_price）
                    tp_price = current_avg_price * (1 + dynamic_tp_pct)
                    sl_price = current_avg_price * (1 + self.stop_loss_pct)
                    add_price = current_avg_price * (1 + self.add_position_trigger_pct)  # 补仓触发价
                    
                    # 🆕 24小时弱势平仓检查（优先于补仓和止盈，避免继续持有表现不佳的币）
                    if self.enable_weak_24h_exit and entry_hour_timestamp and position.get('status') == 'normal':
                        hours_held = (hour_datetime - entry_hour_timestamp).total_seconds() / 3600
                        # 在24-25小时之间检查一次（避免重复检查）
                        if 24 <= hours_held < 25:
                            current_price = row['close']
                            return_24h = (current_price - current_avg_price) / current_avg_price
                            
                            # 如果24小时涨幅低于阈值，判定为弱势币，进入观察状态
                            if return_24h < self.weak_24h_threshold:
                                # 🆕 不完全平仓，而是进入观察状态
                                position['status'] = 'observing'
                                position['observing_since'] = hour_datetime
                                position['observing_entry_price'] = position['avg_entry_price']
                                position['weak_24h_exit_price'] = current_price
                                
                                # 返还资金（释放资金，但保留仓位槽）
                                # 🔧 新逻辑：虚拟补仓时已锁定available_capital，所以进入观察模式时必须释放全部
                                if position.get('capital_already_returned', False):
                                    # 资金已经返还过了，不要重复返还
                                    weak_pnl = (current_price - position['avg_entry_price']) / position['avg_entry_price'] * self.leverage * position['position_value']
                                    logging.info(f"💭 观察模式: {symbol} 资金已返还过，不重复返还")
                                else:
                                    # 🆕 返还全部position_value（包括首仓+虚拟补仓的总金额）
                                    self.available_capital += position['position_value']  # 🆕 归还到可用资金
                                    weak_pnl = (current_price - position['avg_entry_price']) / position['avg_entry_price'] * self.leverage * position['position_value']
                                    position['capital_already_returned'] = True  # 标记资金已返还
                                    logging.info(f"💭 观察模式: 返还资金${position['position_value']:.2f} (含虚拟补仓)")
                                
                                # 记录weak_24h平仓事件（用于报告）
                                position['weak_24h_pnl'] = weak_pnl
                                
                                logging.info(
                                    f"🔍 进入观察状态: {symbol} 24h涨幅{return_24h*100:.2f}% < {self.weak_24h_threshold*100:.0f}%，"
                                    f"平仓价格{current_price:.6f}，盈亏{weak_pnl:.2f}，继续跟踪观察"
                                    f"【状态={position['status']}，观察建仓价={position['observing_entry_price']:.6f}】"
                                )
                                # 不return True，继续跟踪这个position
                    
                    # 检查补仓条件
                    if self.enable_add_position and not position.get('has_add_position', False):
                        # 先判断是否触发补仓（用 low 触发，按 add_price 成交）
                        if low_price <= add_price:
                            self.add_position(position, add_price, hour_date)
                            logging.info(
                                f"🔄 补仓触发: {symbol} 在 {hour_datetime_str} low={low_price:.6f} 触发阈值，按补仓价{add_price:.6f}成交"
                            )
                            # 补仓后，为避免"同小时先low补仓再用high止盈"的顺序偏差：
                            # - 允许继续在同一小时检查止损（更保守）
                            # - 不允许同小时止盈（避免过度乐观），止盈从下一小时开始
                            
                            # ⚠️ 虚拟补仓模式下，add_position已返回，不会走到这里
                            # 只有实际补仓才会继续检查补仓后的止损
                            if not self.use_virtual_add_position:
                                # 补仓后重新计算止损价（使用更新后的平均成本）
                                current_avg_price = position['avg_entry_price']
                                sl_price_after_add = current_avg_price * (1 + self.stop_loss_pct)
                                if low_price <= sl_price_after_add:
                                    self.exit_position(position, sl_price_after_add, hour_datetime_str, "stop_loss")
                                    logging.warning(
                                        f"🛑 补仓后同小时止损: {symbol} low={low_price:.6f} 触发止损阈值，按止损价{sl_price_after_add:.6f}成交"
                                    )
                                    return True
                            continue
                    
                    # 🆕 添加：检查顶级交易者数据止损（可单独控制）
                    if hasattr(self, 'enable_trader_stop_loss') and self.enable_trader_stop_loss:
                        should_stop, stop_reason = self.check_trader_stop_loss(position, hour_datetime)
                        if should_stop:
                            # 按当前小时收盘价止损
                            stop_price = row['close']
                            self.exit_position(position, stop_price, hour_datetime_str, "stop_loss_trader")
                            logging.warning(
                                f"🛑 顶级交易者止损: {symbol} 在 {hour_datetime_str} "
                                f"因{stop_reason}，按价格{stop_price:.6f}止损"
                            )
                            return True
                    
                    # 先止损（无论是否补仓，统一按阈值价成交）
                    if low_price <= sl_price:
                        self.exit_position(position, sl_price, hour_datetime_str, "stop_loss")
                        logging.warning(
                            f"🛑 止损触发: {symbol} 在 {hour_datetime_str} low={low_price:.6f} 触发止损阈值，按止损价{sl_price:.6f}成交"
                        )
                        return True
                    
                    # 🔧 虚拟跟踪额外保护：防止未触发虚拟补仓的交易跌幅超过原始建仓价-18%
                    if position.get('is_virtual_tracking', False) and not position.get('has_add_position', False):
                        original_entry_price = position['avg_entry_price']
                        max_loss_price = original_entry_price * (1 + self.add_position_trigger_pct)  # -18%保护价
                        if low_price <= max_loss_price:
                            self.exit_position(position, max_loss_price, hour_datetime_str, "virtual_stop_loss")
                            logging.warning(
                                f"🛑 虚拟跟踪保护止损: {symbol} 相对原始建仓价跌幅达-18%，按保护价{max_loss_price:.6f}止损"
                            )
                            return True

                    # 再止盈（按阈值价成交，而不是用 high 直接成交）
                    if high_price >= tp_price:
                        position['tp_pct_used'] = dynamic_tp_pct
                        self.exit_position(position, tp_price, hour_datetime_str, "take_profit")
                        logging.info(
                            f"✨ 止盈: {symbol} 在 {hour_datetime_str} high={high_price:.6f} 触发止盈阈值，按止盈价{tp_price:.6f}成交（阈值{dynamic_tp_pct*100:.1f}%）"
                        )
                        return True
            
            # 🔧 备用检查：如果没有小时数据，使用日期差异检查（兼容旧逻辑）
            hours_held = (current_datetime - entry_datetime).total_seconds() / 3600
            if hours_held >= self.max_hold_hours:
                if not hold_period_data.empty:
                    last_row = hold_period_data.iloc[-1]
                    exit_price = last_row['close']
                else:
                    exit_price = current_price
                
                self.exit_position(position, exit_price, current_date, "max_hold_time")
                logging.info(f"⏰ {self.max_hold_hours:.0f}小时强制平仓: {symbol} 持有{hours_held:.1f}小时，平仓价{exit_price:.6f}")
                return True
            
            return False
        
        except Exception as e:
            import traceback
            import sys
            exc_info = sys.exc_info()
            logging.error(f"检查平仓条件失败: {e}")
            logging.error(f"异常类型: {exc_info[0]}")
            logging.error(f"异常值: {exc_info[1]}")
            logging.error(f"异常位置: {exc_info[2].tb_frame.f_code.co_filename}:{exc_info[2].tb_lineno}")
            logging.error(f"完整堆栈:\n{''.join(traceback.format_tb(exc_info[2]))}")
            return False

    def add_position(self, position: Dict, current_price: float, current_date: str):
        """补仓操作（支持虚拟补仓模式）
        
        虚拟补仓模式：
        1. 首仓在-18%时止损清仓（实际平仓，确认亏损）
        2. 转为虚拟跟踪模式，继续占用槽位
        3. 虚拟跟踪新仓位盈亏（假设在止损价建仓）
        4. 虚拟仓位止盈/止损后，释放槽位
        """
        try:
            if self.use_virtual_add_position:
                # 🆕 虚拟补仓模式：不平首仓 + 虚拟追加投入 + 转为虚拟跟踪
                
                # Step 1: 记录首仓信息（不实际平仓）
                entry_price = position['avg_entry_price']
                position_size = position['position_size']
                
                # 🔧 关键修复：首次投入金额只在首次虚拟补仓时保存，避免被累加后的position_value覆盖
                if 'first_position_value' not in position:
                    # 首次虚拟补仓：保存未补偿的原始投入金额（确保所有交易都是-72%）
                    # 使用base_position_value（未包含补偿）而不是position_value（可能包含补偿）
                    position['first_position_value'] = position.get('base_position_value', position['position_value'])
                
                first_position_value = position['first_position_value']  # 使用首次投入金额（未补偿）
                
                # 💡 修正：应该基于首次实际投入的本金计算亏损，而不是base_position_value
                # 原因：虚拟补仓返还的是首次投入（实际投入），所以亏损也应该基于首次投入
                # 计算公式：亏损 = 首次投入本金 × 价格变化% × 杠杆
                # 例如：投入500美元，价格跌18%，4倍杠杆 → 亏损 = 500 × 18% × 4 = 360美元（72%本金）
                
                price_change_pct = (current_price - entry_price) / entry_price  # -18%
                loss_rate = price_change_pct * self.leverage  # -18% × 4 = -72%
                actual_loss = first_position_value * loss_rate  # ✅ 基于首次实际投入的本金计算亏损
                
                logging.info(
                    f"💰 虚拟补仓亏损计算: {position['symbol']} "
                    f"首次投入:${first_position_value:.2f}, "
                    f"价格变化={price_change_pct*100:.2f}%, "
                    f"杠杆={self.leverage}x, "
                    f"实际亏损=${actual_loss:.2f}({abs(loss_rate)*100:.2f}%本金)"
                )
                
                
                #🔧 关键修复：首次虚拟补仓时返还首仓本金
                if 'virtual_add_count' not in position:
                    position['virtual_add_count'] = 0
                    # 首次虚拟补仓：返还原始首仓本金（使用first_position_value，即首次实际投入金额）
                    self.available_capital += first_position_value  # 🆕 归还到可用资金
                    position['capital_already_returned'] = True  # 🔧 标记资金已返还，避免后续重复返还
                    logging.info(
                        f"💭 首次虚拟补仓触发: {position['symbol']} {current_date} "
                        f"价格:{current_price:.4f} 首仓实际亏损:${actual_loss:.2f}({price_change_pct*100:.2f}%) "
                        f"返还首仓本金:${first_position_value:.2f} 资金:${self.capital:.2f}"
                    )
                else:
                    logging.info(
                        f"💭 再次虚拟补仓触发: {position['symbol']} {current_date} "
                        f"价格:{current_price:.4f} (本金已在首次返还)"
                    )
                
                position['virtual_add_count'] += 1
                
                # Step 2: 计算虚拟补仓金额（与实际补仓保持一致）
                # 虚拟补仓金额基于当前资金池计算（与实际补仓的计算方式完全一致）
                virtual_add_value = self.capital * self.add_position_size_ratio  # 虚拟补仓投入金额
                virtual_add_size = (virtual_add_value * self.leverage) / current_price  # 虚拟补仓持仓量
                
                # 🔧 关键修复：虚拟补仓虽然不扣除总资金(self.capital)，但必须锁定可用资金(self.available_capital)
                # - self.capital 不变（虚拟补仓的核心：总资金池保持充足，复利继续增长）
                # - self.available_capital 减少（锁定资金，避免重复使用）
                # 🆕 检查可用资金是否足够
                if self.available_capital < virtual_add_value:
                    locked_capital = self.capital - self.available_capital
                    logging.warning(
                        f"⚠️ 可用资金不足，无法虚拟补仓: {position['symbol']} "
                        f"需要${virtual_add_value:.2f}，可用${self.available_capital:.2f} "
                        f"(总资金${self.capital:.2f}，已锁定${locked_capital:.2f})"
                    )
                    return
                
                self.available_capital -= virtual_add_value  # 🆕 锁定可用资金
                
                logging.info(
                    f"💭 虚拟补仓: {position['symbol']} "
                    f"虚拟投入:${virtual_add_value:.2f}（锁定可用资金） "
                    f"当前总资金:${self.capital:.2f}，可用资金:${self.available_capital:.2f}"
                )
                
                # Step 3: 按持仓量加权计算虚拟平均价（与实际补仓完全一致的计算方式）
                total_value = (entry_price * position_size) + (current_price * virtual_add_size)
                total_size = position_size + virtual_add_size
                virtual_avg_price = total_value / total_size
                
                # Step 4: 更新持仓信息
                # 注意：first_position_value已经在Step 1保存，这里不再修改
                
                # 更新position_value以正确显示总投入金额（首仓+虚拟补仓）
                # 虚拟补仓虽然不实际扣资金，但应该"虚拟占用"，以便追踪总仓位
                position['position_value'] += virtual_add_value  # 累加虚拟补仓金额
                position['virtual_add_value'] = virtual_add_value  # ✅ 记录虚拟补仓金额
                # 注意：不扣除实际资金 self.capital（这是虚拟补仓的核心）
                
                position['is_virtual_tracking'] = True
                position['virtual_entry_price'] = virtual_avg_price  # ✅ 虚拟平均建仓价（用于计算止盈止损）
                position['virtual_entry_date'] = current_date  # 记录虚拟补仓日期（仅用于报告）
                # ⚠️ 关键：不设置virtual_entry_datetime，时间相关计算仍使用原始entry_datetime
                position['real_position_closed'] = False  # ✅ 首仓未平仓，继续占用资金
                
                # 🔧 关键修复：只在首次虚拟补仓时记录价格和亏损，后续补仓不更新
                if position['virtual_add_count'] == 1:
                    # 首次虚拟补仓：统一按-18%阈值价格计算，而不是实际触发价格
                    # 原因：无论实际跌多少（可能-22%、-25%等），都按-18%补仓阈值来计算亏损
                    threshold_exit_price = entry_price * (1 + self.add_position_trigger_pct)  # -18%阈值价
                    threshold_loss_rate = self.add_position_trigger_pct * self.leverage  # -18% × 4 = -72%
                    
                    # 🐛 关键检查：确保first_position_value等于base_position_value（未补偿金额）
                    base_val = position.get('base_position_value', None)
                    if base_val is not None and abs(first_position_value - base_val) > 0.01:
                        logging.warning(
                            f"⚠️⚠️⚠️ {position['symbol']} first_position_value={first_position_value:.2f} "
                            f"!= base_position_value={base_val:.2f}，强制使用base_position_value"
                        )
                        first_position_value = base_val  # 强制使用base_position_value
                        position['first_position_value'] = base_val  # 更新保存的值
                    
                    threshold_loss = first_position_value * threshold_loss_rate  # 基于-18%的亏损
                    
                    position['real_exit_price'] = threshold_exit_price  # ✅ 记录-18%阈值价，而非实际价格
                    position['real_pnl'] = threshold_loss  # ✅ 记录按-18%计算的亏损（72%本金）
                    
                    logging.info(
                        f"💰 首次虚拟补仓亏损记录: {position['symbol']} "
                        f"建仓价={entry_price:.6f}, 实际价={current_price:.6f}, "
                        f"阈值价={threshold_exit_price:.6f}(-18%), "
                        f"记录亏损=${threshold_loss:.2f}({abs(threshold_loss_rate)*100:.0f}%本金)"
                    )
                # 后续虚拟补仓不更新real_exit_price和real_pnl
                
                position['has_add_position'] = True  # 标记触发了补仓逻辑
                
                # ⚠️ 重要：返回，避免继续执行补仓逻辑
                return
                
                logging.info(
                    f"💭 转为虚拟跟踪: {position['symbol']} "
                    f"首仓价:{entry_price:.4f} 止损价:{current_price:.4f} "
                    f"虚拟平均价:{virtual_avg_price:.4f} "
                    f"继续占用槽位，等待虚拟止盈/止损"
                )
                
            else:
                # 实际补仓模式
                position_value = self.capital * self.add_position_size_ratio
                
                # 🆕 检查可用资金余额是否足够补仓
                if self.available_capital < position_value:
                    locked_capital = self.capital - self.available_capital
                    logging.warning(
                        f"⚠️ 可用资金不足，无法补仓: {position['symbol']} "
                        f"需要${position_value:.2f}，可用${self.available_capital:.2f} "
                        f"(总资金${self.capital:.2f}，已锁定${locked_capital:.2f})"
                    )
                    return
                
                # 补仓金额（考虑杠杆）
                add_size = (position_value * self.leverage) / current_price
                
                # 重新计算平均成本
                total_value = (position['avg_entry_price'] * position['position_size']) + (current_price * add_size)
                total_size = position['position_size'] + add_size
                new_avg_price = total_value / total_size
                
                # 更新持仓信息
                position['has_add_position'] = True
                position['add_position_price'] = current_price
                position['add_position_size'] = add_size
                position['avg_entry_price'] = new_avg_price
                position['position_size'] = total_size
                
                # 💰 复利模式：补仓时扣除投入资金（从可用资金中扣除）
                self.available_capital -= position_value
                
                # 💰 更新持仓的总投入（用于平仓时返还本金）
                position['position_value'] += position_value
                
                locked_capital = self.capital - self.available_capital
                logging.info(
                    f"➕ 实际补仓: {position['symbol']} {current_date} 价格:{current_price:.4f} "
                    f"补仓${position_value:.2f} 新平均价:{new_avg_price:.4f} 剩余资金:${self.capital:.2f}"
                )
        except Exception as e:
            logging.error(f"补仓失败: {e}")

    def exit_position(self, position: Dict, exit_price: float, exit_date: str, exit_reason: str):
        """平仓操作
        
        支持虚拟平仓：
        - 如果是虚拟跟踪模式（is_virtual_tracking=True），不影响资金
        - 只从positions列表移除，释放槽位
        """
        try:
            # 🆕 虚拟平仓模式：不影响资金
            if position.get('is_virtual_tracking', False):
                # 使用虚拟建仓价计算盈亏（仅用于记录）
                entry_price = position['virtual_entry_price']
                # position_size已经在add_position时清零了，这里用虚拟值
                position_size = position['position_size'] if position['position_size'] > 0 else 0
                
                # 虚拟盈亏（不影响实际资金）
                virtual_pnl = (exit_price - entry_price) * position_size if position_size > 0 else 0
                virtual_pnl_pct = (exit_price - entry_price) / entry_price * 100
                
                # 🆕 智能解析exit_date
                exit_datetime = None
                try:
                    if ' ' in exit_date:
                        exit_datetime = pd.to_datetime(exit_date)
                        exit_date_only = exit_datetime.strftime('%Y-%m-%d')
                    else:
                        exit_date_only = exit_date
                        exit_datetime = pd.to_datetime(exit_date + ' 00:00:00')
                except:
                    exit_date_only = exit_date.split(' ')[0] if ' ' in exit_date else exit_date
                    exit_datetime = pd.to_datetime(exit_date_only + ' 00:00:00')
                
                # 计算虚拟持仓天数
                virtual_entry_date = datetime.strptime(position['virtual_entry_date'], '%Y-%m-%d')
                exit_dt = datetime.strptime(exit_date_only, '%Y-%m-%d')
                virtual_hold_days = (exit_dt - virtual_entry_date).days
                
                # 💰 虚拟平仓时返还可用资金并计入实际盈亏
                # 🔧 关键修复：虚拟平仓时必须把首仓实际盈亏（real_pnl）计入总资金
                # - real_pnl（首仓实际盈亏）计入self.capital（影响复利）
                # - position_value返还到available_capital（释放锁定的资金）
                position_value = position['position_value']  # 包括首仓+虚拟补仓的总金额
                real_pnl = position.get('real_pnl', 0)  # 首仓实际盈亏
                self.capital += real_pnl  # ✅ 首仓实际盈亏计入总资金
                self.available_capital += position_value  # 🆕 释放锁定的可用资金
                
                # 更新持仓记录（标记为虚拟平仓）
                # 🔧 修改：亏损百分比按价格跌幅计算（18%），而非相对本金（72%）
                real_exit_price = position.get('real_exit_price', exit_price)
                original_entry_price = position['avg_entry_price']
                price_change_pct = (real_exit_price - original_entry_price) / original_entry_price * 100
                
                # 🔧 保存has_add_position标记，避免被update覆盖
                has_add_position = position.get('has_add_position', False)
                first_position_value = position.get('first_position_value')
                
                position.update({
                    'exit_date': exit_date_only,
                    'exit_datetime': exit_datetime.isoformat() if exit_datetime else None,
                    'exit_price': exit_price,
                    'exit_reason': f'virtual_{exit_reason}',  # 标记为虚拟平仓
                    'pnl': position.get('real_pnl', 0),  # 实际PnL是之前记录的虚拟亏损
                    'pnl_pct': price_change_pct,  # ✅ 按价格跌幅计算（-18%），而非相对本金（-72%）
                    'virtual_pnl': virtual_pnl,  # 记录虚拟盈亏
                    'virtual_pnl_pct': virtual_pnl_pct,
                    'hold_days': virtual_hold_days,
                    'real_exit_price': real_exit_price,  # 🔧 明确保留虚拟补仓触发时的价格
                    'has_add_position': has_add_position,  # 🔧 明确保留补仓标记
                })
                
                # 🔧 如果有first_position_value，也要保留
                if first_position_value is not None:
                    position['first_position_value'] = first_position_value
                
                # 从持仓列表中移除（释放槽位）
                if position in self.positions:
                    self.positions.remove(position)
                
                # 🆕 虚拟补仓补偿机制：记录需要补偿的虚拟补仓
                # 下次建仓时会增加投入金额来弥补虚拟补仓的首仓亏损
                self.pending_virtual_compensations += 1
                
                logging.info(
                    f"💭 虚拟平仓: {position['symbol']} {exit_date} 价格:{exit_price:.4f} "
                    f"虚拟盈亏:${virtual_pnl:.2f}({virtual_pnl_pct:+.1f}%) "
                    f"实际PnL:${real_pnl:.2f}（已计入总资金） 原因:{exit_reason} "
                    f"释放资金:${position_value:.2f} 总资金:${self.capital:.2f} 可用:${self.available_capital:.2f} "
                    f"✅ 释放槽位 📊 待补偿虚拟补仓: {self.pending_virtual_compensations}次"
                )
                return
            
            # 真实平仓模式
            entry_price = position['avg_entry_price']
            position_size = position['position_size']
            
            # 计算盈亏
            # 🔧 关键修复：区分虚拟平仓和观察模式平仓
            # - 虚拟平仓（资金未返还）：使用real_pnl（首仓实际亏损）
            # - 观察模式平仓（资金已返还）：正常计算盈亏（从建仓价到平仓价）
            if position.get('is_virtual_tracking', False) and 'real_pnl' in position and not position.get('capital_already_returned', False):
                # 虚拟跟踪仓位 + 资金未返还 → 使用首仓实际盈亏
                pnl = position['real_pnl']
                pnl_pct = pnl / position['position_value'] * 100 if position['position_value'] > 0 else 0
            else:
                # 正常仓位 OR 观察模式平仓 → 正常计算盈亏
                pnl = (exit_price - entry_price) * position_size
                pnl_pct = (exit_price - entry_price) / entry_price * 100
            
            # 🆕 智能解析exit_date，可能包含时间或只有日期
            exit_datetime = None
            try:
                # 尝试解析完整的日期时间
                if ' ' in exit_date:  # 包含时间
                    exit_datetime = pd.to_datetime(exit_date)
                    exit_date_only = exit_datetime.strftime('%Y-%m-%d')
                else:  # 只有日期
                    exit_date_only = exit_date
                    exit_datetime = pd.to_datetime(exit_date + ' 00:00:00')
            except:
                exit_date_only = exit_date.split(' ')[0] if ' ' in exit_date else exit_date
                exit_datetime = pd.to_datetime(exit_date_only + ' 00:00:00')
            
            # 计算持仓天数
            entry_date = datetime.strptime(position['entry_date'], '%Y-%m-%d')
            exit_dt = datetime.strptime(exit_date_only, '%Y-%m-%d')
            hold_days = (exit_dt - entry_date).days
            
            # 💰 复利模式：平仓时返还本金+盈亏（归还到可用资金）
            # 🔧 关键修复：避免重复返还资金
            if position.get('capital_already_returned', False):
                # 资金已经返还过了（虚拟补仓或观察模式时），只返还盈亏
                self.capital += pnl  # 盈亏计入总资金
                self.available_capital += pnl  # 🆕 盈亏也增加可用资金
                logging.info(f"💭 平仓（资金已返还）: {exit_reason} 只返还盈亏${pnl:.2f}，本金已在之前返还，资金:{self.capital:.2f}")
            elif position.get('is_virtual_tracking', False):
                # 🔧 关键修复：虚拟补仓仓位如果走了正常平仓路径
                # - 虚拟补仓从未扣除self.capital，所以不应该"返还"到self.capital
                # - 只返还available_capital（释放锁定的资金）
                # - 只有盈亏才计入self.capital
                logging.warning(f"⚠️ 警告：虚拟补仓仓位不应该走正常平仓路径: {position['symbol']}")
                position_value = position['position_value']  # 包括首仓+虚拟补仓
                self.capital += pnl  # ✅ 只有盈亏计入总资金（虚拟补仓从未扣过self.capital）
                self.available_capital += position_value + pnl  # ✅ 返还全部可用资金
                logging.info(f"💭 虚拟补仓平仓（异常路径）: {exit_reason} 仓位${position_value:.2f} 盈亏${pnl:.2f} 只返还盈亏到总资金 资金:{self.capital:.2f}")
            else:
                # 正常情况：返还全部本金到可用资金
                # 🔧 关键修复：建仓时只扣了available_capital，所以平仓时：
                # - position_value返还到available_capital（释放锁定的资金）
                # - pnl计入capital（盈亏影响总资金）
                position_value = position['position_value']
                self.capital += pnl  # ✅ 只有盈亏计入总资金（本金从未扣过capital）
                self.available_capital += position_value + pnl  # ✅ 返还全部到可用资金
                logging.info(f"💭 正常平仓: {exit_reason} 仓位${position_value:.2f} 盈亏${pnl:.2f} 资金:{self.capital:.2f}")
            
            # 更新持仓记录
            position.update({
                'exit_date': exit_date_only,
                'exit_datetime': exit_datetime.isoformat() if exit_datetime else None,  # 🆕 保存完整时间戳
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'hold_days': hold_days
            })
            
            # 从持仓列表中移除
            if position in self.positions:
                self.positions.remove(position)
            
            logging.info(f"💰 平仓: {position['symbol']} {exit_date} 价格:{exit_price:.4f} 盈亏:${pnl:.2f} ({pnl_pct:+.1f}%) 原因:{exit_reason} 当前资金:${self.capital:.2f}")
        except Exception as e:
            logging.error(f"平仓失败: {e}")

    def get_entry_price(self, symbol: str, date_str: str) -> Optional[float]:
        """获取开盘价作为建仓价格"""
        try:
            table_name = f'K1d{symbol}'
            
            query = text(f'''
                SELECT open
                FROM "{table_name}"
                WHERE trade_date = :date_str OR trade_date LIKE :date_like
            ''')
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {"date_str": date_str, "date_like": f'{date_str}%'}).fetchone()
            
            return result[0] if result and result[0] else None
        
        except Exception as e:
            logging.error(f"获取 {symbol} {date_str} 开盘价失败: {e}")
            return None

    def get_latest_5m_close(self, symbol: str, asof_dt: Optional[datetime] = None):
        """获取某交易对在 asof_dt 之前最近一根 5m K线的收盘价（用于持仓单的“当前浮盈亏”计算）

        数据来源：PostgreSQL `crypto_data` 的 `Kline5m_{symbol}` 表。
        返回：(trade_date_str, close_price)；若缺数据返回 (None, None)。
        """
        try:
            if not symbol:
                return None, None

            table_name = f'K5m{symbol}'

            with self.engine.connect() as conn:
                # 先检查表是否存在
                check_query = text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = :table_name")
                if conn.execute(check_query, {"table_name": table_name}).fetchone() is None:
                    return None, None

                if asof_dt is None:
                    asof_dt = datetime.now()
                asof_str = asof_dt.strftime('%Y-%m-%d %H:%M:%S')

                query = text(f'''
                SELECT trade_date, close
                FROM "{table_name}"
                WHERE trade_date <= :asof_str
                ORDER BY trade_date DESC
                LIMIT 1
                ''')
                
                row = conn.execute(query, {"asof_str": asof_str}).fetchone()
                
                if not row:
                    return None, None
                trade_date, close = row[0], row[1]
                if close is None:
                    return trade_date, None
                return trade_date, float(close)
        except Exception:
            return None, None

    def get_5m_closes_in_window(self, symbol: str, start_dt: datetime, end_dt: datetime) -> List[float]:
        """获取指定时间窗口内的 5m K线 close 序列（按时间正序）。

        数据来源：PostgreSQL `crypto_data` 的 `Kline5m_{symbol}` 表。
        """
        try:
            if not symbol:
                return []

            table_name = f'K5m{symbol}'

            with self.engine.connect() as conn:
                # 检查表是否存在
                check_query = text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = :table_name")
                if conn.execute(check_query, {"table_name": table_name}).fetchone() is None:
                    return []

                start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')

                query = text(f'''
                SELECT close
                FROM "{table_name}"
                WHERE trade_date >= :start_str AND trade_date < :end_str
                ORDER BY trade_date ASC
                ''')
                
                rows = conn.execute(query, {"start_str": start_str, "end_str": end_str}).fetchall()
                
                closes: List[float] = []
                for (c,) in rows:
                    if c is None:
                        continue
                    closes.append(float(c))
                return closes
        except Exception as e:
            logging.debug(f"读取5m close失败 {symbol}: {e}")
            return []

    def run_backtest(self, start_date: str, end_date: str):
        """运行回测"""
        # 保存回测结束日期，供CSV里计算“未平仓持仓”的持仓时长使用
        self._backtest_end_date = end_date
        logging.info(f"开始买量暴涨策略回测（小时线优化版-修复后+性能优化）: {start_date} 到 {end_date}")
        logging.info(f"初始资金: ${self.initial_capital:,.2f}")
        logging.info(f"杠杆倍数: {self.leverage}x")
        logging.info(f"买量暴涨阈值: {self.buy_surge_threshold}倍（某小时买量 vs 昨日平均小时买量）")
        logging.info(f"等待策略: 2-3倍→5%（2-10倍均可进信号池，按倍数映射不同等待回调）")
        logging.info(f"最大持仓时间: {self.max_hold_hours:.0f}小时（{self.max_hold_hours/24:.0f}天）")
        
        # 🔧 兼容两种日期格式：'2025-11-01' 或 '2025-11-01 00:00:00'
        start_date_only = start_date.split()[0] if ' ' in start_date else start_date
        end_date_only = end_date.split()[0] if ' ' in end_date else end_date
        
        current_date = datetime.strptime(start_date_only, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date_only, '%Y-%m-%d')
        
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # 🆕 每天输出进度信息
            logging.info(f"📅 处理日期: {date_str} | 当前资金: ${self.capital:,.2f} | 持仓数: {len(self.positions)} | 待建仓信号: {len(self.pending_signals)}")
            
            # 记录每日资金
            self.daily_capital.append({
                'date': date_str,
                'capital': self.capital,
                'positions_count': len(self.positions)
            })
            
            # 检查现有持仓（直接使用小时K线，不依赖日K线）
            positions_to_check = self.positions.copy()
            for position in positions_to_check:
                try:
                    # 🔧 修复：不再依赖日K线，直接传入当前日期，check_exit_conditions内部会读取小时K线
                    # 传入一个虚拟price（不影响，因为函数内部用小时线数据）
                    self.check_exit_conditions(position, 0, date_str)
                
                except Exception as e:
                    logging.error(f"❌ 检查持仓失败 {position['symbol']}: {e}")
                    import traceback
                    logging.error(traceback.format_exc())
            
            # 检查待建仓信号（使用小时线数据）
            signals_to_remove = []
            for signal in self.pending_signals[:]:  # 复制列表避免迭代时修改
                symbol = signal['symbol']
                signal_close = signal['signal_close']
                buy_surge_ratio = signal['buy_surge_ratio']
                target_drop_pct = self.get_wait_drop_pct(buy_surge_ratio)
                target_price = signal_close * (1 + target_drop_pct)
                
                # 检查是否已持仓
                if any(pos['symbol'] == symbol for pos in self.positions):
                    signals_to_remove.append(signal)
                    continue
                
                # 检查是否超时
                if current_date > signal['timeout_datetime']:
                    logging.info(f"⏰ {symbol} 信号超时，放弃建仓（买量{buy_surge_ratio:.1f}倍）")
                    self._update_signal_record(symbol, signal.get('signal_date'), status='timeout', note='超时未成交')
                    signals_to_remove.append(signal)
                    continue
                
                # 获取小时线数据检查是否达到目标价格（优化：只查询信号日到当前日的数据）
                signal_date_str = signal['signal_datetime'].strftime('%Y-%m-%d')
                hourly_df = self.get_hourly_kline_data(symbol, start_date=signal_date_str, end_date=date_str)
                if not hourly_df.empty:
                    # 筛选信号日之后到当前日期的小时数据
                    hourly_df['trade_datetime'] = pd.to_datetime(hourly_df['trade_date'])
                    signal_datetime = signal['signal_datetime']
                    
                    # 🔧 修复：确保signal_datetime也是Timestamp类型，避免类型不匹配导致比较失效
                    if not isinstance(signal_datetime, pd.Timestamp):
                        signal_datetime = pd.Timestamp(signal_datetime)
                    
                    mask = (hourly_df['trade_datetime'] >= signal_datetime) & (hourly_df['trade_datetime'] <= current_date)
                    check_period_data = hourly_df[mask]
                    
                    # 检查是否有小时低点达到目标价格
                    for _, row in check_period_data.iterrows():
                        if row['low'] <= target_price:
                            # 达到目标价格，建仓
                            entry_price = target_price
                            entry_datetime = row['trade_datetime']
                            
                            # 🔧 修复：验证建仓时间不早于最早可建仓时间
                            if entry_datetime < signal_datetime:
                                logging.warning(f"⚠️ {symbol} 建仓时间异常：{entry_datetime} < 信号时间{signal_datetime}，跳过")
                                continue
                            
                            entry_date = entry_datetime.strftime('%Y-%m-%d')
                            
                            # 🔧 持仓数量检查（在尝试建仓前立即检查）
                            current_pos_count = len(self.positions)
                            if current_pos_count < self.max_daily_positions:  # 检查持仓数量限制
                                logging.debug(f"🔍 {symbol} 尝试建仓: 当前持仓{current_pos_count}/{self.max_daily_positions}")
                                before_trades = len(self.trade_records)
                                self.execute_trade(symbol, entry_price, entry_date, 
                                                 signal['signal_date'], buy_surge_ratio, 
                                                 entry_datetime=entry_datetime)  # 🆕 传入完整时间戳
                                if len(self.trade_records) > before_trades:
                                    logging.info(f"✅ {symbol} 达到目标跌幅{target_drop_pct*100:.0f}%，"
                                               f"信号时间{signal['signal_date']}，建仓时间{entry_datetime}，建仓价{entry_price:.6f}")
                                    self._update_signal_record(
                                        symbol,
                                        signal.get('signal_date'),
                                        status='entered',
                                        entry_datetime=entry_datetime,
                                        entry_price=entry_price,
                                        note='触发目标价并建仓'
                                    )
                                else:
                                    # execute_trade 内部可能因为资金/风控拒绝
                                    self._update_signal_record(
                                        symbol,
                                        signal.get('signal_date'),
                                        status='reached_not_entered',
                                        entry_datetime=entry_datetime,
                                        entry_price=entry_price,
                                        note='触发目标价但未建仓（资金/风控）'
                                    )
                            else:
                                # 🔧 持仓数达到上限，不能建仓
                                logging.warning(
                                    f"⚠️ {symbol} 触发目标价但持仓已满: 当前{current_pos_count}/{self.max_daily_positions}个，"
                                    f"信号时间{signal['signal_date']}，触发时间{entry_datetime}"
                                )
                                self._update_signal_record(
                                    symbol,
                                    signal.get('signal_date'),
                                    status='reached_position_full',
                                    entry_datetime=entry_datetime,
                                    entry_price=entry_price,
                                    note=f'触发目标价但持仓已满({current_pos_count}/{self.max_daily_positions})'
                                )
                            
                            signals_to_remove.append(signal)
                            break
            
            # 移除已处理的信号
            for signal in signals_to_remove:
                if signal in self.pending_signals:
                    self.pending_signals.remove(signal)
            
            # 🆕 寻找新的买量暴涨信号（优化版：每天检测1次）
            if len(self.positions) < self.max_daily_positions:
                # 🚀 每天检测1次，找出今天哪些小时的买量超过昨日
                logging.debug(f"🔍 开始扫描 {date_str} 的买量暴涨信号...")
                daily_signals = self.get_daily_1hour_surge_signals(date_str)
                logging.debug(f"✅ 扫描完成，发现 {len(daily_signals)} 个信号")
                
                for signal in daily_signals:
                    symbol = signal['symbol']
                    surge_ratio = signal['surge_ratio']
                    signal_price = signal['signal_price']
                    signal_datetime = signal['signal_datetime']  # 信号发生的小时（例如19:00）
                    
                    # 检查是否已在待建仓列表或已持仓
                    if any(s['symbol'] == symbol for s in self.pending_signals):
                        continue
                    if any(pos['symbol'] == symbol for pos in self.positions):
                        continue
                    
                    # 🆕 添加：顶级交易者数据筛选
                    passed, account_ratio, filter_reason = self.check_trader_signal_filter(symbol, signal_datetime)
                    if not passed:
                        logging.info(f"🚫 过滤信号: {symbol} 在 {signal_datetime} 买量暴涨 {surge_ratio:.1f}倍，"
                                    f"但{filter_reason}，跳过该信号")
                        # 记录被过滤的信号
                        self._update_signal_record(
                            symbol,
                            signal_datetime.strftime('%Y-%m-%d %H:%M'),
                            status='filtered_trader',
                            note=filter_reason
                        )
                        continue
                    else:
                        if account_ratio:
                            logging.info(f"✅ 通过顶级交易者筛选: {symbol} 账户多空比={account_ratio:.4f}")
                    
                    # 🔧 关键修复：小时K线数据只有在该小时结束后才能看到
                    # 例如19:00的K线，要到20:00才能看到完整数据
                    # 🎯 优化：信号后至少等待6小时才开始尝试建仓（基于数据分析，0-6小时胜率最低60.2%）
                    earliest_entry_datetime = signal_datetime + timedelta(hours=self.wait_min_hours)
                    
                    # 🎯 根据买量倍数动态设置等待回调比例
                    target_drop_pct = self.get_wait_drop_pct(surge_ratio)
                    timeout_datetime = earliest_entry_datetime + timedelta(hours=self.wait_timeout_hours)
                    
                    self.pending_signals.append({
                        'symbol': symbol,
                        'signal_date': signal_datetime.strftime('%Y-%m-%d %H:%M'),  # 保存原始信号时间用于显示
                        'signal_datetime': earliest_entry_datetime,  # 实际可以开始建仓的时间（信号时间+1小时）
                        'signal_close': signal_price,
                        'buy_surge_ratio': surge_ratio,
                        'target_drop_pct': target_drop_pct,
                        'timeout_datetime': timeout_datetime,
                        'signal_account_ratio': account_ratio  # 🆕 保存信号时的账户多空比
                    })

                    # 🆕 记录“发现信号”（用于输出未成交反馈表）
                    try:
                        self.signal_records.append({
                            'symbol': symbol,
                            'signal_date': signal_datetime.strftime('%Y-%m-%d %H:%M'),  # 与pending_signals一致，用于匹配更新
                            'signal_time': signal_datetime.strftime('%Y-%m-%d %H:00:00'),
                            'earliest_entry_time': earliest_entry_datetime.strftime('%Y-%m-%d %H:00:00'),
                            'signal_price': float(signal_price),
                            'buy_surge_ratio': float(surge_ratio),
                            'target_drop_pct': float(target_drop_pct),
                            'target_price': float(signal_price) * (1 + float(target_drop_pct)),
                            'timeout_time': timeout_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                            'status': 'pending',
                            'entry_time': '',
                            'entry_price': '',
                            'note': ''
                        })
                    except Exception:
                        pass
                    
                    logging.info(f"🔔 新信号: {symbol} @{signal_datetime.strftime('%H:00')} 买量{surge_ratio:.2f}倍，可建仓时间: {earliest_entry_datetime.strftime('%H:00')}")
            
            current_date += timedelta(days=1)
        
        # 最后一天：先用小时K线检查一次止盈/止损，避免错过应该止盈的机会
        logging.info(f"⏰ 回测结束，检查剩余{len(self.positions)}个持仓...")
        positions_to_check = self.positions.copy()
        for position in positions_to_check:
            try:
                # 先检查是否满足止盈/止损条件
                self.check_exit_conditions(position, 0, end_date)
            except Exception as e:
                logging.error(f"最后检查失败 {position['symbol']}: {e}")
        
        # 强制平仓剩余持仓（经过上面检查后还没平仓的）
        for position in self.positions.copy():
            try:
                table_name = f'K1d{position["symbol"]}'
                
                query = text(f'''
                    SELECT close
                    FROM "{table_name}"
                    WHERE trade_date = :end_date OR trade_date LIKE :end_date_like
                    ORDER BY trade_date DESC
                    LIMIT 1
                ''')
                
                with self.engine.connect() as conn:
                    result = conn.execute(query, {"end_date": end_date, "end_date_like": f'{end_date}%'}).fetchone()
                
                if result and result[0]:
                    exit_price = result[0]
                    # 记录当前应该使用的止盈阈值（用于CSV）
                    if position.get('entry_datetime'):
                        entry_datetime = pd.to_datetime(position['entry_datetime'])
                        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                        hourly_df = pd.DataFrame()  # 空的，因为只是为了获取当前止盈阈值
                        current_tp = self.calculate_dynamic_take_profit(position, hourly_df, entry_datetime, end_datetime)
                        position['tp_pct_used'] = current_tp
                    
                    self.exit_position(position, exit_price, end_date, "force_close")
                    logging.warning(f"⚠️ 强制平仓: {position['symbol']} 价格:{exit_price:.4f}")
            
            except Exception as e:
                logging.error(f"强制平仓失败: {e}")
        
        logging.info("回测完成")

    def generate_report(self):
        """生成回测报告"""
        print("\n" + "="*80)
        print("🚀 买量暴涨策略回测报告")
        print("="*80)
        
        # 基本统计
        total_trades = len(self.trade_records)
        winning_trades = len([t for t in self.trade_records if t['pnl'] > 0])
        losing_trades = len([t for t in self.trade_records if t['pnl'] < 0])
        
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 资金统计
        final_capital = self.capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        
        # 最大回撤计算
        max_capital = self.initial_capital
        max_drawdown = 0
        
        for record in self.daily_capital:
            max_capital = max(max_capital, record['capital'])
            drawdown = (max_capital - record['capital']) / max_capital * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        print(f"💰 初始资金: ${self.initial_capital:,.2f}")
        print(f"💰 最终资金: ${final_capital:,.2f}")
        print(f"📈 总收益率: {total_return:+.2f}%")
        print(f"📊 总交易次数: {total_trades}")
        print(f"✅ 盈利交易: {winning_trades}")
        print(f"❌ 亏损交易: {losing_trades}")
        print(f"🎯 胜率: {win_rate:.1f}%")
        print(f"📉 最大回撤: {max_drawdown:.2f}%")
        
        # 生成CSV详细报告
        self.generate_trade_csv_report()

        # 🆕 生成“信号反馈表”（包含发现但未成交的信号）
        self.generate_signal_csv_report()
        
        # 动态止盈统计分析
        print(f"\n{'='*80}")
        print("📊 动态止盈详细统计")
        print("="*80)
        
        # 统计不同止盈阈值的交易（只统计已平仓的）
        closed_trades = [t for t in self.trade_records if t.get('exit_reason') and t['exit_reason'] != 'holding']
        
        # 区分高止盈和普通止盈（使用tp_pct_used字段）
        trades_with_high_tp = [t for t in closed_trades if t.get('tp_pct_used') and t['tp_pct_used'] > 0.10]
        trades_with_normal_tp = [t for t in closed_trades if t.get('tp_pct_used') and t['tp_pct_used'] <= 0.10]
        
        high_tp_triggered = len(trades_with_high_tp)
        normal_tp_count = len(trades_with_normal_tp)
        total_closed = len(closed_trades)
        
        print(f"\n💰 止盈触发统计 (已平仓{total_closed}笔):")
        if total_closed > 0:
            print(f"  🚀 动态止盈(>10%)触发: {high_tp_triggered}次 ({high_tp_triggered/total_closed*100:.1f}%)")
            print(f"  📊 普通止盈(≤10%)触发: {normal_tp_count}次 ({normal_tp_count/total_closed*100:.1f}%)")
            print(f"  ⏳ 其他平仓: {total_closed-high_tp_triggered-normal_tp_count}次 ({(total_closed-high_tp_triggered-normal_tp_count)/total_closed*100:.1f}%)")
        
        # 动态止盈成功率分析
        if high_tp_triggered > 0:
            high_tp_success = len([t for t in trades_with_high_tp if t.get('exit_reason') == 'take_profit'])
            high_tp_profit = sum([t['pnl'] for t in trades_with_high_tp])
            high_tp_avg_profit = high_tp_profit / high_tp_triggered
            
            print(f"\n✅ 动态止盈表现:")
            print(f"  触发次数: {high_tp_triggered}次")
            print(f"  成功止盈: {high_tp_success}次")
            print(f"  成功率: {high_tp_success/high_tp_triggered*100:.1f}%")
            print(f"  总贡献: ${high_tp_profit:,.2f}")
            print(f"  平均收益: ${high_tp_avg_profit:,.2f}")
        
        # 普通止盈统计
        if normal_tp_count > 0:
            normal_tp_profit = sum([t['pnl'] for t in trades_with_normal_tp])
            normal_tp_avg = normal_tp_profit / normal_tp_count
            
            print(f"\n📈 普通止盈表现:")
            print(f"  触发次数: {normal_tp_count}次")
            print(f"  总贡献: ${normal_tp_profit:,.2f}")
            print(f"  平均收益: ${normal_tp_avg:,.2f}")
        
        # 止损、超时和强制平仓统计
        stop_loss_trades = [t for t in closed_trades if t.get('exit_reason') == 'stop_loss']
        max_hold_trades = [t for t in closed_trades if t.get('exit_reason') == 'max_hold_time']
        force_close_trades = [t for t in closed_trades if t.get('exit_reason') == 'force_close']
        
        if stop_loss_trades:
            stop_loss_total = sum([t['pnl'] for t in stop_loss_trades])
            print(f"\n⚠️ 止损统计:")
            print(f"  止损次数: {len(stop_loss_trades)}次 ({len(stop_loss_trades)/total_closed*100:.1f}%)")
            print(f"  止损损失: ${stop_loss_total:,.2f}")
        
        if max_hold_trades:
            max_hold_profit = sum([t['pnl'] for t in max_hold_trades])
            max_hold_positive = len([t for t in max_hold_trades if t['pnl'] > 0])
            print(f"\n⏰ 超时平仓统计:")
            print(f"  超时次数: {len(max_hold_trades)}次 ({len(max_hold_trades)/total_closed*100:.1f}%)")
            print(f"  盈利: {max_hold_positive}次, 亏损: {len(max_hold_trades)-max_hold_positive}次")
            print(f"  总盈亏: ${max_hold_profit:,.2f}")
        
        if force_close_trades:
            force_close_profit = sum([t['pnl'] for t in force_close_trades])
            force_close_positive = len([t for t in force_close_trades if t['pnl'] > 0])
            print(f"\n🔚 回测结束强制平仓:")
            print(f"  强制平仓: {len(force_close_trades)}次 ({len(force_close_trades)/total_closed*100:.1f}%)")
            print(f"  盈利: {force_close_positive}次, 亏损: {len(force_close_trades)-force_close_positive}次")
            print(f"  总盈亏: ${force_close_profit:,.2f}")
            print(f"  ℹ️ 注意：强制平仓的交易可能还未达到最佳止盈点")
        
        # 详细交易记录
        print(f"\n{'='*80}")
        print(f"📋 详细交易记录 (前20条):")
        print("-" * 120)
        print(f"{'序号':<4} {'交易对':<15} {'买量倍数':<10} {'建仓日期':<12} {'建仓价':>10} {'平仓日期':<12} {'平仓价':>10} {'盈亏':>12} {'持仓天数':<10}")
        print("-" * 120)
        
        for i, trade in enumerate(self.trade_records[:20], 1):
            exit_info = f"{trade['exit_price']:.4f}" if trade['exit_price'] else "-"
            pnl_info = f"${trade['pnl']:+.2f}" if trade['pnl'] != 0 else "-"
            surge_ratio = f"{trade.get('buy_surge_ratio', 0):.1f}x"
            
            print(f"{i:<4} {trade['symbol']:<15} {surge_ratio:<10} {trade['entry_date']:<12} {trade['entry_price']:<10.4f} "
                  f"{trade['exit_date'] or '-':<12} {exit_info:>10} {pnl_info:>12} {trade.get('hold_days', 0):<10}")

    def generate_trade_csv_report(self):
        """生成交易详细CSV报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"buy_surge_backtest_report_{timestamp}.csv"
        
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    '序号', '交易对', '买量暴涨倍数', '信号时间', '建仓日期', '建仓具体时间', '建仓价', 
                    '平仓日期', '平仓具体时间', '平仓价', '盈亏金额', '盈亏百分比', '平仓原因', '杠杆倍数', '仓位金额',
                    '是否有补仓', '补仓价格', '补仓后平均价', '持仓小时数', '最大跌幅%', '2小时最大涨幅%', '24小时最大涨幅%', '止盈阈值%',
                    # 🆕 添加顶级交易者数据字段
                    '建仓时账户多空比', '平仓时账户多空比', '账户多空比变化',
                    # 🆕 未平仓持仓的“当前浮盈亏”（按本地5m最新close做mark-to-market）
                    '当前5m时间', '当前5m收盘价', '当前浮盈金额', '当前浮盈百分比'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # 输出“已建仓”的交易：包含已平仓 + 回测结束时仍持仓（原来就是这样展示的）
                entered_trades = [
                    t for t in self.trade_records
                    if t.get('entry_date') and t.get('entry_price')
                ]

                for i, trade in enumerate(entered_trades, 1):
                    # 计算补仓后平均价
                    avg_price_after_add = ''
                    if trade.get('has_add_position', False) and trade.get('add_position_price'):
                        avg_price_after_add = f"{trade['avg_entry_price']:.6f}"
                    
                    # 🆕 获取建仓具体时间
                    entry_datetime_str = ''
                    if trade.get('entry_datetime'):
                        try:
                            if isinstance(trade['entry_datetime'], str):
                                entry_dt = pd.to_datetime(trade['entry_datetime'])
                            else:
                                entry_dt = trade['entry_datetime']
                            entry_datetime_str = entry_dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            entry_datetime_str = trade.get('entry_date', '') + ' 00:00:00'
                    else:
                        entry_datetime_str = trade.get('entry_date', '') + ' 00:00:00'
                    
                    # 🆕 获取平仓具体时间
                    exit_datetime_str = ''
                    if trade.get('exit_datetime'):
                        try:
                            if isinstance(trade['exit_datetime'], str):
                                exit_dt = pd.to_datetime(trade['exit_datetime'])
                            else:
                                exit_dt = trade['exit_datetime']
                            exit_datetime_str = exit_dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            exit_datetime_str = trade.get('exit_date', '') + ' 00:00:00' if trade.get('exit_date') else ''
                    else:
                        exit_datetime_str = trade.get('exit_date', '') + ' 00:00:00' if trade.get('exit_date') else ''
                    
                    # 🆕 计算持仓小时数（未平仓则计算到回测结束日23:59:59）
                    hold_hours = 0
                    try:
                        if trade.get('entry_datetime'):
                            entry_dt = pd.to_datetime(trade['entry_datetime'])
                        else:
                            entry_dt = datetime.strptime(trade.get('entry_date', ''), '%Y-%m-%d')

                        if trade.get('exit_datetime'):
                            exit_dt = pd.to_datetime(trade['exit_datetime'])
                        elif trade.get('exit_date'):
                            exit_dt = pd.to_datetime(trade['exit_date'] + ' 23:59:59')
                        else:
                            end_date = getattr(self, '_backtest_end_date', None)
                            exit_dt = pd.to_datetime((end_date or trade.get('entry_date')) + ' 23:59:59')

                        hold_hours = round((exit_dt - entry_dt).total_seconds() / 3600, 1)
                    except Exception:
                        hold_hours = trade.get('hold_days', 0) * 24

                    # 🆕 若未平仓：用“当前时间最近一根5m close”计算浮盈亏（不会影响回测统计，仅用于观察）
                    m2m_trade_time = ''
                    m2m_close = ''
                    m2m_pnl_amt = ''
                    m2m_pnl_pct = ''
                    if not trade.get('exit_date'):
                        td, close = self.get_latest_5m_close(trade['symbol'])
                        if td and close is not None:
                            m2m_trade_time = td
                            m2m_close = f"{close:.6f}"
                            try:
                                entry_price_for_pnl = float(trade.get('avg_entry_price') or trade.get('entry_price') or 0)
                                position_size = float(trade.get('position_size') or 0)
                                if entry_price_for_pnl > 0 and position_size > 0:
                                    upnl = (close - entry_price_for_pnl) * position_size
                                    upnl_pct = (close - entry_price_for_pnl) / entry_price_for_pnl * 100
                                    m2m_pnl_amt = f"{upnl:.2f}"
                                    m2m_pnl_pct = f"{upnl_pct:.2f}%"
                            except Exception:
                                pass
                    
                    row = {
                        '序号': i,
                        '交易对': trade['symbol'],
                        '买量暴涨倍数': f"{trade.get('buy_surge_ratio', 0):.1f}倍",
                        '信号时间': trade.get('signal_date', ''),  # 🆕 信号时间（已经包含小时）
                        '建仓日期': trade['entry_date'],
                        '建仓具体时间': entry_datetime_str,
                        '建仓价': f"{trade['entry_price']:.6f}",
                        '平仓日期': trade.get('exit_date', ''),
                        # 🆕 平仓具体时间：未平仓时用估值5m时间（便于你看"按哪个时刻估值"）
                        '平仓具体时间': exit_datetime_str if trade.get('exit_date') else (m2m_trade_time or ''),
                        # 🆕 平仓价：虚拟补仓交易显示虚拟补仓触发时的价格（-18%阈值价），否则显示最终平仓价
                        '平仓价': (
                            f"{trade.get('real_exit_price', trade.get('exit_price', 0)):.6f}" 
                            if trade.get('is_virtual_tracking') and trade.get('has_add_position') and trade.get('exit_date')
                            else (f"{trade.get('exit_price', 0):.6f}" if trade.get('exit_price') else '')
                        ) if trade.get('exit_date') else (m2m_close or ''),
                        # 🆕 盈亏：虚拟补仓交易使用real_pnl（首仓实际亏损），否则使用pnl
                        '盈亏金额': (
                            f"{trade.get('real_pnl', trade.get('pnl', 0)):.2f}" 
                            if trade.get('is_virtual_tracking') and trade.get('exit_date')
                            else f"{trade.get('pnl', 0):.2f}"
                        ) if trade.get('exit_date') else (m2m_pnl_amt or ''),
                        '盈亏百分比': f"{trade.get('pnl_pct', 0):.2f}%" if trade.get('exit_date') else (m2m_pnl_pct or ''),
                        '平仓原因': trade.get('exit_reason', '') or ('holding' if not trade.get('exit_date') else ''),
                        '杠杆倍数': trade['leverage'],
                        # 🔧 虚拟补仓交易：显示首次投入金额（不含虚拟补仓），确保亏损占比正确显示为72%
                        '仓位金额': (
                            f"{trade.get('first_position_value', trade['position_value']):.2f}"
                            if trade.get('is_virtual_tracking') and trade.get('has_add_position')
                            else f"{trade['position_value']:.2f}"
                        ),
                        '是否有补仓': '✅是' if trade.get('has_add_position', False) else '否',
                        '补仓价格': f"{trade.get('add_position_price', 0):.6f}" if trade.get('add_position_price') else '',
                        '补仓后平均价': avg_price_after_add,
                        '持仓小时数': hold_hours,  # 🆕 改为小时数
                        '最大跌幅%': f"{trade.get('max_drawdown', 0)*100:.2f}%" if trade.get('max_drawdown') else '0.00%',
                        '2小时最大涨幅%': (
                            f"{float(trade.get('max_up_2h'))*100:.2f}%" if trade.get('max_up_2h') is not None else ''
                        ),
                        '24小时最大涨幅%': (
                            f"{float(trade.get('max_up_24h'))*100:.2f}%" if trade.get('max_up_24h') is not None else ''
                        ),
                        # 真实止盈阈值（仅 take_profit 平仓时有意义）
                        # - 旧版这里用 .0f 会把 8.5% 四舍五入成 8%，导致误判“动态止盈没生效”
                        '止盈阈值%': (
                            f"{float(trade.get('tp_pct_used'))*100:.1f}%" if trade.get('tp_pct_used') else ''
                        ),
                        # 🆕 添加顶级交易者数据
                        '建仓时账户多空比': f"{trade.get('entry_account_ratio', 0):.4f}" if trade.get('entry_account_ratio') else "",
                        '平仓时账户多空比': f"{trade.get('current_account_ratio', 0):.4f}" if trade.get('current_account_ratio') else "",
                        '账户多空比变化': f"{trade.get('account_ratio_change', 0):.4f}" if trade.get('account_ratio_change') else "",
                        '当前5m时间': m2m_trade_time,
                        '当前5m收盘价': m2m_close,
                        '当前浮盈金额': m2m_pnl_amt,
                        '当前浮盈百分比': m2m_pnl_pct
                    }
                    writer.writerow(row)
            
            print(f"📄 交易详细CSV报告已生成: {csv_filename}")
            
            # 🆕 自动运行 CSV 校验
            try:
                # 添加 validate_csv_with_kline.py 的目录到 sys.path
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.append(current_dir)
                
                from validate_csv_with_kline import KlineCSVValidator
                
                print(f"\n🚀 正在对生成的 CSV 报告进行 K 线数据校验...")
                validator = KlineCSVValidator(csv_filename)
                results = validator.validate()
                report_path = validator.save_report()
                
                print(f"✅ 校验完成，报告已保存到: {report_path}")
                
                # 打印校验摘要
                total_issues = (
                    len(results['entry_price_issues']) +
                    len(results['exit_price_issues']) +
                    len(results.get('pnl_consistency_issues', [])) +
                    len(results['errors'])
                )
                
                if total_issues == 0:
                    print("🎉 完美！所有交易记录都通过了 K 线数据校验")
                else:
                    print(f"⚠️  发现 {total_issues} 个校验问题，请查看报告详情")
                    
            except Exception as e:
                print(f"❌ 自动校验失败: {e}")
                import traceback
                traceback.print_exc()
        
        except Exception as e:
            print(f"❌ 生成CSV报告失败: {e}")

    def _update_signal_record(self, symbol: str, signal_date: str, status: str,
                              entry_datetime=None, entry_price=None, note: str = ''):
        """更新信号记录状态（用于反馈表）"""
        if not symbol or not signal_date:
            return
        sd = str(signal_date)
        for rec in reversed(self.signal_records):
            if rec.get('symbol') == symbol and str(rec.get('signal_date')) == sd:
                rec['status'] = status
                if entry_datetime is not None and hasattr(entry_datetime, 'strftime'):
                    rec['entry_time'] = entry_datetime.strftime('%Y-%m-%d %H:%M:%S')
                if entry_price is not None:
                    try:
                        rec['entry_price'] = f"{float(entry_price):.6f}"
                    except Exception:
                        rec['entry_price'] = str(entry_price)
                if note:
                    rec['note'] = note
                return

    def generate_signal_csv_report(self):
        """生成信号反馈CSV（包含：发现信号但未成交）"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"buy_surge_signal_feedback_{timestamp}.csv"
        try:
            # 反馈表允许包含“未成交信号”（用于核对FHE/BDXN等为什么没成交）
            for rec in self.signal_records:
                if rec.get('status') == 'pending':
                    rec['status'] = 'unfilled'
                    if not rec.get('note'):
                        rec['note'] = '回测区间内未触发目标价/未成交'

            import csv
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    'symbol', 'buy_surge_ratio', 'signal_time', 'signal_date', 'earliest_entry_time',
                    'signal_price', 'target_drop_pct', 'target_price', 'timeout_time',
                    'status', 'entry_time', 'entry_price', 'note'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for rec in self.signal_records:
                    writer.writerow({k: rec.get(k, '') for k in fieldnames})

            print(f"📄 信号反馈CSV已生成(含未成交): {csv_filename}")
        except Exception as e:
            print(f"❌ 生成信号反馈CSV失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='买量暴涨策略回测程序')
    parser.add_argument(
        '--start-time',
        type=str,
        default='2025-11-01',
        help='开始日期(默认: 2025-11-01)'
    )
    parser.add_argument(
        '--end-time',
        type=str,
        default='2026-01-10',
        help='结束日期(默认: 2026-01-10)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=13.1,
        help='买量暴涨阈值(默认: 13.1倍)'
    )

    parser.add_argument(
        '--max-multiple',
        type=float,
        default=3.0,
        help='买量暴涨倍数上限（默认3.0；例如3表示只做2-3倍; 10表示2-10倍）'
    )

    parser.add_argument(
        '--dynamic-tp-boost',
        type=float,
        default=None,
        help='动态止盈加成幅度（传入则覆盖按倍数分档的加成；例如 0.05 表示统一 +5%%）'
    )

    parser.add_argument(
        '--dynamic-tp-lookback-minutes',
        type=int,
        default=720,
        help='动态止盈"强势判定"窗口长度（分钟; 默认720=12小时；基于数据分析最佳判定时机）'
    )

    parser.add_argument(
        '--dynamic-tp-close-up-pct',
        type=float,
        default=0.025,
        help='动态止盈强势判定：5m close 需要高于建仓价的涨幅比例（默认0.025=+2.5%%; 12小时分水岭）'
    )

    parser.add_argument(
        '--enable-trader-filter',
        action='store_true',
        default=False,
        help='启用顶级交易者数据风控（默认关闭）'
    )

    parser.add_argument(
        '--min-account-ratio',
        type=float,
        default=0.84,
        help='最小账户多空比阈值（默认0.84; 平衡型）'
    )

    parser.add_argument(
        '--account-stop-threshold',
        type=float,
        default=-0.10,
        help='账户多空比下降止损阈值（默认-0.10; 平衡型）'
    )
    
    args = parser.parse_args()
    
    backtest = BuySurgeBacktest()
    
    # 可以通过参数调整阈值
    if args.threshold:
        backtest.buy_surge_threshold = args.threshold
        logging.info(f"买量暴涨阈值设置为: {args.threshold}倍")

    if args.max_multiple is not None:
        backtest.buy_surge_max = float(args.max_multiple)
        logging.info(f"买量暴涨倍数上限设置为: {backtest.buy_surge_max}倍")

    # 若显式传入 --dynamic-tp-boost，则用“统一加成”覆盖分档配置（便于做对照实验）
    if args.dynamic_tp_boost is not None:
        backtest.dynamic_tp_boost_pct = float(args.dynamic_tp_boost)
        backtest.dynamic_tp_boost_config = [(9999, backtest.dynamic_tp_boost_pct)]
        logging.info(f"动态止盈加成幅度设置为(覆盖分档): +{backtest.dynamic_tp_boost_pct*100:.1f}%")

    if args.dynamic_tp_lookback_minutes is not None:
        backtest.dynamic_tp_lookback_minutes = int(args.dynamic_tp_lookback_minutes)
        logging.info(f"动态止盈强势判定窗口设置为: {backtest.dynamic_tp_lookback_minutes}分钟")

    if args.dynamic_tp_close_up_pct is not None:
        backtest.dynamic_tp_close_up_pct = float(args.dynamic_tp_close_up_pct)
        logging.info(f"动态止盈强势判定涨幅阈值设置为: +{backtest.dynamic_tp_close_up_pct*100:.1f}%")
    
    # 🆕 应用顶级交易者风控参数
    if args.enable_trader_filter:
        backtest.enable_trader_filter = True
        backtest.min_account_ratio = args.min_account_ratio
        backtest.account_ratio_stop_threshold = args.account_stop_threshold
        logging.info(f"✅ 启用顶级交易者风控")
        logging.info(f"   - 最小账户多空比: {backtest.min_account_ratio}")
        logging.info(f"   - 下降止损阈值: {backtest.account_ratio_stop_threshold}")
    
    try:
        # 运行回测
        backtest.run_backtest(args.start_time, args.end_time)
        
        # 生成报告
        backtest.generate_report()
    
    except KeyboardInterrupt:
        logging.info("用户中断回测")
    except Exception as e:
        logging.error(f"回测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logging.info("回测程序结束")

if __name__ == "__main__":
    main()
