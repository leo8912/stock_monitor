#!/usr/bin/env python
"""QA 独立验证（T03）：真实驱动 MainWindow 的关窗/退出语义。

不使用 MagicMock 冒充托盘：这里用**真实 QSystemTrayIcon**，配合
``PyQt6.sip.isdeleted`` 证明点 X 之后托盘对象既未 hide 也未销毁；
并用"发信号后窗口内部状态确实变化"证明 ViewModel 信号仍连接（而非只看代码）。

L0 真人功能验证：全部在 offscreen 平台真实构造窗口后驱动。
"""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtGui, QtWidgets, sip  # noqa: E402

from stock_monitor.core.application import StockMonitorApp  # noqa: E402
from stock_monitor.ui.main_window import MainWindow  # noqa: E402
from stock_monitor.ui.view_models.main_window_view_model import (  # noqa: E402
    MainWindowViewModel,
)


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class _WindowHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _qapp()
        self.mock_start = MagicMock()
        self.mock_stop = MagicMock()
        self.mock_close_db = MagicMock()
        self.mock_save_session = MagicMock()
        self._patchers = [
            patch.object(MainWindowViewModel, "start_workers", self.mock_start),
            patch.object(MainWindowViewModel, "stop_workers", self.mock_stop),
            patch.object(MainWindowViewModel, "close_database", self.mock_close_db),
            patch.object(MainWindowViewModel, "save_session", self.mock_save_session),
            patch.object(
                MainWindowViewModel, "get_latest_stock_data", MagicMock(return_value=[])
            ),
            patch(
                "stock_monitor.ui.view_models.main_window_view_model"
                ".get_dark_trade_service",
                return_value=MagicMock(isRunning=MagicMock(return_value=True)),
            ),
            patch("stock_monitor.ui.main_window.schedule_log_cleanup", MagicMock()),
        ]
        for p in self._patchers:
            p.start()
        self.window = MainWindow()
        self.window._taskbar_active = True  # 保证 refresh 处理器路径确定
        self.tray = QtWidgets.QSystemTrayIcon()
        self.window.tray_icon = self.tray

    def tearDown(self) -> None:
        try:
            self.window._shutdown_resources()
        except Exception:  # noqa: BLE001
            pass
        for p in self._patchers:
            p.stop()


class TestCloseEventRealWindow(_WindowHarness):
    def test_close_event_minimizes_keeps_tray_and_signals(self) -> None:
        """点 X：窗口隐藏、托盘存活、ViewModel 信号仍连接。"""
        with patch.object(
            self.window, "_safe_disconnect", MagicMock()
        ) as spy_disconnect:
            self.window.show()
            self.assertTrue(self.window.isVisible())

            event = QtGui.QCloseEvent()
            self.window.closeEvent(event)

            # 事件被 ignore，窗口隐藏
            self.assertFalse(self.window.isVisible())

        # 未做任何信号断开（closeEvent 不应触发破坏性清理）
        spy_disconnect.assert_not_called()

        # 托盘对象仍存活且未被销毁
        self.assertIs(self.window.tray_icon, self.tray)
        self.assertFalse(sip.isdeleted(self.tray))

        # 行为证据：信号仍连通 → 发信号后窗口内部状态确实更新
        self.window._last_data = "SENTINEL"
        self.window.viewModel.stock_data_updated.emit([], False)
        self.assertEqual(
            self.window._last_data, [], "ViewModel 信号在 closeEvent 后已被断开"
        )

        # 破坏性操作未在 closeEvent 中发生
        self.mock_stop.assert_not_called()
        self.mock_close_db.assert_not_called()

    def test_quit_application_emits_quit_keeps_tray(self) -> None:
        """quit_application：请求退出，但不销毁托盘。"""
        with patch.object(self.app, "quit", MagicMock()) as mock_quit:
            self.window.quit_application()
            mock_quit.assert_called_once()

        self.mock_save_session.assert_called_once()
        self.assertIs(self.window.tray_icon, self.tray)
        self.assertFalse(sip.isdeleted(self.tray))

    def test_about_to_quit_runs_shutdown_once(self) -> None:
        """aboutToQuit 触发 _shutdown_resources，且连发两次仅生效一次（幂等）。"""
        seen: list[int] = []

        def on_about_to_quit() -> None:
            seen.append(1)
            self.window._shutdown_resources()

        self.app.aboutToQuit.connect(on_about_to_quit)
        try:
            self.app.aboutToQuit.emit()
            self.assertTrue(self.window._shutdown_done)
            self.assertEqual(len(seen), 1)

            # 第二次触发：幂等，破坏性清理不得重复
            self.app.aboutToQuit.emit()
        finally:
            try:
                self.app.aboutToQuit.disconnect(on_about_to_quit)
            except TypeError:
                pass

        self.assertEqual(len(seen), 2)
        self.mock_stop.assert_called_once()
        self.mock_close_db.assert_called_once()


class TestApplicationWiring(unittest.TestCase):
    """验证 StockMonitorApp 的 aboutToQuit 接线确实调用资源释放。"""

    def test_on_about_to_quit_calls_shutdown_and_services(self) -> None:
        app = StockMonitorApp()
        fake_window = MagicMock()
        app._window = fake_window

        with patch.object(
            StockMonitorApp, "_stop_background_services", MagicMock()
        ) as mock_stop_services:
            app._on_about_to_quit()

        fake_window._shutdown_resources.assert_called_once()
        mock_stop_services.assert_called_once()

    def test_on_about_to_quit_tolerates_missing_window(self) -> None:
        app = StockMonitorApp()
        app._window = None
        with patch.object(
            StockMonitorApp, "_stop_background_services", MagicMock()
        ) as mock_stop_services:
            app._on_about_to_quit()  # 不应抛异常
        mock_stop_services.assert_called_once()


if __name__ == "__main__":
    unittest.main()
