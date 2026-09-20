from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 强制收集 pandas_ta 的所有子模块（如 technical, utils, overlap 等）
hiddenimports = collect_submodules("pandas_ta")

# 收集可能存在的元数据或配置文件
datas = collect_data_files("pandas_ta")

# 调试信息（PyInstaller 构建期 hook 输出，非应用日志，故保留 print）
print(f"HOOK pandas_ta: Collecting {len(hiddenimports)} submodules")
