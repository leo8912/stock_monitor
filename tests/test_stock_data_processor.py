#!/usr/bin/env python
"""
StockDataProcessor 单元测试模块

测试股票数据处理器功能，包括：
- 原始数据处理
- 特殊股票代码处理
- 价格信息提取
- 涨跌幅计算
- 颜色映射
- 封单信息计算
- 大单信息处理
- 集合竞价数据处理
"""

import unittest

from stock_monitor.core.stock_data_processor import StockDataProcessor


class TestStockDataProcessorBasic(unittest.TestCase):
    """StockDataProcessor 基础功能测试"""

    def test_process_raw_data_with_complete_data(self):
        """测试处理完整的股票数据"""
        raw_data = {
            "name": "测试股票",
            "now": 10.50,
            "close": 10.00,
            "high": 10.80,
            "low": 9.80,
            "bid1": 10.50,
            "ask1": 0,
            "bid1_volume": 50000,
            "ask1_volume": 0,
            "large_order_vol": (1000, 500, 200),
            "auction_data": {"price": 10.20, "volume": 1000, "intensity": 5.5},
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertEqual(result.code, "sz000001")
        self.assertEqual(result.name, "平安银行")  # 特殊股票名称处理
        self.assertEqual(result.price, "10.50")
        self.assertIn("+", result.change_str)  # 涨幅应为正
        self.assertIsNotNone(result.color_hex)

    def test_process_raw_data_with_missing_fields(self):
        """测试处理缺失字段的股票数据"""
        raw_data = {
            "name": "测试股票"
            # 缺少价格数据
        }

        result = StockDataProcessor.process_raw_data("sz000002", raw_data)

        self.assertEqual(result.code, "sz000002")
        self.assertEqual(result.price, "--")
        self.assertEqual(result.change_str, "--")
        self.assertEqual(result.color_hex, "#e6eaf3")  # 默认颜色

    def test_process_raw_data_with_none_values(self):
        """测试处理 None 值的数据"""
        raw_data = {"name": "测试股票", "now": None, "close": None}

        result = StockDataProcessor.process_raw_data("sz000003", raw_data)

        self.assertEqual(result.price, "--")
        self.assertEqual(result.change_str, "--")


class TestSpecialStockHandling(unittest.TestCase):
    """特殊股票处理测试"""

    def test_shanghai_index_name(self):
        """测试上证指数名称处理"""
        raw_data = {"name": "上证指数"}
        result = StockDataProcessor._handle_special_stocks("sh000001", raw_data)

        self.assertEqual(result["name"], "上证指数")

    def test_pingan_bank_name(self):
        """测试平安银行名称处理"""
        raw_data = {"name": "平安银行"}
        result = StockDataProcessor._handle_special_stocks("sz000001", raw_data)

        self.assertEqual(result["name"], "平安银行")

    def test_normal_stock_no_change(self):
        """测试普通股票不修改名称"""
        raw_data = {"name": "普通股票"}
        result = StockDataProcessor._handle_special_stocks("sz000002", raw_data)

        self.assertEqual(result["name"], "普通股票")

    def test_extract_name_from_info(self):
        """测试从 info 中提取名称"""
        info = {"name": "股票名称"}
        name = StockDataProcessor._extract_name("sz000001", info)

        self.assertEqual(name, "股票名称")

    def test_extract_name_default_to_code(self):
        """测试无名称时使用代码"""
        info = {}
        name = StockDataProcessor._extract_name("sz000001", info)

        self.assertEqual(name, "sz000001")

    def test_extract_hk_stock_name_remove_english(self):
        """测试港股名称去除英文部分"""
        info = {"name": "腾讯控股-Tencent"}
        name = StockDataProcessor._extract_name("hk00700", info)

        self.assertEqual(name, "腾讯控股")


class TestPriceInfoExtraction(unittest.TestCase):
    """价格信息提取测试"""

    def test_extract_price_info_success(self):
        """测试成功提取价格信息"""
        info = {"now": 11.00, "close": 10.00}

        result = StockDataProcessor._extract_price_info("sz000001", info)

        self.assertIsNotNone(result)
        price_str, change_str, color, f_now, f_close = result
        self.assertEqual(price_str, "11.00")
        self.assertEqual(f_now, 11.00)
        self.assertEqual(f_close, 10.00)
        self.assertIn("+", change_str)  # 上涨

    def test_extract_price_info_fallback_to_close(self):
        """测试价格回退到昨收价"""
        info = {"now": None, "close": 10.50}

        result = StockDataProcessor._extract_price_info("sz000001", info)

        # 当 now 无效时，应回退到 close
        self.assertIsNotNone(result)

    def test_extract_price_info_last_close_fallback(self):
        """测试 last_close 回退字段"""
        info = {"now": 10.50, "close": None, "last_close": 10.00}

        result = StockDataProcessor._extract_price_info("sz000001", info)

        self.assertIsNotNone(result)

    def test_extract_price_info_lastprice_fallback(self):
        """测试 lastPrice 回退字段"""
        info = {"now": 10.50, "close": None, "last_close": None, "lastPrice": 10.00}

        result = StockDataProcessor._extract_price_info("sz000001", info)

        self.assertIsNotNone(result)

    def test_extract_price_info_invalid_now_use_close(self):
        """测试 now 无效时使用 close"""
        info = {
            "now": -1,  # 无效价格
            "close": 10.50,
        }

        result = StockDataProcessor._extract_price_info("sz000001", info)

        # 应该回退到 close
        self.assertIsNotNone(result)

    def test_extract_price_info_both_none(self):
        """测试 now 和 close 都为 None"""
        info = {"now": None, "close": None}

        result = StockDataProcessor._extract_price_info("sz000001", info)

        self.assertIsNone(result)

    def test_extract_price_info_zero_close(self):
        """测试 close 为 0（除权情况）"""
        info = {"now": 10.00, "close": 0}

        result = StockDataProcessor._extract_price_info("sz000001", info)

        self.assertIsNotNone(result)
        # 涨跌幅应为 0
        _, change_str, _, _, _ = result
        self.assertEqual(change_str, "+0.00%")


class TestColorMapping(unittest.TestCase):
    """颜色映射测试"""

    def test_color_up_limit(self):
        """测试涨停颜色"""
        info = {"now": 11.00, "close": 10.00}  # +10%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#FF0000")  # 涨停红

    def test_color_up_bright(self):
        """测试大涨颜色"""
        info = {"now": 10.70, "close": 10.00}  # +7%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#FF4500")  # 大涨亮红

    def test_color_up_normal(self):
        """测试正常上涨颜色"""
        info = {"now": 10.30, "close": 10.00}  # +3%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#e74c3f")  # 标准红

    def test_color_neutral(self):
        """测试平盘颜色"""
        info = {"now": 10.00, "close": 10.00}  # 0%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#e6eaf3")  # 灰白

    def test_color_down_normal(self):
        """测试正常下跌颜色"""
        info = {"now": 9.70, "close": 10.00}  # -3%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#27ae60")  # 标准绿

    def test_color_down_deep(self):
        """测试大跌颜色"""
        info = {"now": 9.30, "close": 10.00}  # -7%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#1e8449")  # 深绿

    def test_color_down_limit(self):
        """测试跌停颜色"""
        info = {"now": 9.00, "close": 10.00}  # -10%
        result = StockDataProcessor._extract_price_info("sz000001", info)
        _, _, color, _, _ = result
        self.assertEqual(color, "#145a32")  # 最深绿


class TestSealInfoCalculation(unittest.TestCase):
    """封单信息计算测试"""

    def test_calculate_seal_info_up_limit(self):
        """测试涨停封单计算"""
        info = {
            "high": 11.00,
            "low": 10.50,
            "bid1": 11.00,
            "ask1": 0,
            "bid1_volume": 150000,
            "ask1_volume": 0,
        }

        seal_vol, seal_type = StockDataProcessor._calculate_seal_info(info, 11.00)

        self.assertEqual(seal_type, "up")
        self.assertIn("k", seal_vol)  # 应以 k 为单位

    def test_calculate_seal_info_down_limit(self):
        """测试跌停封单计算"""
        info = {
            "high": 10.50,
            "low": 9.00,
            "bid1": 0,
            "ask1": 9.00,
            "bid1_volume": 0,
            "ask1_volume": 200000,
        }

        seal_vol, seal_type = StockDataProcessor._calculate_seal_info(info, 9.00)

        self.assertEqual(seal_type, "down")
        self.assertIn("k", seal_vol)

    def test_calculate_seal_info_no_seal(self):
        """测试无封单情况"""
        info = {
            "high": 10.80,
            "low": 9.80,
            "bid1": 10.40,
            "ask1": 10.50,
            "bid1_volume": 1000,
            "ask1_volume": 1000,
        }

        seal_vol, seal_type = StockDataProcessor._calculate_seal_info(info, 10.45)

        self.assertEqual(seal_type, "")
        self.assertEqual(seal_vol, "")

    def test_calculate_seal_info_small_volume(self):
        """测试小量封单不显示 k 单位"""
        info = {
            "high": 11.00,
            "low": 10.50,
            "bid1": 11.00,
            "ask1": 0,
            "bid1_volume": 5000,  # 小于 100k
            "ask1_volume": 0,
        }

        seal_vol, seal_type = StockDataProcessor._calculate_seal_info(info, 11.00)

        self.assertEqual(seal_type, "up")
        self.assertNotIn("k", seal_vol)  # 小量不显示 k


class TestLargeOrderInfo(unittest.TestCase):
    """大单信息处理测试"""

    def test_large_order_net_inflow(self):
        """测试大单净流入"""
        raw_data = {
            "name": "测试",
            "now": 10.00,
            "close": 10.00,
            "large_order_vol": (2000, 1000, 500),  # 买 2000, 卖 1000, 净 500
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertIn("+", result.large_order_info)  # 净流入为正

    def test_large_order_net_outflow(self):
        """测试大单净流出"""
        raw_data = {
            "name": "测试",
            "now": 10.00,
            "close": 10.00,
            "large_order_vol": (1000, 2000, -500),  # 买 1000, 卖 2000, 净 -500
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertIn("-", result.large_order_info)  # 净流出为负

    def test_large_order_yi_unit(self):
        """测试大单亿单位显示"""
        raw_data = {
            "name": "测试",
            "now": 10.00,
            "close": 10.00,
            "large_order_vol": (200000000, 100000000, 50000000),  # 亿级别
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertIn("亿", result.large_order_info)

    def test_large_order_wan_unit(self):
        """测试大单万单位显示"""
        raw_data = {
            "name": "测试",
            "now": 10.00,
            "close": 10.00,
            "large_order_vol": (20000, 10000, 5000),  # 万级别
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertIn("万", result.large_order_info)

    def test_large_order_no_data(self):
        """测试无大单数据"""
        raw_data = {"name": "测试", "now": 10.00, "close": 10.00}

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertEqual(result.large_order_info, "")


class TestAuctionData(unittest.TestCase):
    """集合竞价数据测试"""

    def test_auction_data_extraction(self):
        """测试集合竞价数据提取"""
        raw_data = {
            "name": "测试",
            "now": 10.00,
            "close": 10.00,
            "auction_data": {"price": 10.20, "volume": 5000, "intensity": 8.5},
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertEqual(result.auction_price, 10.20)
        self.assertEqual(result.auction_vol, 5000)
        self.assertEqual(result.auction_intensity, 8.5)

    def test_auction_data_missing(self):
        """测试缺失集合竞价数据"""
        raw_data = {"name": "测试", "now": 10.00, "close": 10.00}

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertEqual(result.auction_price, 0.0)
        self.assertEqual(result.auction_vol, 0.0)
        self.assertEqual(result.auction_intensity, 0.0)

    def test_auction_data_partial(self):
        """测试部分集合竞价数据"""
        raw_data = {
            "name": "测试",
            "now": 10.00,
            "close": 10.00,
            "auction_data": {
                "price": 10.20
                # volume 和 intensity 缺失
            },
        }

        result = StockDataProcessor.process_raw_data("sz000001", raw_data)

        self.assertEqual(result.auction_price, 10.20)
        self.assertEqual(result.auction_vol, 0.0)
        self.assertEqual(result.auction_intensity, 0.0)


if __name__ == "__main__":
    unittest.main()
