import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.data.stocks import format_stock_code, is_equal

class TestStocks(unittest.TestCase):
    
    def test_format_stock_code_valid_shanghai(self):
        """测试有效的上海股票代码格式化"""
        self.assertEqual(format_stock_code('600460'), 'sh600460')
        self.assertEqual(format_stock_code('510050'), 'sh510050')
    
    def test_format_stock_code_valid_shenzhen(self):
        """测试有效的深圳股票代码格式化"""
        self.assertEqual(format_stock_code('000001'), 'sz000001')
        self.assertEqual(format_stock_code('300001'), 'sz300001')
        self.assertEqual(format_stock_code('200001'), 'sz200001')
    
    def test_format_stock_code_valid_with_prefix(self):
        """测试已经带有前缀的股票代码"""
        self.assertEqual(format_stock_code('sh600460'), 'sh600460')
        self.assertEqual(format_stock_code('sz000001'), 'sz000001')
    
    def test_format_stock_code_invalid(self):
        """测试无效的股票代码"""
        self.assertIsNone(format_stock_code('invalid'))
        self.assertIsNone(format_stock_code('999999'))  # 不存在的交易所代码
        self.assertIsNone(format_stock_code(''))
        # 注意：None值不进行测试，因为函数参数类型为str
    
    def test_is_equal(self):
        """测试数值相等判断"""
        self.assertTrue(is_equal('1.00', '1.00'))
        self.assertTrue(is_equal('1.00', '1.01', 0.02))
        self.assertFalse(is_equal('1.00', '1.05', 0.02))
        self.assertFalse(is_equal('invalid', '1.00'))

if __name__ == '__main__':
    unittest.main()