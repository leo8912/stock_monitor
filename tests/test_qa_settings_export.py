#!/usr/bin/env python
"""QA 独立验证（T08）：设置对话框导出改后台 QThread 后的行为与线程归属。

真实构造 ``NewSettingsDialog`` 并驱动导出按钮处理函数，验证旧缺陷已修复：
- 完成后 WaitCursor 能恢复、按钮能重新启用（旧实现子线程调 singleShot → 永不回调）
- ``export_finished`` 回调确实在主线程执行（QThread.currentThread() 断言）
- 成功/无数据两条路径分别弹出 information / warning
"""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from stock_monitor.ui.dialogs.settings_dialog import (  # noqa: E402
    DarkTradeStatsExcelExportThread,
    NewSettingsDialog,
)

EXPORT_TARGET = (
    "stock_monitor.services.dark_trade.exporter.export_dark_trade_stats_excel"
)


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _pump_until(predicate, timeout_s: float = 8.0) -> bool:
    """泵事件直到 predicate 为真或超时。"""
    app = _qapp()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return predicate()


class TestExportThreadAffinity(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _qapp()

    def test_callback_runs_in_main_thread_on_success(self) -> None:
        recorded: dict = {}

        def probe(ok, payload):
            recorded["is_main"] = QtCore.QThread.currentThread() is self.app.thread()
            recorded["payload"] = (ok, payload)

        loop = QtCore.QEventLoop()
        with patch(EXPORT_TARGET, return_value="C:/tmp/out.xlsx"):
            thread = DarkTradeStatsExcelExportThread(["sh600000"])
            thread.export_finished.connect(probe)
            thread.export_finished.connect(loop.quit)
            QtCore.QTimer.singleShot(5000, loop.quit)
            thread.start()
            loop.exec()
            thread.wait(5000)

        self.assertEqual(recorded.get("payload"), (True, "C:/tmp/out.xlsx"))
        self.assertTrue(recorded.get("is_main"), "导出回调未在主线程执行")

    def test_callback_reports_failure(self) -> None:
        recorded: dict = {}

        def probe(ok, payload):
            recorded["payload"] = (ok, payload)

        loop = QtCore.QEventLoop()
        with patch(EXPORT_TARGET, side_effect=RuntimeError("boom")):
            thread = DarkTradeStatsExcelExportThread(["sh600000"])
            thread.export_finished.connect(probe)
            thread.export_finished.connect(loop.quit)
            QtCore.QTimer.singleShot(5000, loop.quit)
            thread.start()
            loop.exec()
            thread.wait(5000)

        ok, payload = recorded.get("payload", (None, None))
        self.assertFalse(ok)
        self.assertIn("boom", payload)

    def test_no_data_reports_false_empty(self) -> None:
        recorded: dict = {}

        def probe(ok, payload):
            recorded["payload"] = (ok, payload)

        loop = QtCore.QEventLoop()
        with patch(EXPORT_TARGET, return_value=None):
            thread = DarkTradeStatsExcelExportThread(["sh600000"])
            thread.export_finished.connect(probe)
            thread.export_finished.connect(loop.quit)
            QtCore.QTimer.singleShot(5000, loop.quit)
            thread.start()
            loop.exec()
            thread.wait(5000)

        self.assertEqual(recorded.get("payload"), (False, ""))


class TestDialogExportFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _qapp()
        self.dialog = NewSettingsDialog(None)
        self.dialog._quant_page.ctx.stocks_provider = MagicMock(
            return_value=["sh600000"]
        )
        self._mb_info = patch.object(QtWidgets.QMessageBox, "information", MagicMock())
        self._mb_warn = patch.object(QtWidgets.QMessageBox, "warning", MagicMock())
        self.mock_info = self._mb_info.start()
        self.mock_warn = self._mb_warn.start()

    def tearDown(self) -> None:
        self._mb_info.stop()
        self._mb_warn.stop()
        while QtWidgets.QApplication.overrideCursor() is not None:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.dialog.deleteLater()

    def _run_export(self, return_value):
        with patch(EXPORT_TARGET, return_value=return_value):
            self.dialog._quant_page.btn_export_dark_trade_excel.click()
            thread = self.dialog._quant_page._dark_stats_excel_thread
            _pump_until(lambda: not thread.isRunning(), timeout_s=8.0)
            # 再泵一会儿以投递排队的信号回调
            _pump_until(
                lambda: self.dialog._quant_page.btn_export_dark_trade_excel.isEnabled(),
                timeout_s=4.0,
            )

    def test_success_restores_cursor_and_button(self) -> None:
        self._run_export("C:/tmp/out.xlsx")

        self.assertEqual(QtWidgets.QApplication.overrideCursor(), None)
        self.assertTrue(self.dialog._quant_page.btn_export_dark_trade_excel.isEnabled())
        self.mock_info.assert_called_once()

    def test_no_data_warns_and_restores(self) -> None:
        self._run_export(None)

        self.assertEqual(QtWidgets.QApplication.overrideCursor(), None)
        self.assertTrue(self.dialog._quant_page.btn_export_dark_trade_excel.isEnabled())
        self.mock_warn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
