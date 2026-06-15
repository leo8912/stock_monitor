"""
版本管理模块
唯一版本来源：pyproject.toml
"""

import os
import sys


def _read_version_from_toml(toml_path: str):
    """从 pyproject.toml 读取 version 字段"""
    try:
        with open(toml_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("version"):
                    parts = stripped.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def _resolve_version() -> str:
    """按优先级解析版本号：installed package > pyproject.toml > frozen > dev"""
    # 1. 已安装的包元数据
    try:
        from importlib import metadata

        return metadata.version("stock_monitor")
    except Exception:
        pass

    # 2. 源码目录下的 pyproject.toml
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    for _ in range(3):
        toml_path = os.path.join(project_root, "pyproject.toml")
        if os.path.exists(toml_path):
            ver = _read_version_from_toml(toml_path)
            if ver:
                return ver
        parent = os.path.dirname(project_root)
        if parent == project_root:
            break
        project_root = parent

    # 3. PyInstaller frozen 环境
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        toml_path = os.path.join(sys._MEIPASS, "pyproject.toml")
        if os.path.exists(toml_path):
            ver = _read_version_from_toml(toml_path)
            if ver:
                return ver

    return "0.0.0-dev"


__version__: str = _resolve_version()
