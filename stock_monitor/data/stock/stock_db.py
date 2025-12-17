"""
股票数据库访问模块
提供对SQLite股票数据库的访问接口
"""

import sqlite3
import json
import os
import threading
from typing import List, Dict, Any, Optional, Tuple
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.helpers import resource_path

# 数据库文件路径
DB_FILE = "stocks.db"

class StockDatabase:
    """股票数据库访问类"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化数据库连接"""
        if not hasattr(self, '_initialized'):
            self.db_path = resource_path(DB_FILE)
            self._initialized = True
            self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建股票表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stocks (
                        code TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        pinyin TEXT,
                        abbr TEXT,
                        market_type TEXT,  -- 'A' for A股, 'INDEX' for 指数, 'HK' for 港股
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON stocks(name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pinyin ON stocks(pinyin)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_abbr ON stocks(abbr)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_type ON stocks(market_type)")
                
                conn.commit()
                app_logger.info("股票数据库初始化完成")
        except Exception as e:
            app_logger.error(f"初始化股票数据库失败: {e}")
            raise
    
    def insert_stocks(self, stocks: List[Dict[str, Any]]) -> int:
        """
        插入或更新股票数据
        
        Args:
            stocks: 股票数据列表
            
        Returns:
            int: 成功插入或更新的记录数
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                inserted_count = 0
                updated_count = 0
                unchanged_count = 0
                
                for stock in stocks:
                    code = stock['code']
                    name = stock['name']
                    pinyin = stock.get('pinyin', '')
                    abbr = stock.get('abbr', '')
                    
                    # 确定市场类型
                    market_type = 'A'  # 默认为A股
                    if code.startswith('hk'):
                        market_type = 'HK'
                    elif code.startswith(('sh000', 'sz399')):
                        market_type = 'INDEX'
                    
                    # 检查记录是否已存在
                    cursor.execute("SELECT name, pinyin, abbr, market_type FROM stocks WHERE code = ?", (code,))
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        # 记录已存在，检查数据是否发生变化
                        existing_name, existing_pinyin, existing_abbr, existing_market_type = existing_record
                        if (existing_name == name and existing_pinyin == pinyin and 
                            existing_abbr == abbr and existing_market_type == market_type):
                            # 数据未变化，无需更新
                            unchanged_count += 1
                        else:
                            # 数据有变化，执行更新
                            cursor.execute("""
                                UPDATE stocks 
                                SET name = ?, pinyin = ?, abbr = ?, market_type = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE code = ?
                            """, (name, pinyin, abbr, market_type, code))
                            updated_count += 1
                    else:
                        # 新记录，执行插入
                        cursor.execute("""
                            INSERT INTO stocks 
                            (code, name, pinyin, abbr, market_type, updated_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (code, name, pinyin, abbr, market_type))
                        inserted_count += 1
                
                conn.commit()
                app_logger.info(f"股票数据更新完成: 新增 {inserted_count} 条，更新 {updated_count} 条，未变化 {unchanged_count} 条")
                return inserted_count + updated_count
        except Exception as e:
            app_logger.error(f"插入股票数据失败: {e}")
            return 0
    
    def get_stock_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        根据股票代码获取股票信息
        
        Args:
            code: 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票信息，未找到返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT code, name, pinyin, abbr FROM stocks WHERE code = ?", (code,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'code': row[0],
                        'name': row[1],
                        'pinyin': row[2],
                        'abbr': row[3]
                    }
                return None
        except Exception as e:
            app_logger.error(f"查询股票 {code} 失败: {e}")
            return None
    
    def search_stocks(self, keyword: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            List[Dict[str, Any]]: 匹配的股票列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建搜索查询
                search_pattern = f"%{keyword}%"
                cursor.execute("""
                    SELECT code, name, pinyin, abbr 
                    FROM stocks 
                    WHERE code = ? OR name LIKE ? OR pinyin LIKE ? OR abbr LIKE ?
                    ORDER BY 
                        CASE 
                            WHEN code = ? THEN 1
                            WHEN name LIKE ? THEN 2
                            WHEN pinyin LIKE ? THEN 3
                            WHEN abbr LIKE ? THEN 4
                            ELSE 5
                        END,
                        code
                    LIMIT ?
                """, (keyword, search_pattern, search_pattern, search_pattern,
                      keyword, search_pattern, search_pattern, search_pattern, limit))
                
                rows = cursor.fetchall()
                return [{'code': row[0], 'name': row[1], 'pinyin': row[2], 'abbr': row[3]} 
                        for row in rows]
        except Exception as e:
            app_logger.error(f"搜索股票失败: {e}")
            return []
    
    def get_stocks_by_market_type(self, market_type: str) -> List[Dict[str, Any]]:
        """
        根据市场类型获取股票列表
        
        Args:
            market_type: 市场类型 ('A', 'INDEX', 'HK')
            
        Returns:
            List[Dict[str, Any]]: 股票列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT code, name, pinyin, abbr FROM stocks WHERE market_type = ?", 
                              (market_type,))
                rows = cursor.fetchall()
                return [{'code': row[0], 'name': row[1], 'pinyin': row[2], 'abbr': row[3]} 
                        for row in rows]
        except Exception as e:
            app_logger.error(f"按市场类型查询股票失败: {e}")
            return []
    
    def get_all_stocks_count(self) -> int:
        """
        获取股票总数
        
        Returns:
            int: 股票总数
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM stocks")
                return cursor.fetchone()[0]
        except Exception as e:
            app_logger.error(f"获取股票总数失败: {e}")
            return 0
    
    def get_all_stocks(self) -> List[Dict[str, Any]]:
        """
        获取所有股票数据
        
        Returns:
            List[Dict[str, Any]]: 所有股票数据
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT code, name, pinyin, abbr FROM stocks ORDER BY code")
                rows = cursor.fetchall()
                return [{'code': row[0], 'name': row[1], 'pinyin': row[2], 'abbr': row[3]} 
                        for row in rows]
        except Exception as e:
            app_logger.error(f"获取所有股票数据失败: {e}")
            return []

# 创建全局实例
stock_db = StockDatabase()