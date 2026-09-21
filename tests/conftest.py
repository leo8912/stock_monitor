"""
Pytest 配置文件

设置测试环境的通用配置和 fixtures。
"""

import os
import sys
from pathlib import Path

import pytest

# 确保 Windows 环境下使用 UTF-8 编码
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def pytest_configure(config):
    """pytest 配置钩子，在测试收集前执行"""
    # 设置控制台编码（只执行一次，避免在每个 test item 上重复执行）
    if sys.platform == "win32":
        for stream in ("stdout", "stderr"):
            s = getattr(sys, stream, None)
            if s is not None and hasattr(s, "reconfigure"):
                try:
                    s.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass


def pytest_collection_modifyitems(config, items):
    """统一标记 integration 目录中的外部服务测试。"""
    integration_dir = Path(__file__).parent / "integration"
    for item in items:
        if integration_dir in Path(item.fspath).parents:
            item.add_marker(pytest.mark.integration)
