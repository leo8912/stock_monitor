"""Data handling module"""

# 导入公共函数，统一接口
from .stocks import load_stock_data, enrich_pinyin, is_equal, format_stock_code
from .quotation import get_quotation_engine, is_market_open, process_stock_data, get_name_by_code
from .updater import update_stock_database, get_stock_list

__all__ = [
    'load_stock_data',
    'enrich_pinyin', 
    'is_equal',
    'format_stock_code',
    'get_quotation_engine',
    'is_market_open',
    'process_stock_data',
    'get_name_by_code',
    'update_stock_database',
    'get_stock_list'
]