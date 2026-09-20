#!/usr/bin/env python
"""MainWindow 关闭/退出语义回归测试（T03）。

真实构造 ``MainWindow`` 并驱动 ``closeEvent`` / ``quit_application`` /
``_shutdown_resources``，验证：
- 点 X 仅最小化，不销毁托盘、不断开信号
- ``_shutdown_resources`` 幂等且集中释放资源
- ``quit_application`` 触发应用退出但不销毁托盘
"""

import os
import unittest
from unittest.mock import MagicMock, patch

# 使用离屏平台，避免在无显示环境下创建真实窗口
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from stock_monitor.ui.main_window import MainWindow  # noqa: E402
from stock_monitor.ui.view_models.main_window_view_model import (  # noqa: E402
    MainWindowViewModel,
)


def _get_qapp() -> QtWidgets.QApplication:
    """获取或创建全局 QApplication（离屏模式）。"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class TestMainWindowShutdown(unittest.TestCase):
    """主窗口关闭/退出流程测试。"""

    def setUp(self):
        self.app = _get_qapp()

        # 隔离真实后台线程/网络：Worker 启动停止、数据库关闭、会话保存全部 mock
        self.mock_start_workers = MagicMock()
        self.mock_stop_workers = MagicMock()
        self.mock_close_database = MagicMock()
        self.mock_save_session = MagicMock()
        self.mock_latest = MagicMock(return_value=[])

        self._patchers = [
            patch.object(MainWindowViewModel, "start_workers", self.mock_start_workers),
            patch.object(MainWindowViewModel, "stop_workers", self.mock_stop_workers),
            patch.object(
                MainWindowViewModel, "close_database", self.mock_close_database
            ),
            patch.object(MainWindowViewModel, "save_session", self.mock_save_session),
            patch.object(
                MainWindowViewModel, "get_latest_stock_data", self.mock_latest
            ),
            patch(
                "stock_monitor.ui.view_models.main_window_view_model"
                ".get_dark_trade_service",
                return_value=MagicMock(isRunning=MagicMock(return_value=True)),
            ),
            # 日志清理使用模块级 QTimer，跨实例复用会残留失效句柄，测试中隔离
            patch("stock_monitor.ui.main_window.schedule_log_cleanup", MagicMock()),
        ]
        for patcher in self._patchers:
            patcher.start()

        self.window = MainWindow()

    def tearDown(self):
        try:
            self.window._shutdown_resources()
        except Exception:  # noqa: BLE001 - 测试清理容错
            pass
        for patcher in self._patchers:
            patcher.stop()

    def test_close_event_only_minimizes_and_keeps_tray(self):
        """closeEvent 只隐藏窗口，不断信号、不销毁托盘。"""
        self.window.tray_icon = MagicMock()
        view_model = self.window.viewModel

        self.window.show()
        self.assertTrue(self.window.isVisible())

        event = MagicMock()
        self.window.closeEvent(event)

        # 事件被忽略（窗口未真正关闭），窗口已隐藏
        event.ignore.assert_called_once()
        self.assertFalse(self.window.isVisible())

        # ViewModel 与托盘对象仍存活，未被断开/销毁
        self.assertIs(self.window.viewModel, view_model)
        self.window.tray_icon.hide.assert_not_called()
        self.window.tray_icon.deleteLater.assert_not_called()
        self.mock_stop_workers.assert_not_called()
        self.mock_close_database.assert_not_called()

    def test_shutdown_resources_is_idempotent(self):
        """_shutdown_resources 连调两次不抛异常，且破坏性清理只执行一次。"""
        tray = MagicMock()
        self.window.tray_icon = tray

        self.window._shutdown_resources()
        self.window._shutdown_resources()  # 第二次应直接返回

        tray.hide.assert_called_once()
        tray.deleteLater.assert_called_once()
        self.mock_stop_workers.assert_called_once()
        self.mock_close_database.assert_called_once()
        self.assertTrue(self.window._shutdown_done)

    def test_quit_application_triggers_quit_without_deleting_tray(self):
        """quit_application 触发 app.quit，但不销毁托盘。"""
        tray = MagicMock()
        self.window.tray_icon = tray

        with patch.object(self.app, "quit") as mock_quit:
            self.window.quit_application()
            mock_quit.assert_called_once()

        # 保存会话被调用；托盘保留（未 hide/deleteLater）
        self.mock_save_session.assert_called_once()
        tray.hide.assert_not_called()
        tray.deleteLater.assert_not_called()


if __name__ == "__main__":
    unittest.main()
