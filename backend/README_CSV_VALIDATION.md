# CSV文件验证模块使用说明

## 概述

`validate_csv.py` 模块用于验证CSV文件中的数据与数据库中的交易记录是否一致。主要用于验证买量暴涨策略回测生成的CSV文件。

## 功能特性

- ✅ 自动匹配CSV记录和数据库记录（基于交易对、建仓日期、建仓价）
- ✅ 比较关键字段的一致性（价格、盈亏、平仓原因等）
- ✅ 检测未匹配的记录（CSV中存在但数据库中不存在，或反之）
- ✅ 生成详细的验证报告
- ✅ 支持日期范围过滤
- ✅ 容差处理（浮点数比较允许小的差异）

## 使用方法

### 1. 命令行使用

```bash
# 基本用法
python backend/validate_csv.py data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv

# 指定日期范围
python backend/validate_csv.py data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv \
    --start-date 2025-12-01 \
    --end-date 2025-12-31

# 打印报告到控制台
python backend/validate_csv.py data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv --print

# 指定报告输出路径
python backend/validate_csv.py data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv \
    --output validation_report.txt
```

### 2. Python代码中使用

```python
from validate_csv import CSVValidator

# 创建验证器
validator = CSVValidator('data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv')

# 执行验证
results = validator.validate(start_date='2025-12-01', end_date='2025-12-31')

# 生成报告
report = validator.generate_report()
print(report)

# 保存报告
report_path = validator.save_report()

# 检查结果
if results['matched_records'] == results['total_csv_records']:
    print("✅ 所有记录匹配")
else:
    print(f"⚠️  有 {len(results['unmatched_csv_records'])} 条记录未匹配")
```

## 验证字段

模块会验证以下关键字段：

| CSV字段 | 数据库字段 | 类型 | 说明 |
|---------|-----------|------|------|
| 交易对 | symbol | 字符串 | 交易对名称 |
| 建仓日期 | entry_date | 日期 | 建仓日期 |
| 建仓价 | entry_price | 浮点数 | 建仓价格 |
| 平仓日期 | exit_date | 日期 | 平仓日期 |
| 平仓价 | exit_price | 浮点数 | 平仓价格 |
| 盈亏金额 | profit_loss | 浮点数 | 盈亏金额（USDT） |
| 盈亏百分比 | profit_loss_pct | 浮点数 | 盈亏百分比 |
| 平仓原因 | exit_reason | 字符串 | 平仓原因 |
| 杠杆倍数 | leverage | 整数 | 杠杆倍数 |
| 仓位金额 | position_size | 浮点数 | 仓位金额（USDT） |
| 持仓小时数 | hold_days | 整数 | 持仓时间 |

## 验证结果

验证结果包含以下信息：

- **total_csv_records**: CSV文件中的记录总数
- **total_db_records**: 数据库中的记录总数
- **matched_records**: 成功匹配的记录数
- **unmatched_csv_records**: CSV中存在但数据库中未找到的记录列表
- **unmatched_db_records**: 数据库中存在但CSV中未找到的记录列表
- **field_mismatches**: 字段值不匹配的记录列表
- **errors**: 验证过程中发生的错误列表

## 报告格式

验证报告包含：

1. **基本统计**: 记录数量统计
2. **未匹配的CSV记录**: CSV中存在但数据库中未找到的记录
3. **未匹配的数据库记录**: 数据库中存在但CSV中未找到的记录
4. **字段不匹配**: 字段值不一致的详细信息
5. **错误信息**: 验证过程中的错误
6. **总结**: 验证结果总结

## 注意事项

1. **日期格式**: CSV中的日期格式可能不同，模块会自动尝试多种格式解析
2. **价格容差**: 浮点数比较允许0.01的差异（可调整）
3. **空值处理**: 空值、`-`、空字符串都被视为空值
4. **匹配逻辑**: 基于交易对、建仓日期、建仓价进行匹配（建仓价允许0.0001的差异）

## 示例输出

```
================================================================================
CSV文件验证报告
================================================================================
CSV文件: data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv
生成时间: 2026-01-23 12:30:00

基本统计:
  CSV记录数: 187
  数据库记录数: 187
  匹配记录数: 187

✅ 验证通过：所有记录匹配，未发现不一致
================================================================================
```

## 故障排查

### 问题1: 找不到CSV文件
- 检查文件路径是否正确
- 确保使用绝对路径或相对于项目根目录的路径

### 问题2: 数据库连接失败
- 检查数据库配置（`backend/services/shared/config.py`）
- 确保数据库服务正在运行
- 检查环境变量设置

### 问题3: 匹配率低
- 检查日期格式是否一致
- 检查价格精度是否匹配
- 确认CSV和数据库中的数据是否来自同一回测

## 扩展开发

如需添加新的验证字段或修改匹配逻辑，可以：

1. 修改 `compare_fields()` 方法添加新字段
2. 修改 `match_records()` 方法调整匹配逻辑
3. 修改 `normalize_value()` 方法处理特殊数据类型

## 相关文件

- `backend/validate_csv.py`: 验证模块主文件
- `backend/validate_csv_example.py`: 使用示例
- `backend/hm20260121.py`: 生成CSV的回测脚本
- `backend/db.py`: 数据库连接配置
