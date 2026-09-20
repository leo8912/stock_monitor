"""暗盘统计 Excel 导出线程（T08 重构）测试

直接把 ``run()`` 同步执行（不真正启动线程、不需要事件循环），
校验成功/无数据/异常三种情形的信号载荷与「真实异常信息」传递。
"""

import unittest
from unittest.mock import patch

from stock_monitor.ui.dialogs.settings_dialog import (
    DarkTradeStatsExcelExportThread,
)

_EXPORTER = "stock_monitor.services.dark_trade.exporter.export_dark_trade_stats_excel"


class TestDarkTradeStatsExcelExportThread(unittest.TestCase):
    def _run_thread(self):
        thread = DarkTradeStatsExcelExportThread(["sh600000"])
        results = []
        thread.export_finished.connect(lambda ok, p: results.append((ok, p)))
        thread.run()  # 同步执行，规避真实线程/事件循环
        return results

    def test_success_emits_path(self):
        with patch(_EXPORTER, return_value="/tmp/dark.xlsx"):
            results = self._run_thread()
        self.assertEqual(results, [(True, "/tmp/dark.xlsx")])

    def test_no_data_emits_false_empty(self):
        with patch(_EXPORTER, return_value=None):
            results = self._run_thread()
        self.assertEqual(results, [(False, "")])

    def test_exception_emits_real_message(self):
        with patch(_EXPORTER, side_effect=RuntimeError("boom")):
            results = self._run_thread()
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("boom", results[0][1])


if __name__ == "__main__":
    unittest.main()
