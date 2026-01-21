import pytest
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add backend directory to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from backtrade4 import Backtrade4Backtest


class TestFindEntryTriggerPoint:
    """Tests for find_entry_trigger_point method"""
    
    @pytest.fixture
    def backtest(self):
        """Create a Backtrade4Backtest instance"""
        bt = Backtrade4Backtest()
        bt.entry_rise_threshold = 0.05  # 5%
        bt.entry_wait_hours = 24
        bt.enable_max_rise_filter = False
        return bt
    
    def test_immediate_entry_when_threshold_zero(self, backtest):
        """Test immediate entry when rise_threshold is 0"""
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0,
            wait_hours=24,
            entry_pct_chg=30
        )
        
        assert result['triggered'] is True
        assert result['entry_price'] == 50000.0
        assert result['entry_datetime'] == '2024-01-01 00:00:00'
        assert result['hours_waited'] == 0
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_successful_trigger_within_wait_period(self, mock_get_data, backtest):
        """Test successful trigger when price reaches target within wait period"""
        # Create mock hourly data
        hourly_data = pd.DataFrame({
            'trade_date': [
                '2024-01-01 00:00:00',
                '2024-01-01 01:00:00',
                '2024-01-01 02:00:00',
                '2024-01-01 03:00:00'
            ],
            'high': [50000, 51000, 52500, 53000],
            'low': [49000, 50000, 51000, 52000],
            'close': [50500, 51500, 52000, 52500]
        })
        mock_get_data.return_value = hourly_data
        
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.05,  # Target: 52500
            wait_hours=24,
            entry_pct_chg=30
        )
        
        assert result['triggered'] is True
        assert result['entry_price'] == 52500.0
        assert result['entry_datetime'] == '2024-01-01 02:00:00'
        assert result['hours_waited'] == 2
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_timeout_without_trigger(self, mock_get_data, backtest):
        """Test timeout when price never reaches target"""
        # Create mock hourly data that never reaches target
        hourly_data = pd.DataFrame({
            'trade_date': [
                '2024-01-01 00:00:00',
                '2024-01-01 01:00:00',
                '2024-01-01 02:00:00'
            ],
            'high': [50000, 50500, 51000],  # Never reaches 52500
            'low': [49000, 49500, 50000],
            'close': [49500, 50000, 50500]
        })
        mock_get_data.return_value = hourly_data
        
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.05,  # Target: 52500
            wait_hours=3,
            entry_pct_chg=30
        )
        
        assert result['triggered'] is False
        assert result['entry_price'] is None
        assert result['entry_datetime'] is None
        assert result['hours_waited'] == 3
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_max_rise_filter_blocks_entry(self, mock_get_data, backtest):
        """Test that max rise filter blocks entry when enabled"""
        backtest.enable_max_rise_filter = True
        backtest.max_rise_before_entry = {
            (25, 40): 0.01  # 1% max rise for 25-40% entry_pct_chg
        }
        
        # Create mock data with excessive rise
        hourly_data = pd.DataFrame({
            'trade_date': [
                '2024-01-01 00:00:00',
                '2024-01-01 01:00:00',
                '2024-01-01 02:00:00'
            ],
            'high': [50000, 51000, 52000],  # 4% rise exceeds 1% limit
            'low': [49000, 50000, 51000],
            'close': [50500, 51500, 51800]
        })
        mock_get_data.return_value = hourly_data
        
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.02,  # Target: 51000
            wait_hours=24,
            entry_pct_chg=30  # Falls in 25-40% range
        )
        
        assert result['triggered'] is False
        assert result['entry_price'] is None
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_max_rise_filter_allows_entry(self, mock_get_data, backtest):
        """Test that max rise filter allows entry when rise is within limit"""
        backtest.enable_max_rise_filter = True
        backtest.max_rise_before_entry = {
            (25, 40): 0.05  # 5% max rise
        }
        
        # Create mock data with acceptable rise
        hourly_data = pd.DataFrame({
            'trade_date': [
                '2024-01-01 00:00:00',
                '2024-01-01 01:00:00',
                '2024-01-01 02:00:00'
            ],
            'high': [50000, 51000, 51500],  # 3% rise, within 5% limit
            'low': [49000, 50000, 50500],
            'close': [50500, 51000, 51300]
        })
        mock_get_data.return_value = hourly_data
        
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.02,  # Target: 51000
            wait_hours=24,
            entry_pct_chg=30
        )
        
        assert result['triggered'] is True
        assert result['entry_price'] == 51000.0
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_empty_hourly_data(self, mock_get_data, backtest):
        """Test handling of empty hourly data"""
        mock_get_data.return_value = pd.DataFrame()
        
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.05,
            wait_hours=24,
            entry_pct_chg=30
        )
        
        assert result['triggered'] is False
        assert result['entry_price'] is None
        assert result['entry_datetime'] is None
        assert result['hours_waited'] == 0
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_uses_default_instance_variables(self, mock_get_data, backtest):
        """Test that function uses instance variables when parameters are None"""
        backtest.entry_rise_threshold = 0.03
        backtest.entry_wait_hours = 12
        
        hourly_data = pd.DataFrame({
            'trade_date': ['2024-01-01 00:00:00', '2024-01-01 01:00:00'],
            'high': [50000, 51500],
            'low': [49000, 50500],
            'close': [50500, 51300]
        })
        mock_get_data.return_value = hourly_data
        
        # Call without rise_threshold and wait_hours
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            entry_pct_chg=30
        )
        
        # Should use instance variables (0.03 threshold = 51500 target)
        assert result['triggered'] is True
        assert result['entry_price'] == 51500.0
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_different_entry_pct_chg_ranges(self, mock_get_data, backtest):
        """Test max rise filter with different entry_pct_chg ranges"""
        backtest.enable_max_rise_filter = True
        backtest.max_rise_before_entry = {
            (25, 40): 0.01,
            (40, 60): 0.08,
            (60, 90): 0.06,
            (90, 999): 0.10
        }
        
        hourly_data = pd.DataFrame({
            'trade_date': ['2024-01-01 00:00:00', '2024-01-01 01:00:00'],
            'high': [50000, 54000],  # 8% rise
            'low': [49000, 53000],
            'close': [50500, 53500]
        })
        mock_get_data.return_value = hourly_data
        
        # Test with 50% entry_pct_chg (should allow 8% rise)
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.08,
            wait_hours=24,
            entry_pct_chg=50  # Falls in 40-60% range, allows 8% rise
        )
        
        assert result['triggered'] is True
    
    @patch.object(Backtrade4Backtest, 'get_hourly_kline_data')
    def test_exception_handling(self, mock_get_data, backtest):
        """Test that exceptions are handled gracefully"""
        mock_get_data.side_effect = Exception("Database error")
        
        result = backtest.find_entry_trigger_point(
            symbol='BTCUSDT',
            open_price=50000.0,
            start_date='2024-01-01',
            rise_threshold=0.05,
            wait_hours=24,
            entry_pct_chg=30
        )
        
        assert result['triggered'] is False
        assert result['entry_price'] is None
        assert result['entry_datetime'] is None