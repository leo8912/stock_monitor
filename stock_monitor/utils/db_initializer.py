"""
数据库初始化模块
用于将现有的JSON股票数据导入到SQLite数据库中
"""

import json
import os
from typing import List, Dict, Any
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.helpers import resource_path
from stock_monitor.data.stock.stock_db import stock_db
from pypinyin import lazy_pinyin, Style

def migrate_json_to_sqlite():
    """
    将现有的JSON股票数据迁移到SQLite数据库
    """
    try:
        # 读取现有的JSON文件
        json_file_path = resource_path("stock_basic.json")
        if not os.path.exists(json_file_path):
            app_logger.error(f"JSON文件不存在: {json_file_path}")
            return False
            
        with open(json_file_path, 'r', encoding='utf-8') as f:
            stocks_data: List[Dict[str, Any]] = json.load(f)
        
        app_logger.info(f"从JSON文件加载了 {len(stocks_data)} 条股票数据")
        
        # 为股票数据添加拼音信息
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
        
        # 将数据插入到SQLite数据库
        inserted_count = stock_db.insert_stocks(stocks_data)
        
        app_logger.info(f"成功将 {inserted_count} 条股票数据迁移到SQLite数据库")
        return True
        
    except Exception as e:
        app_logger.error(f"迁移JSON到SQLite数据库失败: {e}")
        import traceback
        app_logger.error(f"详细错误信息: {traceback.format_exc()}")
        return False

def initialize_database():
    """
    初始化数据库，如果数据库为空则执行迁移
    """
    try:
        # 检查数据库是否已经有数据
        stock_count = stock_db.get_all_stocks_count()
        
        if stock_count == 0:
            app_logger.info("数据库为空，开始执行初始数据迁移...")
            return migrate_json_to_sqlite()
        else:
            app_logger.info(f"数据库已有 {stock_count} 条股票数据，跳过初始迁移")
            return True
            
    except Exception as e:
        app_logger.error(f"初始化数据库失败: {e}")
        return False

if __name__ == "__main__":
    # 可以直接运行此脚本来执行迁移
    initialize_database()