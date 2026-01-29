"""
CSV验证模块使用示例
"""

from validate_csv import CSVValidator
import logging

logging.basicConfig(level=logging.INFO)

# 示例1: 验证CSV文件
def example_validate_csv():
    """验证CSV文件与数据库的一致性"""
    
    # CSV文件路径
    csv_file = "../data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv"
    
    # 创建验证器
    validator = CSVValidator(csv_file)
    
    # 执行验证（可选：指定日期范围）
    results = validator.validate(
        start_date="2025-12-01",  # 可选
        end_date="2025-12-31"     # 可选
    )
    
    # 生成并打印报告
    report = validator.generate_report()
    print(report)
    
    # 保存报告到文件
    report_path = validator.save_report()
    print(f"\n验证报告已保存到: {report_path}")
    
    # 返回验证结果
    return results


# 示例2: 在代码中使用验证器
def example_programmatic_validation():
    """在代码中程序化使用验证器"""
    
    csv_file = "../data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv"
    validator = CSVValidator(csv_file)
    
    # 执行验证
    results = validator.validate()
    
    # 检查验证结果
    if results['matched_records'] == results['total_csv_records']:
        print("✅ 所有CSV记录都在数据库中找到匹配")
    else:
        print(f"⚠️  有 {len(results['unmatched_csv_records'])} 条CSV记录未在数据库中找到")
    
    # 检查字段不匹配
    if results['field_mismatches']:
        print(f"⚠️  发现 {len(results['field_mismatches'])} 条记录的字段不匹配")
        for mismatch_info in results['field_mismatches'][:5]:  # 显示前5个
            print(f"  交易对: {mismatch_info['csv_record'].get('交易对')}")
            for mismatch in mismatch_info['mismatches']:
                print(f"    字段 '{mismatch['field']}': CSV={mismatch['csv_value']}, DB={mismatch['db_value']}")
    
    return results


if __name__ == '__main__':
    # 运行示例
    print("=" * 80)
    print("CSV验证模块使用示例")
    print("=" * 80)
    print()
    
    # 示例1
    print("示例1: 完整验证流程")
    print("-" * 80)
    try:
        results = example_validate_csv()
    except Exception as e:
        print(f"错误: {e}")
    
    print()
    print("=" * 80)
    print()
    
    # 示例2
    print("示例2: 程序化验证")
    print("-" * 80)
    try:
        results = example_programmatic_validation()
    except Exception as e:
        print(f"错误: {e}")
