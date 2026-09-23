#!/usr/bin/env python
"""QA 独立验证：Python 3.11 语法兼容性静态扫描（自研，未复用工程师脚本）。

历史背景：本文件原为 Python 3.9 兼容性守卫（CI 曾用 3.9）。项目
``requires-python`` 已提升为 ``>=3.11``，守卫基线随之切换到 3.11：

* 硬失败（Hard）——在 3.11 上会直接 ``SyntaxError`` / 不可运行：
  - 使用 ``ast.parse(..., feature_version=(3, 11))`` 解析失败的源码
    （按最低支持版本语法面解析；不能再用 3.9 口径，否则 3.10+ 语法会误报）。
  - **重复装饰器**（同一函数上同一装饰器出现两次，如 ``@staticmethod`` 两次）：
    解析出的属性会成为装饰器对象本身；在 3.9 上 ``staticmethod`` 对象
    “可调用”是 3.10 才引入的（CPython bpo-43682）。虽最低版本已到 3.11，
    重复装饰器仍是明确的逻辑缺陷，保留硬失败。
* 软提示（Soft，供人工复核）：
  - 函数体内局部变量注解 ``X | Y``（PEP 526 不求值）等历史 3.9 观察项。

用法：``python tests/test_qa_py39_compat.py`` 直接查看命中清单。
"""

from __future__ import annotations

import ast
import os
import sys
import unittest

_MIN_FEATURE = (3, 11)


def _is_bitor(node: ast.AST) -> bool:
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)


def _duplicated_decorators(func: ast.AST) -> list:
    """返回该函数上重复出现的装饰器名字（保持稳定顺序）。

    用 ``ast.unparse`` 归一化装饰器表达式（如 ``@staticmethod`` →
    ``staticmethod``），比较去重前后长度以判定重复。
    """
    names = [ast.unparse(deco) for deco in func.decorator_list]
    seen = set()
    dupes = []
    for name in names:
        if name in seen and name not in dupes:
            dupes.append(name)
        seen.add(name)
    return dupes


def _scan_source(source: str, path: str) -> dict:
    """扫描一段源码文本（``path`` 仅用于报告与解析文件名）。"""
    result = {"hard": [], "soft": [], "syntax_error": None}
    # feature_version=(3, 11)：按最低支持版本语法面解析，抓 3.11 无法解析的源码。
    try:
        tree = ast.parse(source, filename=path, feature_version=_MIN_FEATURE)
    except SyntaxError as e:
        result["syntax_error"] = (path, e.lineno, str(e))
        return result
    except TypeError:
        # 极老的 CPython 无 feature_version kwarg：退回默认解析。
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as e:
            result["syntax_error"] = (path, e.lineno, str(e))
            return result

    # 1. 重复装饰器：同一函数上同一装饰器出现多次（如 @staticmethod 两次）
    #    解析后属性 = 装饰器对象本身；仍是明确缺陷，保留为硬失败。
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco_name in _duplicated_decorators(node):
                result["hard"].append(
                    (
                        path,
                        node.lineno,
                        f"重复装饰器 @{deco_name}（装饰器对象覆盖函数定义）",
                    )
                )

    # 2. 软提示：函数体内局部变量注解 X | Y（历史观察项，3.11 安全）
    func_local_anns = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.AnnAssign):
                    func_local_anns.add(id(sub))

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and _is_bitor(node.annotation):
            if id(node) in func_local_anns:
                result["soft"].append(
                    (
                        path,
                        node.lineno,
                        "函数内变量注解 X | Y（PEP526 不求值，3.11 安全）",
                    )
                )

    # 签名注解 X | Y 在 3.10+ 合法，不再作为 hard/soft 计入。
    return result


def scan_tree(root: str) -> dict:
    agg = {"hard": [], "soft": [], "syntax_error": []}
    for dirpath, _dirs, files in os.walk(root):
        if "__pycache__" in dirpath or ".venv" in dirpath:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            full_path = os.path.join(dirpath, name)
            with open(full_path, encoding="utf-8") as fh:
                source = fh.read()
            res = _scan_source(source, full_path)
            agg["hard"].extend(res["hard"])
            agg["soft"].extend(res["soft"])
            if res["syntax_error"]:
                agg["syntax_error"].append(res["syntax_error"])
    return agg


class TestPy311Compatibility(unittest.TestCase):
    """若命中硬失败项，在 requires-python>=3.11 下仍属缺陷 → 断言应为空。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _report(self, agg: dict) -> None:
        lines = []
        for path, lineno, kind in agg["hard"]:
            lines.append(f"HARD {path}:{lineno} {kind}")
        for path, lineno, kind in agg["soft"]:
            lines.append(f"SOFT {path}:{lineno} {kind}")
        if lines:
            print("\n=== 3.11 兼容性扫描命中 ===")
            print("\n".join(lines))

    def test_source_hard_compat(self) -> None:
        agg = scan_tree(os.path.join(self.repo_root, "stock_monitor"))
        self._report(agg)
        self.assertEqual(agg["syntax_error"], [], f"解析失败: {agg['syntax_error']!r}")
        self.assertEqual(agg["hard"], [], f"3.11 硬不兼容命中: {agg['hard']!r}")

    def test_tests_hard_compat(self) -> None:
        agg = scan_tree(os.path.join(self.repo_root, "tests"))
        self._report(agg)
        self.assertEqual(agg["syntax_error"], [], f"解析失败: {agg['syntax_error']!r}")
        self.assertEqual(agg["hard"], [], f"3.11 硬不兼容命中: {agg['hard']!r}")


class TestGuardSelfCheck(unittest.TestCase):
    """守卫自检：证明扫描器确实能抓到“已知 P0”（重复装饰器）。

    一个抓不到已知缺陷的门禁等于没有门禁。本类用**内联源码**复现
    wave_analyzer 曾出现的 ``staticmethod(staticmethod(f))`` 场景，
    断言守卫必然命中 Hard。
    """

    def test_duplicate_staticmethod_is_flagged(self) -> None:
        src = (
            "class A:\n"
            "    @staticmethod\n"
            "    @staticmethod\n"
            "    def f():\n"
            "        return 1\n"
        )
        res = _scan_source(src, "<inline-duplicate>")
        self.assertEqual(res["syntax_error"], None)
        self.assertTrue(
            any("重复装饰器" in kind for _p, _l, kind in res["hard"]),
            f"守卫未抓到重复装饰器, hard={res['hard']!r}",
        )

    def test_duplicate_arbitrary_decorator_is_flagged(self) -> None:
        src = (
            "import functools\n"
            "@functools.lru_cache()\n"
            "@functools.lru_cache()\n"
            "def g():\n"
            "    return 2\n"
        )
        res = _scan_source(src, "<inline-duplicate2>")
        self.assertTrue(
            any("重复装饰器" in kind for _p, _l, kind in res["hard"]),
            f"守卫未抓到重复装饰器, hard={res['hard']!r}",
        )

    def test_single_decorator_not_flagged(self) -> None:
        src = "class A:\n    @staticmethod\n    def f():\n        return 1\n"
        res = _scan_source(src, "<inline-single>")
        self.assertEqual(res["hard"], [], f"误报: {res['hard']!r}")

    def test_real_wave_analyzer_has_no_duplicate_decorator(self) -> None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target = os.path.join(
            root, "stock_monitor", "core", "engine", "wave_analyzer.py"
        )
        with open(target, encoding="utf-8") as fh:
            source = fh.read()
        res = _scan_source(source, target)
        self.assertTrue(
            all("重复装饰器" not in kind for _p, _l, kind in res["hard"]),
            f"wave_analyzer 仍存在重复装饰器: {res['hard']!r}",
        )


if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _target in ("stock_monitor", "tests"):
        _agg = scan_tree(os.path.join(_root, _target))
        print(f"\n===== 扫描 {_target} =====")
        print(f"HARD 命中: {len(_agg['hard'])}")
        for _p, _l, _k in _agg["hard"]:
            print(f"  HARD {_p}:{_l} {_k}")
        print(f"SOFT 提示: {len(_agg['soft'])}")
        for _p, _l, _k in _agg["soft"]:
            print(f"  SOFT {_p}:{_l} {_k}")
        print(f"语法错误: {len(_agg['syntax_error'])}")
        for _p, _l, _k in _agg["syntax_error"]:
            print(f"  SYNTAX {_p}:{_l} {_k}")
    sys.exit(0)
