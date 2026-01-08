# VectorBT 重构回测代码分析

## 当前回测代码特点

### 策略复杂度

当前策略包含以下复杂逻辑：

1. **多持仓管理**
   - 同时持有多个交易对的仓位
   - 每个仓位独立跟踪（entry_price, add_position_count等）
   - 已持仓的交易对不重复建仓

2. **延迟入场机制**
   - 需要监控1小时K线数据
   - 判断涨势减弱（多个条件组合）
   - 跨时间框架（日线 + 小时线）

3. **补仓逻辑**
   - 第一次止损时补仓
   - 补仓后重新计算平均建仓价
   - 跟踪补仓次数

4. **动态资金管理**
   - 每次建仓金额 = 账户余额 × 百分比
   - 账户余额随交易动态变化

5. **复杂平仓条件**
   - 止盈：价格下跌达到阈值
   - 止损：价格上涨达到阈值
   - 补仓后再次止损直接平仓

---

## VectorBT 特点分析

### ✅ VectorBT 的优势

1. **性能极高**
   - 向量化计算，比循环快 100-1000 倍
   - 基于 Pandas/NumPy，利用 SIMD 指令
   - 适合大规模参数优化

2. **易于并行化**
   - 可以同时测试数千个参数组合
   - 内置并行计算支持

3. **代码简洁**
   - 对于简单策略，代码量大幅减少
   - 声明式编程风格

4. **内置分析工具**
   - 丰富的性能指标
   - 可视化支持

### ❌ VectorBT 的局限性

1. **不适合复杂状态管理**
   - 难以处理补仓逻辑
   - 多持仓状态跟踪困难
   - 动态资金管理复杂

2. **跨时间框架困难**
   - 主要设计用于单一时间框架
   - 延迟入场需要小时线数据，实现复杂

3. **学习曲线**
   - 需要理解向量化思维
   - 与传统事件驱动回测差异大

4. **调试困难**
   - 向量化操作难以单步调试
   - 错误信息不够直观

---

## 适用性评估

### ❌ 不适合用 VectorBT 的部分

#### 1. 补仓逻辑
```python
# 当前代码：第一次止损时补仓
if price_change_high >= _loss_threshold:
    if current_position.get('add_position_count', 0) == 0:
        # 补仓逻辑
        # 重新计算平均建仓价
```

**原因**: VectorBT 难以处理这种条件状态（是否已补仓）

#### 2. 多持仓管理
```python
# 当前代码：同时管理多个持仓
current_positions = [
    {'symbol': 'BTCUSDT', 'entry_price': 50000, ...},
    {'symbol': 'ETHUSDT', 'entry_price': 3000, ...},
]
```

**原因**: VectorBT 更适合单一资产或固定资产组合

#### 3. 延迟入场（跨时间框架）
```python
# 当前代码：需要小时线数据判断入场时机
hourly_df = get_hourly_kline_data_for_date(symbol, date_str, hours=12)
can_entry, entry_price = check_momentum_weakening(hourly_df)
```

**原因**: VectorBT 主要处理单一时间框架，跨框架需要额外处理

#### 4. 动态资金管理
```python
# 当前代码：每次建仓金额 = 账户余额 × 百分比
position_size = account_balance * _position_size_ratio
```

**原因**: VectorBT 更适合固定仓位大小

---

### ✅ 适合用 VectorBT 的部分

#### 1. 信号生成
```python
# 可以向量化：找出每天涨幅第一的交易对
# 计算涨幅
pct_chg = df['close'].pct_change() * 100
# 找出每天涨幅最大的
top_gainer = df.groupby('date')['pct_chg'].idxmax()
```

#### 2. 简单止盈止损
```python
# 可以向量化：基于价格变化的止盈止损
profit_signal = (entry_price - close_price) / entry_price >= profit_threshold
loss_signal = (close_price - entry_price) / entry_price >= loss_threshold
```

#### 3. 参数优化
```python
# VectorBT 的优势：快速测试多个参数组合
for profit_threshold in [0.15, 0.20, 0.25]:
    for loss_threshold in [0.19, 0.29, 0.39]:
        # 快速回测
```

---

## 重构方案对比

### 方案1: 完全用 VectorBT 重构 ❌

**难度**: ⭐⭐⭐⭐⭐ (极高)
**可行性**: ❌ 不推荐

**原因**:
- 需要重写所有复杂逻辑
- 补仓、多持仓管理难以实现
- 跨时间框架需要大量额外工作
- 代码可读性可能下降

**工作量**: 2-3周
**风险**: 高（可能无法完全实现现有功能）

---

### 方案2: 混合方案 ✅ (推荐)

**思路**: 
- 简单部分用 VectorBT（信号生成、参数优化）
- 复杂部分保持事件驱动（补仓、多持仓）

**架构**:
```
VectorBT 层（信号生成）
    ↓
事件驱动层（持仓管理、补仓逻辑）
    ↓
结果统计
```

**优点**:
- ✅ 保留现有复杂逻辑
- ✅ 利用 VectorBT 的性能优势
- ✅ 渐进式重构，风险低
- ✅ 易于维护和调试

**工作量**: 1周
**风险**: 低

---

### 方案3: 简化策略后用 VectorBT ✅

**思路**: 
- 先简化策略（移除补仓、延迟入场）
- 用 VectorBT 实现简化版本
- 对比性能提升

**适用场景**:
- 想快速验证 VectorBT 的效果
- 可以接受功能简化

**工作量**: 3-5天
**风险**: 中（功能可能不如原版）

---

### 方案4: 保持现状，优化性能 ✅

**思路**: 
- 保持事件驱动架构
- 优化关键路径（向量化计算部分）
- 使用 Numba 加速循环

**优点**:
- ✅ 无需重构
- ✅ 风险最低
- ✅ 性能提升明显（2-5倍）

**工作量**: 2-3天
**风险**: 低

---

## 性能对比预估

### 当前实现（事件驱动）
- **回测速度**: ~10秒/年数据
- **参数优化**: 需要手动循环，慢
- **内存占用**: 低

### VectorBT（完全重构）
- **回测速度**: ~0.1秒/年数据（100倍提升）
- **参数优化**: 内置支持，快
- **内存占用**: 高（需要加载所有数据）

### 混合方案
- **回测速度**: ~1秒/年数据（10倍提升）
- **参数优化**: 部分支持
- **内存占用**: 中等

### 优化现状
- **回测速度**: ~2秒/年数据（2倍提升）
- **参数优化**: 需要手动循环
- **内存占用**: 低

---

## 具体建议

### 短期（1-2周）

**推荐: 方案4 - 优化现有代码**

1. **向量化关键计算**
```python
# 优化前：循环计算涨幅
for date in dates:
    pct_chg = calculate_pct_chg(date)

# 优化后：向量化计算
df['pct_chg'] = df['close'].pct_change() * 100
```

2. **使用 Numba 加速循环**
```python
from numba import jit

@jit(nopython=True)
def check_exit_conditions(price_changes, profit_threshold, loss_threshold):
    # 加速的退出条件检查
    pass
```

3. **批量处理数据**
```python
# 一次性加载所有需要的数据
all_data = load_all_kline_data(start_date, end_date)
# 避免重复查询数据库
```

**预期效果**: 性能提升 2-5倍，代码改动小

---

### 中期（1-2个月）

**推荐: 方案2 - 混合方案**

1. **用 VectorBT 生成信号**
```python
import vectorbt as vbt

# 向量化生成入场信号
entry_signals = vbt.Signals.from_entries(
    df['pct_chg'] >= min_pct_chg,
    ...
)
```

2. **保持事件驱动处理复杂逻辑**
```python
# 补仓、多持仓管理仍用事件驱动
for signal in entry_signals:
    if should_add_position(signal):
        add_position(...)
```

3. **逐步迁移**
- 先迁移信号生成
- 再优化参数搜索
- 最后考虑简化复杂逻辑

**预期效果**: 性能提升 5-10倍，保留所有功能

---

### 长期（3-6个月）

**如果业务增长，考虑**:

1. **简化策略**
   - 移除补仓逻辑（或改为固定补仓规则）
   - 简化延迟入场（改为固定延迟时间）

2. **完全迁移到 VectorBT**
   - 策略简化后，VectorBT 实现更容易
   - 获得最大性能提升

---

## 代码示例对比

### 当前实现（事件驱动）

```python
def simulate_trading(...):
    current_positions = []
    account_balance = initial_capital
    
    for date in date_range:
        # 检查平仓
        for position in current_positions:
            if should_exit(position, date):
                close_position(position)
        
        # 检查建仓
        top_gainer = get_top_gainer(date)
        if top_gainer and not is_holding(top_gainer):
            if delay_entry:
                # 检查小时线
                hourly_data = get_hourly_data(top_gainer, date)
                if check_momentum_weakening(hourly_data):
                    open_position(...)
            else:
                open_position(...)
```

### VectorBT 实现（简化版）

```python
import vectorbt as vbt

# 加载数据
price = vbt.YFData.download('BTCUSDT', period='1y').get('Close')

# 生成信号
entries = (price.pct_change() >= min_pct_chg) & (price.pct_change() <= max_pct_chg)
exits = (price.pct_change() <= -profit_threshold) | (price.pct_change() >= loss_threshold)

# 回测
portfolio = vbt.Portfolio.from_signals(
    price,
    entries,
    exits,
    size=position_size,
    fees=0.001,
    freq='1d'
)

# 结果
print(portfolio.stats())
```

**注意**: 这个简化版无法处理补仓、多持仓、延迟入场等复杂逻辑

---

## 最终建议

### ✅ 推荐方案: 混合方案（方案2）

**理由**:
1. **保留现有功能**: 补仓、多持仓管理等复杂逻辑继续使用事件驱动
2. **性能提升**: 信号生成和参数优化用 VectorBT，获得 5-10倍性能提升
3. **风险可控**: 渐进式重构，可以逐步迁移
4. **易于维护**: 复杂逻辑保持可读性

### 实施步骤

1. **第1周**: 用 VectorBT 重构信号生成部分
2. **第2周**: 用 VectorBT 优化参数搜索
3. **第3-4周**: 保持复杂逻辑不变，优化性能

### 不推荐: 完全用 VectorBT 重构

**原因**:
- 当前策略太复杂（补仓、多持仓、跨时间框架）
- VectorBT 不适合这种场景
- 重构成本高，风险大
- 可能无法完全实现现有功能

---

## 总结

| 方案 | 性能提升 | 工作量 | 风险 | 推荐度 |
|------|---------|--------|------|--------|
| 完全 VectorBT | 100倍 | 2-3周 | 高 | ❌ |
| 混合方案 | 5-10倍 | 1周 | 低 | ✅✅✅ |
| 简化后 VectorBT | 50倍 | 3-5天 | 中 | ✅✅ |
| 优化现状 | 2-5倍 | 2-3天 | 低 | ✅✅✅ |

**最终建议**: 
- **现在**: 优化现有代码（方案4）
- **未来**: 如果策略简化，考虑混合方案（方案2）

**记住**: 不要为了用 VectorBT 而用 VectorBT，要根据实际需求选择最合适的方案！

