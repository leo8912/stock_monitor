#!/usr/bin/env python
"""QA 独立验证：Python 3.9 语法兼容性静态扫描（自研，未复用工程师脚本）。

CI 使用 Python 3.9，本地为 3.13 —— "本地绿 != CI 绿" 的高危区。本扫描在
AST 层检测会导致 3.9 直接报错/运行期 TypeError 的构造：

* 硬失败（Hard）：
  - ``match`` 语句（3.9 语法错误）
  - 函数签名注解中的 ``X | Y``（PEP 604，3.9 求值时 ``TypeError``），
    除非该模块含 ``from __future__ import annotations``
  - 类/模块级变量注解中的 ``X | Y``（同样会被求值）
  - **重复装饰器**（同一函数上同一装饰器出现两次，如 ``@staticmethod`` 两次）：
    解析出的属性会成为装饰器对象本身；``staticmethod`` 对象"可调用"是 Python
    3.10 才引入的（CPython bpo-43682），3.9 调用即 ``TypeError``。本地 3.13 掩盖。
* 软提示（Soft，供人工复核）：
  - 函数体内局部变量注解 ``X | Y``（PEP 526 不求值，3.9 安全）

用法：``python tests/test_qa_py39_compat.py`` 直接查看命中清单。
"""

import ast
import os
import sys
import unittest


def _is_bitor(node: ast.AST) -> bool:
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)


# 关键：``ast.Match`` 是 Python 3.10 才加入的，3.9 的 ast 模块**没有该属性**。
# 本守卫自身要在 CI 的 Python 3.9 上运行，直接写 ``isinstance(node, ast.Match)``
# 会抛 ``AttributeError: module 'ast' has no attribute 'Match'``，导致守卫在 3.9
# 上全线 FAIL —— 即"3.9 兼容性守卫自己不兼容 3.9"的自指陷阱（v4.8.0 CI 真实踩到）。
# 因此用 getattr 安全降级：属性缺失时按「无 match 语句」处理。
_AST_MATCH_NODES = tuple(
    node_type for node_type in (getattr(ast, "Match", None),) if node_type is not None
)


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    return True
    return False


def _iter_annotation_nodes(func: ast.AST):
    """产出函数签名里所有会被求值的注解表达式。"""
    args = func.args
    for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
        if arg.annotation is not None:
            yield arg.annotation
    if args.vararg is not None and args.vararg.annotation is not None:
        yield args.vararg.annotation
    if args.kwarg is not None and args.kwarg.annotation is not None:
        yield args.kwarg.annotation
    if func.returns is not None:
        yield func.returns


def _walk_annotations(node: ast.AST):
    for child in ast.walk(node):
        if isinstance(child, ast.AnnAssign):
            yield child.annotation


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
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        result["syntax_error"] = (path, e.lineno, str(e))
        return result

    has_future = _has_future_annotations(tree)

    # 1. match 语句：3.9 语法错误（本地能解析出来即已命中）
    #    注意：3.9 无 ast.Match，故用降级元组；为空元组时短路跳过。
    for node in ast.walk(tree):
        if _AST_MATCH_NODES and isinstance(node, _AST_MATCH_NODES):
            result["hard"].append((path, node.lineno, "match 语句（3.9 语法错误）"))

    # 2. 函数签名注解中的 X | Y
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ann in _iter_annotation_nodes(node):
                if _is_bitor(ann):
                    kind = "签名注解 X | Y"
                    if not has_future:
                        result["hard"].append((path, ann.lineno, kind))
                    else:
                        result["soft"].append(
                            (path, ann.lineno, kind + "（有 future import，安全）")
                        )

    # 3. 变量注解：区分函数体内（安全）与模块/类级（会被求值）
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
                        "函数内变量注解 X | Y（PEP526 不求值，3.9 安全）",
                    )
                )
            elif not has_future:
                result["hard"].append(
                    (path, node.lineno, "模块/类级变量注解 X | Y（会被求值）")
                )

    # 4. 重复装饰器：同一函数上同一装饰器出现多次（如 @staticmethod 两次）
    #    解析后属性 = 装饰器对象本身；装饰器对象"可调用"是 3.10 才引入的
    #    （CPython bpo-43682），3.9 调用即 TypeError。本地 3.13 会掩盖该缺陷。
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco_name in _duplicated_decorators(node):
                result["hard"].append(
                    (
                        path,
                        node.lineno,
                        f"重复装饰器 @{deco_name}（3.9 运行期 TypeError，bpo-43682）",
                    )
                )

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


class TestPy39Compatibility(unittest.TestCase):
    """若命中硬失败项，CI 在 3.9 下必然失败 → 断言应为空。"""

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
            print("\n=== 3.9 兼容性扫描命中 ===")
            print("\n".join(lines))

    def test_source_hard_compat(self) -> None:
        agg = scan_tree(os.path.join(self.repo_root, "stock_monitor"))
        self._report(agg)
        self.assertEqual(agg["syntax_error"], [], f"解析失败: {agg['syntax_error']!r}")
        self.assertEqual(agg["hard"], [], f"3.9 硬不兼容命中: {agg['hard']!r}")

    def test_tests_hard_compat(self) -> None:
        agg = scan_tree(os.path.join(self.repo_root, "tests"))
        self._report(agg)
        self.assertEqual(agg["syntax_error"], [], f"解析失败: {agg['syntax_error']!r}")
        self.assertEqual(agg["hard"], [], f"3.9 硬不兼容命中: {agg['hard']!r}")


class TestGuardSelfCheck(unittest.TestCase):
    """守卫自检：证明扫描器确实能抓到"已知 P0"（重复装饰器）。

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
            f"守卫未抓到重复装饰器，hard={res['hard']!r}",
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
            f"守卫未抓到重复装饰器，hard={res['hard']!r}",
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
