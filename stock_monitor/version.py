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


def _find_pyproject_version() -> str | None:
    """从源码树或 frozen 资源目录定位 pyproject.toml 并读版本。"""
    # 源码目录：stock_monitor/ → 项目根（最多向上 3 层）
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

    # PyInstaller frozen 环境
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        toml_path = os.path.join(sys._MEIPASS, "pyproject.toml")
        if os.path.exists(toml_path):
            ver = _read_version_from_toml(toml_path)
            if ver:
                return ver
    return None


def _installed_metadata_version() -> str | None:
    """已安装包元数据版本（仅在没有 pyproject.toml 时兜底）。"""
    try:
        from importlib import metadata

        return metadata.version("stock_monitor")
    except Exception:
        return None


def _resolve_version() -> str:
    """按优先级解析版本号：pyproject.toml > installed metadata > dev

    pyproject.toml 是唯一版本真源。过期的 egg-info / dist-info（例如本地
    ``pip install -e`` 后未重新生成）不得覆盖它，否则界面版本与更新检查
    会停在旧号上。
    """
    ver = _find_pyproject_version()
    if ver:
        return ver

    ver = _installed_metadata_version()
    if ver:
        return ver

    return "0.0.0-dev"


__version__: str = _resolve_version()
