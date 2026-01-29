"""
基于K线数据的CSV文件验证模块

用于验证CSV文件中的交易记录是否能在实际的K线数据中实现。

验证内容：
1. 建仓验证：
   - 建仓时间是否能在K线数据中找到
   - 建仓价是否在对应K线的[low, high]范围内
   - 补仓信息是否正确记录

2. 平仓验证：
   - 平仓时间是否能在K线数据中找到
   - 平仓价是否在对应K线的合理范围内（根据平仓原因判断）
   - 虚拟补仓交易使用更宽松的验证标准
   - 补仓信息是否正确记录

3. 盈亏金额一致性验证：
   - 正常交易：盈亏金额 = (平仓价 - 建仓价) / 建仓价 × 仓位金额 × 杠杆倍数
   - 虚拟补仓交易：盈亏金额 = 仓位金额 × (-0.72) = -72%本金
   - 盈亏百分比是否与盈亏金额/仓位金额匹配

支持的特殊情况：
- 虚拟补仓交易：使用更宽松的价格验证标准
- 不同平仓原因：止盈/止损/超时使用不同的价格验证逻辑
"""

import csv
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from db import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KlineCSVValidator:
    """基于K线数据的CSV验证器"""
    
    def __init__(self, csv_file_path: str):
        """
        初始化验证器
        
        Args:
            csv_file_path: CSV文件路径
        """
        self.csv_file_path = csv_file_path
        self.csv_records = []
        self.validation_results = {
            'total_records': 0,
            'validated_records': 0,
            'entry_price_valid': 0,
            'entry_price_invalid': 0,
            'exit_price_valid': 0,
            'exit_price_invalid': 0,
            'pnl_consistency_valid': 0,  # 🆕 盈亏金额一致性验证通过数
            'pnl_consistency_invalid': 0,  # 🆕 盈亏金额一致性验证失败数
            'missing_kline_data': [],
            'entry_price_issues': [],
            'exit_price_issues': [],
            'pnl_consistency_issues': [],  # 🆕 盈亏金额一致性问题
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
        
        self.validation_results['total_records'] = len(self.csv_records)
        logger.info(f"成功加载 {len(self.csv_records)} 条CSV记录")
        
        return self.csv_records
    
    def parse_datetime(self, date_str: str, time_str: str = None) -> Optional[datetime]:
        """
        解析日期时间字符串
        
        Args:
            date_str: 日期字符串 'YYYY-MM-DD'
            time_str: 时间字符串 'HH:MM:SS' 或 'YYYY-MM-DD HH:MM:SS'（可选）
        
        Returns:
            datetime对象，解析失败返回None
        """
        try:
            if time_str:
                # 如果time_str包含完整日期时间
                if ' ' in time_str and len(time_str) > 10:
                    return pd.to_datetime(time_str)
                # 否则组合日期和时间
                datetime_str = f"{date_str} {time_str}"
                return pd.to_datetime(datetime_str)
            else:
                return pd.to_datetime(date_str)
        except Exception as e:
            logger.warning(f"解析日期时间失败: {date_str} {time_str}, 错误: {e}")
            return None

    def _get_kline_from_db(self, symbol: str, target_time: datetime, interval: str = "1h") -> Optional[pd.Series]:
        """
        从数据库查询指定时间的K线
        """
        try:
            table_name = f'K{interval}{symbol}'
            safe_table_name = f'"{table_name}"'
            
            # 针对小时K线，确保时间是整点
            if interval == '1h':
                query_time = target_time.replace(minute=0, second=0, microsecond=0)
            elif interval == '5m':
                minute = (target_time.minute // 5) * 5
                query_time = target_time.replace(minute=minute, second=0, microsecond=0)
            else:
                query_time = target_time.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 转换为字符串格式，因为数据库中 trade_date 是 text 类型
            query_time_str = query_time.strftime('%Y-%m-%d %H:%M:%S')
                
            stmt = text(f"SELECT * FROM {safe_table_name} WHERE trade_date = :query_time")
            
            with engine.connect() as conn:
                result = conn.execute(stmt, {"query_time": query_time_str}).fetchone()
                
                if result:
                    # 将结果转换为Series，保持字段名
                    return pd.Series(result._mapping)
            
            return None
        except Exception as e:
            logger.debug(f"查询K线失败: {e}")
            return None

    def _get_nearest_kline_from_db(self, symbol: str, target_time: datetime, interval: str = "1h", max_diff_minutes: int = 60) -> Optional[pd.Series]:
        """
        从数据库查询最近的K线
        """
        try:
            table_name = f'K{interval}{symbol}'
            safe_table_name = f'"{table_name}"'
            
            # 使用 PostgreSQL 的时间差计算
            # 查找时间差绝对值最小的记录
            # 注意：trade_date 是 text 类型，需要转换为 timestamp
            stmt = text(f"""
                SELECT *, ABS(EXTRACT(EPOCH FROM (TO_TIMESTAMP(trade_date, 'YYYY-MM-DD HH24:MI:SS') - :target_time))) as diff_seconds
                FROM {safe_table_name}
                WHERE trade_date >= :start_time AND trade_date <= :end_time
                ORDER BY diff_seconds ASC
                LIMIT 1
            """)
            
            # 限制搜索范围以提高性能
            window = timedelta(minutes=max_diff_minutes * 2)
            start_time = (target_time - window).strftime('%Y-%m-%d %H:%M:%S')
            end_time = (target_time + window).strftime('%Y-%m-%d %H:%M:%S')
            
            with engine.connect() as conn:
                result = conn.execute(stmt, {
                    "target_time": target_time,
                    "start_time": start_time,
                    "end_time": end_time
                }).fetchone()
                
                if result:
                    diff_minutes = result.diff_seconds / 60
                    if diff_minutes <= max_diff_minutes:
                        return pd.Series(result._mapping)
            
            return None
        except Exception as e:
            logger.debug(f"查询最近K线失败: {e}")
            return None

    def find_kline_at_time(self, symbol: str, target_time: datetime, interval: str = '1h') -> Optional[pd.Series]:
        """
        查找指定时间点的K线数据
        """
        return self._get_kline_from_db(symbol, target_time, interval)
    
    def find_nearest_kline(self, symbol: str, target_time: datetime, interval: str = '1h', 
                          max_diff_minutes: int = 60) -> Optional[pd.Series]:
        """
        查找最接近指定时间的K线数据
        """
        return self._get_nearest_kline_from_db(symbol, target_time, interval, max_diff_minutes)
    
    def validate_price_in_kline(self, price: float, kline: pd.Series, 
                               price_type: str = 'entry', exit_reason: str = None, 
                               has_add_position: bool = False) -> Dict:
        """
        验证价格是否在K线的合理范围内
        
        Args:
            price: 要验证的价格
            kline: K线数据（Series）
            price_type: 价格类型 ('entry' 或 'exit')
            exit_reason: 平仓原因（仅用于exit类型）
            has_add_position: 是否有补仓（用于虚拟补仓交易的宽松验证）
        
        Returns:
            验证结果字典
        """
        result = {
            'valid': False,
            'price': price,
            'kline_open': None,
            'kline_high': None,
            'kline_low': None,
            'kline_close': None,
            'kline_time': None,
            'reason': '',
            'expected_price_field': None  # 🆕 期望的价格字段
        }
        
        try:
            # 获取K线价格字段
            open_price = kline.get('open')
            high_price = kline.get('high')
            low_price = kline.get('low')
            close_price = kline.get('close')
            kline_time = kline.get('trade_date')
            
            result['kline_open'] = float(open_price) if open_price is not None else None
            result['kline_high'] = float(high_price) if high_price is not None else None
            result['kline_low'] = float(low_price) if low_price is not None else None
            result['kline_close'] = float(close_price) if close_price is not None else None
            result['kline_time'] = str(kline_time) if kline_time is not None else None
            
            tolerance = 0.0001  # 价格容差
            
            # 🔧 根据回测逻辑进行验证
            if price_type == 'entry':
                # 建仓价格：基于信号close计算的目标回调价格，当low达到目标价格时建仓
                # 验证：建仓价应该在 [low, high] 范围内
                if high_price is not None and low_price is not None:
                    if low_price - tolerance <= price <= high_price + tolerance:
                        result['valid'] = True
                        result['reason'] = f'建仓价在K线范围内 [{low_price:.6f}, {high_price:.6f}]'
                        result['expected_price_field'] = 'low/high range'
                    else:
                        result['reason'] = f'建仓价超出K线范围 [{low_price:.6f}, {high_price:.6f}]'
                else:
                    result['reason'] = 'K线数据缺少价格字段'
            
            elif price_type == 'exit':
                # 🔧 平仓价格：根据回测逻辑，不同平仓原因使用不同的价格
                # 注意：止盈/止损使用阈值价格，不是直接用high/low
                if exit_reason:
                    exit_reason_lower = exit_reason.lower()
                    
                    # 止盈：触发条件是high >= 止盈阈值，但平仓价是止盈阈值价格
                    # 验证：平仓价应该在 [low, high] 范围内，且应该 <= high（因为阈值价格 <= high）
                    if 'take_profit' in exit_reason_lower or 'profit' in exit_reason_lower:
                        if high_price is not None and low_price is not None:
                            result['expected_price_field'] = 'take_profit_threshold (within [low, high])'
                            # 🆕 虚拟补仓交易：使用更宽松的验证标准（因为平仓价基于虚拟建仓价计算）
                            virtual_tolerance = tolerance * 10 if has_add_position and 'virtual' in exit_reason_lower else tolerance
                            # 止盈阈值价格应该在 [low, high] 范围内，且 <= high
                            if low_price - virtual_tolerance <= price <= high_price + virtual_tolerance:
                                result['valid'] = True
                                if has_add_position and 'virtual' in exit_reason_lower and (price < low_price - tolerance or price > high_price + tolerance):
                                    result['reason'] = f'止盈价在K线范围内（虚拟补仓，已放宽验证）: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                                else:
                                    result['reason'] = f'止盈价在K线范围内: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                                if price > high_price + tolerance:
                                    result['reason'] += f' (注意: 止盈价不应超过high，但允许容差)'
                            else:
                                if has_add_position and 'virtual' in exit_reason_lower:
                                    result['reason'] = f'止盈价超出K线范围（虚拟补仓，可能基于虚拟建仓价计算）: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                                else:
                                    result['reason'] = f'止盈价超出K线范围: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                        else:
                            result['reason'] = 'K线数据缺少high或low字段'
                    
                    # 止损：触发条件是low <= 止损阈值，但平仓价是止损阈值价格
                    # 验证：平仓价应该在 [low, high] 范围内，且应该 >= low（因为阈值价格 >= low）
                    elif 'stop_loss' in exit_reason_lower and 'trader' not in exit_reason_lower:
                        if low_price is not None and high_price is not None:
                            result['expected_price_field'] = 'stop_loss_threshold (within [low, high])'
                            # 🆕 虚拟补仓交易：使用更宽松的验证标准（因为平仓价基于虚拟建仓价计算）
                            virtual_tolerance = tolerance * 10 if has_add_position and 'virtual' in exit_reason_lower else tolerance
                            # 止损阈值价格应该在 [low, high] 范围内，且 >= low
                            if low_price - virtual_tolerance <= price <= high_price + virtual_tolerance:
                                result['valid'] = True
                                if has_add_position and 'virtual' in exit_reason_lower and (price < low_price - tolerance or price > high_price + tolerance):
                                    result['reason'] = f'止损价在K线范围内（虚拟补仓，已放宽验证）: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                                else:
                                    result['reason'] = f'止损价在K线范围内: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                                if price < low_price - tolerance:
                                    result['reason'] += f' (注意: 止损价不应低于low，但允许容差)'
                            else:
                                if has_add_position and 'virtual' in exit_reason_lower:
                                    result['reason'] = f'止损价超出K线范围（虚拟补仓，可能基于虚拟建仓价计算）: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                                else:
                                    result['reason'] = f'止损价超出K线范围: 平仓价={price:.6f}, K线范围=[{low_price:.6f}, {high_price:.6f}]'
                        else:
                            result['reason'] = 'K线数据缺少low或high字段'
                    
                    # 顶级交易者止损：使用close价格
                    elif 'stop_loss_trader' in exit_reason_lower or ('stop_loss' in exit_reason_lower and 'trader' in exit_reason_lower):
                        if close_price is not None:
                            result['expected_price_field'] = 'close'
                            # 顶级交易者止损使用close价格（允许小的差异）
                            close_tolerance = 0.001  # 收盘价允许稍大的容差（0.1%）
                            if abs(price - close_price) <= close_tolerance or (low_price is not None and high_price is not None and low_price - tolerance <= price <= high_price + tolerance):
                                result['valid'] = True
                                result['reason'] = f'顶级交易者止损价接近K线收盘价: close={close_price:.6f}, 平仓价={price:.6f}'
                            else:
                                result['reason'] = f'顶级交易者止损价与K线收盘价差异较大: close={close_price:.6f}, 平仓价={price:.6f}'
                        else:
                            result['reason'] = 'K线数据缺少close字段'
                    
                    # 超时平仓：使用close价格
                    elif 'timeout' in exit_reason_lower or 'max_hold' in exit_reason_lower or 'observing' in exit_reason_lower:
                        if close_price is not None:
                            result['expected_price_field'] = 'close'
                            # 超时平仓使用close价格（允许小的差异）
                            close_tolerance = 0.001  # 收盘价允许稍大的容差（0.1%）
                            if abs(price - close_price) <= close_tolerance or (low_price is not None and high_price is not None and low_price - tolerance <= price <= high_price + tolerance):
                                result['valid'] = True
                                result['reason'] = f'超时平仓价接近K线收盘价: close={close_price:.6f}, 平仓价={price:.6f}'
                            else:
                                result['reason'] = f'超时平仓价与K线收盘价差异较大: close={close_price:.6f}, 平仓价={price:.6f}'
                        else:
                            result['reason'] = 'K线数据缺少close字段'
                    
                    # 其他平仓原因：检查是否在 [low, high] 范围内
                    else:
                        if high_price is not None and low_price is not None:
                            result['expected_price_field'] = 'low/high range'
                            if low_price - tolerance <= price <= high_price + tolerance:
                                result['valid'] = True
                                result['reason'] = f'平仓价在K线范围内 [{low_price:.6f}, {high_price:.6f}]'
                            else:
                                result['reason'] = f'平仓价超出K线范围 [{low_price:.6f}, {high_price:.6f}]'
                        else:
                            result['reason'] = 'K线数据缺少价格字段'
                else:
                    # 没有平仓原因，默认检查是否在 [low, high] 范围内
                    if high_price is not None and low_price is not None:
                        result['expected_price_field'] = 'low/high range'
                        if low_price - tolerance <= price <= high_price + tolerance:
                            result['valid'] = True
                            result['reason'] = f'平仓价在K线范围内 [{low_price:.6f}, {high_price:.6f}]'
                        else:
                            result['reason'] = f'平仓价超出K线范围 [{low_price:.6f}, {high_price:.6f}]'
                    else:
                        result['reason'] = 'K线数据缺少价格字段'
            else:
                result['reason'] = f'未知的价格类型: {price_type}'
        
        except Exception as e:
            result['reason'] = f'验证过程出错: {str(e)}'
        
        return result
    
    def validate_pnl_consistency(self, record: Dict, entry_price: Optional[float], exit_price: float, exit_reason: str, has_add_position: bool = False) -> Dict:
        """
        验证盈亏金额与仓位金额的关系是否合理
        
        Args:
            record: CSV记录
            entry_price: 建仓价
            exit_price: 平仓价
            exit_reason: 平仓原因
            has_add_position: 是否有补仓
        
        Returns:
            验证结果字典
        """
        result = {
            'valid': True,
            'reason': '',
            'expected_pnl': None,
            'actual_pnl': None,
            'position_value': None,
            'leverage': None,
            'entry_price': None,
            'exit_price': exit_price
        }
        
        try:
            # 读取相关字段
            pnl_str = record.get('盈亏金额', '').strip()
            pnl_pct_str = record.get('盈亏百分比', '').strip()
            position_value_str = record.get('仓位金额', '').strip()
            leverage_str = record.get('杠杆倍数', '').strip()
            
            # 如果没有盈亏金额，跳过验证
            if not pnl_str or pnl_str == '-':
                result['reason'] = '盈亏金额为空，跳过验证'
                return result
            
            # 解析数值
            try:
                actual_pnl = float(pnl_str)
                result['actual_pnl'] = actual_pnl
            except ValueError:
                result['valid'] = False
                result['reason'] = f'盈亏金额格式错误: {pnl_str}'
                return result
            
            try:
                position_value = float(position_value_str) if position_value_str else None
                result['position_value'] = position_value
            except ValueError:
                result['valid'] = False
                result['reason'] = f'仓位金额格式错误: {position_value_str}'
                return result
            
            try:
                leverage = float(leverage_str) if leverage_str else None
                result['leverage'] = leverage
            except ValueError:
                leverage = 4.0  # 默认杠杆倍数
                result['leverage'] = leverage
            
            # 使用传入的entry_price参数
            result['entry_price'] = entry_price
            
            if position_value is None or entry_price is None:
                result['valid'] = False
                result['reason'] = '缺少仓位金额或建仓价，无法验证'
                return result
            
            # 判断是否为虚拟补仓交易
            is_virtual_tracking = 'virtual' in exit_reason.lower() and has_add_position
            
            # 计算预期盈亏金额
            tolerance = 0.01  # 允许1美分的误差
            
            if is_virtual_tracking:
                # 🆕 虚拟补仓交易：盈亏金额应该是-72%本金
                # real_pnl = first_position_value * (-0.72)
                # 注意：仓位金额字段显示的是first_position_value（首次投入金额）
                expected_pnl = position_value * (-0.72)
                result['expected_pnl'] = expected_pnl
                
                if abs(actual_pnl - expected_pnl) > tolerance:
                    result['valid'] = False
                    result['reason'] = (
                        f'虚拟补仓交易盈亏金额不合理: 实际={actual_pnl:.2f}, '
                        f'预期={expected_pnl:.2f}(-72%本金), 差异={abs(actual_pnl - expected_pnl):.2f}'
                    )
                else:
                    result['reason'] = f'虚拟补仓交易盈亏金额合理: {actual_pnl:.2f} = -72%本金'
            else:
                # 正常交易：盈亏金额 = (平仓价 - 建仓价) / 建仓价 × 仓位金额 × 杠杆倍数
                if exit_price and entry_price > 0:
                    price_change_pct = (exit_price - entry_price) / entry_price
                    expected_pnl = price_change_pct * position_value * leverage
                    result['expected_pnl'] = expected_pnl
                    
                    if abs(actual_pnl - expected_pnl) > tolerance:
                        result['valid'] = False
                        result['reason'] = (
                            f'盈亏金额不合理: 实际={actual_pnl:.2f}, '
                            f'预期={expected_pnl:.2f}(价格变化{price_change_pct*100:.2f}% × 仓位{position_value:.2f} × 杠杆{leverage:.1f}), '
                            f'差异={abs(actual_pnl - expected_pnl):.2f}'
                        )
                    else:
                        result['reason'] = f'盈亏金额合理: {actual_pnl:.2f}'
                else:
                    result['valid'] = False
                    result['reason'] = '缺少平仓价或建仓价，无法验证'
            
            # 🆕 验证盈亏百分比是否与盈亏金额一致
            if pnl_pct_str and pnl_pct_str != '-':
                try:
                    actual_pnl_pct = float(pnl_pct_str.rstrip('%'))
                    expected_pnl_pct = (actual_pnl / position_value * 100) if position_value > 0 else 0
                    
                    if abs(actual_pnl_pct - expected_pnl_pct) > 0.1:  # 允许0.1%的误差
                        # 🆕 尝试检查是否是未加杠杆的百分比（即价格变化百分比）
                        unleveraged_expected_pct = expected_pnl_pct / leverage
                        if abs(actual_pnl_pct - unleveraged_expected_pct) <= 0.1:
                            result['valid'] = True  # 视为通过，但在原因中注明
                            result['reason'] += f' (注: 盈亏百分比为未加杠杆的价格涨跌幅: {actual_pnl_pct:.2f}%)'
                        else:
                            result['valid'] = False
                            result['reason'] += f' | 盈亏百分比不一致: 实际={actual_pnl_pct:.2f}%, 预期={expected_pnl_pct:.2f}% (含杠杆) 或 {unleveraged_expected_pct:.2f}% (未加杠杆)'
                except ValueError:
                    pass  # 盈亏百分比格式错误，忽略
        
        except Exception as e:
            result['valid'] = False
            result['reason'] = f'验证盈亏金额时出错: {str(e)}'
        
        return result
    
    def validate_entry(self, record: Dict) -> Dict:
        """
        验证建仓信息
        
        Args:
            record: CSV记录
        
        Returns:
            验证结果
        """
        symbol = record.get('交易对', '').strip()
        entry_date = record.get('建仓日期', '').strip()
        entry_time = record.get('建仓具体时间', '').strip()
        entry_price_str = record.get('建仓价', '').strip()
        
        result = {
            'symbol': symbol,
            'entry_date': entry_date,
            'entry_time': entry_time,
            'entry_price': None,
            'valid': False,
            'kline_found': False,
            'price_valid': False,
            'issues': [],
            'has_add_position': None,  # 🆕 补仓信息
            'add_position_price': None  # 🆕 补仓价格
        }
        
        # 🆕 读取补仓信息
        has_add_position_str = record.get('是否有补仓', '').strip()
        if has_add_position_str:
            # 判断是否有补仓（可能是"是"、"✅是"、"否"等）
            has_add_position_str_lower = has_add_position_str.lower()
            if '是' in has_add_position_str_lower or 'yes' in has_add_position_str_lower or 'true' in has_add_position_str_lower:
                result['has_add_position'] = True
                # 读取补仓价格
                add_position_price_str = record.get('补仓价格', '').strip()
                if add_position_price_str:
                    try:
                        result['add_position_price'] = float(add_position_price_str)
                    except ValueError:
                        pass  # 补仓价格格式错误，忽略
            else:
                result['has_add_position'] = False
        
        # 解析建仓价格
        try:
            entry_price = float(entry_price_str) if entry_price_str else None
            result['entry_price'] = entry_price
        except ValueError:
            result['issues'].append(f'建仓价格式错误: {entry_price_str}')
            return result
        
        if entry_price is None:
            result['issues'].append('建仓价为空')
            return result
        
        # 解析建仓时间
        entry_datetime = self.parse_datetime(entry_date, entry_time)
        if entry_datetime is None:
            result['issues'].append(f'无法解析建仓时间: {entry_date} {entry_time}')
            return result
        
        # 🔧 根据回测逻辑：建仓使用小时K线（1h）
        # 建仓价格是基于信号close计算的目标回调价格，当小时K线的low达到目标价格时建仓
        kline = None
        kline_interval = None
        
        # 优先使用小时K线（与回测逻辑一致）
        kline = self.find_kline_at_time(symbol, entry_datetime, '1h')
        if kline is not None:
            kline_interval = '1h'
        else:
            # 尝试查找最近的K线
            kline = self.find_nearest_kline(symbol, entry_datetime, '1h', max_diff_minutes=60)
            if kline is not None:
                kline_interval = '1h (nearest)'
        
        if kline is None:
            result['issues'].append(f'未找到建仓时间点的K线数据 (时间: {entry_datetime})')
            return result
        
        result['kline_found'] = True
        result['kline_interval'] = kline_interval
        
        # 验证价格
        price_validation = self.validate_price_in_kline(entry_price, kline, 'entry')
        result['price_validation'] = price_validation
        result['price_valid'] = price_validation['valid']
        
        if not price_validation['valid']:
            result['issues'].append(price_validation['reason'])
        
        result['valid'] = result['price_valid']
        
        return result
    
    def validate_exit(self, record: Dict) -> Dict:
        """
        验证平仓信息
        
        Args:
            record: CSV记录
        
        Returns:
            验证结果
        """
        symbol = record.get('交易对', '').strip()
        exit_date = record.get('平仓日期', '').strip()
        exit_time = record.get('平仓具体时间', '').strip()
        exit_price_str = record.get('平仓价', '').strip()
        
        result = {
            'symbol': symbol,
            'exit_date': exit_date,
            'exit_time': exit_time,
            'exit_price': None,
            'entry_price': None,  # 🆕 建仓价（用于盈亏金额验证）
            'valid': False,
            'kline_found': False,
            'price_valid': False,
            'issues': [],
            'has_add_position': None,  # 🆕 补仓信息
            'add_position_price': None  # 🆕 补仓价格
        }
        
        # 🆕 读取建仓价（用于盈亏金额验证）
        entry_price_str = record.get('建仓价', '').strip()
        if entry_price_str:
            try:
                result['entry_price'] = float(entry_price_str)
            except ValueError:
                pass
        
        # 🆕 读取补仓信息
        has_add_position_str = record.get('是否有补仓', '').strip()
        if has_add_position_str:
            # 判断是否有补仓（可能是"是"、"✅是"、"否"等）
            has_add_position_str_lower = has_add_position_str.lower()
            if '是' in has_add_position_str_lower or 'yes' in has_add_position_str_lower or 'true' in has_add_position_str_lower:
                result['has_add_position'] = True
                # 读取补仓价格
                add_position_price_str = record.get('补仓价格', '').strip()
                if add_position_price_str:
                    try:
                        result['add_position_price'] = float(add_position_price_str)
                    except ValueError:
                        pass  # 补仓价格格式错误，忽略
            else:
                result['has_add_position'] = False
        
        # 如果没有平仓信息，跳过验证
        if not exit_date or not exit_price_str or exit_price_str == '-':
            result['issues'].append('未平仓或平仓信息缺失')
            return result
        
        # 解析平仓价格
        try:
            exit_price = float(exit_price_str) if exit_price_str else None
            result['exit_price'] = exit_price
        except ValueError:
            result['issues'].append(f'平仓价格式错误: {exit_price_str}')
            return result
        
        if exit_price is None:
            result['issues'].append('平仓价为空')
            return result
        
        # 解析平仓时间
        exit_datetime = self.parse_datetime(exit_date, exit_time)
        if exit_datetime is None:
            result['issues'].append(f'无法解析平仓时间: {exit_date} {exit_time}')
            return result
        
        # 🔧 根据回测逻辑：平仓使用小时K线（1h）
        # 止盈使用high，止损使用low，超时使用close
        kline = None
        kline_interval = None
        
        # 优先使用小时K线（与回测逻辑一致）
        kline = self.find_kline_at_time(symbol, exit_datetime, '1h')
        if kline is not None:
            kline_interval = '1h'
        else:
            # 尝试查找最近的K线
            kline = self.find_nearest_kline(symbol, exit_datetime, '1h', max_diff_minutes=60)
            if kline is not None:
                kline_interval = '1h (nearest)'
        
        if kline is None:
            result['issues'].append(f'未找到平仓时间点的K线数据 (时间: {exit_datetime})')
            return result
        
        result['kline_found'] = True
        result['kline_interval'] = kline_interval
        
        # 获取平仓原因
        exit_reason = record.get('平仓原因', '').strip()
        
        # 验证价格（传入平仓原因和补仓信息）
        price_validation = self.validate_price_in_kline(exit_price, kline, 'exit', exit_reason, result.get('has_add_position', False))
        result['price_validation'] = price_validation
        result['price_valid'] = price_validation['valid']
        result['exit_reason'] = exit_reason
        
        if not price_validation['valid']:
            result['issues'].append(price_validation['reason'])
        
        # 🆕 验证盈亏金额与仓位金额的关系
        pnl_validation = self.validate_pnl_consistency(record, result.get('entry_price'), exit_price, exit_reason, result.get('has_add_position', False))
        result['pnl_validation'] = pnl_validation
        if not pnl_validation['valid']:
            result['issues'].append(pnl_validation['reason'])
        
        result['valid'] = result['price_valid'] and pnl_validation['valid']
        
        return result
    
    def validate(self) -> Dict:
        """
        执行验证
        
        Returns:
            验证结果字典
        """
        try:
            # 加载CSV
            self.load_csv()
            
            # 验证每条记录
            for i, record in enumerate(self.csv_records, 1):
                symbol = record.get('交易对', '').strip()
                logger.info(f"验证记录 {i}/{len(self.csv_records)}: {symbol}")
                
                # 验证建仓
                entry_result = self.validate_entry(record)
                if entry_result['valid']:
                    self.validation_results['entry_price_valid'] += 1
                else:
                    self.validation_results['entry_price_invalid'] += 1
                    self.validation_results['entry_price_issues'].append({
                        'record_index': i,
                        'symbol': symbol,
                        'result': entry_result
                    })
                
                # 验证平仓（如果有）
                exit_result = self.validate_exit(record)
                if exit_result.get('exit_price') is not None:
                    if exit_result['valid']:
                        self.validation_results['exit_price_valid'] += 1
                    else:
                        self.validation_results['exit_price_invalid'] += 1
                        # 🆕 保存建仓信息到平仓问题记录中，方便报告时显示
                        self.validation_results['exit_price_issues'].append({
                            'record_index': i,
                            'symbol': symbol,
                            'result': exit_result,
                            'entry_result': entry_result  # 添加建仓验证结果
                        })
                    
                    # 🆕 验证盈亏金额一致性
                    if exit_result.get('pnl_validation'):
                        pnl_validation = exit_result['pnl_validation']
                        if pnl_validation.get('valid', True):
                            self.validation_results['pnl_consistency_valid'] += 1
                        else:
                            self.validation_results['pnl_consistency_invalid'] += 1
                            self.validation_results['pnl_consistency_issues'].append({
                                'record_index': i,
                                'symbol': symbol,
                                'result': exit_result,
                                'pnl_validation': pnl_validation
                            })
                
                self.validation_results['validated_records'] += 1
            
            logger.info("验证完成")
        
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
        report_lines.append("基于K线数据的CSV文件验证报告")
        report_lines.append("=" * 80)
        report_lines.append(f"CSV文件: {self.csv_file_path}")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 基本统计
        report_lines.append("基本统计:")
        report_lines.append(f"  总记录数: {self.validation_results['total_records']}")
        report_lines.append(f"  已验证记录数: {self.validation_results['validated_records']}")
        report_lines.append("")
        
        # 建仓验证统计
        total_entry_validations = (
            self.validation_results['entry_price_valid'] + 
            self.validation_results['entry_price_invalid']
        )
        if total_entry_validations > 0:
            entry_success_rate = (
                self.validation_results['entry_price_valid'] / total_entry_validations * 100
            )
            report_lines.append("建仓验证统计:")
            report_lines.append(f"  验证通过: {self.validation_results['entry_price_valid']} 条")
            report_lines.append(f"  验证失败: {self.validation_results['entry_price_invalid']} 条")
            report_lines.append(f"  通过率: {entry_success_rate:.1f}%")
            report_lines.append("")
        
        # 平仓验证统计
        total_exit_validations = (
            self.validation_results['exit_price_valid'] + 
            self.validation_results['exit_price_invalid']
        )
        if total_exit_validations > 0:
            exit_success_rate = (
                self.validation_results['exit_price_valid'] / total_exit_validations * 100
            )
            report_lines.append("平仓验证统计:")
            report_lines.append(f"  验证通过: {self.validation_results['exit_price_valid']} 条")
            report_lines.append(f"  验证失败: {self.validation_results['exit_price_invalid']} 条")
            report_lines.append(f"  通过率: {exit_success_rate:.1f}%")
            report_lines.append("")
        
        # 🆕 盈亏金额一致性验证统计
        total_pnl_validations = (
            self.validation_results['pnl_consistency_valid'] + 
            self.validation_results['pnl_consistency_invalid']
        )
        if total_pnl_validations > 0:
            pnl_success_rate = (
                self.validation_results['pnl_consistency_valid'] / total_pnl_validations * 100
            )
            report_lines.append("盈亏金额一致性验证统计:")
            report_lines.append(f"  验证通过: {self.validation_results['pnl_consistency_valid']} 条")
            report_lines.append(f"  验证失败: {self.validation_results['pnl_consistency_invalid']} 条")
            report_lines.append(f"  通过率: {pnl_success_rate:.1f}%")
            report_lines.append("")
        
        # 建仓问题详情
        if self.validation_results['entry_price_issues']:
            report_lines.append(f"⚠️  建仓验证问题 ({len(self.validation_results['entry_price_issues'])} 条):")
            for issue in self.validation_results['entry_price_issues'][:20]:
                result = issue['result']
                # 🆕 尝试获取对应的CSV记录以显示平仓信息
                record_index = issue['record_index'] - 1  # 转换为0-based索引
                csv_record = None
                if 0 <= record_index < len(self.csv_records):
                    csv_record = self.csv_records[record_index]
                
                report_lines.append(f"  {issue['record_index']}. {issue['symbol']}:")
                
                # 显示建仓信息
                report_lines.append(f"     【建仓信息】")
                report_lines.append(f"     建仓时间: {result['entry_date']} {result['entry_time']}")
                report_lines.append(f"     建仓价: {result['entry_price']}")
                # 🆕 显示补仓信息
                if result.get('has_add_position') is not None:
                    if result['has_add_position']:
                        add_price_info = f"补仓价格: {result.get('add_position_price', 'N/A')}" if result.get('add_position_price') else "补仓价格: N/A"
                        report_lines.append(f"     是否有补仓: ✅ 是 ({add_price_info})")
                    else:
                        report_lines.append(f"     是否有补仓: ❌ 否")
                if result.get('kline_found'):
                    pv = result.get('price_validation', {})
                    report_lines.append(f"     建仓K线间隔: {result.get('kline_interval', 'N/A')}")
                    report_lines.append(f"     建仓K线时间: {pv.get('kline_time', 'N/A')}")
                    report_lines.append(f"     建仓K线范围: [{pv.get('kline_low', 0):.6f}, {pv.get('kline_high', 0):.6f}]")
                    if pv.get('expected_price_field'):
                        report_lines.append(f"     期望价格字段: {pv.get('expected_price_field')}")
                for problem in result['issues']:
                    report_lines.append(f"     问题: {problem}")
                
                # 🆕 显示平仓信息（如果有）
                if csv_record:
                    exit_date = csv_record.get('平仓日期', '').strip()
                    exit_time = csv_record.get('平仓具体时间', '').strip()
                    exit_price = csv_record.get('平仓价', '').strip()
                    exit_reason = csv_record.get('平仓原因', '').strip()
                    
                    if exit_date and exit_price and exit_price != '-':
                        report_lines.append(f"     【平仓信息】")
                        report_lines.append(f"     平仓时间: {exit_date} {exit_time}")
                        report_lines.append(f"     平仓价: {exit_price}")
                        report_lines.append(f"     平仓原因: {exit_reason}")
                        # 🆕 显示补仓信息（如果有）
                        has_add_position_str = csv_record.get('是否有补仓', '').strip()
                        if has_add_position_str:
                            has_add_position_str_lower = has_add_position_str.lower()
                            if '是' in has_add_position_str_lower or 'yes' in has_add_position_str_lower or 'true' in has_add_position_str_lower:
                                add_price = csv_record.get('补仓价格', '').strip()
                                add_price_info = f" (补仓价格: {add_price})" if add_price else ""
                                report_lines.append(f"     是否有补仓: ✅ 是{add_price_info}")
                            else:
                                report_lines.append(f"     是否有补仓: ❌ 否")
                    else:
                        report_lines.append(f"     【平仓信息】未平仓")
            if len(self.validation_results['entry_price_issues']) > 20:
                report_lines.append(f"  ... 还有 {len(self.validation_results['entry_price_issues']) - 20} 条未显示")
            report_lines.append("")
        
        # 平仓问题详情
        if self.validation_results['exit_price_issues']:
            report_lines.append(f"⚠️  平仓验证问题 ({len(self.validation_results['exit_price_issues'])} 条):")
            for issue in self.validation_results['exit_price_issues'][:20]:
                result = issue['result']
                entry_result = issue.get('entry_result', {})  # 🆕 获取建仓验证结果
                
                report_lines.append(f"  {issue['record_index']}. {issue['symbol']}:")
                
                # 🆕 显示建仓信息
                report_lines.append(f"     【建仓信息】")
                if entry_result:
                    report_lines.append(f"     建仓时间: {entry_result.get('entry_date', 'N/A')} {entry_result.get('entry_time', 'N/A')}")
                    report_lines.append(f"     建仓价: {entry_result.get('entry_price', 'N/A')}")
                    # 🆕 显示补仓信息
                    if entry_result.get('has_add_position') is not None:
                        if entry_result['has_add_position']:
                            add_price_info = f"补仓价格: {entry_result.get('add_position_price', 'N/A')}" if entry_result.get('add_position_price') else "补仓价格: N/A"
                            report_lines.append(f"     是否有补仓: ✅ 是 ({add_price_info})")
                        else:
                            report_lines.append(f"     是否有补仓: ❌ 否")
                    if entry_result.get('kline_found'):
                        entry_pv = entry_result.get('price_validation', {})
                        report_lines.append(f"     建仓K线间隔: {entry_result.get('kline_interval', 'N/A')}")
                        report_lines.append(f"     建仓K线时间: {entry_pv.get('kline_time', 'N/A')}")
                        report_lines.append(f"     建仓K线范围: [{entry_pv.get('kline_low', 0):.6f}, {entry_pv.get('kline_high', 0):.6f}]")
                    if entry_result.get('issues'):
                        report_lines.append(f"     建仓验证状态: ❌ 失败")
                        for entry_problem in entry_result['issues']:
                            report_lines.append(f"        - {entry_problem}")
                    else:
                        report_lines.append(f"     建仓验证状态: ✅ 通过")
                else:
                    report_lines.append(f"     建仓信息: 未找到")
                
                # 显示平仓信息
                report_lines.append(f"     【平仓信息】")
                report_lines.append(f"     平仓时间: {result['exit_date']} {result['exit_time']}")
                report_lines.append(f"     平仓价: {result['exit_price']}")
                report_lines.append(f"     平仓原因: {result.get('exit_reason', 'N/A')}")
                # 🆕 显示补仓信息
                if result.get('has_add_position') is not None:
                    if result['has_add_position']:
                        add_price_info = f"补仓价格: {result.get('add_position_price', 'N/A')}" if result.get('add_position_price') else "补仓价格: N/A"
                        report_lines.append(f"     是否有补仓: ✅ 是 ({add_price_info})")
                    else:
                        report_lines.append(f"     是否有补仓: ❌ 否")
                if result.get('kline_found'):
                    pv = result.get('price_validation', {})
                    report_lines.append(f"     平仓K线间隔: {result.get('kline_interval', 'N/A')}")
                    report_lines.append(f"     平仓K线时间: {pv.get('kline_time', 'N/A')}")
                    if pv.get('expected_price_field'):
                        report_lines.append(f"     期望价格字段: {pv.get('expected_price_field')}")
                        if pv.get('expected_price_field') == 'high':
                            report_lines.append(f"     K线最高价: {pv.get('kline_high', 0):.6f}")
                        elif pv.get('expected_price_field') == 'low':
                            report_lines.append(f"     K线最低价: {pv.get('kline_low', 0):.6f}")
                        elif pv.get('expected_price_field') == 'close':
                            report_lines.append(f"     K线收盘价: {pv.get('kline_close', 0):.6f}")
                    report_lines.append(f"     平仓K线范围: [{pv.get('kline_low', 0):.6f}, {pv.get('kline_high', 0):.6f}]")
                for problem in result['issues']:
                    report_lines.append(f"     问题: {problem}")
            if len(self.validation_results['exit_price_issues']) > 20:
                report_lines.append(f"  ... 还有 {len(self.validation_results['exit_price_issues']) - 20} 条未显示")
            report_lines.append("")
        
        # 🆕 盈亏金额一致性问题详情
        if self.validation_results['pnl_consistency_issues']:
            report_lines.append(f"⚠️  盈亏金额一致性问题 ({len(self.validation_results['pnl_consistency_issues'])} 条):")
            for issue in self.validation_results['pnl_consistency_issues'][:20]:
                result = issue['result']
                pnl_validation = issue.get('pnl_validation', {})
                
                report_lines.append(f"  {issue['record_index']}. {issue['symbol']}:")
                report_lines.append(f"     建仓价: {result.get('entry_price', 'N/A')}")
                report_lines.append(f"     平仓价: {result.get('exit_price', 'N/A')}")
                report_lines.append(f"     仓位金额: {pnl_validation.get('position_value', 'N/A')}")
                report_lines.append(f"     杠杆倍数: {pnl_validation.get('leverage', 'N/A')}")
                report_lines.append(f"     实际盈亏金额: {pnl_validation.get('actual_pnl', 'N/A')}")
                report_lines.append(f"     预期盈亏金额: {pnl_validation.get('expected_pnl', 'N/A')}")
                report_lines.append(f"     平仓原因: {result.get('exit_reason', 'N/A')}")
                report_lines.append(f"     是否有补仓: {'是' if result.get('has_add_position') else '否'}")
                report_lines.append(f"     问题: {pnl_validation.get('reason', 'N/A')}")
            if len(self.validation_results['pnl_consistency_issues']) > 20:
                report_lines.append(f"  ... 还有 {len(self.validation_results['pnl_consistency_issues']) - 20} 条未显示")
            report_lines.append("")
        
        # 错误信息
        if self.validation_results['errors']:
            report_lines.append("❌ 错误信息:")
            for error in self.validation_results['errors']:
                report_lines.append(f"  {error}")
            report_lines.append("")
        
        # 总结
        total_issues = (
            len(self.validation_results['entry_price_issues']) +
            len(self.validation_results['exit_price_issues']) +
            len(self.validation_results['pnl_consistency_issues']) +
            len(self.validation_results['errors'])
        )
        
        if total_issues == 0:
            report_lines.append("✅ 验证通过：所有价格都能在实际K线数据中找到")
        else:
            report_lines.append(f"⚠️  发现 {total_issues} 个问题，请检查上述详细信息")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_report(self, output_path: Optional[str] = None) -> str:
        """
        保存验证报告到文件
        
        Args:
            output_path: 输出文件路径（可选）
        
        Returns:
            保存的文件路径
        """
        if output_path is None:
            csv_dir = os.path.dirname(self.csv_file_path)
            csv_basename = os.path.basename(self.csv_file_path)
            csv_name_without_ext = os.path.splitext(csv_basename)[0]
            output_path = os.path.join(csv_dir, f"{csv_name_without_ext}_kline_validation_report.txt")
        
        report_text = self.generate_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        logger.info(f"验证报告已保存到: {output_path}")
        return output_path


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='基于K线数据验证CSV文件')
    parser.add_argument('csv_file', help='CSV文件路径')
    parser.add_argument('--output', help='验证报告输出路径', default=None)
    parser.add_argument('--print', action='store_true', help='打印验证报告到控制台')
    
    args = parser.parse_args()
    
    # 创建验证器
    validator = KlineCSVValidator(args.csv_file)
    
    # 执行验证
    results = validator.validate()
    
    # 生成报告
    report = validator.generate_report()
    
    # 保存报告
    report_path = validator.save_report(args.output)
    
    # 打印报告
    if args.print:
        print(report)
    
    # 返回退出码
    total_issues = (
        len(results['entry_price_issues']) +
        len(results['exit_price_issues']) +
        len(results.get('pnl_consistency_issues', [])) +
        len(results['errors'])
    )
    
    exit(0 if total_issues == 0 else 1)


if __name__ == '__main__':
    main()
