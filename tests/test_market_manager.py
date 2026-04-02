#!/usr/bin/env python
"""
MarketManager 单元测试模块

测试市场管理器功能，包括：
- 单例模式验证
- 市场状态判断
- 市场情绪数据管理
- 刷新间隔计算
- 边界情况处理
"""

import datetime
import unittest
from unittest.mock import patch

from stock_monitor.core.market_manager import (
    MarketManager,
    MarketSentiment,
)


class TestMarketSentiment(unittest.TestCase):
    """MarketSentiment 容器测试"""

    def test_initial_values(self):
        """测试初始值"""
        sentiment = MarketSentiment()

        self.assertEqual(sentiment.up_count, 0)
        self.assertEqual(sentiment.down_count, 0)
        self.assertEqual(sentiment.flat_count, 0)
        self.assertEqual(sentiment.total_count, 0)
        self.assertIsNone(sentiment.last_update)

    def test_update_method(self):
        """测试 update 方法"""
        sentiment = MarketSentiment()
        before_update = datetime.datetime.now()

        sentiment.update(2000, 1500, 500, 4000)

        after_update = datetime.datetime.now()

        self.assertEqual(sentiment.up_count, 2000)
        self.assertEqual(sentiment.down_count, 1500)
        self.assertEqual(sentiment.flat_count, 500)
        self.assertEqual(sentiment.total_count, 4000)
        self.assertIsNotNone(sentiment.last_update)
        self.assertGreaterEqual(sentiment.last_update, before_update)
        self.assertLessEqual(sentiment.last_update, after_update)

    def test_up_ratio_normal(self):
        """测试上涨占比计算（正常情况）"""
        sentiment = MarketSentiment()
        sentiment.update(3000, 1000, 0, 4000)

        ratio = sentiment.up_ratio

        self.assertAlmostEqual(ratio, 0.75)

    def test_up_ratio_zero_total(self):
        """测试上涨占比计算（总数为 0）"""
        sentiment = MarketSentiment()
        # total_count 默认为 0

        ratio = sentiment.up_ratio

        self.assertEqual(ratio, 0.5)  # 默认返回 0.5

    def test_up_ratio_all_up(self):
        """测试上涨占比计算（全部上涨）"""
        sentiment = MarketSentiment()
        sentiment.update(4000, 0, 0, 4000)

        ratio = sentiment.up_ratio

        self.assertAlmostEqual(ratio, 1.0)

    def test_up_ratio_all_down(self):
        """测试上涨占比计算（全部下跌）"""
        sentiment = MarketSentiment()
        sentiment.update(0, 4000, 0, 4000)

        ratio = sentiment.up_ratio

        self.assertAlmostEqual(ratio, 0.0)


class TestMarketManagerSingleton(unittest.TestCase):
    """MarketManager 单例模式测试"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = MarketManager()
        manager2 = MarketManager()

        self.assertIs(manager1, manager2)

    def test_sentiment_initialized_once(self):
        """测试 sentiment 只初始化一次"""
        manager = MarketManager()
        sentiment1 = manager.sentiment

        # 再次获取实例
        manager2 = MarketManager()
        sentiment2 = manager2.sentiment

        self.assertIs(sentiment1, sentiment2)


class TestMarketManagerIsMarketOpen(unittest.TestCase):
    """MarketManager.is_market_open() 静态方法测试"""

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekend_saturday(self, mock_datetime):
        """测试周六闭市"""
        mock_now = datetime.datetime(2024, 1, 6, 10, 0)  # Saturday
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertFalse(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekend_sunday(self, mock_datetime):
        """测试周日闭市"""
        mock_now = datetime.datetime(2024, 1, 7, 10, 0)  # Sunday
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertFalse(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekday_morning_trading(self, mock_datetime):
        """测试工作日交易时段（上午）"""
        mock_now = datetime.datetime(2024, 1, 8, 10, 0)  # Monday 10:00
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertTrue(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekday_afternoon_trading(self, mock_datetime):
        """测试工作日交易时段（下午）"""
        mock_now = datetime.datetime(2024, 1, 8, 14, 0)  # Monday 14:00
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertTrue(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekday_before_market(self, mock_datetime):
        """测试工作日开市前"""
        mock_now = datetime.datetime(2024, 1, 8, 9, 0)  # Monday 09:00
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertFalse(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekday_lunch_break(self, mock_datetime):
        """测试工作日午休时间"""
        mock_now = datetime.datetime(2024, 1, 8, 12, 0)  # Monday 12:00
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertFalse(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_weekday_after_market(self, mock_datetime):
        """测试工作日收市后"""
        mock_now = datetime.datetime(2024, 1, 8, 15, 30)  # Monday 15:30
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertFalse(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_market_open_start_time(self, mock_datetime):
        """测试开市时间点（9:15）"""
        mock_now = datetime.datetime(2024, 1, 8, 9, 15)  # Monday 09:15
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertTrue(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_market_morning_end_time(self, mock_datetime):
        """测试上午收市时间点（11:30）"""
        mock_now = datetime.datetime(2024, 1, 8, 11, 30)  # Monday 11:30
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertTrue(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_market_afternoon_start_time(self, mock_datetime):
        """测试下午开市时间点（13:00）"""
        mock_now = datetime.datetime(2024, 1, 8, 13, 0)  # Monday 13:00
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertTrue(result)

    @patch("stock_monitor.core.market_manager.datetime")
    def test_market_afternoon_end_time(self, mock_datetime):
        """测试下午收市时间点（15:00）"""
        mock_now = datetime.datetime(2024, 1, 8, 15, 0)  # Monday 15:00
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.time.side_effect = datetime.time

        result = MarketManager.is_market_open()

        self.assertTrue(result)


class TestMarketManagerGetMarketStatus(unittest.TestCase):
    """MarketManager.get_market_status() 测试"""

    @patch("stock_monitor.core.market_manager.MarketManager.is_market_open")
    def test_get_market_status_open(self, mock_is_open):
        """测试获取开市状态"""
        mock_is_open.return_value = True

        status = MarketManager.get_market_status()

        self.assertEqual(status, "开市")

    @patch("stock_monitor.core.market_manager.MarketManager.is_market_open")
    def test_get_market_status_closed(self, mock_is_open):
        """测试获取闭市状态"""
        mock_is_open.return_value = False

        status = MarketManager.get_market_status()

        self.assertEqual(status, "闭市")


class TestMarketManagerGetRefreshInterval(unittest.TestCase):
    """MarketManager.get_refresh_interval() 测试"""

    @patch("stock_monitor.core.market_manager.MarketManager.is_market_open")
    def test_get_refresh_interval_during_market(self, mock_is_open):
        """测试开市期间的刷新间隔"""
        mock_is_open.return_value = True

        interval = MarketManager.get_refresh_interval(5)

        self.assertEqual(interval, 5)

    @patch("stock_monitor.core.market_manager.MarketManager.is_market_open")
    def test_get_refresh_interval_after_market(self, mock_is_open):
        """测试闭市期间的刷新间隔"""
        mock_is_open.return_value = False

        interval = MarketManager.get_refresh_interval(5)

        self.assertEqual(interval, 30)  # 固定 30 秒


class TestMarketManagerUpdateSentiment(unittest.TestCase):
    """MarketManager.update_sentiment() 测试"""

    def test_update_sentiment(self):
        """测试更新市场情绪"""
        manager = MarketManager()

        manager.update_sentiment(2500, 1200, 300, 4000)

        sentiment = manager.get_sentiment()
        self.assertEqual(sentiment.up_count, 2500)
        self.assertEqual(sentiment.down_count, 1200)
        self.assertEqual(sentiment.flat_count, 300)
        self.assertEqual(sentiment.total_count, 4000)


class TestMarketManagerGetSentiment(unittest.TestCase):
    """MarketManager.get_sentiment() 测试"""

    def test_get_sentiment_returns_object(self):
        """测试获取情绪数据返回对象"""
        manager = MarketManager()

        sentiment = manager.get_sentiment()

        self.assertIsInstance(sentiment, MarketSentiment)

    def test_get_sentiment_same_as_instance(self):
        """测试获取的情绪数据与实例相同"""
        manager = MarketManager()

        sentiment = manager.get_sentiment()

        self.assertIs(sentiment, manager.sentiment)


if __name__ == "__main__":
    unittest.main()
