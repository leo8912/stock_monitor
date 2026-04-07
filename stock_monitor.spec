# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files, copy_metadata
import os

datas = [
    ('pyproject.toml', '.'),
    ('stock_monitor/resources/icon.ico', 'stock_monitor/resources'),
    ('stock_monitor/resources/stocks_base.db', 'stock_monitor/resources'),
    ('stock_monitor/resources/styles', 'stock_monitor/resources/styles'),
]

# Get paths for third-party files (using env vars from GitHub Action)
eq_path = os.environ.get('EQPATH')
if eq_path:
    datas.append((os.path.join(eq_path, 'stock_codes.conf'), 'easyquotation'))

zhconv_path = os.environ.get('ZHCONVPATH')
if zhconv_path:
    datas.append((os.path.join(zhconv_path, 'zhcdict.json'), 'zhconv'))

# --- Collect dependencies ---
binaries = []

# --- Force Include pandas_ta ---
# 移除了动态探测逻辑，改用专用钩子 (stock_monitor/hooks/hook-pandas_ta.py)
# 和下方的 hiddenimports 显式声明来保证收集完整性。

# 基础隐藏导入
hiddenimports = [
    'pypinyin.style',
    'curl_cffi',
    'stock_monitor.core.cache',
    'stock_monitor.core.cache.cache_warmer',
    # pandas 相关
    'pandas',
    'pandas.api.extensions',
    'pandas.core.arrays.arrow',
    'pandas.core.arrays.arrow._arrow_utils',
    'pandas._libs',
    'pandas._libs.tslibs',
    'numpy',
    # 网络相关
    'requests',
    'urllib3',
    'urllib3.util',
    'charset_normalizer',
    'idna',
    'chardet',
    # 数据库相关
    'sqlalchemy',
    # 图像处理
    'PIL',
    # Excel 处理
    'openpyxl',
    'xlrd',
    # 其他
    'tabulate',
    'tqdm',
    'pytz',
    'certifi',
    # mootdx 相关
    'mootdx',
    'mootdx.quotes',
    'mootdx.business',
    'mootdx.utils',
    # pandas-ta (显式隐藏导入，配合 Hook 确保万无一失)
    'pandas_ta',
    'pandas_ta.technical',
    'pandas_ta.utils',
    'pandas_ta.overlap',
    'pandas_ta.performance',
    'pandas_ta.statistics',
    'pandas_ta.trend',
    'pandas_ta.volatility',
    'pandas_ta.momentum',
    # scipy (pandas-ta 的核心隐式依赖)
    'scipy',
    'scipy.signal',
    'scipy.stats',
    'scipy.special',
    'scipy.optimize',
]

# akshare 专用隐藏导入列表
akshare_hiddenimports = [
    'akshare',
    # 股票相关核心模块
    'akshare.stock',
    'akshare.stock.stock_zh_a_spot_em',
    'akshare.stock.stock_info',
    'akshare.stock.stock_financial_abstract',
    'akshare.stock.stock_financial_abstract_ths',
    'akshare.stock.stock_zh_a_hist',
    'akshare.stock.stock_zh_index_spot',
    'akshare.stock.stock_board_industry_name_em',
    'akshare.stock.stock_individual_info_em',
    'akshare.stock.stock_individual_basic_info_em',
    # 基础模块
    'akshare.common',
    'akshare.utils',
    'akshare.data_interface',
    'akshare.data_interface.api',
    'akshare.data_interface.interface',
    'akshare.feature',
    'akshare.stock_feature',
    # 其他市场
    'akshare.index',
    'akshare.fund',
    'akshare.bond',
    'akshare.currency',
    'akshare.global_futures',
    # lxml 和解析相关
    'lxml',
    'lxml.etree',
    'lxml._elementpath',
    'lxml.objectify',
    # beautifulsoup4 相关
    'bs4',
    'bs4.dammit',
    'bs4.element',
    'bs4.builder',
    'bs4.builder._lxml',
    'bs4.builder._html5lib',
    # html5lib 相关
    'html5lib',
    'html5lib._inputstream',
    'html5lib.treebuilders',
    'html5lib.treewalkers',
    'html5lib.serializer',
    # JSON 处理
    'jsonpath',
    'simplejson',
    'demjson3',
]

hiddenimports += akshare_hiddenimports

# 使用 collect_submodules 确保获取所有 akshare 子模块
try:
    print("Collecting all akshare submodules...")
    akshare_all_subs = collect_submodules('akshare')
    hiddenimports += akshare_all_subs
    print(f"Collected {len(akshare_all_subs)} akshare submodules")
except Exception as e:
    print(f"Warning: Could not collect all akshare submodules: {e}")

# 收集 akshare 的数据文件
try:
    print("Collecting akshare data files...")
    akshare_datas = collect_data_files('akshare', include_py_files=True)
    datas += akshare_datas
    print(f"Collected {len(akshare_datas)} akshare data files")
except Exception as e:
    print(f"Warning: Could not collect akshare data files: {e}")

# 专门处理 mootdx - 在循环之前单独处理
try:
    print("Collecting mootdx submodules and data files...")
    mootdx_subs = collect_submodules('mootdx')
    hiddenimports += mootdx_subs
    mootdx_datas = collect_data_files('mootdx', include_py_files=True)
    datas += mootdx_datas
    print(f"Collected {len(mootdx_subs)} mootdx submodules and {len(mootdx_datas)} data files")
except Exception as e:
    print(f"Warning: Could not collect mootdx: {str(e)}")
    # Fallback
    try:
        hiddenimports += collect_submodules('mootdx')
        datas += collect_data_files('mootdx')
    except Exception as e2:
        print(f"Warning: Fallback collection for mootdx also failed: {str(e2)}")

# 收集其他包的完整依赖（移除 mootdx 避免重复）
pkgs_to_collect = ['pandas_ta', 'pytz', 'certifi', 'pypinyin']

for pkg in pkgs_to_collect:
    try:
        tmp_ret = collect_all(pkg)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning: Issue collecting {pkg} with collect_all: {str(e)}")
        try:
            hiddenimports += collect_submodules(pkg)
            datas += collect_data_files(pkg)
        except Exception as e2:
            print(f"Warning: Fallback collection for {pkg} also failed: {str(e2)}")

# 额外收集 easyquotation 和 zhconv
try:
    hiddenimports += collect_submodules('easyquotation')
    datas += collect_data_files('easyquotation')
except Exception as e:
    print(f"Warning: Issue collecting easyquotation: {str(e)}")

try:
    hiddenimports += collect_submodules('zhconv')
    datas += collect_data_files('zhconv', include_py_files=True)
except Exception as e:
    print(f"Warning: Issue collecting zhconv: {str(e)}")

# 强制收集 stock_monitor.core 的所有子模块，解决动态重构和重新导出导致的 ModuleNotFoundError
try:
    print("Collecting stock_monitor.core submodules...")
    core_subs = collect_submodules('stock_monitor.core')
    hiddenimports += core_subs
    print(f"Collected {len(core_subs)} core submodules")
except Exception as e:
    print(f"Warning: Could not collect stock_monitor.core submodules: {e}")

# 强制包含 akshare 和 pandas_ta（物理注入双重保险）
try:
    import akshare
    akshare_path = os.path.dirname(akshare.__file__)
    datas.append((akshare_path, 'akshare'))
    if 'akshare' not in hiddenimports:
        hiddenimports.append('akshare')
    print(f"Force included akshare from: {akshare_path}")
except Exception as e:
    print(f"Critical Warning: Could not locate akshare path directly: {str(e)}")

try:
    # 动态探测 pandas-ta 或 pandas-ta-classic
    try:
        import pandas_ta_classic as pta
        ta_lib_name = 'pandas-ta-classic'
    except ImportError:
        import pandas_ta as pta
        ta_lib_name = 'pandas-ta'

    ta_path = os.path.dirname(pta.__file__)
    # 物理路径注入 (目录名即为模块名)
    ta_mod_name = os.path.basename(ta_path)
    datas.append((ta_path, ta_mod_name))

    # 增加元数据收集，确保 pandas 的 Entry Points 能够发现这个插件
    from PyInstaller.utils.hooks import copy_metadata
    datas += copy_metadata(ta_lib_name)

    if ta_mod_name not in hiddenimports:
        hiddenimports.append(ta_mod_name)
    print(f"Force included {ta_lib_name} from: {ta_path}")
except Exception as e:
    print(f"Critical Warning: Could not locate pandas_ta path directly: {str(e)}")

# 移除重复项
hiddenimports = list(set(hiddenimports))

print(f"\n=== Build Configuration ===")
print(f"Total hidden imports: {len(hiddenimports)}")
print(f"Total data files: {len(datas)}")
print(f"=========================\n")

# 设置自定义 hooks 目录 - 优先使用项目根目录
import sys

# 尝试多个可能的路径
possible_hooks_paths = [
    # GitHub Actions 环境：工作目录是项目根目录
    os.path.join(os.getcwd(), 'stock_monitor', 'hooks'),
    # 开发环境
    os.path.join(os.path.dirname(__file__), 'stock_monitor', 'hooks') if '__file__' in dir() else None,
    # 打包后环境（备用）
    os.path.join(sys._MEIPASS, 'stock_monitor', 'hooks') if getattr(sys, 'frozen', False) else None,
]

hooks_path = []
for path in possible_hooks_paths:
    if path and os.path.exists(path):
        print(f"Using custom hooks from: {path}")
        hooks_path = [path]
        break
else:
    print("No custom hooks directory found")

block_cipher = None

a = Analysis(
    ['stock_monitor/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hooks_path,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stock_monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['stock_monitor/resources/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stock_monitor',
)
