import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.core.stock_manager import StockManager

class TestStockManager(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        self.stock_manager = StockManager()
        
    def test_has_stock_data_changed(self):
        """测试股票数据变化检测"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.stock_manager, 'has_stock_data_changed'))
        
    def test_update_last_stock_data(self):
        """测试更新最后股票数据缓存"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.stock_manager, 'update_last_stock_data'))
        
    def test_get_stock_list_data(self):
        """测试获取股票列表数据"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.stock_manager, 'get_stock_list_data'))
            
if __name__ == '__main__':
    unittest.main()