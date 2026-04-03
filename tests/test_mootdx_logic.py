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
        阈值：500,000 元
        数据集：
          - vol=50: amount=50*10.0*100=50,000 (< 阈值，过滤)
          - vol=100: amount=100*10.1*100=101,000 (< 阈值，过滤)
          - vol=200: amount=200*10.2*100=204,000 (< 阈值，过滤)
          - vol=80: amount=80*10.1*100=80,800 (< 阈值，过滤)
          - vol=500: amount=500*10.3*100=515,000 (>= 阈值，统计) 主动买入
        buy_vol = 515,000
        sell_vol = 0
        net = 515,000
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
        self.assertEqual(buy_vol, 515000.0)  # 只有 vol=500 的被统计
        self.assertEqual(sell_vol, 0.0)  # vol=200 的金额不足阈值
        self.assertEqual(net, 515000.0)

    @unittest.mock.patch("stock_monitor.core.quant_engine.ak")
    def test_fetch_large_orders_flow_empty(self, mock_ak):
        """测试空数据时返回 (0.0, 0.0) 元组"""
        # Ensure empty DataFrame is returned
        self.mock_client.transaction.return_value = pd.DataFrame()

        # Mock akshare to return None/empty to prevent compensation
        mock_ak.stock_individual_fund_flow.return_value = pd.DataFrame()

        # Clear cache before test
        self.quant_engine._large_order_cache.clear()

        # Also need to reset the cache for this specific stock
        self.quant_engine._large_order_cache.pop("sz000001", None)

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
