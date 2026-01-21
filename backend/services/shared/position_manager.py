#!/usr/bin/env python3
"""
仓位控制模块
提供统一的仓位管理功能，包括建仓、补仓、平仓、持仓检查等

使用方式：
    from services.shared.position_manager import Position, PositionManager
    
    manager = PositionManager(initial_capital=10000.0)
    position = manager.create_position(
        symbol='BTCUSDT',
        entry_price=50000.0,
        entry_datetime=datetime.now(),
        position_size_ratio=0.05,
        leverage=4.0
    )
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Position:
    """仓位数据结构"""
    symbol: str
    entry_price: float
    entry_datetime: datetime
    position_size: float
    position_value: float
    leverage: float
    position_type: str = "long"  # "long" 或 "short"
    
    # 补仓相关
    has_add_position: bool = False
    add_position_price: Optional[float] = None
    add_position_size: Optional[float] = None
    avg_entry_price: float = field(init=False)
    
    # 平仓相关
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_days: float = 0.0
    
    # 其他信息
    max_drawdown: float = 0.0
    signal_date: Optional[str] = None
    entry_pct_chg: Optional[float] = None
    
    def __post_init__(self):
        """初始化后处理"""
        self.avg_entry_price = self.entry_price
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'symbol': self.symbol,
            'entry_date': self.entry_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'entry_price': self.entry_price,
            'avg_entry_price': self.avg_entry_price,
            'position_size': self.position_size,
            'position_value': self.position_value,
            'leverage': self.leverage,
            'position_type': self.position_type,
            'has_add_position': self.has_add_position,
            'add_position_price': self.add_position_price,
            'add_position_size': self.add_position_size,
            'exit_date': self.exit_date,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'hold_days': self.hold_days,
            'max_drawdown': self.max_drawdown,
            'signal_date': self.signal_date,
            'entry_pct_chg': self.entry_pct_chg,
        }


class PositionManager:
    """仓位管理器"""
    
    def __init__(self, initial_capital: float = 10000.0):
        """
        初始化仓位管理器
        
        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: List[Position] = []
        self.trade_records: List[Dict] = []
    
    def create_position(
        self,
        symbol: str,
        entry_price: float,
        entry_datetime: datetime,
        position_size_ratio: float,
        leverage: float = 1.0,
        position_type: str = "long",
        signal_date: Optional[str] = None,
        entry_pct_chg: Optional[float] = None
    ) -> Position:
        """
        创建新仓位（建仓）
        
        Args:
            symbol: 交易对符号
            entry_price: 建仓价格
            entry_datetime: 建仓时间
            position_size_ratio: 建仓金额占账户余额的比例
            leverage: 杠杆倍数
            position_type: 仓位类型（"long" 或 "short"）
            signal_date: 信号日期
            entry_pct_chg: 入场涨幅百分比
        
        Returns:
            Position对象
        """
        # 计算建仓金额
        position_value = self.capital * position_size_ratio
        
        # 计算建仓数量（考虑杠杆）
        position_size = (position_value * leverage) / entry_price
        
        # 创建仓位对象
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            entry_datetime=entry_datetime,
            position_size=position_size,
            position_value=position_value,
            leverage=leverage,
            position_type=position_type,
            signal_date=signal_date,
            entry_pct_chg=entry_pct_chg
        )
        
        # 扣除建仓金额（作为保证金）
        self.capital -= position_value
        
        # 添加到持仓列表
        self.positions.append(position)
        
        # 记录交易记录
        trade_record = position.to_dict()
        trade_record['pnl'] = 0.0
        trade_record['pnl_pct'] = 0.0
        self.trade_records.append(trade_record)
        
        logging.info(
            f"🚀 建仓: {symbol} {entry_datetime.strftime('%Y-%m-%d %H:%M:%S')} "
            f"价格:{entry_price:.4f} 杠杆:{leverage}x 仓位:${position_value:.2f}"
        )
        
        return position
    
    def add_position(
        self,
        position: Position,
        add_price: float,
        add_datetime: datetime,
        add_size_ratio: Optional[float] = None
    ) -> Position:
        """
        补仓操作
        
        Args:
            position: 要补仓的仓位对象
            add_price: 补仓价格
            add_datetime: 补仓时间
            add_size_ratio: 补仓金额占账户余额的比例（如果为None，则使用原仓位大小）
        
        Returns:
            更新后的Position对象
        """
        if add_size_ratio is None:
            # 补仓相同数量
            add_size = position.position_size
            add_value = position.position_value
        else:
            # 使用指定比例补仓
            add_value = self.capital * add_size_ratio
            add_size = (add_value * position.leverage) / add_price
        
        # 重新计算平均成本
        total_value = (position.avg_entry_price * position.position_size) + (add_price * add_size)
        total_size = position.position_size + add_size
        new_avg_price = total_value / total_size
        
        # 更新仓位信息
        position.has_add_position = True
        position.add_position_price = add_price
        position.add_position_size = add_size
        position.avg_entry_price = new_avg_price
        position.position_size = total_size
        position.position_value += add_value
        
        # 扣除补仓金额
        self.capital -= add_value
        
        logging.info(
            f"➕ 补仓: {position.symbol} {add_datetime.strftime('%Y-%m-%d %H:%M:%S')} "
            f"价格:{add_price:.4f} 新平均价:{new_avg_price:.4f}"
        )
        
        return position
    
    def exit_position(
        self,
        position: Position,
        exit_price: float,
        exit_datetime: datetime,
        exit_reason: str
    ) -> Dict:
        """
        平仓操作
        
        Args:
            position: 要平仓的仓位对象
            exit_price: 平仓价格
            exit_datetime: 平仓时间
            exit_reason: 平仓原因
        
        Returns:
            交易记录字典
        """
        entry_price = position.avg_entry_price
        position_size = position.position_size
        
        # 计算盈亏
        if position.position_type == "long":
            # 做多：价格上涨盈利
            pnl = (exit_price - entry_price) * position_size
        else:
            # 做空：价格下跌盈利
            pnl = (entry_price - exit_price) * position_size
        
        pnl_pct = (exit_price - entry_price) / entry_price * 100 if position.position_type == "long" else (entry_price - exit_price) / entry_price * 100
        
        # 计算持仓天数（精确到小时）
        time_diff = exit_datetime - position.entry_datetime
        hold_days = time_diff.total_seconds() / 86400
        
        # 格式化平仓日期时间
        exit_date_str = exit_datetime.strftime('%Y-%m-%d %H:%M:%S')
        
        # 更新资金
        self.capital += position.position_value + pnl
        
        # 更新仓位记录
        position.exit_date = exit_date_str
        position.exit_price = exit_price
        position.exit_reason = exit_reason
        position.pnl = pnl
        position.pnl_pct = pnl_pct
        position.hold_days = round(hold_days, 2)
        
        # 从持仓列表中移除
        if position in self.positions:
            self.positions.remove(position)
        
        # 更新交易记录
        trade_record = position.to_dict()
        for i, record in enumerate(self.trade_records):
            if record.get('symbol') == position.symbol and record.get('entry_date') == position.entry_datetime.strftime('%Y-%m-%d %H:%M:%S'):
                self.trade_records[i] = trade_record
                break
        
        logging.info(
            f"💰 平仓: {position.symbol} {exit_date_str} "
            f"价格:{exit_price:.4f} 盈亏:${pnl:.2f} ({pnl_pct:+.1f}%) 原因:{exit_reason}"
        )
        
        return trade_record
    
    def check_exit_conditions(
        self,
        position: Position,
        current_price: float,
        current_datetime: datetime,
        take_profit_pct: float,
        stop_loss_pct: float,
        add_position_trigger_pct: Optional[float] = None,
        max_hold_hours: Optional[int] = None
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        检查是否满足平仓条件
        
        Args:
            position: 仓位对象
            current_price: 当前价格
            current_datetime: 当前时间
            take_profit_pct: 止盈比例（正数，如0.20表示20%）
            stop_loss_pct: 止损比例（负数，如-0.18表示-18%）
            add_position_trigger_pct: 补仓触发比例（负数，如-0.18表示-18%）
            max_hold_hours: 最大持仓小时数
        
        Returns:
            (是否平仓, 平仓原因, 平仓价格)
        """
        entry_price = position.avg_entry_price
        
        # 计算价格变化百分比
        if position.position_type == "long":
            # 做多：价格上涨为正
            price_change_pct = (current_price - entry_price) / entry_price
        else:
            # 做空：价格下跌为正（盈利）
            price_change_pct = (entry_price - current_price) / entry_price
        
        # 检查止盈
        if price_change_pct >= take_profit_pct:
            return True, "take_profit", current_price
        
        # 检查止损
        if price_change_pct <= stop_loss_pct:
            return True, "stop_loss", current_price
        
        # 检查补仓条件（如果未补仓且提供了补仓触发比例）
        if not position.has_add_position and add_position_trigger_pct is not None:
            if price_change_pct <= add_position_trigger_pct:
                return False, "add_position", current_price
        
        # 检查最大持仓时间
        if max_hold_hours is not None:
            hours_held = (current_datetime - position.entry_datetime).total_seconds() / 3600
            if hours_held >= max_hold_hours:
                return True, "max_hold_time", current_price
        
        return False, None, None
    
    def get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """根据交易对符号获取仓位"""
        for position in self.positions:
            if position.symbol == symbol:
                return position
        return None
    
    def has_position(self, symbol: str) -> bool:
        """检查是否持有指定交易对的仓位"""
        return any(pos.symbol == symbol for pos in self.positions)
    
    def get_total_position_value(self) -> float:
        """获取所有仓位的总价值"""
        return sum(pos.position_value for pos in self.positions)
    
    def get_total_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """
        获取所有仓位的未实现盈亏
        
        Args:
            current_prices: 当前价格字典 {symbol: price}
        
        Returns:
            总未实现盈亏
        """
        total_pnl = 0.0
        for position in self.positions:
            if position.symbol in current_prices:
                current_price = current_prices[position.symbol]
                if position.position_type == "long":
                    pnl = (current_price - position.avg_entry_price) * position.position_size
                else:
                    pnl = (position.avg_entry_price - current_price) * position.position_size
                total_pnl += pnl
        return total_pnl
    
    def force_close_all(self, exit_prices: Dict[str, float], exit_datetime: datetime, reason: str = "force_close"):
        """
        强制平仓所有仓位
        
        Args:
            exit_prices: 平仓价格字典 {symbol: price}
            exit_datetime: 平仓时间
            reason: 平仓原因
        """
        positions_to_close = self.positions.copy()
        for position in positions_to_close:
            if position.symbol in exit_prices:
                self.exit_position(position, exit_prices[position.symbol], exit_datetime, reason)
