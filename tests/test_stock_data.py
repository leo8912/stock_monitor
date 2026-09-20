import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stock_monitor.data.stock.stocks import load_stock_data


class TestStockData(unittest.TestCase):
    def test_load_stock_data(self):
        """测试加载股票数据"""
        # 测试函数存在
        self.assertTrue(callable(load_stock_data))

        # 尝试加载数据
        try:
            data = load_stock_data()
            # 验证返回数据结构
            self.assertIsInstance(data, list)
            if data:  # 如果有数据
                # 检查第一条数据的结构
                first_stock = data[0]
                self.assertIsInstance(first_stock, dict)
                self.assertIn("code", first_stock)
                self.assertIn("name", first_stock)
        except Exception as e:
            # 如果文件不存在或加载失败，应该返回空列表而不是抛出异常
            self.fail(f"load_stock_data raised {type(e).__name__} unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
