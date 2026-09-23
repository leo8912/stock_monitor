#!/usr/bin/env python
"""T2：包内 Excel 导出可导入 + stock_fetcher 资源关闭。

验收：
- 不依赖 ``scripts/`` 路径即可导入包内 export 模块
- ``stock_monitor`` 包内无运行时 ``from scripts....`` 导入
- ``StockFetcher.close()`` 幂等关闭线程池
"""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "stock_monitor"


class TestPackageExcelExportImport(unittest.TestCase):
    """包内 Excel 导入不依赖 scripts/。"""

    def test_export_module_imports_without_scripts_on_path(self):
        """sys.path 剔除含 scripts 的条目后仍可导入包内实现。"""
        saved = list(sys.path)

        def _has_scripts_segment(entry: str) -> bool:
            parts = Path(entry).parts
            return "scripts" in parts

        try:
            sys.path[:] = [p for p in sys.path if p and not _has_scripts_segment(p)]
            import stock_monitor.services.reporting.export_stocks_to_excel as mod

            self.assertTrue(hasattr(mod, "export_to_excel"))
            source = inspect.getsource(mod)
            self.assertNotIn("from scripts", source)
            self.assertNotIn("import scripts", source)
        finally:
            sys.path[:] = saved

    def test_no_runtime_scripts_imports_in_package(self):
        """stock_monitor 包内不得出现 scripts.reporting 运行时导入。"""
        offenders: list[str] = []
        for path in PACKAGE_ROOT.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "scripts" or node.module.startswith("scripts."):
                        offenders.append(
                            f"{path.relative_to(PACKAGE_ROOT).as_posix()}:{node.lineno}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "scripts" or alias.name.startswith("scripts."):
                            offenders.append(
                                f"{path.relative_to(PACKAGE_ROOT).as_posix()}:{node.lineno}"
                            )
        self.assertEqual(offenders, [], f"包内存在 scripts 运行时导入: {offenders}")

    def test_callers_use_package_export_path(self):
        """三处调用方均从包内导入 export_to_excel。"""
        expected = [
            PACKAGE_ROOT / "core" / "workers" / "quant_worker.py",
            PACKAGE_ROOT / "services" / "close_export_scheduler.py",
            PACKAGE_ROOT / "ui" / "workers" / "settings_workers.py",
        ]
        for path in expected:
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "stock_monitor.services.reporting.export_stocks_to_excel",
                text,
                f"{path} 未使用包内 export 路径",
            )
            self.assertNotIn(
                "scripts.reporting.export_stocks_to_excel",
                text,
                f"{path} 仍引用 scripts.reporting",
            )


class TestStockFetcherClose(unittest.TestCase):
    """data.fetcher 模块级 stock_fetcher 关闭语义。"""

    def test_close_shuts_down_executor_idempotently(self):
        from stock_monitor.data.fetcher import StockFetcher

        fetcher = StockFetcher()
        executor = fetcher._executor

        self.assertFalse(fetcher._closed)
        fetcher.close()
        self.assertTrue(fetcher._closed)
        self.assertTrue(executor._shutdown, "executor 未被 shutdown")

        # 幂等
        fetcher.close()
        fetcher.shutdown()

    def test_module_level_fetcher_has_close_api(self):
        """模块级单例具备幂等 close API。"""
        from stock_monitor.data.fetcher import stock_fetcher

        self.assertTrue(callable(stock_fetcher.close))
        self.assertTrue(callable(stock_fetcher.shutdown))
        self.assertIsInstance(stock_fetcher._closed, bool)


if __name__ == "__main__":
    unittest.main()
