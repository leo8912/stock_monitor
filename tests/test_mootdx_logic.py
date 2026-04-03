import unittest
from unittest.mock import MagicMock

import pandas as pd

from stock_monitor.core.quant_engine import QuantEngine


class TestMootdxIntegration(unittest.TestCase):
    def setUp(self):
        # Create a mock for mootdx_client
        self.mock_client = MagicMock()

        # Mock the transaction method to return empty by default
        self.mock_client.transaction.return_value = pd.DataFrame()

        # Create QuantEngine with mocked client
        self.quant_engine = QuantEngine(self.mock_client)

        # Clear any existing cache to ensure clean state
        self.quant_engine._large_order_cache.clear()

    def test_fetch_large_orders_flow(self):
        """
        测试主动大单买卖量统计
        数据集：vol >= 100 的条目：
          - 索引 1: vol=100, buyorsell=0 (主动买入)
          - 索引 2: vol=200, buyorsell=1 (主动卖出)
          - 索引 4: vol=500, buyorsell=0 (主动买入)
        buy_vol = 100 + 500 = 600
        sell_vol = 200
        """
        data = {
            "time": ["09:30", "09:31", "09:32", "09:33", "09:34"],  # 添加时间列
            "vol": [50, 100, 200, 80, 500],
            "buyorsell": [0, 0, 1, 0, 0],  # 0:主动买，1:主动卖
            "price": [10.0, 10.1, 10.2, 10.1, 10.3],
        }
        df = pd.DataFrame(data)
        self.mock_client.transaction.return_value = df

        # Clear cache before test
        self.quant_engine._large_order_cache.clear()

        buy_vol, sell_vol, net = self.quant_engine.fetch_large_orders_flow("sh600519")
        self.assertEqual(buy_vol, 600.0)  # 100 + 500
        self.assertEqual(sell_vol, 200.0)  # 200
        self.assertEqual(net, 400.0)  # 600 - 200

    def test_fetch_large_orders_flow_empty(self):
        """测试空数据时返回 (0.0, 0.0) 元组"""
        # Ensure empty DataFrame is returned
        self.mock_client.transaction.return_value = pd.DataFrame()

        # Clear cache before test
        self.quant_engine._large_order_cache.clear()

        buy_vol, sell_vol, net = self.quant_engine.fetch_large_orders_flow("sz000001")
        self.assertEqual(buy_vol, 0.0)
        self.assertEqual(sell_vol, 0.0)
        self.assertEqual(net, 0.0)

    def test_fetch_large_orders_flow_filter(self):
        """测试 < 100 手的小单被过滤"""
        data = {
            "time": ["09:30", "09:31", "09:32"],  # 添加时间列
            "vol": [10, 50, 99],
            "buyorsell": [0, 1, 0],
            "price": [10.0, 10.1, 10.2],
        }
        df = pd.DataFrame(data)
        self.mock_client.transaction.return_value = df

        # Clear cache before test
        self.quant_engine._large_order_cache.clear()

        buy_vol, sell_vol, net = self.quant_engine.fetch_large_orders_flow("sh600000")
        self.assertEqual(buy_vol, 0.0)
        self.assertEqual(sell_vol, 0.0)
        self.assertEqual(net, 0.0)


if __name__ == "__main__":
    unittest.main()
