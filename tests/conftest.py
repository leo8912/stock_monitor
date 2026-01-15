"""
Pytest 配置文件

设置测试环境的通用配置和 fixtures。
"""

import os
import sys

# 确保 Windows 环境下使用 UTF-8 编码
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def pytest_configure(config):
    """pytest 配置钩子，在测试收集前执行"""
    # 设置控制台编码
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
