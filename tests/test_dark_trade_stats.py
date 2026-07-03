"""
暗盘统计数据计算与推送单元测试
"""

import unittest
from unittest.mock import patch

from stock_monitor.services.dark_trade_stats import (
    _clean_code,
    _get_recent_trade_dates,
    calculate_dark_trade_stats,
    format_dark_trade_stats_message,
    push_dark_trade_stats,
)


class TestCleanCode(unittest.TestCase):
    """_clean_code 函数测试"""

    def test_clean_code_with_sh_prefix(self):
        """测试去除 sh 前缀"""
        self.assertEqual(_clean_code("sh600519"), "600519")

    def test_clean_code_with_sz_prefix(self):
        """测试去除 sz 前缀"""
        self.assertEqual(_clean_code("sz000559"), "000559")

    def test_clean_code_with_uppercase_prefix(self):
        """测试去除大写前缀"""
        self.assertEqual(_clean_code("SH600519"), "600519")
        self.assertEqual(_clean_code("SZ000559"), "000559")

    def test_clean_code_without_prefix(self):
        """测试无前缀的情况"""
        self.assertEqual(_clean_code("600519"), "600519")

    def test_clean_code_with_hk_prefix(self):
        """测试去除 hk 前缀"""
        self.assertEqual(_clean_code("hk00700"), "00700")


class TestGetRecentTradeDates(unittest.TestCase):
    """_get_recent_trade_dates 函数测试"""

    def test_get_recent_trade_dates_basic(self):
        """测试获取交易日期基本功能"""
        dates = _get_recent_trade_dates(3)
        self.assertEqual(len(dates), 3)
        for d in dates:
            self.assertRegex(d, r"^\d{8}$")
            # 验证日期格式有效
            year = int(d[:4])
            month = int(d[4:6])
            day = int(d[6:8])
            self.assertGreaterEqual(year, 2020)
            self.assertGreaterEqual(month, 1)
            self.assertLessEqual(month, 12)
            self.assertGreaterEqual(day, 1)
            self.assertLessEqual(day, 31)

    def test_get_recent_trade_dates_single(self):
        """测试获取单个交易日日期"""
        dates = _get_recent_trade_dates(1)
        self.assertEqual(len(dates), 1)
        self.assertRegex(dates[0], r"^\d{8}$")


class TestCalculateDarkTradeStats(unittest.TestCase):
    """calculate_dark_trade_stats 函数测试"""

    @patch("stock_monitor.services.dark_trade_stats.fetch_all_dark_trade")
    @patch("stock_monitor.services.dark_trade_stats.build_net_flow_index")
    def test_calculate_stats_basic(self, mock_build, mock_fetch):
        """测试基本统计计算"""
        # 模拟数据
        mock_fetch.return_value = [{"4": "600519", "6": 1000000}]
        mock_build.return_value = {"600519": 100.0}

        stats = calculate_dark_trade_stats(["sh600519"], history_days=1)

        self.assertIn("market_summary", stats)
        self.assertIn("watchlist_details", stats)
        self.assertIn("date", stats)
        self.assertIsInstance(stats["market_summary"], dict)

    @patch("stock_monitor.services.dark_trade_stats.fetch_all_dark_trade")
    @patch("stock_monitor.services.dark_trade_stats.build_net_flow_index")
    def test_calculate_stats_market_summary(self, mock_build, mock_fetch):
        """测试全市场概览统计"""
        # 模拟多个股票的数据
        mock_fetch.return_value = [{"4": "600519", "6": 1000000}]
        mock_build.return_value = {
            "600519": 100.0,  # 流入
            "000559": -50.0,  # 流出
        }

        stats = calculate_dark_trade_stats([], history_days=1)
        market = stats["market_summary"]

        self.assertIn("inflow_3day_count", market)
        self.assertIn("inflow_5day_gt3_count", market)
        self.assertIn("total_inflow_wan", market)
        self.assertEqual(market["inflow_3day_count"], 1)  # 600519 流入

    @patch("stock_monitor.services.dark_trade_stats.fetch_all_dark_trade")
    @patch("stock_monitor.services.dark_trade_stats.build_net_flow_index")
    def test_calculate_stats_watchlist(self, mock_build, mock_fetch):
        """测试自选股统计"""
        mock_fetch.return_value = [{"4": "600519", "6": 1000000}]
        mock_build.return_value = {"600519": 100.0}

        stats = calculate_dark_trade_stats(["sh600519"], history_days=1)
        watchlist = stats["watchlist_details"]

        self.assertEqual(len(watchlist), 1)
        self.assertEqual(watchlist[0]["code"], "600519")
        self.assertIn("inflow_3day_wan", watchlist[0])
        self.assertIn("inflow_5day_count", watchlist[0])
        self.assertIn("total_inflow_wan", watchlist[0])


class TestFormatDarkTradeStatsMessage(unittest.TestCase):
    """format_dark_trade_stats_message 函数测试"""

    def test_format_message_basic(self):
        """测试基本消息格式"""
        stats = {
            "market_summary": {
                "inflow_3day_count": 100,
                "inflow_5day_gt3_count": 50,
                "total_inflow_wan": 123456.78,
            },
            "watchlist_details": [
                {
                    "code": "600519",
                    "name": "贵州茅台",
                    "inflow_3day_wan": 100.0,
                    "inflow_5day_count": 3,
                    "total_inflow_wan": 500.0,
                }
            ],
            "date": "20260703",
        }

        message = format_dark_trade_stats_message(stats)

        self.assertIn("📊 暗盘资金统计", message)
        self.assertIn("【全市场概览】", message)
        self.assertIn("【自选股暗盘明细】", message)
        self.assertIn("600519", message)
        self.assertIn("贵州茅台", message)

    def test_format_message_empty_watchlist(self):
        """测试无自选股的情况"""
        stats = {
            "market_summary": {
                "inflow_3day_count": 100,
                "inflow_5day_gt3_count": 50,
                "total_inflow_wan": 123456.78,
            },
            "watchlist_details": [],
            "date": "20260703",
        }

        message = format_dark_trade_stats_message(stats)

        self.assertIn("（无自选股）", message)

    def test_format_message_date_display(self):
        """测试日期显示格式"""
        stats = {
            "market_summary": {
                "inflow_3day_count": 0,
                "inflow_5day_gt3_count": 0,
                "total_inflow_wan": 0,
            },
            "watchlist_details": [],
            "date": "20260703",
        }

        message = format_dark_trade_stats_message(stats)

        self.assertIn("2026-07-03", message)


class TestPushDarkTradeStats(unittest.TestCase):
    """push_dark_trade_stats 函数测试"""

    @patch("stock_monitor.services.notifier.NotifierService.dispatch_custom_message")
    @patch("stock_monitor.services.dark_trade_stats.calculate_dark_trade_stats")
    def test_push_success(self, mock_calc, mock_dispatch):
        """测试推送成功"""
        mock_calc.return_value = {
            "market_summary": {"inflow_3day_count": 100},
            "watchlist_details": [],
            "date": "20260703",
        }
        mock_dispatch.return_value = True

        config = {"wecom_webhook": "https://test.com"}
        result = push_dark_trade_stats(config, ["sh600519"])

        self.assertTrue(result)
        mock_dispatch.assert_called_once()

    @patch("stock_monitor.services.dark_trade_stats.calculate_dark_trade_stats")
    def test_push_empty_stats(self, mock_calc):
        """测试空统计数据跳过推送"""
        mock_calc.return_value = {"market_summary": {}, "watchlist_details": []}

        config = {"wecom_webhook": "https://test.com"}
        result = push_dark_trade_stats(config, [])

        self.assertFalse(result)

    @patch("stock_monitor.services.dark_trade_stats.calculate_dark_trade_stats")
    def test_push_exception(self, mock_calc):
        """测试推送异常处理"""
        mock_calc.side_effect = Exception("Test exception")

        config = {"wecom_webhook": "https://test.com"}
        result = push_dark_trade_stats(config, [])

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
