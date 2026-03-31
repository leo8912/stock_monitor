"""
PyInstaller hook for akshare to ensure all dependencies are included.
Place this file in: stock_monitor/hooks/hook-akshare.py
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 收集所有 akshare 子模块
hiddenimports = collect_submodules("akshare")

# 收集所有数据文件
datas = collect_data_files("akshare", include_py_files=True)

# 显式包含常用但可能被遗漏的模块
explicit_imports = [
    # 股票相关
    "akshare.stock.stock_zh_a_spot_em",
    "akshare.stock.stock_info",
    "akshare.stock.stock_financial_abstract",
    "akshare.stock.stock_financial_abstract_ths",
    "akshare.stock.stock_zh_a_hist",
    "akshare.stock.stock_zh_index_spot",
    "akshare.stock.stock_board_industry_name_em",
    "akshare.stock.stock_individual_info_em",
    "akshare.stock.stock_individual_basic_info_em",
    # 基础模块
    "akshare.common",
    "akshare.utils",
    "akshare.data_interface",
    "akshare.data_interface.api",
    "akshare.data_interface.interface",
    "akshare.feature",
    "akshare.stock_feature",
    # 其他市场
    "akshare.index",
    "akshare.fund",
    "akshare.bond",
    "akshare.currency",
    "akshare.global_futures",
    # lxml 相关
    "lxml.etree",
    "lxml._elementpath",
    "lxml.objectify",
    # beautifulsoup4 相关
    "bs4",
    "bs4.dammit",
    "bs4.element",
    "bs4.builder",
    "bs4.builder._lxml",
    "bs4.builder._html5lib",
    # html5lib 相关
    "html5lib",
    "html5lib._inputstream",
    "html5lib.treebuilders",
    "html5lib.treewalkers",
    "html5lib.serializer",
    # pandas 相关
    "pandas.core.arrays.arrow",
    "pandas.core.arrays.arrow._arrow_utils",
    "pandas._libs",
    "pandas._libs.tslibs",
    "pandas._libs.lib",
    "pandas._libs.parsers",
    "pandas.io.formats.format",
    "pandas.io.clipboard",
    "pandas.io.excel",
    "pandas.io.excel._openpyxl",
    # 网络和编码相关
    "chardet",
    "chardet.universaldetector",
    "charset_normalizer",
    "charset_normalizer.md",
    "urllib3",
    "urllib3.util",
    "urllib3.contrib",
    # JSON 处理
    "jsonpath",
    "simplejson",
    "demjson3",
    # 其他依赖
    "tqdm",
    "tabulate",
    "xlrd",
    "openpyxl",
    "pytz",
    "numpy",
]

hiddenimports.extend(explicit_imports)

# 打印调试信息
print(f"Collected {len(hiddenimports)} hidden imports for akshare")
print(f"Collected {len(datas)} data files for akshare")
