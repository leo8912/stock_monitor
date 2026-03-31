import unittest
from unittest.mock import MagicMock

import pandas as pd

from stock_monitor.core.stock_data_fetcher import StockDataFetcher


class TestMootdxIntegration(unittest.TestCase):
    def setUp(self):
        self.fetcher = StockDataFetcher()
        # Mock mootdx_client
        self.fetcher.mootdx_client = MagicMock()

    def test_fetch_large_orders_flow(self):
        """
        测试主动大单买卖量统计
        数据集：vol >= 100 的条目：
          - 索引1: vol=100, buyorsell=0 (主动买入)
          - 索引2: vol=200, buyorsell=1 (主动卖出)
          - 索引4: vol=500, buyorsell=0 (主动买入)
        buy_vol = 100 + 500 = 600
        sell_vol = 200
        """
        data = {
            "vol": [50, 100, 200, 80, 500],
            "buyorsell": [0, 0, 1, 0, 0],  # 0:主动买, 1:主动卖
            "price": [10.0, 10.1, 10.2, 10.1, 10.3],
        }
        df = pd.DataFrame(data)
        self.fetcher.mootdx_client.transaction.return_value = df

        buy_vol, sell_vol = self.fetcher.fetch_large_orders_flow("sh600519")
        self.assertEqual(buy_vol, 600.0)  # 100 + 500
        self.assertEqual(sell_vol, 200.0)  # 200

    def test_fetch_large_orders_flow_empty(self):
        """测试空数据时返回 (0.0, 0.0) 元组"""
        self.fetcher.mootdx_client.transaction.return_value = pd.DataFrame()
        buy_vol, sell_vol = self.fetcher.fetch_large_orders_flow("sz000001")
        self.assertEqual(buy_vol, 0.0)
        self.assertEqual(sell_vol, 0.0)

    def test_fetch_large_orders_flow_filter(self):
        """测试 < 100手的小单被过滤"""
        data = {
            "vol": [10, 50, 99],
            "buyorsell": [0, 1, 0],
            "price": [10.0, 10.1, 10.2],
        }
        df = pd.DataFrame(data)
        self.fetcher.mootdx_client.transaction.return_value = df

        buy_vol, sell_vol = self.fetcher.fetch_large_orders_flow("sh600000")
        self.assertEqual(buy_vol, 0.0)
        self.assertEqual(sell_vol, 0.0)


if __name__ == "__main__":
    unittest.main()
