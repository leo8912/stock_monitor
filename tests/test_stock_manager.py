import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.core.stock_manager import StockManager

class TestStockManager(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        self.stock_manager = StockManager()
        
    def test_is_stock_data_valid(self):
        """测试股票数据有效性检查"""
        # 测试有效数据
        valid_data = {'now': 10.0, 'close': 9.5}
        self.assertTrue(self.stock_manager.is_stock_data_valid(valid_data))
        
        # 测试无效数据
        invalid_data = {'name': 'test'}
        self.assertFalse(self.stock_manager.is_stock_data_valid(invalid_data))
        
        # 测试空数据
        self.assertFalse(self.stock_manager.is_stock_data_valid({}))
        # 测试None数据
        self.assertFalse(self.stock_manager.is_stock_data_valid(None))  # type: ignore
        
    def test_fetch_stock_data(self):
        """测试获取股票数据"""
        # 使用少量真实存在的股票代码进行测试
        stocks_list = ['sh600460', 'sz000001']
        stocks, failed_stocks = self.stock_manager.fetch_stock_data(stocks_list)
        
        # 验证返回的数据结构
        self.assertIsInstance(stocks, list)
        self.assertIsInstance(failed_stocks, list)
        
        # 验证每个股票数据的格式
        for stock in stocks:
            self.assertEqual(len(stock), 6)  # (name, price, change_str, color, seal_vol, seal_type)
            
if __name__ == '__main__':
    unittest.main()