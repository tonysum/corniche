"""
CSV文件验证模块

用于验证CSV文件中的数据与数据库中的交易记录是否一致。
支持验证买量暴涨策略回测生成的CSV文件。
"""

import csv
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy import text
from db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVValidator:
    """CSV文件验证器"""
    
    def __init__(self, csv_file_path: str):
        """
        初始化验证器
        
        Args:
            csv_file_path: CSV文件路径
        """
        self.csv_file_path = csv_file_path
        self.csv_records = []
        self.db_records = []
        self.validation_results = {
            'total_csv_records': 0,
            'total_db_records': 0,
            'matched_records': 0,
            'unmatched_csv_records': [],
            'unmatched_db_records': [],
            'field_mismatches': [],
            'errors': []
        }
    
    def load_csv(self) -> List[Dict]:
        """
        加载CSV文件
        
        Returns:
            CSV记录列表
        """
        if not os.path.exists(self.csv_file_path):
            raise FileNotFoundError(f"CSV文件不存在: {self.csv_file_path}")
        
        logger.info(f"正在加载CSV文件: {self.csv_file_path}")
        
        with open(self.csv_file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            self.csv_records = list(reader)
        
        self.validation_results['total_csv_records'] = len(self.csv_records)
        logger.info(f"成功加载 {len(self.csv_records)} 条CSV记录")
        
        return self.csv_records
    
    def load_db_records(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """
        从数据库加载交易记录
        
        Args:
            start_date: 开始日期（可选，用于过滤）
            end_date: 结束日期（可选，用于过滤）
        
        Returns:
            数据库记录列表
        """
        logger.info("正在从数据库加载交易记录...")
        
        with engine.connect() as conn:
            # 构建查询条件
            where_conditions = []
            params = {}
            
            if start_date:
                where_conditions.append("entry_date >= :start_date")
                params['start_date'] = start_date
            
            if end_date:
                where_conditions.append("entry_date <= :end_date")
                params['end_date'] = end_date
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    id,
                    entry_date,
                    symbol,
                    entry_price,
                    entry_pct_chg,
                    position_size,
                    leverage,
                    exit_date,
                    exit_price,
                    exit_reason,
                    profit_loss,
                    profit_loss_pct,
                    max_profit,
                    max_loss,
                    hold_days,
                    add_position_count,
                    delay_entry,
                    entry_reason,
                    delay_hours,
                    exit_hour,
                    created_at
                FROM backtrade_records
                {where_clause}
                ORDER BY entry_date, symbol, entry_price
            """
            
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            
            # 转换为字典列表
            columns = [
                'id', 'entry_date', 'symbol', 'entry_price', 'entry_pct_chg',
                'position_size', 'leverage', 'exit_date', 'exit_price', 'exit_reason',
                'profit_loss', 'profit_loss_pct', 'max_profit', 'max_loss', 'hold_days',
                'add_position_count', 'delay_entry', 'entry_reason', 'delay_hours',
                'exit_hour', 'created_at'
            ]
            
            self.db_records = [dict(zip(columns, row)) for row in rows]
        
        self.validation_results['total_db_records'] = len(self.db_records)
        logger.info(f"成功加载 {len(self.db_records)} 条数据库记录")
        
        return self.db_records
    
    def normalize_value(self, value: any, value_type: str = 'float') -> Optional[any]:
        """
        标准化值（处理空值、字符串等）
        
        Args:
            value: 原始值
            value_type: 目标类型 ('float', 'int', 'str', 'date')
        
        Returns:
            标准化后的值
        """
        if value is None or value == '' or value == '-':
            return None
        
        try:
            if value_type == 'float':
                # 处理百分比字符串
                if isinstance(value, str):
                    value = value.replace('%', '').replace(',', '').strip()
                return float(value) if value else None
            elif value_type == 'int':
                return int(float(value)) if value else None
            elif value_type == 'str':
                return str(value).strip() if value else None
            elif value_type == 'date':
                # 处理日期字符串
                if isinstance(value, str):
                    # 尝试解析日期
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S']:
                        try:
                            return datetime.strptime(value.split()[0], fmt).date()
                        except:
                            continue
                return value
        except (ValueError, TypeError) as e:
            logger.warning(f"无法转换值 '{value}' 为 {value_type}: {e}")
            return None
    
    def match_records(self, csv_record: Dict, db_records: List[Dict]) -> Optional[Dict]:
        """
        匹配CSV记录和数据库记录
        
        Args:
            csv_record: CSV记录
            db_records: 数据库记录列表
        
        Returns:
            匹配的数据库记录，如果未找到则返回None
        """
        # 提取关键字段用于匹配
        csv_symbol = csv_record.get('交易对', '').strip()
        csv_entry_date = self.normalize_value(csv_record.get('建仓日期', ''), 'date')
        csv_entry_price = self.normalize_value(csv_record.get('建仓价', ''), 'float')
        
        if not csv_symbol or not csv_entry_date or csv_entry_price is None:
            return None
        
        # 在数据库记录中查找匹配项
        for db_record in db_records:
            db_symbol = db_record.get('symbol', '').strip()
            db_entry_date = self.normalize_value(db_record.get('entry_date', ''), 'date')
            db_entry_price = self.normalize_value(db_record.get('entry_price'), 'float')
            
            # 匹配条件：交易对、建仓日期、建仓价（允许小的价格差异，如0.0001）
            if (db_symbol == csv_symbol and 
                db_entry_date == csv_entry_date and 
                db_entry_price is not None and
                abs(db_entry_price - csv_entry_price) < 0.0001):
                return db_record
        
        return None
    
    def compare_fields(self, csv_record: Dict, db_record: Dict) -> List[Dict]:
        """
        比较CSV记录和数据库记录的字段
        
        Args:
            csv_record: CSV记录
            db_record: 数据库记录
        
        Returns:
            不匹配的字段列表
        """
        mismatches = []
        
        # 字段映射关系
        field_mapping = {
            '交易对': ('symbol', 'str'),
            '建仓日期': ('entry_date', 'date'),
            '建仓价': ('entry_price', 'float'),
            '平仓日期': ('exit_date', 'date'),
            '平仓价': ('exit_price', 'float'),
            '盈亏金额': ('profit_loss', 'float'),
            '盈亏百分比': ('profit_loss_pct', 'float'),
            '平仓原因': ('exit_reason', 'str'),
            '杠杆倍数': ('leverage', 'int'),
            '仓位金额': ('position_size', 'float'),
            '持仓小时数': ('hold_days', 'int'),  # CSV中是小时数，DB中可能是天数
        }
        
        for csv_field, (db_field, value_type) in field_mapping.items():
            csv_value = csv_record.get(csv_field)
            db_value = db_record.get(db_field)
            
            # 标准化值
            csv_normalized = self.normalize_value(csv_value, value_type)
            db_normalized = self.normalize_value(db_value, value_type)
            
            # 比较
            if csv_normalized is None and db_normalized is None:
                continue  # 两者都为空，认为匹配
            
            if csv_normalized is None or db_normalized is None:
                mismatches.append({
                    'field': csv_field,
                    'csv_value': csv_value,
                    'db_value': db_value,
                    'reason': '一方为空'
                })
                continue
            
            # 对于浮点数，允许小的差异
            if value_type == 'float':
                tolerance = 0.01  # 允许0.01的差异
                if abs(csv_normalized - db_normalized) > tolerance:
                    mismatches.append({
                        'field': csv_field,
                        'csv_value': csv_value,
                        'db_value': db_value,
                        'csv_normalized': csv_normalized,
                        'db_normalized': db_normalized,
                        'difference': abs(csv_normalized - db_normalized),
                        'reason': f'差异超过容差 {tolerance}'
                    })
            elif csv_normalized != db_normalized:
                mismatches.append({
                    'field': csv_field,
                    'csv_value': csv_value,
                    'db_value': db_value,
                    'reason': '值不匹配'
                })
        
        return mismatches
    
    def validate(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """
        执行验证
        
        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        
        Returns:
            验证结果字典
        """
        try:
            # 加载数据
            self.load_csv()
            self.load_db_records(start_date, end_date)
            
            # 匹配记录
            matched_db_ids = set()
            
            for csv_record in self.csv_records:
                db_record = self.match_records(csv_record, self.db_records)
                
                if db_record:
                    matched_db_ids.add(db_record['id'])
                    self.validation_results['matched_records'] += 1
                    
                    # 比较字段
                    mismatches = self.compare_fields(csv_record, db_record)
                    if mismatches:
                        self.validation_results['field_mismatches'].append({
                            'csv_record': csv_record,
                            'db_record': db_record,
                            'mismatches': mismatches
                        })
                else:
                    self.validation_results['unmatched_csv_records'].append(csv_record)
            
            # 找出未匹配的数据库记录
            for db_record in self.db_records:
                if db_record['id'] not in matched_db_ids:
                    self.validation_results['unmatched_db_records'].append(db_record)
            
            logger.info(f"验证完成: 匹配 {self.validation_results['matched_records']} 条记录")
            
        except Exception as e:
            error_msg = f"验证过程中发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.validation_results['errors'].append(error_msg)
        
        return self.validation_results
    
    def generate_report(self) -> str:
        """
        生成验证报告
        
        Returns:
            报告文本
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CSV文件验证报告")
        report_lines.append("=" * 80)
        report_lines.append(f"CSV文件: {self.csv_file_path}")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 基本统计
        report_lines.append("基本统计:")
        report_lines.append(f"  CSV记录数: {self.validation_results['total_csv_records']}")
        report_lines.append(f"  数据库记录数: {self.validation_results['total_db_records']}")
        report_lines.append(f"  匹配记录数: {self.validation_results['matched_records']}")
        report_lines.append("")
        
        # 未匹配的CSV记录
        if self.validation_results['unmatched_csv_records']:
            report_lines.append(f"⚠️  未匹配的CSV记录 ({len(self.validation_results['unmatched_csv_records'])} 条):")
            for i, record in enumerate(self.validation_results['unmatched_csv_records'][:10], 1):
                report_lines.append(f"  {i}. {record.get('交易对', 'N/A')} - {record.get('建仓日期', 'N/A')} - {record.get('建仓价', 'N/A')}")
            if len(self.validation_results['unmatched_csv_records']) > 10:
                report_lines.append(f"  ... 还有 {len(self.validation_results['unmatched_csv_records']) - 10} 条未显示")
            report_lines.append("")
        
        # 未匹配的数据库记录
        if self.validation_results['unmatched_db_records']:
            report_lines.append(f"⚠️  未匹配的数据库记录 ({len(self.validation_results['unmatched_db_records'])} 条):")
            for i, record in enumerate(self.validation_results['unmatched_db_records'][:10], 1):
                report_lines.append(f"  {i}. {record.get('symbol', 'N/A')} - {record.get('entry_date', 'N/A')} - {record.get('entry_price', 'N/A')}")
            if len(self.validation_results['unmatched_db_records']) > 10:
                report_lines.append(f"  ... 还有 {len(self.validation_results['unmatched_db_records']) - 10} 条未显示")
            report_lines.append("")
        
        # 字段不匹配
        if self.validation_results['field_mismatches']:
            report_lines.append(f"⚠️  字段不匹配 ({len(self.validation_results['field_mismatches'])} 条记录):")
            for i, mismatch_info in enumerate(self.validation_results['field_mismatches'][:10], 1):
                csv_record = mismatch_info['csv_record']
                db_record = mismatch_info['db_record']
                mismatches = mismatch_info['mismatches']
                
                report_lines.append(f"  {i}. {csv_record.get('交易对', 'N/A')} - {csv_record.get('建仓日期', 'N/A')}:")
                for mismatch in mismatches:
                    report_lines.append(f"     字段 '{mismatch['field']}': CSV={mismatch['csv_value']}, DB={mismatch['db_value']}")
                    if 'difference' in mismatch:
                        report_lines.append(f"     差异: {mismatch['difference']}")
            if len(self.validation_results['field_mismatches']) > 10:
                report_lines.append(f"  ... 还有 {len(self.validation_results['field_mismatches']) - 10} 条未显示")
            report_lines.append("")
        
        # 错误信息
        if self.validation_results['errors']:
            report_lines.append("❌ 错误信息:")
            for error in self.validation_results['errors']:
                report_lines.append(f"  {error}")
            report_lines.append("")
        
        # 总结
        total_issues = (
            len(self.validation_results['unmatched_csv_records']) +
            len(self.validation_results['unmatched_db_records']) +
            len(self.validation_results['field_mismatches']) +
            len(self.validation_results['errors'])
        )
        
        if total_issues == 0:
            report_lines.append("✅ 验证通过：所有记录匹配，未发现不一致")
        else:
            report_lines.append(f"⚠️  发现 {total_issues} 个问题，请检查上述详细信息")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_report(self, output_path: Optional[str] = None) -> str:
        """
        保存验证报告到文件
        
        Args:
            output_path: 输出文件路径（可选，默认在CSV文件同目录）
        
        Returns:
            保存的文件路径
        """
        if output_path is None:
            csv_dir = os.path.dirname(self.csv_file_path)
            csv_basename = os.path.basename(self.csv_file_path)
            csv_name_without_ext = os.path.splitext(csv_basename)[0]
            output_path = os.path.join(csv_dir, f"{csv_name_without_ext}_validation_report.txt")
        
        report_text = self.generate_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        logger.info(f"验证报告已保存到: {output_path}")
        return output_path


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='验证CSV文件与数据库的一致性')
    parser.add_argument('csv_file', help='CSV文件路径')
    parser.add_argument('--start-date', help='开始日期（YYYY-MM-DD）', default=None)
    parser.add_argument('--end-date', help='结束日期（YYYY-MM-DD）', default=None)
    parser.add_argument('--output', help='验证报告输出路径', default=None)
    parser.add_argument('--print', action='store_true', help='打印验证报告到控制台')
    
    args = parser.parse_args()
    
    # 创建验证器
    validator = CSVValidator(args.csv_file)
    
    # 执行验证
    results = validator.validate(args.start_date, args.end_date)
    
    # 生成报告
    report = validator.generate_report()
    
    # 保存报告
    report_path = validator.save_report(args.output)
    
    # 打印报告
    if args.print:
        print(report)
    
    # 返回退出码
    total_issues = (
        len(results['unmatched_csv_records']) +
        len(results['unmatched_db_records']) +
        len(results['field_mismatches']) +
        len(results['errors'])
    )
    
    exit(0 if total_issues == 0 else 1)


if __name__ == '__main__':
    main()
