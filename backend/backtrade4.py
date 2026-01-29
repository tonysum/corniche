"""
根据U本位合约K线数据模拟交易脚本

功能：
1. 从本地SQLite数据库（crypto_data.db）读取所有USDT交易对的K线数据
2. 计算每天的涨幅（pct_chg），找出涨幅第一的交易对
3. 每天建仓一个交易对（涨幅第一的），除非该交易对已在持仓中且未止盈
4. 建仓策略：
   - 初始资金：10000 USDT
   - 每次建仓金额：账户余额的3%
   - 杠杆：3倍
   - 建仓条件：涨幅>=20% 且 该交易对未持仓
   - 建仓方向：卖空（做空）
   - 建仓价格：第二天开盘价
5. 平仓策略：
   - 止盈：价格下跌20%时盈利平仓（买入平仓）
   - 止损：价格上涨49%时止损平仓（买入平仓）
#    - 补仓：第一次触发止损时，进行补仓（补仓数量=持仓数量），补仓后重新计算平均建仓价和止盈止损价格
#    - 如果已补仓过，再次触发止损则直接平仓
6. 持仓管理：
   - 支持同时持有多个仓位
   - 已开仓的交易对在未平仓期间，不重复建仓同一交易对
   - 每天检查所有持仓的平仓条件
7. 数据保存：
   - 交易记录保存到SQLite数据库（backtrade_records表）
   - 交易记录保存到CSV文件（backtrade_records_{start_date}_{end_date}.csv）

注意：本策略是做空策略，建仓方向是卖空，平仓方向是买入平仓
"""

import os
import logging
import re
import random
import sqlite3

import pandas as pd  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import text  # pyright: ignore[reportMissingImports]

from db import engine, create_table, create_trade_table
from data import get_local_symbols, get_local_kline_data, get_top_gainer_by_date, get_all_top_gainers, get_kline_data_for_date
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Backtrade4Backtest:
    """Backtrade4策略回测器"""
    
    def __init__(self):
        """初始化回测实例"""
        # 交易参数
        self.initial_capital = 10000.0  # 初始资金10000美金
        self.position_size_ratio = 0.1  # 每次建仓金额为账户余额的10%（基础仓位）
        self.min_pct_chg = 0.25  # 最小涨幅25%才建仓
        self.entry_rise_threshold = 0  # 等待开盘价上涨X%后建仓（0表示直接以开盘价建仓）
        self.entry_wait_hours = 24  # 最长等待时间（小时），超时则放弃该交易

        # 双向交易模式配置
        self.enable_long_trade = True  # 是否允许做多（需配合手动确认使用）
        self.trade_direction = 'auto'  # 交易方向: 'short'=只做空, 'long'=只做多, 'auto'=根据信号自动选择
        
        # 巨鲸数据阈值配置（手动确认参考）
        self.whale_config = {
            'long_signal_ratio': 200,     # 巨鲸多空比 > 200% 时建议做多
            'short_signal_ratio': 100,    # 巨鲸多空比 < 100% 时建议做空
            'danger_ratio': 300,          # 巨鲸多空比 > 300% 时绝对不做空
            'neutral_low': 100,           # 100-200% 区间观望
            'neutral_high': 200,
        }
        
        # 成交额分级仓位配置
        self.enable_volume_position_sizing = True  # 是否启用成交额分级仓位
        self.volume_position_config = [
            (1,   0.5),   # 成交额 < 1亿: 半仓（流动性差，风险高）
            (3,   0.7),   # 成交额 1-3亿: 7成仓
            (5,   0.85),  # 成交额 3-5亿: 8.5成仓
            (10,  1.0),   # 成交额 5-10亿: 满仓
            (999, 1.2),   # 成交额 > 10亿: 1.2倍仓（流动性充足）
        ]
        
        # 实盘模式配置
        self.is_live_trading = False  # 是否为实盘模式（True时需要手动确认）
        self.require_whale_confirm = True  # 实盘模式下是否需要手动确认巨鲸数据
        
        # 动态杠杆策略配置
        self.enable_dynamic_leverage = True  # 是否启用动态杠杆策略
        self.dynamic_strategy_config = [
            # (涨幅上限%, 杠杆倍数, 止盈%, 止损%, 补仓阈值%, 入场等待涨幅%)
            (25,  2, 0.30, 0.28, 0.30, 0.00),   # 极低涨幅(<25%): 2倍杠杆, 直接开盘建仓（不符合MIN_PCT_CHG，实际不会触发）
            (40,  2, 0.25, 0.45, 0.35, 0.01),   # 中低涨幅(25-40%): 2倍杠杆，止盈25%，止损45%，补仓35%，盈亏比1:1.8
            (60,  2, 0.25, 0.45, 0.35, 0.08),   # 中涨幅(40-60%): 2倍杠杆，止盈25%，止损45%，补仓35%，盈亏比1:1.8
            (90,  2, 0.25, 0.45, 0.40, 0.06),   # 大涨幅(60-90%): 2倍杠杆，止盈25%，止损45%，补仓40%，盈亏比1:1.8
            (999, 2, 0.25, 0.45, 0.40, 0.10),   # 特大涨幅(>=90%): 2倍杠杆，止盈25%，止损45%，补仓40%，盈亏比1:1.8
        ]
        
        # 最大涨幅风控配置
        self.enable_max_rise_filter = False  # 是否启用最大涨幅风控
        self.max_rise_before_entry = {
            (25, 40): 0.01,    # 25-40%涨幅，等待期间最大涨1%
            (40, 60): 0.08,    # 40-60%涨幅，等待期间最大涨08%
            (60, 90): 0.06,    # 60-90%涨幅，等待期间最大涨6%
            (90, 999): 0.10,   # >=90%涨幅，等待期间最大涨10%
        }
        
        # 成交额过滤配置
        self.enable_volume_filter = False  # 是否启用成交额过滤（暂时关闭）
        self.high_pct_chg_threshold = 50  # 高涨幅阈值（%）
        self.min_volume_for_high_pct = 2e8  # 高涨幅币的最小成交额（2亿）
        
        # 固定策略参数（当enable_dynamic_leverage=False时使用）
        self.leverage = 2  # 固定杠杆倍数
        self.profit_threshold = 0.3   # 固定止盈30%
        self.stop_loss_threshold = 0.35  # 固定止损35%
        self.add_position_threshold = 0.35  # 固定补仓阈值35%
        self.profit_threshold_after_add = 0.3  # 补仓后止盈（与止盈相同）
        
        # 实盘风控配置
        self.enable_risk_control = False  # 是否启用实盘风控检查
        self.risk_control_config = {
            'top_long_short_ratio_max': 2.0,  # 大户多空比 > 2.0 时放弃建仓
            'global_short_ratio_min': 0.45,  # 散户做空 > 45% 时警惕（反向指标）
            'open_interest_change_max': 0.15,  # 1小时持仓量增幅 > 15% 时警惕
            'taker_buy_sell_ratio_max': 1.8,  # 主动买卖比 > 1.8 时放弃建仓
            'funding_rate_max': 0.0005,  # 资金费率 > 0.05% 时警惕
            'max_danger_signals': 1,  # 超过1个危险信号时放弃
        }
        
        # 交易记录
        self.capital = self.initial_capital
        self.positions = []  # 当前持仓
        self.trade_records = []  # 交易记录
    


    def get_dynamic_params(self, entry_pct_chg: float) -> dict:
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
        if not self.enable_dynamic_leverage:
            # 使用固定参数
            return {
                'leverage': self.leverage,
                'profit_threshold': self.profit_threshold,
                'stop_loss_threshold': self.stop_loss_threshold,
                'add_position_threshold': self.add_position_threshold,
                'profit_threshold_after_add': self.profit_threshold_after_add,
                'entry_rise_threshold': self.entry_rise_threshold
            }
        
        # 根据涨幅匹配动态策略
        for max_pct, leverage, profit_th, stop_loss_th, add_pos_th, entry_rise in self.dynamic_strategy_config:
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
        _, leverage, profit_th, stop_loss_th, add_pos_th, entry_rise = self.dynamic_strategy_config[-1]
        return {
            'leverage': leverage,
            'profit_threshold': profit_th,
            'stop_loss_threshold': stop_loss_th,
            'add_position_threshold': add_pos_th,
            'profit_threshold_after_add': profit_th,
            'entry_rise_threshold': entry_rise  # 动态入场等待涨幅
        }


    def get_position_size_multiplier(self, volume_24h: float) -> float:
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
        if not self.enable_volume_position_sizing:
            return 1.0  # 不启用时返回基础仓位
        
        volume_yi = volume_24h / 1e8  # 转换为亿
        
        for threshold, multiplier in self.volume_position_config:
            if volume_yi < threshold:
                return multiplier
        
        # 默认返回最后一档
        return self.volume_position_config[-1][1]

    def get_volume_category(self, volume_24h: float) -> str:
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

    def generate_trade_signal(self, symbol: str, pct_chg: float, api_sentiment: Optional[dict]) -> dict:
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
                f"   • > {self.whale_config['danger_ratio']}%：❌ 绝对不做空，可考虑做多",
                f"   • {self.whale_config['neutral_high']}-{self.whale_config['danger_ratio']}%：⚠️ 观望，做空风险高",
                f"   • {self.whale_config['neutral_low']}-{self.whale_config['neutral_high']}%：➡️ 中性区间",
                f"   • < {self.whale_config['short_signal_ratio']}%：✅ 可以做空",
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
            result['suggested_direction'] = 'short' if self.trade_direction != 'long' else 'long'
            result['confidence'] = 60
        else:
            result['message'] = f"📈 {symbol} {rise_category}({pct_chg:.1f}%)，回调概率较高"
            result['suggested_direction'] = 'short'
            result['confidence'] = 70
        
        return result


    def print_trade_opportunity(self, symbol: str, pct_chg: float, entry_price: float, 
                               volume_24h: float, api_sentiment: Optional[dict]) -> dict:
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
        volume_cat = self.get_volume_category(volume_24h)
        position_mult = self.get_position_size_multiplier(volume_24h)
        print(f"   24h成交额: {volume_yi:.2f}亿 ({volume_cat})")
        print(f"   建议仓位: {position_mult*100:.0f}% 基础仓位")
        
        # 获取动态参数
        params = self.get_dynamic_params(pct_chg)
        print(f"\n⚙️ 动态参数:")
        print(f"   杠杆: {params['leverage']}x")
        print(f"   止盈: {params['profit_threshold']*100:.0f}%")
        print(f"   止损: {params['stop_loss_threshold']*100:.0f}%")
        print(f"   补仓阈值: {params['add_position_threshold']*100:.0f}%")
        
        # 生成交易信号
        signal = self.generate_trade_signal(symbol, pct_chg, api_sentiment)
        
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
        
        if self.is_live_trading and self.require_whale_confirm:
            print(f"\n⏳ 等待您确认巨鲸数据后输入交易决策...")
            print(f"   输入 'long' 做多 | 'short' 做空 | 'skip' 跳过")
        
        print("=" * 70 + "\n")
        
        return signal

    def get_user_trade_decision(self) -> str:
        """
        获取用户交易决策（实盘模式使用）
        
        Returns:
            str: 'long', 'short', 或 'skip'
        """
        if not self.is_live_trading or not self.require_whale_confirm:
            # 非实盘模式或不需要确认，返回默认做空
            return 'short' if self.trade_direction != 'long' else 'long'
        
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


    def get_market_sentiment(self, symbol: str) -> dict:
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
            
            # 4. 主动买入过强
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


    def check_risk_control(self, symbol: str, entry_pct_chg: float) -> dict:
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
        
        if not self.enable_risk_control:
            result['message'] = '风控检查已禁用'
            return result
        
        # 获取市场情绪数据
        sentiment = self.get_market_sentiment(symbol)
        result['sentiment_data'] = sentiment
        
        if not sentiment['success']:
            # 无法获取数据时，允许交易（可能是回测模式或API问题）
            result['message'] = '无法获取市场情绪数据，跳过风控检查'
            return result
        
        config = self.risk_control_config
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

    def get_hourly_kline_data(self, symbol: str) -> pd.DataFrame:
        """获取本地数据库中指定交易对的小时K线数据"""
        table_name = f'K1h{symbol}'
        safe_table_name = f'"{table_name}"'
        try:
            stmt = f"SELECT * FROM {safe_table_name} ORDER BY trade_date ASC"
            with engine.connect() as conn:
                result = conn.execute(text(stmt))
                data = result.fetchall()
                columns = result.keys()
            df = pd.DataFrame(data, columns=columns)
            return df
        except Exception as e:
            logging.warning(f"获取 {symbol} 小时K线数据失败: {e}")
            return pd.DataFrame()

    def get_24h_quote_volume(self, symbol: str, entry_datetime: str) -> float:
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
        safe_table_name = f'"{table_name}"'
        try:
            # 解析建仓时间
            if ' ' in entry_datetime:
                entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d %H:%M:%S')
            else:
                entry_dt = datetime.strptime(entry_datetime, '%Y-%m-%d')
            
            # 计算24小时前的时间
            start_dt = entry_dt - timedelta(hours=24)
            
            # 查询24小时内的成交额总和（PostgreSQL 使用单引号包裹字符串）
            query = f'''
                SELECT SUM(quote_volume) as total_volume
                FROM {safe_table_name}
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


    def find_entry_trigger_point(self, symbol: str, open_price: float, start_date: str, 
                                 rise_threshold: Optional[float] = None,
                                 wait_hours: Optional[int] = None,
                                 entry_pct_chg: float = 0) -> dict:
        """
        查找价格上涨到目标价的触发时间点
        
        Args:
            symbol: 交易对
            open_price: 开盘价
            start_date: 开始查找的日期（YYYY-MM-DD格式）
            rise_threshold: 上涨阈值（如0.05表示5%），默认使用实例变量
            wait_hours: 最长等待小时数，默认使用实例变量
            entry_pct_chg: 入场涨幅（第一天的涨幅百分比，用于风控）
        
        Returns:
            dict: {
                'triggered': bool,  # 是否触发
                'entry_price': float,  # 实际建仓价（目标价）
                'entry_datetime': str,  # 触发时间
                'hours_waited': int  # 等待的小时数
            }
        """
        if rise_threshold is None:
            rise_threshold = self.entry_rise_threshold
        if wait_hours is None:
            wait_hours = self.entry_wait_hours
        
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
        if self.enable_max_rise_filter and entry_pct_chg > 0:
            for (pct_min, pct_max), max_rise in self.max_rise_before_entry.items():
                if pct_min <= entry_pct_chg < pct_max:
                    max_rise_threshold = max_rise
                    break
        
        try:
            # 获取小时K线数据
            hourly_df = self.get_hourly_kline_data(symbol)
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
            
            # 循环结束后未触发，超时返回
            result['hours_waited'] = len(valid_data)
            return result
            
        except Exception as e:
            logging.error(f"查找 {symbol} 建仓触发点失败: {e}")
            return result


    def check_position_hourly(self, position: dict, current_capital: float, end_date: str) -> dict:
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
        dynamic_params = self.get_dynamic_params(entry_pct_chg)
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
            hourly_df = self.get_hourly_kline_data(symbol)
            if hourly_df.empty:
                # 如果没有小时K线数据，使用日线备用检查
                logging.debug(f"{symbol} 没有小时K线数据，使用日线备用检查")
                daily_result = self.check_daily_fallback(symbol, entry_date.split()[0], position, result)
                return daily_result

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

            # 最大检查小时数（15天 * 24小时 = 360小时）
            max_check_hours = 360
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
                    # 超过最大检查时间，强制平仓（使用当前市场价）
                    result['action'] = 'exit'
                    # 使用当前小时的收盘价作为平仓价
                    result['exit_price'] = float(hour_data['close'])
                    result['exit_datetime'] = hour_data['trade_date']
                    result['exit_reason'] = self.generate_exit_reason(f"持有时间超过15天，强制平仓", has_added_position)
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
                    result['exit_reason'] = self.generate_exit_reason(f"价格下跌{current_profit_threshold*100:.0f}%，持仓{hold_hours}小时止盈", has_added_position)
                    return result

                # 2. 检查补仓（未补仓且价格上涨达到阈值）- 使用动态参数
                if not has_added_position and price_change_high >= add_position_threshold:
                    # 计算补仓后的新平均价格
                    add_position_price = current_entry_price * (1 + add_position_threshold)
                    add_position_value = min(current_capital * self.position_size_ratio, current_capital)

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
                    result['exit_reason'] = self.generate_exit_reason(f"价格上涨{stop_loss_threshold*100:.0f}%，持仓{hold_hours}小时止损", has_added_position)
                    return result

                # 所有小时都检查完了，没有触发任何条件
                # 这意味着数据不足或者价格一直在安全范围内
                return result

        except Exception as e:
            logging.warning(f"逐小时检查 {symbol} 失败: {e}")
            import traceback
            traceback.print_exc()

        return result

    def check_daily_fallback(self, symbol: str, check_date: str, position: dict, result: dict) -> dict:
        """
        当没有小时线数据时的备用检查：使用日线数据检查整个持仓期间是否有止盈止损

        思路：检查从建仓日期到当前日期的所有日线数据，看是否有价格触发止盈止损条件
        """
        try:
            entry_price = position['entry_price']
            entry_date = position['entry_date']

            # 获取日线数据
            daily_df = get_local_kline_data(symbol)
            
            if daily_df.empty:
                return None

            # 解析建仓日期
            if ' ' in entry_date:
                entry_dt = datetime.strptime(entry_date.split()[0], '%Y-%m-%d')
            else:
                entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')

            # 解析检查日期
            check_dt = datetime.strptime(check_date, '%Y-%m-%d')

            # 获取建仓日期之后的所有日线数据（包括未来数据，因为这是回测）
            # 由于trade_date格式是 '2025-11-04 00:00:00.000000'，需要转换
            daily_df['date'] = pd.to_datetime(daily_df['trade_date'].str[:10])
            relevant_data = daily_df[daily_df['date'] >= entry_dt].copy()

            if relevant_data.empty:
                return None

            # 按日期排序
            relevant_data = relevant_data.sort_values('date')

            # 获取动态交易参数
            entry_pct_chg = position.get('entry_pct_chg', 30)
            dynamic_params = self.get_dynamic_params(entry_pct_chg)
            profit_threshold = dynamic_params['profit_threshold']
            stop_loss_threshold = dynamic_params['stop_loss_threshold']
            has_added_position = position.get('has_added_position', False)

            # 检查每一天的数据，看是否有触发条件
            for idx, daily_data in relevant_data.iterrows():
                high_price = daily_data['high']
                low_price = daily_data['low']
                trade_date = daily_data['trade_date'][:10]  # 提取日期部分

                # 做空交易：价格下跌我们盈利，价格上涨我们亏损
                price_change_high = (high_price - entry_price) / entry_price
                price_change_low = (low_price - entry_price) / entry_price

                if price_change_low <= -profit_threshold:
                    # 止盈：价格下跌超过阈值
                    result['action'] = 'exit'
                    result['exit_price'] = entry_price * (1 - profit_threshold)
                    result['exit_reason'] = self.generate_exit_reason(f"日线数据止盈（价格下跌{profit_threshold*100:.0f}%）", has_added_position)
                    result['exit_datetime'] = f"{trade_date} 12:00:00"
                    return result
                elif price_change_high >= stop_loss_threshold:
                    # 止损：价格上涨超过阈值
                    result['action'] = 'exit'
                    result['exit_price'] = entry_price * (1 + stop_loss_threshold)
                    result['exit_reason'] = self.generate_exit_reason(f"日线数据止损（价格上涨{stop_loss_threshold*100:.0f}%）", has_added_position)
                    result['exit_datetime'] = f"{trade_date} 12:00:00"
                    return result

            # 没有触发条件，继续持有
            result['action'] = 'none'
            return result
        except Exception as e:
            logging.warning(f"日线备用检查 {symbol} 在 {check_date} 失败: {e}")
            
            

    def generate_exit_reason(self, base_reason: str, has_added_position: bool) -> str:
        """生成平仓原因，包含补仓信息"""
        if has_added_position:
            return f"{base_reason}（已补仓）"
        return base_reason

    def check_daily_hourly_exit_safe(self, position: dict, check_date: str) -> dict:
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
            hourly_df = self.get_hourly_kline_data(symbol)
            if hourly_df.empty:
                return result
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
                    entry_pct_chg = position.get('entry_pct_chg', 30)
                    dynamic_params = self.get_dynamic_params(entry_pct_chg)
                    current_profit_threshold = dynamic_params['profit_threshold_after_add'] if has_added_position else dynamic_params['profit_threshold']
                    stop_loss_threshold = dynamic_params['stop_loss_threshold']
                    add_position_threshold = dynamic_params['add_position_threshold']
                    
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

                    if price_change_high >= stop_loss_threshold:
                        earliest_loss_exit = hour_data['trade_date']
                        break

                # 查找最早的补仓时机（未补仓的情况下）
                earliest_add_position = None
                if not has_added_position:
                    for i, hour_data in enumerate(hold_period_data[:-1]):  # 排除最后一个检查时刻
                        high_price = hour_data['high']
                        price_change_high = (high_price - entry_price) / entry_price

                        if price_change_high >= add_position_threshold:
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
                    result['exit_reason'] = self.generate_exit_reason(f"24小时内价格下跌{current_profit_threshold*100:.0f}%，盈利平仓", has_added_position)
                    result['exit_datetime'] = earliest_profit_exit
                    return result

                elif earliest_loss_exit:
                    # 有止损时机
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 + stop_loss_threshold)
                    result['exit_reason'] = self.generate_exit_reason(f"24小时内价格上涨{stop_loss_threshold*100:.0f}%，止损平仓", has_added_position)
                    result['exit_datetime'] = earliest_loss_exit
                    return result

                # 如果24小时内都没有满足条件，则在24小时结束时平仓（使用整体判断）
                elif min_change <= -current_profit_threshold:
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 - current_profit_threshold)
                    result['exit_reason'] = self.generate_exit_reason(f"24小时内价格下跌{current_profit_threshold*100:.0f}%，盈利平仓", has_added_position)
                    result['exit_datetime'] = check_date + ' 00:00:00'
                    return result

                elif max_change >= stop_loss_threshold:
                    result['should_exit'] = True
                    result['exit_price'] = entry_price * (1 + stop_loss_threshold)
                    result['exit_reason'] = self.generate_exit_reason(f"价格上涨{stop_loss_threshold*100:.0f}%，平仓", has_added_position)
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
            return None

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        initial_capital: Optional[float] = None,
        position_size_ratio: Optional[float] = None,
        min_pct_chg: Optional[float] = None,
        enable_dynamic_leverage: Optional[bool] = None,
        enable_long_trade: Optional[bool] = None,
        trade_direction: Optional[str] = None,
        enable_volume_position_sizing: Optional[bool] = None,
        enable_risk_control: Optional[bool] = None
    ) -> Optional[Dict]:
        """
        运行回测
        
        Args:
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            initial_capital: 初始资金（USDT），默认使用实例变量
            position_size_ratio: 基础仓位比例，默认使用实例变量
            min_pct_chg: 最小涨幅要求，默认使用实例变量
            enable_dynamic_leverage: 是否启用动态杠杆策略，默认使用实例变量
            enable_long_trade: 是否允许做多，默认使用实例变量
            trade_direction: 交易方向，默认使用实例变量
            enable_volume_position_sizing: 是否启用成交额分级仓位，默认使用实例变量
            enable_risk_control: 是否启用实盘风控检查，默认使用实例变量
        
        Returns:
            dict: 回测结果字典，包含统计信息和CSV文件名
        """
        # 使用传入的参数或默认值
        if initial_capital is not None:
            self.initial_capital = initial_capital
            self.capital = initial_capital
        if position_size_ratio is not None:
            self.position_size_ratio = position_size_ratio
        if min_pct_chg is not None:
            self.min_pct_chg = min_pct_chg
        if enable_dynamic_leverage is not None:
            self.enable_dynamic_leverage = enable_dynamic_leverage
        if enable_long_trade is not None:
            self.enable_long_trade = enable_long_trade
        if trade_direction is not None:
            self.trade_direction = trade_direction
        if enable_volume_position_sizing is not None:
            self.enable_volume_position_sizing = enable_volume_position_sizing
        if enable_risk_control is not None:
            self.enable_risk_control = enable_risk_control
        
        # 创建交易记录表
        create_trade_table()
        
        # 连接顶级交易者数据库（用于风控）
        trader_db_path = os.path.join(os.path.dirname(__file__), 'db', 'top_trader_data.db')
        trader_conn = None
        if os.path.exists(trader_db_path):
            trader_conn = sqlite3.connect(trader_db_path)
            logging.info(f"已连接顶级交易者数据库：{trader_db_path}")
        else:
            logging.warning(f"顶级交易者数据库不存在：{trader_db_path}，将跳过多空比风控")
        
        # 获取所有涨幅第一的交易对
        logging.info(f"正在获取 {start_date} 到 {end_date} 期间的涨幅第一交易对...")
        top_gainers_df = get_all_top_gainers(start_date, end_date)
        
        if top_gainers_df.empty:
            logging.warning("未找到任何涨幅第一的交易对")
            return None
        
        logging.info(f"共找到 {len(top_gainers_df)} 个涨幅第一的交易对")
        
        # 当前持仓
        current_positions = []  # 支持多个仓位同时存在
        # 记录所有曾经建仓过的交易对，避免重复建仓同一交易对
        traded_symbols = set()
        self.capital = self.initial_capital
        self.trade_records = []
        
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
                hourly_result = self.check_position_hourly(current_position, self.capital, end_date)

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
                    position_leverage = current_position.get('leverage', self.leverage)
                    profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * position_leverage
                    profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price

                    trade_record = {
                        'entry_date': original_entry_date,
                        'symbol': symbol,
                        'entry_price': original_entry_price,
                        'entry_pct_chg': current_position.get('entry_pct_chg'),
                        'position_size': current_position['position_size'],
                        'leverage': position_leverage,  # 使用动态杠杆
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

                    self.trade_records.append(trade_record)

                    position_value = current_position.get('position_value', 0)
                    self.capital += position_value + profit_loss

                    position_info = " | 已补仓" if has_added_position else ""
                    logging.info(
                        f"{exit_datetime}: 平仓（买入） {symbol} | "
                        f"建仓价（卖空）: {entry_price:.8f} | "
                        f"平仓价（买入）: {exit_price:.8f} | "
                        f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                        f"持仓小时: {hold_hours} | "
                        f"原因: {exit_reason}{position_info} | "
                        f"当前资金: {self.capital:.2f} USDT"
                    )

                    positions_to_remove.add(i)

                elif hourly_result['action'] == 'add_position':
                    # 触发补仓 - 使用check_position_hourly返回的计算结果
                    new_avg_entry_price = hourly_result['new_entry_price']
                    total_position_size = hourly_result['new_position_size']
                    add_position_value = hourly_result['add_position_value']
                    add_position_datetime = hourly_result['exit_datetime']
                    # 获取动态参数以获取补仓阈值
                    entry_pct_chg = current_position.get('entry_pct_chg', 30)
                    dynamic_params = self.get_dynamic_params(entry_pct_chg)
                    add_position_threshold = dynamic_params['add_position_threshold']
                    add_position_price = entry_price * (1 + add_position_threshold)

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

                        self.capital -= add_position_value

                        logging.info(
                            f"{add_position_datetime}: 补仓 {symbol} | "
                            f"原建仓价: {entry_price:.8f} | "
                            f"补仓价: {add_position_price:.8f} | "
                            f"新平均价: {new_avg_entry_price:.8f} | "
                            f"补仓金额: {add_position_value:.2f} USDT | "
                            f"账户余额: {self.capital:.2f} USDT"
                        )
                    # 补仓后继续持有，不移除持仓

            # ========== 日线检查已被移除，全部由逐小时检查处理 ==========
            # 如果逐小时检查没有触发任何条件，持仓继续持有

            # 移除标记的持仓（反向移除避免索引错乱）
            for i in sorted(positions_to_remove, reverse=True):
                if i < len(current_positions):  # 安全检查
                    current_positions.pop(i)
    
            # 检查持有时间过长的交易，强制平仓
            max_hold_days = 15  # 最大持有15天
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
                    logging.warning(f"{symbol} 触发强制平仓条件: hold_days({hold_days}) >= max_hold_days({max_hold_days})")
                    # 强制平仓
                    # 根据是否补仓选择合适的止盈阈值
                    entry_pct_chg = current_position.get('entry_pct_chg', 30)
                    dynamic_params = self.get_dynamic_params(entry_pct_chg)
                    current_profit_threshold = dynamic_params['profit_threshold_after_add'] if has_added_position else dynamic_params['profit_threshold']
                    # 使用当前有效的平均成本计算止盈价格
                    actual_entry_price = current_position['entry_price']
                    exit_price = actual_entry_price * (1 - current_profit_threshold)  # 假设盈利平仓
                    exit_datetime = date_str + ' 23:59:59'  # 当天结束时平仓
                    exit_reason = self.generate_exit_reason(f"持有时间超过{max_hold_days}天，强制平仓", has_added_position)
    
                    # 计算持仓时间和盈亏
                    exit_dt = datetime.strptime(exit_datetime, '%Y-%m-%d %H:%M:%S')
                    final_hold_hours = int((exit_dt - entry_dt).total_seconds() / 3600)
                    # 使用实际的持仓成本计算盈亏（考虑补仓后的平均成本）
                    position_leverage = current_position.get('leverage', self.leverage)
                    profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * position_leverage
                    profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price
    
                    trade_record = {
                        'entry_date': original_entry_date,
                        'symbol': symbol,
                        'entry_price': original_entry_price,
                        'entry_pct_chg': current_position.get('entry_pct_chg'),
                        'position_size': current_position['position_size'],
                        'leverage': position_leverage,  # 使用动态杠杆
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
    
                    self.trade_records.append(trade_record)
    
                    logging.info(
                        f"{date_str}: 强制平仓（超期） {symbol} | "
                        f"建仓价（卖空）: {original_entry_price:.8f} | "
                        f"平仓价（买入）: {exit_price:.8f} | "
                        f"盈亏: {profit_loss:.2f} USDT ({profit_loss_pct*100:.2f}%) | "
                        f"持仓小时: {final_hold_hours} | "
                        f"原因: {exit_reason}"
                    )
    
                    self.capital += current_position.get('position_value', 0) + profit_loss
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
    
                # 只有当涨幅>=阈值且该交易对从未被交易过时才建仓
                # 建仓条件：涨幅>=阈值 且 该交易对从未被交易过
                # 一旦建仓过同一交易对，就不再建仓（避免重复交易同一交易对）
                if pct_chg >= self.min_pct_chg * 100 and not already_traded:
                    # ============================================================
                    # 风控1：检查顶级交易者多空比，如果 < 0.5 则延迟一天建仓
                    # 原因：多空比 < 0.5 表示空头主导（做空占比>66%），
                    #       第二天容易出现"短挤效应"导致价格疯涨，对做空者极其危险
                    # ============================================================
                    delay_entry = False  # 多空比风控延迟标志
                    delay_entry_60d = False  # 60天均涨风控延迟标志
                    skip_entry = False  # 新增：完全跳过建仓标志（暂未使用）
                    
                    # ============================================================
                    # 风控2：检查「从60天平均价涨幅」，避免主力获利不足继续拉升
                    # 逻辑：如果从60天平均价涨幅不足，说明主力还没充分获利，
                    #      价格可能继续拉升，不适合做空
                    # 分级风控：根据日涨幅动态调整阈值（见下方详细说明）
                    # ============================================================
                    try:
                        # 获取过去60天的K线数据，计算平均价
                        start_date_60d = (current_date - timedelta(days=60)).strftime('%Y-%m-%d')
                        # 注意：不包括涨幅第一天本身
                        day_before = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
                        
                        query_avg = f'''
                        SELECT AVG(close) as avg_close
                        FROM \"K1d{symbol}\" 
                        WHERE DATE(trade_date) >= :start_date AND DATE(trade_date) <= :end_date
                        '''
                        
                        query_current = f'''
                        SELECT close
                        FROM \"K1d{symbol}\" 
                        WHERE DATE(trade_date) = :current_date
                        '''
                        
                        with engine.connect() as conn_temp:
                            # 获取60天平均价
                            result_avg = conn_temp.execute(
                                text(query_avg),
                                {'start_date': start_date_60d, 'end_date': day_before}
                            )
                            row_avg = result_avg.fetchone()
                            
                            # 获取涨幅第一天的收盘价
                            result_current = conn_temp.execute(
                                text(query_current),
                                {'current_date': date_str}
                            )
                            row_current = result_current.fetchone()
                            
                            if row_avg and row_current and row_avg[0] is not None and row_current[0] is not None:
                                avg_close_60d = row_avg[0]
                                current_close = row_current[0]
                                from_avg_60d_pct = (current_close - avg_close_60d) / avg_close_60d * 100
                                
                                # ============================================================
                                # 分级风控：根据日涨幅动态调整60天均价涨幅阈值
                                # 关键：低涨幅币更危险（HUSDT案例：日涨35%，60天均涨55%仍亏-2343）
                                # - 日涨<40%: 60天均涨>56% (HUSDT 55.1%都亏了，必须严格)
                                # - 日涨40-60%: 60天均涨>45% (RVVUSDT 49%盈利，可放宽)
                                # - 日涨60-100%: 60天均涨>35% (高涨幅动力强)
                                # - 日涨>100%: 60天均涨>25% (极高涨幅说明强驱动)
                                # ============================================================
                                if pct_chg < 40:
                                    threshold = 56
                                    level_desc = "低中涨幅"
                                elif pct_chg < 60:
                                    threshold = 45
                                    level_desc = "中涨幅"
                                elif pct_chg < 100:
                                    threshold = 35
                                    level_desc = "高涨幅"
                                else:
                                    threshold = 25
                                    level_desc = "超高涨幅"
                                
                                if from_avg_60d_pct < threshold:
                                    delay_entry_60d = True
                                    logging.info(
                                        f"{date_str}: {symbol} {level_desc}(日涨{pct_chg:.1f}%), "
                                        f"从60天均价涨幅{from_avg_60d_pct:.1f}%(<{threshold}%)，"
                                        f"主力获利不足，延迟一天建仓（第三天）"
                                    )
                    except Exception as e:
                        logging.warning(f"检查 {symbol} 60天均价涨幅失败：{e}")
                    
                    if trader_conn is not None:
                        try:
                            # 获取当天（涨幅第一那天）的多空比
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            start_ts = int((date_obj - timedelta(days=1)).timestamp() * 1000)
                            end_ts = int((date_obj + timedelta(days=1)).timestamp() * 1000)
                            target_ts = int(date_obj.timestamp() * 1000)
                            
                            query_top = '''
                            SELECT long_short_ratio, long_account, short_account
                            FROM top_account_ratio
                            WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                            ORDER BY ABS(timestamp - ?) ASC LIMIT 1
                            '''
                            df_top = pd.read_sql_query(query_top, trader_conn, params=(symbol, start_ts, end_ts, target_ts))
                            
                            if not df_top.empty:
                                top_ratio = df_top.iloc[0]['long_short_ratio']
                                top_short_pct = df_top.iloc[0]['short_account'] * 100
                                
                                if top_ratio < 0.85:
                                    delay_entry = True
                                    logging.info(
                                        f"{date_str}: {symbol} 多空比{top_ratio:.2f}(<0.5, 空头占{top_short_pct:.1f}%), "
                                        f"存在短挤风险，延迟一天建仓（第三天）"
                                    )
                        except Exception as e:
                            logging.warning(f"查询 {symbol} 多空比失败：{e}，继续正常建仓")
                    
                    # 获取第二天的开盘价（建仓价），如果有延迟则改为第三天
                    # 两种延迟情况：1. 多空比风控 2. 60天均涨风控
                    if delay_entry or delay_entry_60d:
                        entry_delay_days = 2  # 第三天建仓
                    else:
                        entry_delay_days = 1  # 第二天建仓
                    next_date = current_date + timedelta(days=entry_delay_days)
                    next_date_str = next_date.strftime('%Y-%m-%d')
                    
                    if next_date <= end_dt:
                        kline_data = get_kline_data_for_date(symbol, next_date_str)
                        if kline_data is not None:
                            open_price = kline_data['open']
                            
                            # 先获取动态交易参数（根据入场涨幅），以获取动态的入场等待涨幅
                            dynamic_params = self.get_dynamic_params(pct_chg)
                            position_leverage = dynamic_params['leverage']
                            position_profit_threshold = dynamic_params['profit_threshold']
                            position_stop_loss_threshold = dynamic_params['stop_loss_threshold']
                            position_entry_rise = dynamic_params['entry_rise_threshold']  # 动态入场等待涨幅
                            
                            # 查找建仓触发点（等待价格上涨到目标价后建仓）
                            # 使用动态入场等待涨幅：低涨幅直接建仓，中高涨幅等待再涨一些
                            # 添加最大涨幅风控：如果等待期间疯涨超过阈值，放弃建仓
                            trigger_result = self.find_entry_trigger_point(
                                symbol=symbol,
                                open_price=open_price,
                                start_date=next_date_str,
                                rise_threshold=position_entry_rise,  # 使用动态入场等待涨幅
                                wait_hours=self.entry_wait_hours,
                                entry_pct_chg=pct_chg  # 传入第一天涨幅，用于风控
                            )
                            
                            if not trigger_result['triggered']:
                                # 未触发建仓（等待超时）
                                logging.info(
                                    f"{next_date_str}: {symbol} 等待{self.entry_wait_hours}小时未涨到目标价 "
                                    f"(开盘价: {open_price:.8f}, 目标价: {open_price * (1 + position_entry_rise):.8f}, "
                                    f"入场涨幅阈值: {position_entry_rise*100:.1f}%)，放弃建仓"
                                )
                                # 虽然放弃建仓，但仍记录为已尝试交易（避免重复尝试）
                                traded_symbols.add(symbol)
                                continue  # 跳过后续处理，因为未触发建仓
                            
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
                            should_skip = False
                            if self.enable_volume_filter and pct_chg >= self.high_pct_chg_threshold:
                                
                                volume_24h = self.get_24h_quote_volume(symbol, entry_datetime)
                                
                                if volume_24h >= 0 and volume_24h < self.min_volume_for_high_pct:
                                    volume_yi = volume_24h / 1e8  # 转换为亿
                                    logging.info(
                                        f"{next_date_str}: {symbol} 高涨幅{pct_chg:.1f}% + 成交额{volume_yi:.1f}亿 < 2亿，"
                                        f"主力还没出完货，放弃建仓"
                                    )
                                    traded_symbols.add(symbol)
                                    should_skip = True
                            
                            # ============================================================
                            # 实盘风控检查：检查市场情绪是否适合做空
                            # 通过币安API获取大户持仓、散户多空、持仓量变化等数据
                            # 回测模式下会跳过（因为无法获取历史情绪数据）
                            # ============================================================
                            api_sentiment = None
                            if self.enable_risk_control:
                                risk_result = self.check_risk_control(symbol, pct_chg)
                                api_sentiment = risk_result.get('sentiment_data')
                                if not risk_result['should_trade']:
                                    logging.info(
                                        f"{next_date_str}: {symbol} {risk_result['message']}"
                                    )
                                    # 输出危险信号详情
                                    for signal in risk_result['danger_signals']:
                                        logging.info(f"  ⚠️ {signal}")
                                    traded_symbols.add(symbol)
                                    should_skip = True
                                elif risk_result['danger_signals']:
                                    # 有危险信号但未超过阈值，输出警告
                                    logging.info(f"{next_date_str}: {symbol} {risk_result['message']}")
                                    for signal in risk_result['danger_signals']:
                                        logging.info(f"  ⚠️ {signal}")
                            
                            # ============================================================
                            # 获取24小时成交额用于仓位计算
                            # ============================================================
                            volume_24h = self.get_24h_quote_volume(symbol, entry_datetime)
    
                            # ============================================================
                            # 实盘模式：显示交易机会，等待用户手动确认巨鲸数据
                            # 回测模式：自动根据配置决定交易方向
                            # ============================================================
                            trade_direction = 'short'  # 默认做空
                            
                            if self.is_live_trading:
                                # 实盘模式：显示详细交易机会，等待用户确认
                                signal = self.print_trade_opportunity(
                                    symbol=symbol,
                                    pct_chg=pct_chg,
                                    entry_price=entry_price,
                                    volume_24h=volume_24h,
                                    api_sentiment=api_sentiment
                                )
                                
                                if self.require_whale_confirm:
                                    # 需要用户手动确认巨鲸数据
                                    trade_direction = self.get_user_trade_decision()
                                    if trade_direction == 'skip':
                                        logging.info(f"{next_date_str}: {symbol} 用户跳过本次交易")
                                        traded_symbols.add(symbol)
                                        should_skip = True
                                else:
                                    # 不需要确认，使用配置的默认方向
                                    trade_direction = self.trade_direction if self.trade_direction != 'auto' else 'short'
                            else:
                                # 回测模式：自动交易，使用配置方向
                                if self.trade_direction != 'auto':
                                    trade_direction = self.trade_direction
                            
                            # 如果应该跳过建仓，则跳过后续所有建仓逻辑
                            if not should_skip:
                                # ============================================================
                                # 成交额分级仓位计算：
                                # 根据24h成交额动态调整仓位大小
                                # 成交额大 → 流动性好 → 可用更大仓位
                                # ============================================================
                                position_multiplier = self.get_position_size_multiplier(volume_24h)
                            adjusted_position_ratio = self.position_size_ratio * position_multiplier
                            
                            # 每次建仓金额为账户余额的调整后比例
                            position_size = (self.capital * adjusted_position_ratio) / entry_price
    
                            position_value = self.capital * adjusted_position_ratio  # 建仓金额
                            logging.debug(f"建仓前资金: {self.capital:.2f} USDT, 建仓金额: {position_value:.2f} USDT")
                            self.capital -= position_value  # 扣除建仓金额（作为保证金）
                            logging.debug(f"建仓后资金: {self.capital:.2f} USDT")
    
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
                            volume_cat = self.get_volume_category(volume_24h)
                            
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
                    logging.debug(f"{date_str}: {symbol} 涨幅 {pct_chg:.2f}% < {self.min_pct_chg*100:.0f}%，不建仓")
            
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
                    hourly_df = self.get_hourly_kline_data(symbol)
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
                position_leverage = current_position.get('leverage', self.leverage)
                profit_loss = (actual_entry_price - exit_price) * current_position['position_size'] * position_leverage
                profit_loss_pct = (actual_entry_price - exit_price) / actual_entry_price

                has_added_position = current_position.get('has_added_position', False)

                trade_record = {
                    'entry_date': original_entry_date,
                    'symbol': symbol,
                    'entry_price': original_entry_price,
                    'entry_pct_chg': current_position.get('entry_pct_chg'),
                    'position_size': current_position['position_size'],
                    'leverage': position_leverage,  # 使用动态杠杆
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

                self.trade_records.append(trade_record)
                # 强制平仓时：释放保证金 + 盈亏
                position_value = current_position.get('position_value', 0)
                self.capital += position_value + profit_loss

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
                    'leverage': current_position.get('leverage', self.leverage),  # 使用动态杠杆
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

                self.trade_records.append(trade_record)
                position_value = current_position.get('position_value', 0)
                self.capital += position_value + profit_loss

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
            result = None
            if self.trade_records:
                df_trades = pd.DataFrame(self.trade_records)
                
                # 保存到数据库（先清空再插入，避免累积）
                df_trades.to_sql(
                    name='backtrade_records',
                    con=engine,
                    if_exists='replace',
                    index=False
                )
                logging.info(f"成功保存 {len(self.trade_records)} 条交易记录到数据库")
                
                # 保存到CSV文件（保存到data/backtrade_records目录）
                csv_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtrade_records')
                os.makedirs(csv_dir, exist_ok=True)
                csv_filename = os.path.join(csv_dir, f"backtrade_records_{start_date}_{end_date}.csv")
                df_trades.to_csv(csv_filename, index=False, encoding='utf-8-sig')
                logging.info(f"成功保存 {len(self.trade_records)} 条交易记录到CSV文件: {csv_filename}")
            
                # 打印统计信息
                win_trades = len(df_trades[df_trades['profit_loss'] > 0])
                loss_trades = len(df_trades[df_trades['profit_loss'] < 0])
                win_rate = win_trades / len(df_trades) * 100 if len(df_trades) > 0 else 0
                total_profit_loss = self.capital - self.initial_capital  # 总盈亏 = 最终资金 - 初始资金
                total_return_rate = (self.capital - self.initial_capital) / self.initial_capital * 100
                
                logging.info("=" * 60)
                logging.info("回测统计:")
                logging.info(f"初始资金: {self.initial_capital:.2f} USDT")
                logging.info(f"最终资金: {self.capital:.2f} USDT")
                logging.info(f"总盈亏: {total_profit_loss:.2f} USDT")
                logging.info(f"总收益率: {total_return_rate:.2f}%")
                logging.info(f"交易次数: {len(self.trade_records)}")
                logging.info(f"盈利次数: {win_trades}")
                logging.info(f"亏损次数: {loss_trades}")
                logging.info(f"胜率: {win_rate:.2f}%")
                logging.info("=" * 60)
            
                # 返回结果字典
                result = {
                    'status': 'success',
                    'strategy': 'Backtrade4策略',
                    'start_date': start_date,
                    'end_date': end_date,
                    'statistics': {
                        'initial_capital': self.initial_capital,
                        'final_capital': self.capital,
                        'total_profit_loss': total_profit_loss,
                        'total_return_rate': total_return_rate,
                        'total_trades': len(self.trade_records),
                        'win_trades': win_trades,
                        'loss_trades': loss_trades,
                        'win_rate': win_rate
                    },
                    'csv_filename': csv_filename
                }
            else:
                logging.warning("没有交易记录需要保存")
            
            # 关闭顶级交易者数据库连接
            if trader_conn is not None:
                trader_conn.close()
                logging.info("已关闭顶级交易者数据库连接")
            
            return result


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
    
    backtest = Backtrade4Backtest()
    backtest.run_backtest(
        start_date=args.start_date,
        end_date=args.end_date
    )
