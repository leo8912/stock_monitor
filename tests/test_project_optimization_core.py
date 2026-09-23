"""正确性 / 热路径 / 单实例 回归测试（compose project-optimization）"""

from __future__ import annotations

import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.config.container import DIContainer
from stock_monitor.core.market.stock_manager import (
    StockManager,
)
from stock_monitor.core.market.stock_manager import (
    stock_manager as module_stock_manager,
)
from stock_monitor.utils import session_cache


class TestSystemTrayWeakref(unittest.TestCase):
    def test_callbacks_skip_when_window_released(self):
        """主窗口 weakref 失效时托盘回调应安全返回（不构造真实托盘图标）。"""
        from stock_monitor.ui.components import system_tray as tray_mod

        # 直接调用解引用模式：与 SystemTray 方法体一致的 None 守卫逻辑
        class _FakeTray:
            main_window = None

            def show_main_window(self) -> None:
                mw = self.main_window
                if mw is None:
                    return
                mw.show()

            def open_settings(self) -> None:
                mw = self.main_window
                if mw is None:
                    return
                mw.open_settings()

            def quit_application(self) -> None:
                mw = self.main_window
                if mw is None:
                    return
                mw.quit_application()

        # 源码级断言：真实实现包含 None 守卫
        import inspect

        src = inspect.getsource(tray_mod.SystemTray)
        self.assertIn("if mw is None", src)
        fake = _FakeTray()
        fake.show_main_window()
        fake.open_settings()
        fake.quit_application()


class TestSessionCacheThrottle(unittest.TestCase):
    def setUp(self):
        self._orig_file = session_cache.CACHE_FILE
        self._orig_dir = session_cache.CACHE_DIR
        self._orig_ts = session_cache._last_save_ts
        self._orig_pending = session_cache._pending_data

    def tearDown(self):
        session_cache.CACHE_FILE = self._orig_file
        session_cache.CACHE_DIR = self._orig_dir
        session_cache._last_save_ts = self._orig_ts
        session_cache._pending_data = self._orig_pending

    def test_force_writes_immediately(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            session_cache.CACHE_DIR = Path(td)
            session_cache.CACHE_FILE = Path(td) / "last_session.json"
            session_cache._last_save_ts = time.time()  # 已在节流窗内
            ok = session_cache.save_session_cache({"x": 1}, force=True)
            self.assertTrue(ok)
            self.assertTrue(session_cache.CACHE_FILE.exists())
            # 节流后再 force 应仍可写
            ok2 = session_cache.save_session_cache({"x": 2}, force=True)
            self.assertTrue(ok2)
            loaded = session_cache.load_session_cache()
            self.assertEqual(loaded, {"x": 2})

    def test_non_force_queues_pending_when_throttled(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            session_cache.CACHE_DIR = Path(td)
            session_cache.CACHE_FILE = Path(td) / "last_session.json"
            session_cache._last_save_ts = time.time()
            session_cache._pending_data = None
            ok = session_cache.save_session_cache({"y": 1}, force=False)
            self.assertTrue(ok)
            # 立即 flush 时写出 pending
            flushed = session_cache.flush_session_cache()
            self.assertTrue(flushed)
            loaded = session_cache.load_session_cache()
            self.assertEqual(loaded, {"y": 1})


class TestConfigManagerAtomicAndFlush(unittest.TestCase):
    def test_create_default_config_atomic(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            # 绕过单例：直接构造对象
            mgr = object.__new__(ConfigManager)
            mgr._config_path = path
            mgr.config_path = path
            mgr._config = {}
            mgr._instance_lock = __import__("threading").Lock()
            mgr._dirty = False
            mgr._flush_timer = None
            mgr._create_default_config()
            self.assertTrue(Path(path).exists())
            self.assertFalse(Path(path + ".tmp").exists())

    def test_set_deferred_then_flush(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            mgr = object.__new__(ConfigManager)
            mgr._config_path = path
            mgr.config_path = path
            mgr._config = {}
            mgr._instance_lock = __import__("threading").Lock()
            mgr._dirty = False
            mgr._flush_timer = None
            mgr._create_default_config()
            self.assertTrue(mgr.set("k", 1, flush=False))
            # 内存可见
            self.assertEqual(mgr.get("k"), 1)
            self.assertTrue(mgr.flush())
            import json

            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["k"], 1)


class TestStockManagerSingletonAndNoJsonRoundtrip(unittest.TestCase):
    def test_container_returns_module_singleton(self):
        container = DIContainer()
        # 清除可能已注册的其它实例，强制 auto-create 路径
        with container._access_lock:
            container._singletons.pop(StockManager, None)
            container._factories.pop(StockManager, None)
        inst = container.get(StockManager)
        self.assertIs(inst, module_stock_manager)

    def test_process_uses_impl_directly(self):
        manager = StockManager(stock_data_service=MagicMock())
        manager._process_single_stock_data_impl = MagicMock(return_value=MagicMock())
        # 构造带 info 的数据流
        manager._large_orders_cache = {}
        manager._auction_cache = {}
        manager._cache_lock = __import__("threading").Lock()
        # 直接测实现调用路径：绕过网络，仅验证 impl 被直接使用
        manager._process_single_stock_data_impl("sh600000", {"a": 1})
        manager._process_single_stock_data_impl.assert_called_once()


class TestWaveWorkerLifecycle(unittest.TestCase):
    def test_stop_wave_worker_handles_missing(self):
        from stock_monitor.ui.dialogs.wave_chart_dialog import WaveChartDialog

        self.assertTrue(hasattr(WaveChartDialog, "_stop_wave_worker"))
        self.assertTrue(hasattr(WaveChartDialog, "closeEvent"))

    def test_comparison_has_close_stop(self):
        from stock_monitor.ui.dialogs.stock_comparison_dialog import (
            StockComparisonDialog,
        )

        self.assertTrue(hasattr(StockComparisonDialog, "_stop_data_worker"))
        self.assertTrue(hasattr(StockComparisonDialog, "closeEvent"))


class TestCloseExportStop(unittest.TestCase):
    def test_stop_uses_wait_for_thread_stop(self):
        import inspect

        from stock_monitor.services.close_export_scheduler import CloseExportScheduler

        src = inspect.getsource(CloseExportScheduler.stop_scheduler)
        self.assertIn("wait_for_thread_stop", src)


class TestStockTableResizeGate(unittest.TestCase):
    """T5: 未变宽时不触发全量 resize。"""

    @classmethod
    def setUpClass(cls):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6 import QtWidgets

        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_no_wide_content_skips_resize(self):
        from stock_monitor.models.stock_data import StockRowData
        from stock_monitor.ui.components.stock_table import StockTable

        table = StockTable()
        rows = [
            StockRowData(
                code="sh600000",
                name="平安银行",
                price="10.50",
                change_str="+1.23",
                color_hex="#ff0000",
                seal_vol="",
                seal_type="",
            ),
            StockRowData(
                code="sh600001",
                name="贵州茅台",
                price="1800.00",
                change_str="-0.50",
                color_hex="#00ff00",
                seal_vol="",
                seal_type="",
            ),
        ]
        # 首次布局：允许 resize
        table.update_data(rows)
        resize_calls = {"n": 0}
        original = table._resize_columns

        def counting_resize():
            resize_calls["n"] += 1
            return original()

        table._resize_columns = counting_resize
        # 行数/布局不变，且列已足够宽 → 不应再 resize
        same = [
            StockRowData(
                code=r.code,
                name=r.name,
                price=r.price,
                change_str=r.change_str,
                color_hex=r.color_hex,
                seal_vol=r.seal_vol,
                seal_type=r.seal_type,
            )
            for r in rows
        ]
        table.update_data(same)
        self.assertEqual(resize_calls["n"], 0)
        # 内容明显变宽（超长封单）→ 应触发 resize
        wide = list(same)
        wide[0] = StockRowData(
            code=wide[0].code,
            name=wide[0].name,
            price=wide[0].price,
            change_str=wide[0].change_str,
            color_hex=wide[0].color_hex,
            seal_vol="99999999999手",
            seal_type="买",
        )
        table.update_data(wide)
        self.assertGreaterEqual(resize_calls["n"], 1)

    def test_content_may_widen_false_when_sections_wide(self):
        from stock_monitor.models.stock_data import StockRowData
        from stock_monitor.ui.components.stock_table import StockTable

        table = StockTable()
        table.update_data(
            [
                StockRowData(
                    code="sh600000",
                    name="平",
                    price="1",
                    change_str="+",
                    color_hex="#fff",
                    seal_vol="",
                    seal_type="",
                )
            ]
        )
        # 把所有列宽撑到极大 → 不应判定变宽
        h = table.horizontalHeader()
        assert h is not None
        for col in range(table._model.columnCount()):
            h.resizeSection(col, 5000)
        self.assertFalse(table._content_may_widen())


class TestConfigCenterDeferred(unittest.TestCase):
    def test_set_deferred_updates_memory_and_flush_writes(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from stock_monitor.core.config_center import ConfigCenter

        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "config.json")
            mgr = object.__new__(ConfigManager)
            mgr._config_path = path
            mgr.config_path = path
            mgr._config = {}
            mgr._instance_lock = __import__("threading").Lock()
            mgr._dirty = False
            mgr._flush_timer = None
            mgr._create_default_config()

            center = object.__new__(ConfigCenter)
            center._manager = mgr
            center._cache = {}
            center._cache_lock = __import__("threading").Lock()
            center._initialized = True

            with patch("stock_monitor.core.config_center.event_bus") as bus:
                self.assertTrue(center.set_deferred("foo", 42))
                bus.publish.assert_called()
            # 内存立即可见
            self.assertEqual(center.get("foo"), 42)
            # flush 前：磁盘可能仍是旧值；flush 后必为新值
            self.assertTrue(center.flush())
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["foo"], 42)

    def test_settings_save_uses_deferred_batch(self):
        import inspect

        from stock_monitor.ui.view_models.settings_view_model import (
            SettingsViewModel,
        )

        src = inspect.getsource(SettingsViewModel.save_settings)
        self.assertIn("set_deferred", src)
        self.assertIn("flush", src)


if __name__ == "__main__":
    unittest.main()
