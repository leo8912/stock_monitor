"""
ui.utils 纯辅助函数单元测试
"""

import unittest
from types import SimpleNamespace

from stock_monitor.ui.utils import (
    MAX_BACKGROUND_ALPHA,
    MIN_BACKGROUND_ALPHA,
    compute_background_alpha,
    sanitize_font_size,
    sort_stocks_by_user_order,
)


class TestComputeBackgroundAlpha(unittest.TestCase):
    def test_zero_transparency(self):
        self.assertEqual(compute_background_alpha(0), MIN_BACKGROUND_ALPHA)

    def test_full_transparency(self):
        self.assertEqual(compute_background_alpha(100), MAX_BACKGROUND_ALPHA)

    def test_mid_value(self):
        # 128 + 127 * 80 / 100 = 229.6 -> int 229
        self.assertEqual(compute_background_alpha(80), 229)

    def test_clamped_out_of_range(self):
        self.assertEqual(compute_background_alpha(200), MAX_BACKGROUND_ALPHA)
        self.assertEqual(compute_background_alpha(-50), MIN_BACKGROUND_ALPHA)


class TestSanitizeFontSize(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(sanitize_font_size(15), 15)
        self.assertEqual(sanitize_font_size("16"), 16)

    def test_invalid_falls_back(self):
        self.assertEqual(sanitize_font_size("abc"), 13)
        self.assertEqual(sanitize_font_size(None), 13)
        self.assertEqual(sanitize_font_size(0), 13)
        self.assertEqual(sanitize_font_size(-5), 13)

    def test_custom_default(self):
        self.assertEqual(sanitize_font_size(None, default=12), 12)


class TestSortStocksByUserOrder(unittest.TestCase):
    def test_sort_by_code(self):
        data = [
            SimpleNamespace(code="sz000002"),
            SimpleNamespace(code="sh600519"),
            SimpleNamespace(code="sz000001"),
        ]
        ordered = sort_stocks_by_user_order(data, ["sz000001", "sh600519", "sz000002"])
        self.assertEqual(
            [d.code for d in ordered], ["sz000001", "sh600519", "sz000002"]
        )

    def test_unmatched_goes_last(self):
        data = [
            SimpleNamespace(code="xx999999"),
            SimpleNamespace(code="sz000001"),
        ]
        ordered = sort_stocks_by_user_order(data, ["sz000001"])
        self.assertEqual([d.code for d in ordered], ["sz000001", "xx999999"])

    def test_fallback_to_name(self):
        class NoCode:
            name = "平安银行"

        data = [SimpleNamespace(code="zz"), NoCode()]
        ordered = sort_stocks_by_user_order(data, ["平安银行"])
        self.assertIs(ordered[0].name, "平安银行")
        self.assertEqual(ordered[1].code, "zz")

    def test_empty(self):
        self.assertEqual(sort_stocks_by_user_order([], ["a"]), [])


if __name__ == "__main__":
    unittest.main()
