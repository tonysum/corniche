# 仓位控制模块使用说明

## 概述

`position_manager.py` 提供了一个统一的仓位管理功能，包括建仓、补仓、平仓、持仓检查等。这个模块可以用于所有回测策略，避免代码重复。

## 核心类

### Position
仓位数据结构，包含：
- 基本信息：symbol, entry_price, entry_datetime, position_size, position_value, leverage
- 补仓信息：has_add_position, add_position_price, add_position_size, avg_entry_price
- 平仓信息：exit_date, exit_price, exit_reason, pnl, pnl_pct, hold_days
- 其他信息：max_drawdown, signal_date, entry_pct_chg

### PositionManager
仓位管理器，提供以下功能：
- `create_position()` - 建仓
- `add_position()` - 补仓
- `exit_position()` - 平仓
- `check_exit_conditions()` - 检查平仓条件
- `get_position_by_symbol()` - 根据交易对获取仓位
- `has_position()` - 检查是否持有仓位
- `force_close_all()` - 强制平仓所有仓位

## 使用示例

### 基本使用

```python
from datetime import datetime
from services.shared.position_manager import PositionManager

# 创建仓位管理器
manager = PositionManager(initial_capital=10000.0)

# 建仓
position = manager.create_position(
    symbol='BTCUSDT',
    entry_price=50000.0,
    entry_datetime=datetime.now(),
    position_size_ratio=0.05,  # 5%仓位
    leverage=4.0,
    position_type='long'
)

# 补仓
manager.add_position(
    position=position,
    add_price=48000.0,
    add_datetime=datetime.now(),
    add_size_ratio=0.05  # 再补5%
)

# 检查平仓条件
should_exit, reason, exit_price = manager.check_exit_conditions(
    position=position,
    current_price=55000.0,
    current_datetime=datetime.now(),
    take_profit_pct=0.20,  # 20%止盈
    stop_loss_pct=-0.18,   # -18%止损
    add_position_trigger_pct=-0.18,  # -18%触发补仓
    max_hold_hours=72  # 最大持仓72小时
)

# 平仓
if should_exit:
    trade_record = manager.exit_position(
        position=position,
        exit_price=exit_price,
        exit_datetime=datetime.now(),
        exit_reason=reason
    )
```

### 在回测类中使用

```python
from services.shared.position_manager import PositionManager

class MyBacktest:
    def __init__(self):
        self.position_manager = PositionManager(initial_capital=10000.0)
    
    def run_backtest(self, start_date: str, end_date: str):
        # 建仓
        position = self.position_manager.create_position(
            symbol='BTCUSDT',
            entry_price=50000.0,
            entry_datetime=datetime.now(),
            position_size_ratio=0.05,
            leverage=4.0
        )
        
        # 检查持仓
        for position in self.position_manager.positions:
            should_exit, reason, exit_price = self.position_manager.check_exit_conditions(
                position=position,
                current_price=current_price,
                current_datetime=current_datetime,
                take_profit_pct=0.20,
                stop_loss_pct=-0.18
            )
            
            if should_exit:
                self.position_manager.exit_position(
                    position=position,
                    exit_price=exit_price,
                    exit_datetime=current_datetime,
                    exit_reason=reason
                )
```

## 三个回测文件的改造建议

### hm1.py (BuySurgeBacktest)
- 将 `execute_trade()`, `add_position()`, `exit_position()` 改为使用 `PositionManager`
- 将 `self.positions` 改为 `self.position_manager.positions`
- 将 `check_exit_conditions()` 改为使用 `PositionManager.check_exit_conditions()`

### backtrade.py (StandardBacktest)
- 在 `__init__` 中创建 `PositionManager` 实例
- 将建仓逻辑改为使用 `PositionManager.create_position()`
- 将补仓逻辑改为使用 `PositionManager.add_position()`
- 将平仓逻辑改为使用 `PositionManager.exit_position()`

### smartmoney.py (SmartMoneyBacktest)
- 在 `__init__` 中创建 `PositionManager` 实例
- 将 `check_position_hourly()` 改为使用 `PositionManager.check_exit_conditions()`
- 统一使用 `PositionManager` 管理所有仓位操作

## 优势

1. **代码复用**：避免三个文件中重复的仓位管理逻辑
2. **统一接口**：所有回测策略使用相同的仓位管理接口
3. **易于维护**：仓位管理逻辑集中在一个模块中，便于修改和优化
4. **类型安全**：使用 dataclass 定义 Position，类型更清晰
5. **功能扩展**：可以轻松添加新的仓位管理功能

## 注意事项

1. `PositionManager` 会自动管理资金（扣除建仓金额，平仓时返还）
2. 补仓时会自动重新计算平均成本
3. 平仓时会自动从持仓列表中移除
4. 所有时间都使用 `datetime` 对象，确保时间精度
