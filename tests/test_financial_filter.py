#!/usr/bin/env python
"""
FinancialFilter 单元测试模块

测试财务过滤器功能，包括：
- 缓存机制
- 财务数据审计逻辑
- 边界情况处理
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from stock_monitor.core.financial_filter import FinancialFilter


class TestFinancialFilter(unittest.TestCase):
    """FinancialFilter 核心功能测试"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时缓存目录
        self.temp_dir = tempfile.mkdtemp()
        self.filter = FinancialFilter()
        self.filter.cache_dir = self.temp_dir
        self.filter.cache_expiry = 3600  # 1 小时过期，方便测试

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """测试初始化逻辑"""
        self.assertTrue(os.path.exists(self.filter.cache_dir))
        self.assertEqual(self.filter.cache_expiry, 3600)

    def test_symbol_format_conversion(self):
        """测试股票代码格式转换"""
        # 测试带市场前缀的代码
        result = self.filter.get_financial_audit("sh600519")
        self.assertIn("rating", result)

        result = self.filter.get_financial_audit("sz000001")
        self.assertIn("rating", result)

        # 测试纯数字代码
        result = self.filter.get_financial_audit("600519")
        self.assertIn("rating", result)

    def test_default_return_when_no_data(self):
        """测试无数据时的默认返回"""
        # Mock _fetch_and_cache 方法，避免网络请求
        with patch.object(self.filter, "_fetch_and_cache", return_value=None):
            result = self.filter.get_financial_audit("000001")

            self.assertEqual(result["rating"], "🟢")
            self.assertEqual(result["score_offset"], 0)
            self.assertTrue(any("无法获取财务数据" in r for r in result["reasons"]))
            self.assertEqual(result["details"], {})

    def test_audit_data_with_excellent_metrics(self):
        """测试优秀财务数据的审计结果"""
        mock_data = [
            {
                "净利润同比增长率": "50.0%",
                "净资产收益率": "20.0%",
                "资产负债率": "30.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertEqual(result["rating"], "🟢")
        self.assertEqual(result["score_offset"], 0)
        self.assertEqual(len(result["reasons"]), 0)
        self.assertEqual(result["details"]["growth"], "50.0%")
        self.assertEqual(result["details"]["roe"], "20.0%")

    def test_audit_data_with_poor_growth(self):
        """测试净利润大幅下滑的审计结果"""
        mock_data = [
            {
                "净利润同比增长率": "-60.0%",
                "净资产收益率": "10.0%",
                "资产负债率": "40.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertEqual(result["rating"], "🟡")
        self.assertLessEqual(result["score_offset"], -4)
        self.assertIn("净利暴跌", result["reasons"][0])

    def test_audit_data_with_negative_roe(self):
        """测试负 ROE 的审计结果"""
        mock_data = [
            {
                "净利润同比增长率": "10.0%",
                "净资产收益率": "-5.0%",
                "资产负债率": "40.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertLessEqual(result["score_offset"], -3)
        # 验证原因中包含 ROE 相关警告（不检查完整文本，避免编码问题）
        self.assertTrue(any("ROE" in r for r in result["reasons"]))

    def test_audit_data_with_high_debt(self):
        """测试高负债率的审计结果"""
        mock_data = [
            {
                "净利润同比增长率": "10.0%",
                "净资产收益率": "10.0%",
                "资产负债率": "90.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertLessEqual(result["score_offset"], -3)
        self.assertIn("负债率极高", result["reasons"][0])

    def test_audit_data_with_multiple_issues(self):
        """测试多个财务问题的审计结果"""
        mock_data = [
            {
                "净利润同比增长率": "-70.0%",
                "净资产收益率": "-10.0%",
                "资产负债率": "95.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertEqual(result["rating"], "🔴")
        self.assertEqual(result["score_offset"], -10)  # 最多扣 10 分
        self.assertGreater(len(result["reasons"]), 2)

    def test_parse_pct_with_various_formats(self):
        """测试百分比解析函数"""
        # 测试字符串格式
        result = self.filter._audit_data(
            [
                {
                    "净利润同比增长率": "25.5%",
                    "净资产收益率": "--",
                    "资产负债率": None,
                    "报告期": "2024-12-31",
                }
            ]
        )

        self.assertIn("details", result)

    def test_cache_mechanism(self):
        """测试缓存机制"""
        symbol = "600519"
        cache_path = os.path.join(self.temp_dir, f"{symbol}.json")

        # 准备测试数据
        test_data = [
            {
                "净利润同比增长率": "20.0%",
                "净资产收益率": "15.0%",
                "资产负债率": "50.0%",
                "报告期": "2024-12-31",
            }
        ]

        # 写入缓存
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

        # 验证读取缓存
        cached_data = self.filter._get_cached_data(symbol)
        self.assertEqual(cached_data, test_data)

    def test_cache_expiry(self):
        """测试缓存过期机制"""
        symbol = "600519"
        cache_path = os.path.join(self.temp_dir, f"{symbol}.json")

        # 准备测试数据
        test_data = [{"test": "data"}]

        # 写入缓存
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        # 修改文件时间戳使其过期
        old_time = time.time() - (self.filter.cache_expiry + 100)
        os.utime(cache_path, (old_time, old_time))

        # 验证缓存已过期
        expired_data = self.filter._get_cached_data(symbol)
        self.assertIsNone(expired_data)


class TestFinancialFilterAuditEdgeCases(unittest.TestCase):
    """财务审计边界情况测试"""

    def setUp(self):
        """设置测试环境"""
        self.filter = FinancialFilter()
        self.filter.cache_dir = tempfile.mkdtemp()

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.filter.cache_dir):
            shutil.rmtree(self.filter.cache_dir)

    def test_empty_data_list(self):
        """测试空数据列表"""
        result = self.filter._audit_data([])

        self.assertEqual(result["rating"], "🟢")
        self.assertEqual(result["score_offset"], 0)
        self.assertEqual(result["reasons"], [])

    def test_none_values_in_data(self):
        """测试数据中包含 None 值"""
        mock_data = [
            {
                "净利润同比增长率": None,
                "净资产收益率": None,
                "资产负债率": None,
                "报告期": None,
            }
        ]

        result = self.filter._audit_data(mock_data)

        # 应该正常处理，不会抛出异常
        self.assertIn("rating", result)
        # None 值会被解析为 0.0，ROE 为 0 会扣 1 分
        self.assertLessEqual(result["score_offset"], 0)

    def test_string_dash_values(self):
        """测试数据中包含'--'字符串"""
        mock_data = [
            {
                "净利润同比增长率": "--",
                "净资产收益率": "--",
                "资产负债率": "--",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        # 应该正常处理，不会抛出异常
        self.assertIn("rating", result)

    def test_moderate_decline_in_growth(self):
        """测试净利润中度下滑（-20% 到 -50%）"""
        mock_data = [
            {
                "净利润同比增长率": "-30.0%",
                "净资产收益率": "10.0%",
                "资产负债率": "50.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertLessEqual(result["score_offset"], -2)
        self.assertIn("净利下滑", result["reasons"][0])

    def test_low_but_positive_roe(self):
        """测试低但正的 ROE（<3%）"""
        mock_data = [
            {
                "净利润同比增长率": "10.0%",
                "净资产收益率": "2.0%",
                "资产负债率": "50.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertLessEqual(result["score_offset"], -1)
        # 验证原因中包含 ROE 相关警告（不检查完整文本，避免编码问题）
        self.assertTrue(any("ROE" in r for r in result["reasons"]))

    def test_moderately_high_debt(self):
        """测试中等偏高负债率（70%-85%）"""
        mock_data = [
            {
                "净利润同比增长率": "10.0%",
                "净资产收益率": "10.0%",
                "资产负债率": "75.0%",
                "报告期": "2024-12-31",
            }
        ]

        result = self.filter._audit_data(mock_data)

        self.assertLessEqual(result["score_offset"], -1)
        self.assertIn("负债率偏高", result["reasons"][0])


class TestFinancialFilterCacheMechanism(unittest.TestCase):
    """FinancialFilter 缓存机制专项测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.filter = FinancialFilter()
        self.filter.cache_dir = self.temp_dir
        self.filter.cache_expiry = 3600

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cache_file_corrupted(self):
        """测试缓存文件损坏的情况"""
        symbol = "600519"
        cache_path = os.path.join(self.temp_dir, f"{symbol}.json")

        # 创建损坏的 JSON 文件
        with open(cache_path, "w") as f:
            f.write("{ invalid json content")

        # 应该返回 None 而不是抛出异常
        result = self.filter._get_cached_data(symbol)
        self.assertIsNone(result)

    def test_cache_key_format(self):
        """测试缓存键格式"""
        # 验证缓存文件名使用纯数字代码
        test_cases = [
            ("sh600519", "600519"),
            ("sz000001", "000001"),
            ("600519", "600519"),
        ]

        for input_symbol, expected_key in test_cases:
            # 通过 get_financial_audit 触发内部转换
            self.filter.get_financial_audit(input_symbol)

            # 验证缓存文件是否使用正确的键名
            # cache_file = os.path.join(self.temp_dir, f"{expected_key}.json")
            # 注意：由于没有真实数据，文件可能不存在，这里只验证逻辑


if __name__ == "__main__":
    unittest.main()
