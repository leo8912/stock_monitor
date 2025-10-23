import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, time

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.data.quotation import is_market_open, process_stock_data

class TestQuotation(unittest.TestCase):
    
    @patch('stock_monitor.data.quotation.datetime')
    def test_is_market_open_weekday_morning(self, mock_datetime):
        """测试工作日早上开市时间"""
        # 模拟周一上午10:00
        mock_now = MagicMock()
        mock_now.weekday.return_value = 0  # 周一
        mock_now.time.return_value = time(10, 0)
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time = time
        
        self.assertTrue(is_market_open())
    
    @patch('stock_monitor.data.quotation.datetime')
    def test_is_market_open_weekday_noon(self, mock_datetime):
        """测试工作日中午休市时间"""
        # 模拟周一中午12:30
        mock_now = MagicMock()
        mock_now.weekday.return_value = 0  # 周一
        mock_now.time.return_value = time(12, 30)
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time = time
        
        self.assertFalse(is_market_open())
    
    @patch('stock_monitor.data.quotation.datetime')
    def test_is_market_open_weekday_afternoon(self, mock_datetime):
        """测试工作日下午开市时间"""
        # 模拟周一下午14:00
        mock_now = MagicMock()
        mock_now.weekday.return_value = 0  # 周一
        mock_now.time.return_value = time(14, 0)
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time = time
        
        self.assertTrue(is_market_open())
    
    @patch('stock_monitor.data.quotation.datetime')
    def test_is_market_open_weekend(self, mock_datetime):
        """测试周末时间"""
        # 模拟周六上午10:00
        mock_now = MagicMock()
        mock_now.weekday.return_value = 5  # 周六
        mock_now.time.return_value = time(10, 0)
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time = time
        
        self.assertFalse(is_market_open())
    
    def test_process_stock_data_empty(self):
        """测试处理空数据"""
        result = process_stock_data({}, [])
        self.assertEqual(result, [])
    
    def test_process_stock_data_valid(self):
        """测试处理有效数据"""
        mock_data = {
            'sh600460': {
                'name': '士兰微',
                'now': '30.50',
                'close': '30.00',
                'high': '30.50',
                'low': '30.00',
                'bid1': '30.50',
                'bid1_volume': '1000',
                'ask1': '0.0',
                'ask1_volume': '0'
            }
        }
        
        result = process_stock_data(mock_data, ['sh600460'])
        self.assertEqual(len(result), 1)
        # 检查返回的数据格式
        name, price, change, color, seal_vol, seal_type = result[0]
        self.assertEqual(name, '士兰微')
        self.assertEqual(price, '30.50')
        self.assertIn('+', change)  # 涨幅应该是正数
        self.assertEqual(seal_type, 'up')  # 涨停
        
    def test_process_stock_data_invalid(self):
        """测试处理无效数据"""
        mock_data = {
            'invalid_code': None
        }
        
        result = process_stock_data(mock_data, ['invalid_code'])
        self.assertEqual(len(result), 1)
        # 检查返回的默认数据
        name, price, change, color, seal_vol, seal_type = result[0]
        self.assertEqual(name, 'invalid_code')
        self.assertEqual(price, '--')
        self.assertEqual(change, '--')
        
    def test_process_stock_data_boundary_conditions(self):
        """测试边界条件"""
        # 测试价格为0的情况
        mock_data = {
            'sh000001': {
                'name': '上证指数',
                'now': '0',
                'close': '0',
                'high': '0',
                'low': '0',
                'bid1': '0',
                'bid1_volume': '0',
                'ask1': '0',
                'ask1_volume': '0'
            }
        }
        
        result = process_stock_data(mock_data, ['sh000001'])
        self.assertEqual(len(result), 1)
        name, price, change, color, seal_vol, seal_type = result[0]
        self.assertEqual(name, '上证指数')
        self.assertEqual(price, '0.00')
        # 当close为0时，percent应该为0
        self.assertIn('0.00%', change)
        
    def test_process_stock_data_exception_handling(self):
        """测试异常处理"""
        # 测试数据格式错误的情况
        mock_data = {
            'sh600460': {
                'name': '士兰微',
                'now': 'invalid_price',  # 无效价格
                'close': '30.00',
                'high': '30.50',
                'low': '30.00',
                'bid1': '30.50',
                'bid1_volume': '1000',
                'ask1': '0.0',
                'ask1_volume': '0'
            }
        }
        
        result = process_stock_data(mock_data, ['sh600460'])
        self.assertEqual(len(result), 1)
        name, price, change, color, seal_vol, seal_type = result[0]
        self.assertEqual(name, '士兰微')
        # 价格格式错误时应该显示为"--"
        self.assertEqual(price, '--')
        
    def test_process_stock_data_missing_fields(self):
        """测试缺少字段的情况"""
        # 测试缺少必要字段的情况
        mock_data = {
            'sh600460': {
                'name': '士兰微'
                # 缺少其他必要字段
            }
        }
        
        result = process_stock_data(mock_data, ['sh600460'])
        self.assertEqual(len(result), 1)
        name, price, change, color, seal_vol, seal_type = result[0]
        self.assertEqual(name, '士兰微')
        # 缺少必要字段时应该有合理的默认值
        self.assertIsNotNone(price)
        self.assertIsNotNone(change)

if __name__ == '__main__':
    unittest.main()