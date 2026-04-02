#!/usr/bin/env python
"""
StockManager 单元测试模块

测试股票管理器功能，包括：
- 股票数据变化检测
- 缓存更新机制
- 数据处理流程
- 大单流向缓存
- 集合竞价缓存
- 边界情况处理
"""

import unittest
from unittest.mock import MagicMock

from stock_monitor.core.stock_manager import StockManager
from stock_monitor.models.stock_data import StockRowData


class TestStockManagerInitialization(unittest.TestCase):
    """StockManager 初始化测试"""

    def test_initialization(self):
        """测试初始化"""
        manager = StockManager()

        self.assertIsNotNone(manager._processor)
        self.assertEqual(len(manager._last_stock_data), 0)
        self.assertIsNotNone(manager._executor)
        self.assertEqual(len(manager._large_orders_cache), 0)
        self.assertEqual(len(manager._auction_cache), 0)

    def test_initialization_with_custom_service(self):
        """测试使用自定义服务初始化"""
        mock_service = MagicMock()
        manager = StockManager(stock_data_service=mock_service)

        self.assertIs(manager._stock_data_service, mock_service)


class TestStockManagerChangeDetection(unittest.TestCase):
    """StockManager 数据变化检测测试"""

    def setUp(self):
        self.manager = StockManager()

    def test_has_stock_data_changed_empty_cache(self):
        """测试空缓存时检测到变化"""
        stocks = [
            StockRowData(
                code="000001",
                name="平安银行",
                price="10.00",
                change_str="+1.00%",
                color_hex="#ff0000",
                seal_vol="100k",
                seal_type="up",
            )
        ]

        # 空缓存时应返回 True
        result = self.manager.has_stock_data_changed(stocks)

        self.assertTrue(result)

    def test_has_stock_data_changed_no_change(self):
        """测试数据无变化"""
        stock = StockRowData(
            code="000001",
            name="平安银行",
            price="10.00",
            change_str="+1.00%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )
        stocks = [stock]

        # 先更新缓存
        self.manager.update_last_stock_data(stocks)

        # 相同数据应不检测到变化
        result = self.manager.has_stock_data_changed(stocks)

        self.assertFalse(result)

    def test_has_stock_data_changed_price_changed(self):
        """测试价格变化检测"""
        stock1 = StockRowData(
            code="000001",
            name="平安银行",
            price="10.00",
            change_str="+1.00%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )
        stock2 = StockRowData(
            code="000001",
            name="平安银行",
            price="10.50",  # 价格变化
            change_str="+1.50%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )

        # 更新缓存
        self.manager.update_last_stock_data([stock1])

        # 价格变化应检测到
        result = self.manager.has_stock_data_changed([stock2])

        self.assertTrue(result)

    def test_has_stock_data_changed_new_stock_added(self):
        """测试新增股票检测"""
        stock1 = StockRowData(
            code="000001",
            name="平安银行",
            price="10.00",
            change_str="+1.00%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )
        stock2 = StockRowData(
            code="600519",
            name="贵州茅台",
            price="1800.00",
            change_str="+2.00%",
            color_hex="#ff0000",
            seal_vol="50k",
            seal_type="up",
        )

        # 更新缓存（只有平安银行）
        self.manager.update_last_stock_data([stock1])

        # 新增股票应检测到变化
        result = self.manager.has_stock_data_changed([stock1, stock2])

        self.assertTrue(result)

    def test_has_stock_data_changed_stock_removed(self):
        """测试股票移除检测"""
        stock1 = StockRowData(
            code="000001",
            name="平安银行",
            price="10.00",
            change_str="+1.00%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )
        stock2 = StockRowData(
            code="600519",
            name="贵州茅台",
            price="1800.00",
            change_str="+2.00%",
            color_hex="#ff0000",
            seal_vol="50k",
            seal_type="up",
        )

        # 更新缓存（两只股票）
        self.manager.update_last_stock_data([stock1, stock2])

        # 移除一只股票应检测到变化
        result = self.manager.has_stock_data_changed([stock1])

        self.assertTrue(result)

    def test_update_last_stock_data(self):
        """测试更新最后股票数据缓存"""
        stock = StockRowData(
            code="000001",
            name="平安银行",
            price="10.00",
            change_str="+1.00%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )

        self.manager.update_last_stock_data([stock])

        # 验证缓存已更新
        self.assertIn("平安银行", self.manager._last_stock_data)
        self.assertEqual(self.manager._last_stock_data["平安银行"], stock.hash_key)

    def test_update_last_stock_data_clears_previous(self):
        """测试更新缓存会清除之前的数据"""
        stock1 = StockRowData(
            code="000001",
            name="平安银行",
            price="10.00",
            change_str="+1.00%",
            color_hex="#ff0000",
            seal_vol="100k",
            seal_type="up",
        )
        stock2 = StockRowData(
            code="600519",
            name="贵州茅台",
            price="1800.00",
            change_str="+2.00%",
            color_hex="#ff0000",
            seal_vol="50k",
            seal_type="up",
        )

        # 先添加一只股票
        self.manager.update_last_stock_data([stock1])
        self.assertIn("平安银行", self.manager._last_stock_data)

        # 再更新为另一只股票
        self.manager.update_last_stock_data([stock2])

        # 验证旧数据被清除
        self.assertNotIn("平安银行", self.manager._last_stock_data)
        self.assertIn("贵州茅台", self.manager._last_stock_data)


class TestStockManagerLargeOrdersCache(unittest.TestCase):
    """StockManager 大单流向缓存测试"""

    def setUp(self):
        self.manager = StockManager()

    def test_large_orders_cache_storage(self):
        """测试大单流向缓存存储"""
        # 模拟大单数据
        large_order_data = (1000.0, 500.0, 250.0)  # 买，卖，净

        # 存入缓存
        self.manager._large_orders_cache["000001"] = large_order_data

        # 验证缓存
        self.assertIn("000001", self.manager._large_orders_cache)
        self.assertEqual(self.manager._large_orders_cache["000001"], large_order_data)

    def test_large_orders_cache_default_value(self):
        """测试大单流向缓存默认值"""
        # 未缓存的股票应返回默认值
        default_value = self.manager._large_orders_cache.get("000001", (0.0, 0.0, 0.0))

        self.assertEqual(default_value, (0.0, 0.0, 0.0))


class TestStockManagerAuctionCache(unittest.TestCase):
    """StockManager 集合竞价缓存测试"""

    def setUp(self):
        self.manager = StockManager()

    def test_auction_cache_storage(self):
        """测试集合竞价缓存存储"""
        # 模拟竞价数据
        auction_data = {"price": 10.20, "volume": 5000, "intensity": 8.5}

        # 存入缓存
        self.manager._auction_cache["000001"] = auction_data

        # 验证缓存
        self.assertIn("000001", self.manager._auction_cache)
        self.assertEqual(self.manager._auction_cache["000001"], auction_data)

    def test_auction_cache_default_value(self):
        """测试集合竞价缓存默认值"""
        # 未缓存的股票应返回空字典
        default_value = self.manager._auction_cache.get("000001", {})

        self.assertEqual(default_value, {})


class TestStockManagerFetchAndProcessStocks(unittest.TestCase):
    """StockManager 获取并处理股票数据测试"""

    def setUp(self):
        self.manager = StockManager()
        # Mock 数据服务
        self.mock_service = MagicMock()
        self.manager._stock_data_service = self.mock_service

    def test_fetch_and_process_stocks_success(self):
        """测试成功获取并处理股票数据"""
        # Mock 返回数据
        mock_data = {"000001": {"name": "平安银行", "now": 10.50, "close": 10.00}}
        self.mock_service.get_multiple_stocks_data.return_value = mock_data

        # 调用方法
        stocks, failed_count = self.manager.fetch_and_process_stocks(["000001"])

        # 验证结果
        self.assertEqual(len(stocks), 1)
        self.assertIsInstance(stocks[0], StockRowData)
        self.assertEqual(failed_count, 0)

    def test_fetch_and_process_stocks_with_failure(self):
        """测试获取股票数据失败的情况"""
        # Mock 部分失败的数据
        mock_data = {
            "000001": {"name": "平安银行", "now": 10.50, "close": 10.00},
            "600519": None,  # 失败
        }
        self.mock_service.get_multiple_stocks_data.return_value = mock_data

        # 调用方法
        stocks, failed_count = self.manager.fetch_and_process_stocks(
            ["000001", "600519"]
        )

        # 验证结果
        self.assertEqual(len(stocks), 2)
        self.assertEqual(failed_count, 1)
        # 失败的股票应有默认值
        failed_stock = stocks[1]
        self.assertEqual(failed_stock.price, "--")
        self.assertEqual(failed_stock.change_str, "--")

    def test_get_stock_list_data(self):
        """测试获取股票列表数据"""
        # Mock 返回数据
        mock_data = {"000001": {"name": "平安银行", "now": 10.50, "close": 10.00}}
        self.mock_service.get_multiple_stocks_data.return_value = mock_data

        # 调用方法
        stocks = self.manager.get_stock_list_data(["000001"])

        # 验证结果
        self.assertEqual(len(stocks), 1)
        self.assertIsInstance(stocks[0], StockRowData)


class TestStockManagerGetAllMarketData(unittest.TestCase):
    """StockManager 获取全市场数据测试"""

    def setUp(self):
        self.manager = StockManager()
        # Mock 数据服务
        self.mock_service = MagicMock()
        self.manager._stock_data_service = self.mock_service

    def test_get_all_market_data(self):
        """测试获取全市场数据"""
        # Mock 返回数据
        mock_market_data = {
            "up_count": 2000,
            "down_count": 1500,
            "flat_count": 500,
            "total_volume": 5000000000,
        }
        self.mock_service.get_all_market_data.return_value = mock_market_data

        # 调用方法
        result = self.manager.get_all_market_data()

        # 验证结果
        self.assertEqual(result, mock_market_data)
        self.mock_service.get_all_market_data.assert_called_once()


class TestStockManagerProcessSingleStockData(unittest.TestCase):
    """StockManager 处理单只股票数据测试"""

    def setUp(self):
        self.manager = StockManager()

    def test_process_single_stock_data_with_json(self):
        """测试使用 JSON 字符串处理单只股票数据"""
        import json

        info = {"name": "平安银行", "now": 10.50, "close": 10.00}
        info_json = json.dumps(info)

        result = self.manager._process_single_stock_data("000001", info_json)

        self.assertIsInstance(result, StockRowData)
        self.assertEqual(result.name, "平安银行")
        self.assertEqual(result.price, "10.50")

    def test_process_single_stock_data_with_dict(self):
        """测试使用字典处理单只股票数据"""
        info = {"name": "贵州茅台", "now": 1800.00, "close": 1750.00}

        result = self.manager._process_single_stock_data_impl("600519", info)

        self.assertIsInstance(result, StockRowData)
        self.assertEqual(result.name, "贵州茅台")
        self.assertEqual(result.price, "1800.00")

    def test_process_single_stock_data_with_invalid_json(self):
        """测试使用无效 JSON 处理单只股票数据"""
        invalid_json = "{ invalid json }"

        result = self.manager._process_single_stock_data("000001", invalid_json)

        # 应返回默认数据
        self.assertIsInstance(result, StockRowData)
        self.assertEqual(result.code, "000001")


if __name__ == "__main__":
    unittest.main()
