"""
PyInstaller hook for akshare to ensure all dependencies are included.
Place this file in: stock_monitor/hooks/hook-akshare.py
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 收集所有 akshare 子模块
hiddenimports = collect_submodules("akshare")

# 收集数据文件（不收集 .py 源码：模块已进 PYZ，重复收集会放大体积并有遮蔽风险）
datas = collect_data_files("akshare")

# akshare.* 子模块已由 collect_submodules("akshare") 递归覆盖，无需重复列出；
# 此处仅补充 PyInstaller 静态分析追踪不到的动态注册模块
explicit_imports = [
    # bs4 按可用性动态注册 parser 实现
    "bs4.builder._lxml",
]

hiddenimports.extend(explicit_imports)

# 打印调试信息（PyInstaller 构建期 hook 输出，非应用日志，故保留 print）
print(f"Collected {len(hiddenimports)} hidden imports for akshare")
print(f"Collected {len(datas)} data files for akshare")
