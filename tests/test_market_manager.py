import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stock_monitor.core.market_manager import MarketManager


class TestMarketManager(unittest.TestCase):
    def setUp(self):
        """测试前准备"""
        self.market_manager = MarketManager()

    def test_initialization(self):
        """测试市场管理器初始化"""
        self.assertIsInstance(self.market_manager, MarketManager)

    def test_is_market_open(self):
        """测试市场开启状态检测方法"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.market_manager, "is_market_open"))
        # 注意：实际测试需要mock时间

    def test_get_market_status(self):
        """测试获取市场状态方法"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.market_manager, "get_market_status"))
        # 注意：实际测试需要mock时间

    def test_get_refresh_interval(self):
        """测试获取刷新间隔方法"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.market_manager, "get_refresh_interval"))


if __name__ == "__main__":
    unittest.main()
