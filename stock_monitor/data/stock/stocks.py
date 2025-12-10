"""
股票数据处理模块
用于加载和处理股票基础数据，包括拼音处理等功能
"""

import json
import os
from typing import List, Dict, Any, Optional

from stock_monitor.utils.logger import app_logger


def load_stock_data() -> List[Dict[str, Any]]:
    """
    加载股票基础数据
    
    从本地 stock_basic.json 文件中加载股票基础数据，包括股票代码和名称。
    如果文件不存在或加载失败，会返回空列表。
    
    Returns:
        List[Dict[str, Any]]: 股票数据列表，每个元素包含 'code' 和 'name' 字段
    """
    from stock_monitor.utils.helpers import handle_exception
    
    def _load_data():
        # 使用resource_path函数正确获取资源文件路径
        from stock_monitor.utils.helpers import resource_path
        stock_file_path = resource_path('stock_basic.json')
        with open(stock_file_path, 'r', encoding='utf-8') as f:
            data: List[Dict[str, Any]] = json.load(f)
        app_logger.debug(f"股票基础数据加载成功，共{len(data)}条记录")
        return data
    
    return handle_exception(
        "加载股票基础数据",
        _load_data,
        [],
        app_logger
    )


def enrich_pinyin(stock_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    丰富股票的拼音信息
    
    为股票列表中的每只股票添加拼音信息，包括全拼和首字母缩写，
    用于支持拼音搜索功能。
    
    Args:
        stock_list (List[Dict[str, Any]]): 股票列表，每个元素应包含 'name' 字段
        
    Returns:
        List[Dict[str, Any]]: 添加了拼音信息的股票列表，每个元素增加 'pinyin' 和 'abbr' 字段
    """
    from stock_monitor.utils.helpers import handle_exception
    
    def _enrich_pinyin():
        # 延迟导入pypinyin，减少启动时间
        from pypinyin import lazy_pinyin, Style
        
        for s in stock_list:
            name = s['name']
            # 去除*ST、ST等前缀，避免影响拼音识别
            base = name.replace('*', '').replace('ST', '').replace(' ', '')
            # 生成全拼
            full_pinyin = ''.join(lazy_pinyin(base))
            # 生成首字母缩写
            abbr = ''.join(lazy_pinyin(base, style=Style.FIRST_LETTER))
            s['pinyin'] = full_pinyin.lower()
            s['abbr'] = abbr.lower()
        app_logger.debug(f"股票拼音信息处理完成，共处理{len(stock_list)}条记录")
        return stock_list
    
    return handle_exception(
        "处理股票拼音信息",
        _enrich_pinyin,
        stock_list,
        app_logger
    )



def format_stock_code(code: str) -> Optional[str]:
    """
    格式化股票代码，确保正确的前缀
    
    将6位数字股票代码转换为带交易所前缀的标准格式，或验证已带前缀的代码是否有效。
    
    Args:
        code (str): 股票代码，可以是6位数字或已带前缀的8位代码
        
    Returns:
        Optional[str]: 格式化后的股票代码，如果输入无效则返回None
    """
    # 使用工具函数处理股票代码格式化
    from stock_monitor.utils.helpers import format_stock_code
    return format_stock_code(code)