"""
股票数据源接口测试
测试StockDataSource抽象接口及其实现类
"""

import unittest
from unittest.mock import Mock, patch

from stock_monitor.data.stock.stock_data_source import StockDataSource
from stock_monitor.data.stock.stock_db import StockDatabase


class TestStockDataSourceInterface(unittest.TestCase):
    """测试StockDataSource接口定义"""
    
    def test_interface_methods(self):
        """测试接口方法定义"""
        # 确保接口方法存在
        self.assertTrue(hasattr(StockDataSource, 'get_stock_by_code'))
        self.assertTrue(hasattr(StockDataSource, 'search_stocks'))
        self.assertTrue(hasattr(StockDataSource, 'get_all_stocks'))
        self.assertTrue(hasattr(StockDataSource, 'get_stocks_by_market_type'))


class TestStockDatabaseSource(unittest.TestCase):
    """测试StockDatabase实现"""
    
    def setUp(self):
        """测试前准备"""
        # 使用内存数据库进行测试
        with patch.object(StockDatabase, '_initialize_database'):
            self.db_source = StockDatabase()
            self.db_source.db_path = ':memory:'  # 使用内存数据库
            # 注意：这里我们不调用_initialize_database，因为我们已经在patch它了
    
    def test_get_stock_by_code_not_found(self):
        """测试根据代码获取股票信息 - 未找到情况"""
        result = self.db_source.get_stock_by_code("nonexistent")
        self.assertIsNone(result)
    
    def test_search_stocks_empty(self):
        """测试搜索股票 - 空结果"""
        results = self.db_source.search_stocks("nonexistent")
        self.assertEqual(results, [])
    
    def test_get_all_stocks_empty(self):
        """测试获取所有股票 - 空结果"""
        results = self.db_source.get_all_stocks()
        self.assertEqual(results, [])
    
    def test_get_stocks_by_market_type_empty(self):
        """测试按市场类型获取股票 - 空结果"""
        results = self.db_source.get_stocks_by_market_type("A")
        self.assertEqual(results, [])


if __name__ == '__main__':
    unittest.main()