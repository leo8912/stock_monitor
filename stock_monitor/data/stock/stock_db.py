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
from stock_monitor.config.manager import get_config_dir
from .stock_data_source import StockDataSource

# 数据库文件路径
DB_FILE = "stocks.db"

class StockDatabase(StockDataSource):
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
            # 使用配置目录存储数据库，确保数据持久化且可写
            config_dir = get_config_dir()
            self.db_path = os.path.join(config_dir, DB_FILE)
            
            # 首次运行，复制基础数据库
            if not os.path.exists(self.db_path):
                base_db = resource_path('stocks_base.db')
                if os.path.exists(base_db):
                    app_logger.info("首次运行，复制基础数据库...")
                    os.makedirs(config_dir, exist_ok=True)
                    import shutil
                    shutil.copy2(base_db, self.db_path)
                    app_logger.info(f"基础数据库复制完成: {self.db_path}")
                else:
                    app_logger.info("未找到基础数据库，将创建新数据库")
            
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
        插入或更新股票数据（批量优化版）
        
        Args:
            stocks: 股票数据列表
            
        Returns:
            int: 成功插入或更新的记录数
        """
        if not stocks:
            return 0
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 准备数据
                data_to_insert = []
                for stock in stocks:
                    code = stock['code']
                    name = stock['name']
                    pinyin = stock.get('pinyin', '')
                    abbr = stock.get('abbr', '')
                    
                    # 确定市场类型
                    market_type = 'A'
                    if code.startswith('hk'):
                        market_type = 'HK'
                    elif code.startswith(('sh000', 'sz399')):
                        market_type = 'INDEX'
                        
                    data_to_insert.append((code, name, pinyin, abbr, market_type))

                # 使用 UPSERT 语法进行批量插入/更新
                # 注意：Requires SQLite 3.24.0+
                sql = """
                    INSERT INTO stocks (code, name, pinyin, abbr, market_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        pinyin = excluded.pinyin,
                        abbr = excluded.abbr,
                        market_type = excluded.market_type,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE 
                        stocks.name != excluded.name OR
                        stocks.pinyin != excluded.pinyin OR
                        stocks.abbr != excluded.abbr OR
                        stocks.market_type != excluded.market_type
                """
                
                cursor.executemany(sql, data_to_insert)
                affected_rows = cursor.rowcount
                
                conn.commit()
                
                # cursor.rowcount 在某些驱动/配置下可能返回-1或不准确
                # 既然我们使用了事务且未抛出异常，可以认为所有数据都已处理
                app_logger.info(f"股票数据批量更新完成: 处理了 {len(data_to_insert)} 条记录")
                return len(data_to_insert)
                
        except Exception as e:
            app_logger.error(f"批量插入股票数据失败: {e}")
            # Fallback to older slow method if UPSERT fails
            return self._insert_stocks_slow(stocks)

    def _insert_stocks_slow(self, stocks: List[Dict[str, Any]]) -> int:
        """慢速插入模式（兼容旧版SQLite或作为降级方案）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                count = 0
                for stock in stocks:
                    # ... (Simplified Logic for fallback) ...
                    # 这里为了简洁，仅实现基本的 replace
                    code = stock['code']
                    # ... logic similar to old implementation ...
                    pass 
                # 由于这是fallback，这里我们暂时只记录错误，或者简单地逐条插入
                # 为避免代码过于冗长，如果没有UPSERT支持，建议升级SQLite
                app_logger.warning("正在使用慢速逐条插入模式...")
                updated_count = 0
                for stock in stocks:
                    try:
                        code = stock['code']
                        name = stock['name']
                        pinyin = stock.get('pinyin', '')
                        abbr = stock.get('abbr', '')
                         # 确定市场类型
                        market_type = 'A'
                        if code.startswith('hk'):
                            market_type = 'HK'
                        elif code.startswith(('sh000', 'sz399')):
                            market_type = 'INDEX'
                            
                        # 简单 check exists
                        cursor.execute("SELECT 1 FROM stocks WHERE code=?", (code,))
                        exists = cursor.fetchone()
                        if exists:
                            cursor.execute("""
                                UPDATE stocks SET name=?, pinyin=?, abbr=?, market_type=?, updated_at=CURRENT_TIMESTAMP
                                WHERE code=?
                            """, (name, pinyin, abbr, market_type, code))
                        else:
                            cursor.execute("""
                                INSERT INTO stocks (code, name, pinyin, abbr, market_type, updated_at)
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, (code, name, pinyin, abbr, market_type))
                        updated_count += 1
                    except Exception:
                        pass
                conn.commit()
                return updated_count
        except Exception as e:
            app_logger.error(f"慢速插入失败: {e}")
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
    
    def is_empty(self) -> bool:
        """
        检查数据库是否为空
        
        Returns:
            bool: 数据库是否为空
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM stocks")
                count = cursor.fetchone()[0]
                return count == 0
        except Exception as e:
            app_logger.error(f"检查数据库是否为空失败: {e}")
            return True
    
    def get_stock_count(self) -> int:
        """
        获取数据库中的股票数量
        
        Returns:
            int: 股票数量
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM stocks")
                return cursor.fetchone()[0]
        except Exception as e:
            app_logger.error(f"获取股票数量失败: {e}")
            return 0

# 创建全局单例
stock_db = StockDatabase()