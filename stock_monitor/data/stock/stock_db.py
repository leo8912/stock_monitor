"""
股票数据库访问模块
提供对SQLite股票数据库的访问接口
"""

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from stock_monitor.config.manager import get_config_dir
from stock_monitor.utils.helpers import resource_path
from stock_monitor.utils.logger import app_logger

from .stock_data_source import StockDataSource

# 数据库文件路径
DB_FILE = "stocks.db"


def _escape_like_pattern(keyword: str) -> str:
    """
    转义SQL LIKE模式中的特殊字符

    Args:
        keyword: 用户输入的搜索关键词

    Returns:
        转义后的安全搜索模式
    """
    # 转义%, _, \ 这三个LIKE特殊字符
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class ConnectionPool:
    """SQLite 连接池（单例模式）

    归属原则（关键）：任一 ``sqlite3.Connection`` 在任一时刻只归属**创建它的线程**。
    全局结构 ``_all_conns`` 仅用于统计与统一关闭，**不再跨线程分发连接**。
    这样可避免同一连接被多个线程并发复用导致的事务交错 / 脏读问题。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConnectionPool":
        """单例构造：全局仅创建一个 ConnectionPool 实例。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化连接池状态（线程本地连接映射、全局登记与写锁）。"""
        if self._initialized:
            return

        # 线程本地存储：{db_path: sqlite3.Connection}，仅存本线程创建的连接
        self._local = threading.local()
        # 全局连接登记：{id(conn): conn}，仅用于统计与统一关闭
        self._all_conns: dict[int, sqlite3.Connection] = {}
        self._lock = threading.Lock()
        # 全局写锁：串行化所有写事务，避免多连接写交错
        self._write_lock = threading.RLock()
        self._stats = {"created": 0, "reused": 0, "closed": 0}
        self._initialized = True
        app_logger.info("数据库连接池初始化完成")

    def _get_thread_conns(self) -> dict[str, sqlite3.Connection]:
        """获取当前线程的连接映射（惰性创建）。"""
        conns = getattr(self._local, "conns", None)
        if conns is None:
            conns = {}
            self._local.conns = conns
        return conns

    def write_lock(self) -> threading.RLock:
        """返回全局写锁，供写事务串行化使用。"""
        return self._write_lock

    def get_connection(self, db_path: str) -> sqlite3.Connection:
        """获取当前线程在 ``db_path`` 上的连接。

        优先复用本线程已创建且仍有效的连接；否则**由本线程新建**连接，
        绝不从其它线程借还连接。
        """
        conns = self._get_thread_conns()
        conn = conns.get(db_path)
        if conn is not None and self._is_connection_valid(conn):
            with self._lock:
                self._stats["reused"] += 1
            return conn

        # 本线程新建连接并登记
        conn = self._create_connection(db_path)
        conns[db_path] = conn
        with self._lock:
            self._all_conns[id(conn)] = conn
            self._stats["created"] += 1
        return conn

    def return_connection(self, db_path: str, conn: sqlite3.Connection) -> None:
        """归还连接。

        若调用线程正是该连接的创建线程（连接仍在本线程映射中），则保留连接以供
        本线程复用；否则视为异常跨线程路径，关闭连接并从全局登记中移除。
        """
        conns = self._get_thread_conns()
        if conns.get(db_path) is conn and self._is_connection_valid(conn):
            # 连接留在创建它的线程，无需归还
            return

        # 非归属线程或连接已失效：关闭并注销
        conns.pop(db_path, None)
        try:
            conn.close()
        except Exception:
            # 退出/异常清理路径：关闭失败不阻塞，记录后继续
            app_logger.debug("关闭无效数据库连接失败", exc_info=True)
        with self._lock:
            self._all_conns.pop(id(conn), None)
            self._stats["closed"] += 1

    def _create_connection(self, db_path: str) -> sqlite3.Connection:
        """创建新连接并应用优化配置"""
        conn = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    def _is_connection_valid(self, conn: sqlite3.Connection) -> bool:
        """检查连接是否有效。

        ``sqlite3.Connection`` 没有 ``closed`` 属性，不能通过属性访问判断状态。
        用一次无副作用的查询确认连接仍可用；连接只会在创建它的线程中调用，
        因此不会引入跨线程访问问题。
        """
        try:
            conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def close_all(self) -> None:
        """关闭所有已登记连接，并重置线程本地存储。"""
        with self._lock:
            conns = list(self._all_conns.values())
            self._all_conns.clear()
            for conn in conns:
                try:
                    conn.close()
                    self._stats["closed"] += 1
                except Exception:
                    # 退出清理路径：单个连接关闭失败不阻塞其它连接关闭
                    app_logger.debug("关闭数据库连接失败", exc_info=True)
            # 重置线程本地存储，避免残留已关闭连接
            self._local = threading.local()

    def get_stats(self) -> dict:
        """获取连接池统计（active_pools/total_cached 基于全局登记连接数）。"""
        with self._lock:
            active = len(self._all_conns)
            return {
                **self._stats,
                "active_pools": active,
                "total_cached": active,
            }


_db_pool = None


def get_db_pool() -> ConnectionPool:
    """获取全局连接池单例"""
    global _db_pool
    if _db_pool is None:
        _db_pool = ConnectionPool()
    return _db_pool


class StockDatabase(StockDataSource):
    """股票数据库访问类"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "StockDatabase":
        """单例构造：全局仅创建一个 StockDatabase 实例。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化数据库连接"""
        with self._lock:
            if not hasattr(self, "_initialized"):
                # 使用配置目录存储数据库，确保数据持久化且可写
                config_dir = get_config_dir()
                self.db_path = os.path.join(config_dir, DB_FILE)

                self._initialized = True
                # 确保数据库文件和表结构存在
                self._initialize_database()

                # 智能检查：如果数据库为空，导入基础数据
                if self.is_empty():
                    app_logger.info("检测到空数据库，正在初始化...")
                    self._populate_base_data()

    def close(self) -> None:
        """关闭数据库连接池"""
        try:
            pool = get_db_pool()
            pool.close_all()
            app_logger.info("数据库连接池已关闭")
        except Exception as e:
            app_logger.warning(f"关闭数据库连接池失败: {e}")

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """获取数据库连接（上下文管理器，自动归还到连接池）。

        读路径：异常时回滚，避免脏事务随复用连接带到下一次调用。
        """
        pool = get_db_pool()
        conn = pool.get_connection(self.db_path)
        try:
            yield conn
        except Exception:
            # 读路径异常：回滚未提交的隐式事务，防止污染后续复用
            try:
                conn.rollback()
            except Exception:
                app_logger.debug("回滚读事务失败", exc_info=True)
            raise
        finally:
            pool.return_connection(self.db_path, conn)

    @contextmanager
    def _write_connection(self) -> Iterator[sqlite3.Connection]:
        """获取写数据库连接（上下文管理器）。

        在全局写锁内串行化写入，正常结束时提交，异常时回滚并向上抛出。
        """
        pool = get_db_pool()
        with pool.write_lock():
            conn = pool.get_connection(self.db_path)
            try:
                yield conn
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    app_logger.debug("回滚写事务失败", exc_info=True)
                raise
            finally:
                pool.return_connection(self.db_path, conn)

    def _initialize_database(self) -> None:
        """初始化数据库表结构"""
        try:
            with self._write_connection() as conn:
                cursor = conn.cursor()

                # 创建股票表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stocks (
                        code TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        pinyin TEXT,
                        abbr TEXT,
                        market_type TEXT,  -- 'A' for A股, 'INDEX' for 指数, 'HK' for 港股
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON stocks(name)")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_market_type ON stocks(market_type)"
                )

                # 创建量化预警日志表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS quant_alerts_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        name TEXT,
                        signal_type TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        status TEXT NOT NULL, -- 'START', 'CONTINUE', 'END'
                        price REAL,
                        win_rate REAL
                    )
                """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_qlog_symbol ON quant_alerts_log(symbol)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_qlog_time ON quant_alerts_log(timestamp)"
                )

                # 创建波浪预测历史表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wave_predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        prediction_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        wave TEXT NOT NULL,  -- '1', '2', '3', '4', '5', 'A', 'B', 'C'
                        trend TEXT NOT NULL,  -- 'bullish', 'bearish'
                        confidence REAL,
                        price_at_prediction REAL,  -- 预测时的价格
                        target_price REAL,  -- 目标价格
                        timeframe TEXT,  -- '15m', '30m', '60m', 'daily'
                        is_verified BOOLEAN DEFAULT FALSE,  -- 是否已验证
                        verification_time DATETIME,
                        actual_outcome TEXT,  -- 'correct', 'wrong', 'partial'
                        profit_loss_pct REAL,  -- 盈亏百分比
                        notes TEXT
                    )
                """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_wp_symbol ON wave_predictions(symbol)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_wp_time ON wave_predictions(prediction_time)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_wp_verified ON wave_predictions(is_verified)"
                )

                # PRAGMA 优化已统一在 _get_connection 中配置

                app_logger.info("股票数据库初始化完成")
        except Exception as e:
            app_logger.error(f"初始化股票数据库失败: {e}")
            raise

    def _populate_base_data(self) -> None:
        """填充基础数据"""
        base_db = resource_path("stocks_base.db")
        if os.path.exists(base_db):
            app_logger.info("正在导入基础股票数据...")
            try:
                self._import_from_base_db(base_db)
                app_logger.info("基础数据导入成功")
            except Exception as e:
                app_logger.error(f"导入基础数据失败: {e}")
                # 失败后触发后台更新
                self._trigger_background_update()
        else:
            app_logger.warning("未找到基础数据库文件，将在后台更新")
            self._trigger_background_update()

    def _import_from_base_db(self, base_db_path: str) -> None:
        """从基础数据库导入数据"""
        base_conn = None
        try:
            # 连接基础数据库
            base_conn = sqlite3.connect(base_db_path)
            base_cursor = base_conn.cursor()

            # 读取所有股票数据
            base_cursor.execute(
                "SELECT code, name, pinyin, abbr, market_type, updated_at FROM stocks"
            )
            stocks = base_cursor.fetchall()

            if not stocks:
                app_logger.warning("基础数据库为空")
                return

            # 批量插入到当前数据库
            with self._write_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO stocks
                    (code, name, pinyin, abbr, market_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    stocks,
                )

            app_logger.info(f"成功导入 {len(stocks)} 只股票数据")
        except Exception as e:
            app_logger.error(f"导入基础数据时出错: {e}")
            raise
        finally:
            if base_conn is not None:
                try:
                    base_conn.close()
                except Exception:
                    pass

    def _trigger_background_update(self) -> None:
        """触发后台数据库更新"""
        try:
            # 导入并触发更新（避免循环导入）
            from PyQt6.QtCore import QThreadPool

            from stock_monitor.data.stock.stock_updater import update_stock_database
            from stock_monitor.utils.worker import WorkerRunnable

            def update_task() -> None:
                """在 Qt 线程池中执行的实际更新任务。"""
                app_logger.info("开始后台更新股票数据库...")
                update_stock_database()

            # 在 Qt 全局线程池中执行后台更新
            worker = WorkerRunnable(update_task)
            QThreadPool.globalInstance().start(worker)
        except Exception as e:
            app_logger.error(f"触发后台更新失败: {e}")

    def insert_stocks(self, stocks: list[dict[str, Any]]) -> int:
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
            with self._write_connection() as conn:
                cursor = conn.cursor()

                # 准备数据（G-7: 上游字段缺失时跳过该条，不因 KeyError 中断整批入库）
                data_to_insert = []
                skipped = 0
                for stock in stocks:
                    code = stock.get("code")
                    name = stock.get("name")
                    if not code or not name:
                        skipped += 1
                        app_logger.warning(
                            f"跳过字段缺失的股票记录: code={code!r} name={name!r}"
                        )
                        continue
                    pinyin = stock.get("pinyin", "")
                    abbr = stock.get("abbr", "")

                    # 确定市场类型
                    market_type = "A"
                    if code.startswith("hk"):
                        market_type = "HK"
                    elif code.startswith(("sh000", "sz399")):
                        market_type = "INDEX"

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

                # cursor.rowcount 在某些驱动/配置下可能返回-1或不准确
                # 既然我们使用了事务且未抛出异常，可以认为所有数据都已处理
                app_logger.info(
                    f"股票数据批量更新完成: 处理了 {len(data_to_insert)} 条记录，"
                    f"跳过 {skipped} 条"
                )
                return len(data_to_insert)

        except Exception as e:
            app_logger.error(f"批量插入股票数据失败: {e}")
            # Fallback to older slow method if UPSERT fails
            return self._insert_stocks_slow(stocks)

    def _insert_stocks_slow(self, stocks: list[dict[str, Any]]) -> int:
        """慢速插入模式（兼容旧版SQLite或作为降级方案）"""
        try:
            with self._write_connection() as conn:
                cursor = conn.cursor()
                app_logger.warning("正在使用慢速逐条插入模式...")
                updated_count = 0
                for stock in stocks:
                    try:
                        code = stock.get("code")
                        name = stock.get("name")
                        if not code or not name:
                            app_logger.warning(
                                "慢速模式：跳过字段缺失的股票记录 "
                                f"code={code!r} name={name!r}"
                            )
                            continue
                        pinyin = stock.get("pinyin", "")
                        abbr = stock.get("abbr", "")
                        # 确定市场类型
                        market_type = "A"
                        if code.startswith("hk"):
                            market_type = "HK"
                        elif code.startswith(("sh000", "sz399")):
                            market_type = "INDEX"

                        # 使用INSERT OR REPLACE避免N+1查询
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO stocks (code, name, pinyin, abbr, market_type, updated_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                            (code, name, pinyin, abbr, market_type),
                        )
                        updated_count += 1
                    except Exception as e:
                        app_logger.error(
                            f"慢速模式：单条写入股票 {stock.get('code', '未知')} 失败: {e}"
                        )
                return updated_count
        except Exception as e:
            app_logger.error(f"慢速插入失败: {e}")
            return 0

    def get_stock_by_code(self, code: str) -> dict[str, Any] | None:
        """
        根据股票代码获取股票信息

        Args:
            code: 股票代码

        Returns:
            Optional[Dict[str, Any]]: 股票信息，未找到返回None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT code, name, pinyin, abbr FROM stocks WHERE code = ?",
                    (code,),
                )
                row = cursor.fetchone()

                if row:
                    return {
                        "code": row[0],
                        "name": row[1],
                        "pinyin": row[2],
                        "abbr": row[3],
                    }
                return None
        except Exception as e:
            app_logger.error(f"查询股票 {code} 失败: {e}")
            return None

    def search_stocks(self, keyword: str, limit: int = 30) -> list[dict[str, Any]]:
        """
        搜索股票

        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            List[Dict[str, Any]]: 匹配的股票列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 构建搜索查询（转义特殊字符防止LIKE注入）
                search_pattern = _escape_like_pattern(keyword)
                cursor.execute(
                    """
                    SELECT code, name, pinyin, abbr
                    FROM stocks
                    WHERE code = ? OR name LIKE ? ESCAPE '\\' OR pinyin LIKE ? ESCAPE '\\' OR abbr LIKE ? ESCAPE '\\'
                    ORDER BY
                        CASE
                            WHEN code = ? THEN 1
                            WHEN name LIKE ? ESCAPE '\\' THEN 2
                            WHEN pinyin LIKE ? ESCAPE '\\' THEN 3
                            WHEN abbr LIKE ? ESCAPE '\\' THEN 4
                            ELSE 5
                        END,
                        code
                    LIMIT ?
                """,
                    (
                        keyword,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        keyword,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        limit,
                    ),
                )

                rows = cursor.fetchall()
                return [
                    {"code": row[0], "name": row[1], "pinyin": row[2], "abbr": row[3]}
                    for row in rows
                ]
        except Exception as e:
            app_logger.error(f"搜索股票失败: {e}")
            return []

    def get_stocks_by_market_type(self, market_type: str) -> list[dict[str, Any]]:
        """
        根据市场类型获取股票列表

        Args:
            market_type: 市场类型 ('A', 'INDEX', 'HK')

        Returns:
            List[Dict[str, Any]]: 股票列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT code, name, pinyin, abbr FROM stocks WHERE market_type = ?",
                    (market_type,),
                )
                rows = cursor.fetchall()
                return [
                    {"code": row[0], "name": row[1], "pinyin": row[2], "abbr": row[3]}
                    for row in rows
                ]
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
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM stocks")
                return cursor.fetchone()[0]
        except Exception as e:
            app_logger.error(f"获取股票总数失败: {e}")
            return 0

    def get_all_stocks(self) -> list[dict[str, Any]]:
        """
        获取所有股票数据

        Returns:
            List[Dict[str, Any]]: 所有股票数据
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT code, name, pinyin, abbr FROM stocks ORDER BY code"
                )
                rows = cursor.fetchall()
                return [
                    {"code": row[0], "name": row[1], "pinyin": row[2], "abbr": row[3]}
                    for row in rows
                ]
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
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM stocks")
                count = cursor.fetchone()[0]
                return count == 0
        except Exception as e:
            app_logger.error(f"检查数据库是否为空失败: {e}")
            return True
