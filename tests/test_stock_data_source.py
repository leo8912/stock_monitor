"""
股票数据源接口测试
测试StockDataSource抽象接口及其实现类
"""

import unittest

from stock_monitor.data.stock.stock_data_source import StockDataSource
from stock_monitor.data.stock.stock_db import StockDatabase


class TestStockDataSourceInterface(unittest.TestCase):
    """测试StockDataSource接口定义"""

    def test_interface_methods(self):
        """测试接口方法定义"""
        # 确保接口方法存在
        self.assertTrue(hasattr(StockDataSource, "get_stock_by_code"))
        self.assertTrue(hasattr(StockDataSource, "search_stocks"))
        self.assertTrue(hasattr(StockDataSource, "get_all_stocks"))
        self.assertTrue(hasattr(StockDataSource, "get_stocks_by_market_type"))


class TestStockDatabaseSource(unittest.TestCase):
    """测试StockDatabase实现"""

    def setUp(self):
        """测试前准备 - 使用真实表结构的临时文件数据库"""
        import os
        import tempfile

        self._tmp = tempfile.mkdtemp()
        self._db_path = os.path.join(self._tmp, "test_stocks.db")

        # 创建真实的 StockDatabase（触发 _initialize_database 建表）
        # 然后覆盖 db_path 指向临时数据库，避免污染全局单例的数据
        self.db_source = StockDatabase()
        self._original_db_path = self.db_source.db_path
        self.db_source.db_path = self._db_path
        self.db_source._initialize_database()

    def tearDown(self):
        """恢复全局单例的 db_path"""
        if hasattr(self, "_original_db_path"):
            self.db_source.db_path = self._original_db_path

    def _insert_sample_stocks(self):
        """向测试数据库插入样本数据"""
        with self.db_source._write_connection() as conn:
            conn.execute(
                "INSERT INTO stocks (code, name, pinyin, abbr, market_type) VALUES (?, ?, ?, ?, ?)",
                ("sh600519", "贵州茅台", "guizhoumaotai", "GZMT", "A"),
            )
            conn.execute(
                "INSERT INTO stocks (code, name, pinyin, abbr, market_type) VALUES (?, ?, ?, ?, ?)",
                ("sz000001", "平安银行", "pinganyinhang", "PAYH", "A"),
            )

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

    def test_search_stocks_with_data(self):
        """插入数据后搜索应返回匹配结果"""
        self._insert_sample_stocks()

        results = self.db_source.search_stocks("茅台")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "sh600519")
        self.assertEqual(results[0]["name"], "贵州茅台")

    def test_get_stock_by_code_with_data(self):
        """插入数据后按代码查询应返回正确结果"""
        self._insert_sample_stocks()

        result = self.db_source.get_stock_by_code("sz000001")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "平安银行")
        self.assertEqual(result["code"], "sz000001")


if __name__ == "__main__":
    unittest.main()
