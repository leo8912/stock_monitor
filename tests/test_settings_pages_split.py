#!/usr/bin/env python
"""C4 拆分契约测试：settings_pages 页类 / settings_widgets / settings_dialog re-export。

覆盖：
- 各页类（``SettingsContext`` / ``SettingsPage`` / ``GeneralSettingsPage`` /
  ``DisplaySettingsPage`` / ``WatchlistPage`` / ``QuantSettingsPage``）均可实例化；
- 各页 ``load -> collect`` 往返保真；
- ``settings_dialog`` 对自绘控件（``DraggableListWidget`` / ``WatchListManager``）
  与 6 个 QThread 的 re-export 仍然可用；
- 对话框 shell 已收掉兼容桥：各页实例绑定 + 页内信号下沉；
- **防退化**：AST 扫描 ``settings_dialog.py``，断言 ``NewSettingsDialog`` 上不再
  存在已迁移的方法名，且文件行数 ≤ 500。
"""

import ast
import os
import pathlib
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from stock_monitor.ui.dialogs.settings_dialog import (  # noqa: E402
    DarkTradeExportThread,
    DarkTradeStatsExcelExportThread,
    DarkTradeStatsPushThread,
    DraggableListWidget,
    ExcelExportThread,
    NewSettingsDialog,
    TestAppThread,
    UpdateCheckThread,
    WatchListManager,
)
from stock_monitor.ui.dialogs.settings_pages import (  # noqa: E402
    DisplaySettingsPage,
    GeneralSettingsPage,
    QuantSettingsPage,
    SettingsContext,
    SettingsPage,
    WatchlistPage,
)
from stock_monitor.ui.dialogs.settings_widgets import (  # noqa: E402
    DraggableListWidget as DraggableListWidgetDirect,
)
from stock_monitor.ui.dialogs.settings_widgets import (  # noqa: E402
    WatchListManager as WatchListManagerDirect,
)

SHELL_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "stock_monitor"
    / "ui"
    / "dialogs"
    / "settings_dialog.py"
)

# 这些方法/属性在 C4 结构治理中已从 ``NewSettingsDialog`` 迁出，回归即视为退化。
MIGRATED_SHELL_METHODS = frozenset(
    {
        "_setup_watchlist_ui",
        "_setup_quant_settings_ui",
        "_setup_bottom_bar",
        "_bind_migrated_widgets",
        "check_for_updates",
        "_on_update_check_result",
        "_on_test_push_clicked",
        "_on_test_app_clicked",
        "_on_test_app_finished",
        "_on_push_mode_changed",
        "_reset_fib_settings",
        "_on_manual_export_excel_clicked",
        "_on_export_finished",
        "_on_manual_fetch_dark_trade_clicked",
        "_on_test_dark_trade_stats_clicked",
        "_on_export_dark_trade_excel_clicked",
        "_set_auto_start",
        "_create_shortcut",
        "_apply_auto_start",
        "on_font_setting_changed",
        "on_transparency_changed",
        "_clear_preview_state",
        "_sync_original_display_settings_from_controls",
        "get_stocks_from_list",
        "add_stock_from_search",
        "_handle_stock_search_added",
        "_on_search_results_updated",
        "_on_search_return_pressed",
        "_update_original_watch_list",
        "_map_refresh_text_to_value",
        "_map_refresh_value_to_text",
    }
)


def _qapp() -> QtWidgets.QApplication:
    """返回（必要时创建）全局 QApplication 实例。"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _StubViewModel(QtCore.QObject):
    """最小 ViewModel 替身：提供页面构建所需的信号与展示名解析。"""

    search_results_updated = QtCore.pyqtSignal(list)

    def get_stock_display_info(self, code: str) -> str:
        """返回展示名（此处直接回显代码，保证往返可断言）。"""
        return code

    def search_stocks(self, text: str) -> None:
        """搜索槽替身（无操作）。"""


class _StubSignals(QtCore.QObject):
    """承载 shell 信号代理的替身，供页 ``build`` 连接使用。"""

    config_changed = QtCore.pyqtSignal(list, int)
    manual_report_requested = QtCore.pyqtSignal()


class TestPageInstantiation(unittest.TestCase):
    """各页类 / 上下文均可实例化。"""

    def setUp(self) -> None:
        self.app = _qapp()

    def test_context_instantiable(self) -> None:
        ctx = SettingsContext(main_window=None, view_model=_StubViewModel())
        self.assertIsNotNone(ctx.logger)
        self.assertEqual(ctx._webhook_test_cooldown, 60)
        self.assertEqual(ctx._last_webhook_test_time, 0)
        self.assertIsNone(ctx.stocks_provider)

    def test_base_page_instantiable(self) -> None:
        ctx = SettingsContext()
        page = SettingsPage(ctx)
        self.assertIs(page.ctx, ctx)
        self.assertIsInstance(page, QtWidgets.QWidget)
        self.assertTrue(page.validate())
        page.cleanup()
        page.deleteLater()

    def test_general_page_instantiable(self) -> None:
        page = GeneralSettingsPage(SettingsContext())
        self.assertIsInstance(page, SettingsPage)
        page.deleteLater()

    def test_display_page_instantiable(self) -> None:
        page = DisplaySettingsPage(SettingsContext())
        self.assertIsInstance(page, SettingsPage)
        self.assertIsNotNone(page._font_preview_timer)
        page.cleanup()
        page.deleteLater()

    def test_watchlist_page_instantiable(self) -> None:
        page = WatchlistPage(SettingsContext(view_model=_StubViewModel()))
        self.assertIsInstance(page, SettingsPage)
        self.assertEqual(page.original_watch_list, [])
        page.deleteLater()

    def test_quant_page_instantiable(self) -> None:
        page = QuantSettingsPage(SettingsContext())
        self.assertIsInstance(page, SettingsPage)
        page.deleteLater()


class TestGeneralRoundTrip(unittest.TestCase):
    """``GeneralSettingsPage`` 的 load/collect 往返保真。"""

    def setUp(self) -> None:
        self.app = _qapp()
        self.page = GeneralSettingsPage(SettingsContext())
        self.page.build(self.page)

    def tearDown(self) -> None:
        self.page.deleteLater()

    def test_load_collect_round_trip(self) -> None:
        source = {"auto_start": True, "refresh_interval": 10}
        self.page.load(source)
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out, source)

    def test_load_defaults_and_unknown(self) -> None:
        self.page.load({"refresh_interval": 999})
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out["auto_start"], False)
        self.assertEqual(out["refresh_interval"], 5)

    def test_get_refresh_interval(self) -> None:
        self.page.load({"refresh_interval": 30})
        self.assertEqual(self.page.get_refresh_interval(), 30)


class TestDisplayRoundTrip(unittest.TestCase):
    """``DisplaySettingsPage`` 的 load/collect 往返保真。"""

    def setUp(self) -> None:
        self.app = _qapp()
        self.page = DisplaySettingsPage(SettingsContext())
        self.page.build(self.page)

    def tearDown(self) -> None:
        self.page.cleanup()
        self.page.deleteLater()

    def test_load_collect_round_trip(self) -> None:
        source = {
            "font_size": 22,
            "font_family": "楷体",
            "transparency": 55,
            "taskbar_quote_enabled": True,
            "taskbar_per_page": 5,
            "taskbar_carousel_interval": 9,
            "taskbar_show_price": False,
            "taskbar_show_change": True,
            "taskbar_show_dark_flow": True,
        }
        self.page.load(source)
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out, source)

    def test_load_defaults_when_missing(self) -> None:
        self.page.load({})
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out["font_size"], 13)
        self.assertEqual(out["font_family"], "微软雅黑")
        self.assertEqual(out["transparency"], 80)
        self.assertEqual(out["taskbar_quote_enabled"], False)
        self.assertEqual(out["taskbar_per_page"], 3)
        self.assertEqual(out["taskbar_carousel_interval"], 5)
        self.assertEqual(out["taskbar_show_price"], True)
        self.assertEqual(out["taskbar_show_change"], True)
        self.assertEqual(out["taskbar_show_dark_flow"], False)


class TestWatchlistRoundTrip(unittest.TestCase):
    """``WatchlistPage`` 的 load/collect 往返保真。"""

    def setUp(self) -> None:
        self.app = _qapp()
        self.page = WatchlistPage(SettingsContext(view_model=_StubViewModel()))
        self.page.build(self.page)

    def tearDown(self) -> None:
        self.page.deleteLater()

    def test_load_collect_round_trip(self) -> None:
        source = {"user_stocks": ["sh600000", "sz000001", "hk00700"]}
        self.page.load(source)
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out["user_stocks"], ["sh600000", "sz000001", "hk00700"])

    def test_load_empty_collects_empty(self) -> None:
        self.page.load({})
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out["user_stocks"], [])

    def test_build_creates_watch_list_manager(self) -> None:
        self.assertIsInstance(self.page.watch_list_manager, WatchListManager)

    def test_manual_add_then_collect(self) -> None:
        from PyQt6.QtWidgets import QListWidgetItem

        self.page.load({})
        item = QListWidgetItem("⭐ 浦发银行 (sh600000)")
        item.setData(QtCore.Qt.ItemDataRole.UserRole, "sh600000")
        self.page.watch_list.addItem(item)
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out["user_stocks"], ["sh600000"])


class TestQuantRoundTrip(unittest.TestCase):
    """``QuantSettingsPage`` 的 load/collect 往返保真。"""

    def setUp(self) -> None:
        self.app = _qapp()
        self.signals = _StubSignals()
        self.page = QuantSettingsPage(
            SettingsContext(
                manual_report_requested=self.signals.manual_report_requested
            )
        )
        self.page.build(self.page)

    def tearDown(self) -> None:
        self.page.deleteLater()

    def test_load_collect_round_trip(self) -> None:
        source = {
            "quant_enabled": True,
            "auto_export_excel": True,
            "auto_close_export": False,
            "wecom_webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x",
            "push_mode": "app",
            "wecom_corpid": "corpid",
            "wecom_corpsecret": "secret",
            "wecom_agentid": "agent",
            "fib_target_coefficients": {
                "wave_5_target": 0.618,
                "wave_4_retrace": 0.382,
                "wave_b_retrace": 0.5,
            },
        }
        self.page.load(source)
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out, source)

    def test_load_defaults_when_missing(self) -> None:
        self.page.load({})
        out: dict = {}
        self.page.collect(out)
        self.assertEqual(out["quant_enabled"], False)
        self.assertEqual(out["auto_export_excel"], False)
        self.assertEqual(out["auto_close_export"], False)
        self.assertEqual(out["wecom_webhook"], "")
        self.assertEqual(out["push_mode"], "webhook")
        self.assertEqual(
            out["fib_target_coefficients"],
            {"wave_5_target": 0.618, "wave_4_retrace": 0.382, "wave_b_retrace": 0.5},
        )


class TestReExports(unittest.TestCase):
    """``settings_dialog`` 的 re-export 仍然可用。"""

    def test_widget_reexports_are_same_objects(self) -> None:
        self.assertIs(DraggableListWidget, DraggableListWidgetDirect)
        self.assertIs(WatchListManager, WatchListManagerDirect)

    def test_thread_reexports_are_qthread_subclasses(self) -> None:
        thread_classes = (
            DarkTradeExportThread,
            DarkTradeStatsExcelExportThread,
            DarkTradeStatsPushThread,
            ExcelExportThread,
            TestAppThread,
            UpdateCheckThread,
        )
        for cls in thread_classes:
            self.assertTrue(issubclass(cls, QtCore.QThread), cls.__name__)

    def test_pages_package_reexports(self) -> None:
        from stock_monitor.ui.dialogs import settings_pages

        self.assertIs(settings_pages.SettingsContext, SettingsContext)
        self.assertIs(settings_pages.SettingsPage, SettingsPage)
        self.assertIs(settings_pages.GeneralSettingsPage, GeneralSettingsPage)
        self.assertIs(settings_pages.DisplaySettingsPage, DisplaySettingsPage)
        self.assertIs(settings_pages.WatchlistPage, WatchlistPage)
        self.assertIs(settings_pages.QuantSettingsPage, QuantSettingsPage)


class TestDialogShellWiring(unittest.TestCase):
    """对话框 shell 的页实例绑定与页内信号下沉。"""

    def setUp(self) -> None:
        self.app = _qapp()
        self.dialog = NewSettingsDialog(None)

    def tearDown(self) -> None:
        self.dialog.deleteLater()

    def test_page_instances_bound(self) -> None:
        self.assertIsInstance(self.dialog._general_page, GeneralSettingsPage)
        self.assertIsInstance(self.dialog._watchlist_page, WatchlistPage)
        self.assertIsInstance(self.dialog._display_page, DisplaySettingsPage)
        self.assertIsInstance(self.dialog._quant_page, QuantSettingsPage)
        self.assertEqual(len(self.dialog.pages), 4)

    def test_stocks_provider_wired(self) -> None:
        self.assertTrue(callable(self.dialog.ctx.stocks_provider))
        self.assertIsInstance(self.dialog.ctx.stocks_provider(), list)

    def test_watch_list_uses_reexported_class(self) -> None:
        watch_list = self.dialog._watchlist_page.watch_list
        self.assertIsInstance(watch_list, DraggableListWidget)

    def test_tab_titles_preserved(self) -> None:
        titles = [self.dialog.tabs.tabText(i) for i in range(self.dialog.tabs.count())]
        self.assertEqual(
            titles,
            ["📋 自选股管理", "🎨 显示设置", "📊 量化预警"],
        )

    def test_compat_bridge_removed(self) -> None:
        # C4-2：兼容桥与 thin delegate 已删除，shell 不再暴露页控件同名属性
        for name in (
            "watch_list",
            "search_input",
            "watch_list_manager",
            "font_size_slider",
            "font_family_combo",
            "_bind_migrated_widgets",
        ):
            self.assertFalse(hasattr(self.dialog, name), f"shell 仍暴露 {name}")


class TestShellAntiRegression(unittest.TestCase):
    """防退化：AST 扫描 shell，迁移方法不得回归且文件不超过 500 行。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SHELL_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _dialog_methods(self) -> set:
        dialog_cls = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "NewSettingsDialog"
        )
        return {
            node.name
            for node in dialog_cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_shell_has_no_migrated_methods(self) -> None:
        leaked = sorted(self._dialog_methods() & MIGRATED_SHELL_METHODS)
        self.assertEqual(leaked, [], f"以下方法已迁出 shell，不应回归：{leaked}")

    def test_shell_keeps_cross_cutting_methods(self) -> None:
        method_names = self._dialog_methods()
        for expected in (
            "_setup_tabs",
            "_connect_signals",
            "_load_config_from_vm",
            "accept",
            "reject",
            "closeEvent",
            "hideEvent",
        ):
            self.assertIn(expected, method_names)

    def test_shell_line_budget(self) -> None:
        line_count = len(self.source.splitlines())
        self.assertLessEqual(line_count, 500, f"settings_dialog.py 行数={line_count}")


if __name__ == "__main__":
    unittest.main()
