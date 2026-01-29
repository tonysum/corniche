"""
基于K线数据的CSV验证模块使用示例
"""

from validate_csv_with_kline import KlineCSVValidator
import logging

logging.basicConfig(level=logging.INFO)

# 示例1: 完整验证流程
def example_full_validation():
    """完整的验证流程"""
    
    # CSV文件路径
    csv_file = "../data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv"
    
    # 创建验证器
    validator = KlineCSVValidator(csv_file)
    
    # 执行验证
    results = validator.validate()
    
    # 生成并打印报告
    report = validator.generate_report()
    print(report)
    
    # 保存报告到文件
    report_path = validator.save_report()
    print(f"\n验证报告已保存到: {report_path}")
    
    # 返回验证结果
    return results


# 示例2: 检查特定交易对的验证结果
def example_check_specific_symbol():
    """检查特定交易对的验证结果"""
    
    csv_file = "../data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv"
    validator = KlineCSVValidator(csv_file)
    
    # 执行验证
    results = validator.validate()
    
    # 查找特定交易对的问题
    target_symbol = "TRUTHUSDT"
    
    print(f"\n查找 {target_symbol} 的验证问题:")
    print("-" * 80)
    
    # 检查建仓问题
    entry_issues = [
        issue for issue in results['entry_price_issues']
        if issue['symbol'] == target_symbol
    ]
    
    if entry_issues:
        print(f"建仓问题 ({len(entry_issues)} 条):")
        for issue in entry_issues:
            result = issue['result']
            print(f"  记录 #{issue['record_index']}:")
            print(f"    建仓时间: {result['entry_date']} {result['entry_time']}")
            print(f"    建仓价: {result['entry_price']}")
            if result.get('price_validation'):
                pv = result['price_validation']
                print(f"    K线范围: [{pv.get('kline_low', 0):.6f}, {pv.get('kline_high', 0):.6f}]")
            for problem in result['issues']:
                print(f"    问题: {problem}")
    else:
        print(f"✅ {target_symbol} 的建仓验证通过")
    
    # 检查平仓问题
    exit_issues = [
        issue for issue in results['exit_price_issues']
        if issue['symbol'] == target_symbol
    ]
    
    if exit_issues:
        print(f"\n平仓问题 ({len(exit_issues)} 条):")
        for issue in exit_issues:
            result = issue['result']
            print(f"  记录 #{issue['record_index']}:")
            print(f"    平仓时间: {result['exit_date']} {result['exit_time']}")
            print(f"    平仓价: {result['exit_price']}")
            if result.get('price_validation'):
                pv = result['price_validation']
                print(f"    K线范围: [{pv.get('kline_low', 0):.6f}, {pv.get('kline_high', 0):.6f}]")
            for problem in result['issues']:
                print(f"    问题: {problem}")
    else:
        print(f"✅ {target_symbol} 的平仓验证通过")


# 示例3: 统计验证通过率
def example_statistics():
    """统计验证通过率"""
    
    csv_file = "../data/backtrade_records/buy_surge_backtest_report_20260123_122643.csv"
    validator = KlineCSVValidator(csv_file)
    
    # 执行验证
    results = validator.validate()
    
    # 计算通过率
    total_entry = results['entry_price_valid'] + results['entry_price_invalid']
    total_exit = results['exit_price_valid'] + results['exit_price_invalid']
    
    print("\n验证统计:")
    print("=" * 80)
    
    if total_entry > 0:
        entry_rate = results['entry_price_valid'] / total_entry * 100
        print(f"建仓验证:")
        print(f"  通过: {results['entry_price_valid']} / {total_entry} ({entry_rate:.1f}%)")
        print(f"  失败: {results['entry_price_invalid']} / {total_entry} ({100-entry_rate:.1f}%)")
    
    if total_exit > 0:
        exit_rate = results['exit_price_valid'] / total_exit * 100
        print(f"\n平仓验证:")
        print(f"  通过: {results['exit_price_valid']} / {total_exit} ({exit_rate:.1f}%)")
        print(f"  失败: {results['exit_price_invalid']} / {total_exit} ({100-exit_rate:.1f}%)")
    
    print(f"\n总记录数: {results['total_records']}")
    print(f"已验证记录数: {results['validated_records']}")
    
    # 问题统计
    total_issues = (
        len(results['entry_price_issues']) +
        len(results['exit_price_issues'])
    )
    print(f"\n总问题数: {total_issues}")
    
    if total_issues == 0:
        print("✅ 所有验证通过！")
    else:
        print(f"⚠️  发现 {total_issues} 个问题")


if __name__ == '__main__':
    # 运行示例
    print("=" * 80)
    print("基于K线数据的CSV验证模块使用示例")
    print("=" * 80)
    print()
    
    # 示例1
    print("示例1: 完整验证流程")
    print("-" * 80)
    try:
        results = example_full_validation()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print()
    
    # 示例2
    print("示例2: 检查特定交易对")
    print("-" * 80)
    try:
        example_check_specific_symbol()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print()
    
    # 示例3
    print("示例3: 统计验证通过率")
    print("-" * 80)
    try:
        example_statistics()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
