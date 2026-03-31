"""
PyInstaller hook for mootdx to ensure all dependencies are included.
Place this file in: stock_monitor/hooks/hook-mootdx.py
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 收集所有 mootdx 子模块
hiddenimports = collect_submodules("mootdx")

# 收集所有数据文件
datas = collect_data_files("mootdx", include_py_files=True)

# 显式包含常用但可能被遗漏的模块
explicit_imports = [
    # 核心模块
    "mootdx.quotes",
    "mootdx.business",
    "mootdx.utils",
    "mootdx.consts",
    "mootdx.core",
    # 客户端相关
    "mootdx.client",
    "mootdx.factory",
    # 行情相关
    "mootdx.rollup",
    "mootdx.downloader",
    # 工具函数
    "mootdx.helpers",
    "mootdx.logger",
    "mootdx.exceptions",
    # 依赖库
    "pandas",
    "numpy",
    "requests",
    "lxml",
    "lxml.etree",
    "pyquery",
    "cachetools",
    "click",
]

hiddenimports.extend(explicit_imports)

# 打印调试信息
print(f"Collected {len(hiddenimports)} hidden imports for mootdx")
print(f"Collected {len(datas)} data files for mootdx")
