"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 SQLite 数据库
"""

from typing import List, Dict, Any
from stock_monitor.utils.logger import app_logger
from stock_monitor.data.stock.stock_db import stock_db
from stock_monitor.data.fetcher import stock_fetcher
from pypinyin import lazy_pinyin, Style

def update_stock_database() -> bool:
    """
    更新本地股票数据库
    
    Returns:
        bool: 更新是否成功
    """
    return incremental_update_stock_database()


def incremental_update_stock_database() -> bool:
    """
    增量更新本地股票数据库 (包含拼音生成)
    
    Returns:
        bool: 更新是否成功
    """
    try:
        # 1. 获取最新的股票数据
        stocks_data = stock_fetcher.fetch_all_stocks()
        
        if not stocks_data:
            app_logger.warning("未获取到股票数据，取消更新")
            return False
        
        # 2. 按代码排序
        stocks_data.sort(key=lambda x: x['code'])
        
        # 3. 为股票数据添加拼音信息
        app_logger.info("开始为股票数据添加拼音信息...")
        for stock in stocks_data:
            name = stock['name']
            # 去除*ST、ST等前缀，避免影响拼音识别
            base = name.replace('*', '').replace('ST', '').replace(' ', '')
            # 生成全拼
            full_pinyin = ''.join(lazy_pinyin(base))
            # 生成首字母缩写
            abbr = ''.join(lazy_pinyin(base, style=Style.FIRST_LETTER))
            stock['pinyin'] = full_pinyin.lower()
            stock['abbr'] = abbr.lower()
        
        app_logger.info("拼音信息处理完成")
        
        # 4. 批量更新数据库
        inserted_count = stock_db.insert_stocks(stocks_data)
        
        app_logger.info(f"股票数据库更新完成，共处理/更新 {inserted_count} 条记录")
        return True
        
    except Exception as e:
        app_logger.error(f"更新股票数据库失败: {e}")
        return False
