"""
分层架构守卫测试（防止依赖方向回退）

依赖方向约定（``stock_monitor`` 包内）：``ui → services → core → data → utils``
反向依赖（下层导入上层）视为违规。规则：

- ``core``      不得导入 ``ui``
- ``data``      不得导入 ``ui`` / ``core`` / ``services``
- ``services``  不得导入 ``ui``
- ``models``    不得导入 ``ui`` / ``core`` / ``data`` / ``services``
- ``utils``     不得导入 ``ui`` / ``core`` / ``data`` / ``services``

历史遗留的反向依赖记录在 :data:`KNOWN_VIOLATIONS`（含修复方向），
测试只拦截**新增**违规，允许后续逐步清理空白名单。
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "stock_monitor"

# 各层禁止导入的层集合（除同层外）
LAYER_RULES = {
    "core": {"ui"},
    "data": {"ui", "core", "services"},
    "services": {"ui"},
    "models": {"ui", "core", "data", "services"},
    "utils": {"ui", "core", "data", "services"},
}

# 既有违规（(相对路径, 被导入层)）——修复后应从中删除
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # 组合根位置错误：StockMonitorApp 应移出 core（见架构审查 P0-1）
    ("core/application.py", "ui"),
    ("core/application.py", "data"),
    # data 层服务定位器：应改为构造注入（见架构审查 P0-2）
    ("data/market/quotation.py", "core"),
    ("data/market/__init__.py", "core"),
    ("data/stock/stocks.py", "core"),
    ("data/stock/stock_updater.py", "core"),
    # 诊断工具跨层聚合检查（健康检查需要遍历各层状态）
    ("utils/health_check.py", "core"),
    ("utils/health_check.py", "data"),
}


def _iter_python_files():
    for path in PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _imported_top_package(node: ast.AST) -> str | None:
    """提取 ``import stock_monitor.x`` / ``from stock_monitor.x import y`` 的层名。"""
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
    elif isinstance(node, ast.ImportFrom):
        if node.level != 0 or node.module is None:
            return None  # 相对导入视为同包内，不跨层
        names = [node.module]
    else:
        return None

    for name in names:
        parts = name.split(".")
        if len(parts) >= 2 and parts[0] == "stock_monitor":
            return parts[1]
    return None


def _collect_violations() -> list[tuple[str, int, str]]:
    """返回 [(相对路径, 行号, 被导入层)]。"""
    violations = []
    for path in _iter_python_files():
        rel = path.relative_to(PACKAGE_ROOT).as_posix()
        layer = rel.split("/")[0]
        forbidden = LAYER_RULES.get(layer)
        if not forbidden:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - 语法错误由其它测试负责
            continue

        for node in ast.walk(tree):
            imported = _imported_top_package(node)
            if imported and imported in forbidden and imported != layer:
                violations.append((rel, node.lineno, imported))
    return violations


class TestArchitectureLayers(unittest.TestCase):
    def test_package_root_found(self):
        """包目录与分层规则存在（防止规则被静默清空）"""
        self.assertTrue(PACKAGE_ROOT.is_dir(), f"未找到包目录: {PACKAGE_ROOT}")
        self.assertTrue(LAYER_RULES)

    def test_no_new_layer_violations(self):
        """不得引入新的跨层反向依赖"""
        violations = _collect_violations()
        unexpected = [
            (rel, line, imported)
            for rel, line, imported in violations
            if (rel, imported) not in KNOWN_VIOLATIONS
        ]
        message = "\n".join(
            f"  {rel}:{line} 导入了禁止的层 '{imported}'"
            for rel, line, imported in unexpected
        )
        self.assertEqual(
            unexpected,
            [],
            "检测到新的分层违规（请调整导入方向，或确认后登记到 KNOWN_VIOLATIONS）：\n"
            + message,
        )


if __name__ == "__main__":
    unittest.main()
