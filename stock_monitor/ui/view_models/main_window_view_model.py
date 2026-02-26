from PyQt6.QtCore import QObject, pyqtSignal

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.container import container
from stock_monitor.core.stock_manager import StockManager
from stock_monitor.core.workers import MarketStatsWorker, RefreshWorker
from stock_monitor.data.stock.stock_db import StockDatabase
from stock_monitor.data.stock.stocks import load_stock_data
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.stock_utils import StockCodeProcessor


class MainWindowViewModel(QObject):
    """
    ViewModel for MainWindow
    Handles business logic and data state
    """

    # Signals
    stock_data_loaded = pyqtSignal(list)
    stock_data_updated = pyqtSignal(list, bool)
    market_stats_updated = pyqtSignal(int, int, int, int)
    refresh_error_occurred = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._container = container
        self._stock_db = self._container.get(StockDatabase)
        self._config_manager = self._container.get(ConfigManager)
        self._stock_manager = self._container.get(StockManager)

        # Initialize Workers
        self._refresh_worker = RefreshWorker()
        self._market_stats_worker = MarketStatsWorker()

        # Connect Worker Signals
        self._refresh_worker.data_updated.connect(self._on_data_updated)
        self._refresh_worker.refresh_error.connect(self.refresh_error_occurred.emit)
        self._market_stats_worker.stats_updated.connect(self.market_stats_updated.emit)

        self._stocks = []
        self._latest_stock_data = []

    def _on_data_updated(self, stocks, all_failed):
        """Intercept local data updates to cache the latest data"""
        if not all_failed:
            self._latest_stock_data = stocks
        self.stock_data_updated.emit(stocks, all_failed)

    def get_latest_stock_data(self) -> list:
        """Get the most recently fetched/cached stock data"""
        return self._latest_stock_data

    def set_latest_stock_data(self, data: list):
        """Manually set the latest stock data, e.g. from session cache"""
        self._latest_stock_data = data

    def load_stock_data(self):
        """Load stock data from database"""
        try:
            stocks = load_stock_data()
            self._stocks = stocks
            self.stock_data_loaded.emit(stocks)
            return stocks
        except Exception as e:
            msg = f"Failed to load stock data: {e}"
            app_logger.error(msg)
            self.error_occurred.emit(msg)
            return []

    def get_stock_count(self) -> int:
        """Get total number of stocks"""
        return self._stock_db.get_all_stocks_count()

    def is_database_empty(self) -> bool:
        """Check if database is empty"""
        return self._stock_db.get_all_stocks_count() == 0

    def load_user_stocks(self) -> list[str]:
        """Load user selected stocks"""
        try:
            stocks = self._config_manager.get("user_stocks", [])

            # Early return if empty
            if not stocks:
                app_logger.info("User stock list is empty")
                return []

            # Clean stored data
            processor = StockCodeProcessor()
            cleaned_stocks = []
            has_changes = False

            for stock in stocks:
                cleaned = processor.clean_code(stock)
                cleaned_stocks.append(cleaned)

                if cleaned != stock:
                    has_changes = True

            # Save cleaned data if changes detected
            if has_changes:
                app_logger.warning(
                    f"Dirty data detected in user stock list, auto-repaired: {stocks} -> {cleaned_stocks}"
                )
                self._config_manager.set("user_stocks", cleaned_stocks)

            app_logger.info(f"Loaded user stock list: {cleaned_stocks}")
            return cleaned_stocks

        except Exception as e:
            app_logger.error(f"Failed to load user stock list: {e}")
            return []

    def get_stock_list_data(self, stock_codes: list[str]) -> list[tuple]:
        """Get formatted stock data for display"""
        return self._stock_manager.get_stock_list_data(stock_codes)

    def start_workers(self, user_stocks: list[str], refresh_interval: int):
        """Start background workers"""
        self._refresh_worker.start_refresh(user_stocks, refresh_interval)
        self._market_stats_worker.start_worker()

    def stop_workers(self):
        """Stop background workers"""
        if self._refresh_worker.isRunning():
            self._refresh_worker.stop_refresh()
        if self._market_stats_worker.isRunning():
            self._market_stats_worker.stop_worker()

    def update_workers_config(
        self, user_stocks: list[str] = None, refresh_interval: int = None
    ):
        """Update worker configuration on the fly"""
        if user_stocks is not None:
            self._refresh_worker.update_stocks(user_stocks)
        if refresh_interval is not None:
            self._refresh_worker.update_interval(refresh_interval)

    def load_session(self) -> dict:
        """Load session cache"""
        try:
            from stock_monitor.utils.session_cache import load_session_cache

            return load_session_cache()
        except Exception as e:
            app_logger.warning(f"Failed to load session cache: {e}")
            return {}

    def save_session(self, position: list[int], stock_data: list):
        """Save session cache"""
        try:
            from stock_monitor.utils.session_cache import save_session_cache

            session_data = {
                "window_position": position,
                "stock_data": stock_data,
            }
            save_session_cache(session_data)
        except Exception as e:
            app_logger.warning(f"Failed to save session cache: {e}")

    def check_and_update_database(self):
        """检查并更新数据库（异步）"""
        try:
            import time

            from PyQt6.QtCore import QThreadPool

            from stock_monitor.data.market.db_updater import update_stock_database
            from stock_monitor.utils.worker import WorkerRunnable

            last_update = self._config_manager.get("last_db_update", 0)
            current_time = time.time()

            should_update = False
            if current_time - last_update > 86400 or last_update == 0:
                should_update = True
            elif self.is_database_empty():
                app_logger.warning("检测到股票数据库为空，强制启动更新")
                should_update = True

            if should_update:
                worker = WorkerRunnable(update_stock_database)
                QThreadPool.globalInstance().start(worker)
                app_logger.info("启动时数据库更新已启动")

                # 假设更新成功并不在这里记录，由 db_updater 自己控制，
                # 但旧代码是在这里或者_update_database_if_needed里写 set()，
                # 我们这里简单的标记一下请求更新的时间
                self._config_manager.set("last_db_update", current_time)
        except Exception as e:
            app_logger.error(f"启动时数据库更新检查失败: {e}")
