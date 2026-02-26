import json
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stock_monitor.core.stock_manager import StockManager


class TestLRUCacheMechanism(unittest.TestCase):
    def setUp(self):
        """测试前准备"""
        self.stock_manager = StockManager()
        # 清空缓存，确保每次测试都是干净的状态
        self.stock_manager._process_single_stock_data.cache_clear()

    def test_same_stock_data_request_should_hit_cache(self):
        """测试相同股票数据请求是否命中缓存"""
        # 准备测试数据
        code = "sh600000"
        info = {"name": "浦发银行", "now": 10.0, "close": 9.9}
        info_json = json.dumps(info, sort_keys=True)

        # 第一次调用
        result1 = self.stock_manager._process_single_stock_data(code, info_json)

        # 检查缓存信息
        cache_info_before = self.stock_manager._process_single_stock_data.cache_info()
        hits_before = cache_info_before.hits
        misses_before = cache_info_before.misses

        # 第二次调用相同的参数
        result2 = self.stock_manager._process_single_stock_data(code, info_json)

        # 验证结果相同
        self.assertEqual(result1, result2)

        # 验证缓存命中
        cache_info_after = self.stock_manager._process_single_stock_data.cache_info()
        self.assertEqual(cache_info_after.hits, hits_before + 1)
        self.assertEqual(cache_info_after.misses, misses_before)

    def test_different_stock_data_request_should_not_hit_cache(self):
        """测试不同股票数据请求是否正确返回结果"""
        # 准备测试数据
        code1 = "sh600000"
        info1 = {"name": "浦发银行", "now": 10.0, "close": 9.9}
        info_json1 = json.dumps(info1, sort_keys=True)

        code2 = "sh600036"
        info2 = {"name": "招商银行", "now": 20.0, "close": 19.8}
        info_json2 = json.dumps(info2, sort_keys=True)

        # 分别调用
        result1 = self.stock_manager._process_single_stock_data(code1, info_json1)
        result2 = self.stock_manager._process_single_stock_data(code2, info_json2)

        # 验证结果不同
        self.assertNotEqual(result1, result2)

        # 验证缓存未命中（两次都是miss）
        cache_info = self.stock_manager._process_single_stock_data.cache_info()
        self.assertEqual(cache_info.misses, 2)
        self.assertEqual(cache_info.hits, 0)

    def test_cache_size_limit_should_work(self):
        """测试缓存大小限制是否生效"""
        # 获取动态缓存大小
        from stock_monitor.core.stock_manager import get_dynamic_lru_cache_size

        maxsize = get_dynamic_lru_cache_size()

        # 插入超过缓存大小的数据
        for i in range(maxsize + 10):
            code = f"stock{i}"
            info = {"name": f"股票{i}", "now": i, "close": i - 0.1}
            info_json = json.dumps(info, sort_keys=True)
            self.stock_manager._process_single_stock_data(code, info_json)

        cache_info = self.stock_manager._process_single_stock_data.cache_info()

        # 验证缓存条目数不超过限制
        self.assertLessEqual(cache_info.currsize, maxsize)
        self.assertEqual(cache_info.maxsize, maxsize)

    def test_edge_cases_empty_data(self):
        """测试极端情况（如空数据）下的表现"""
        # 空字符串JSON
        result = self.stock_manager._process_single_stock_data("empty", "{}")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 6)  # 应该返回6个元素的元组

        # 无效JSON
        result = self.stock_manager._process_single_stock_data(
            "invalid", "invalid json"
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 6)  # 应该返回6个元素的元组

    def test_edge_cases_none_values(self):
        """测试包含None值的数据"""
        code = "test"
        info = {"name": "测试", "now": None, "close": None}
        info_json = json.dumps(info, sort_keys=True)

        result = self.stock_manager._process_single_stock_data(code, info_json)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 6)  # 应该返回6个元素的元组
        # 验证返回的是默认值（"--"）
        self.assertEqual(result[1], "--")  # price
        self.assertEqual(result[2], "--")  # change

    def test_get_stock_list_data_integration(self):
        """集成测试：验证get_stock_list_data是否正确使用缓存"""
        # Mock instance's service
        mock_service = MagicMock()
        mock_service.get_multiple_stocks_data.return_value = {
            "sh600000": {"name": "浦发银行", "now": 10.0, "close": 9.9},
            "sh600036": {"name": "招商银行", "now": 20.0, "close": 19.8},
        }

        # Replace the service in the manager instance
        original_service = self.stock_manager._stock_data_service
        self.stock_manager._stock_data_service = mock_service

        try:
            # 调用方法
            stock_codes = ["sh600000", "sh600036"]
            result = self.stock_manager.get_stock_list_data(stock_codes)

            # 验证结果
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0][0], "浦发银行")
            self.assertEqual(result[1][0], "招商银行")

            # 验证缓存被调用
            cache_info = self.stock_manager._process_single_stock_data.cache_info()
            self.assertEqual(cache_info.misses, 2)  # 两次新的缓存访问

            # 再次调用同样的数据
            # 重新设置mock返回值以确保数据一致
            mock_service.get_multiple_stocks_data.return_value = {
                "sh600000": {"name": "浦发银行", "now": 10.0, "close": 9.9},
                "sh600036": {"name": "招商银行", "now": 20.0, "close": 19.8},
            }
            result2 = self.stock_manager.get_stock_list_data(stock_codes)

            # 验证缓存命中
            cache_info2 = self.stock_manager._process_single_stock_data.cache_info()
            # Expect hits to increase by 2 (for 2 items)
            self.assertEqual(cache_info2.hits, cache_info.hits + 2)

            # 验证关键字段一致
            self.assertEqual(len(result), len(result2))

        finally:
            self.stock_manager._stock_data_service = original_service


if __name__ == "__main__":
    unittest.main()
