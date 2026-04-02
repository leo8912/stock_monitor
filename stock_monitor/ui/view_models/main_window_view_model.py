from PyQt6.QtCore import QObject, pyqtSignal

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.container import container
from stock_monitor.core.stock_data_fetcher import StockDataFetcher
from stock_monitor.core.stock_manager import StockManager
from stock_monitor.core.workers import MarketStatsWorker, QuantWorker, RefreshWorker
from stock_monitor.data.stock.stock_db import StockDatabase
from stock_monitor.data.stock.stocks import load_stock_data
from stock_monitor.utils.config_helper import ConfigHelper, ConfigKeys
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
    market_stats_updated = pyqtSignal(int, int, int, float)
    refresh_error_occurred = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._container = container
        self._stock_db = self._container.get(StockDatabase)
        config_manager = self._container.get(ConfigManager)
        self._config_helper = ConfigHelper(config_manager)
        self._stock_manager = self._container.get(StockManager)
        self._fetcher = self._container.get(StockDataFetcher)

        # Initialize Workers
        self._refresh_worker = RefreshWorker()
        self._market_stats_worker = MarketStatsWorker()

        wecom_webhook = self._config_helper.get_str(ConfigKeys.WECOM_WEBHOOK, "")
        self._quant_worker = QuantWorker(self._fetcher, wecom_webhook)

        # 注册到容器中，方便 SettingsViewModel 获取
        self._container.register_singleton(QuantWorker, self._quant_worker)

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
            stocks = self._config_helper.get_list(ConfigKeys.USER_STOCKS, [])

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

        # Start quant worker if enabled
        quant_enabled = self._config_helper.get_bool(ConfigKeys.QUANT_ENABLED, False)
        webhook = self._config_helper.get_str(ConfigKeys.WECOM_WEBHOOK, "")
        self._quant_worker.wecom_webhook = webhook
        self._quant_worker.set_symbols(user_stocks)

        if quant_enabled:
            self._quant_worker.start_worker()
        else:
            self._quant_worker.stop_worker()

    def request_immediate_refresh(self, user_stocks: list[str] = None):
        """
        请求立即刷新行情（异步）

        Args:
            user_stocks: 可选，更新要刷新的股票列表
        """
        if user_stocks is not None:
            self._refresh_worker.update_stocks(user_stocks)

        if not self._refresh_worker.isRunning():
            # 确保线程已启动
            config = self._config_manager.get_all()
            self._refresh_worker.start_refresh(
                user_stocks or config.get("user_stocks", []),
                config.get("refresh_interval", 5),
            )
        else:
            self._refresh_worker.trigger_now()

    def stop_workers(self):
        """Stop background workers"""
        if self._refresh_worker.isRunning():
            self._refresh_worker.stop_refresh()
        if self._market_stats_worker.isRunning():
            self._market_stats_worker.stop_worker()
        if self._quant_worker.isRunning():
            self._quant_worker.stop_worker()

    def update_workers_config(
        self, user_stocks: list[str] = None, refresh_interval: int = None
    ):
        """Update worker configuration on the fly"""
        if user_stocks is not None:
            self._refresh_worker.update_stocks(user_stocks)
            self._quant_worker.set_symbols(user_stocks)
        if refresh_interval is not None:
            self._refresh_worker.update_interval(refresh_interval)

        quant_enabled = self._config_helper.get_bool(ConfigKeys.QUANT_ENABLED, False)
        webhook = self._config_helper.get_str(ConfigKeys.WECOM_WEBHOOK, "")
        self._quant_worker.wecom_webhook = webhook

        if quant_enabled:
            if not self._quant_worker.isRunning():
                self._quant_worker.start_worker()
        else:
            if self._quant_worker.isRunning():
                self._quant_worker.stop_worker()

    def load_session(self) -> dict:
        """Load session cache"""
        try:
            from stock_monitor.models.stock_data import StockRowData
            from stock_monitor.utils.session_cache import load_session_cache

            cache = load_session_cache()
            if cache and "stock_data" in cache:
                deserialized = []
                for item in cache["stock_data"]:
                    if isinstance(item, dict):
                        # Fix for compatibility when fields are missing
                        valid_keys = StockRowData.__dataclass_fields__.keys()
                        safe_item = {k: v for k, v in item.items() if k in valid_keys}
                        deserialized.append(StockRowData(**safe_item))
                    else:
                        deserialized.append(item)
                cache["stock_data"] = deserialized
            return cache or {}
        except Exception as e:
            app_logger.warning(f"Failed to load session cache: {e}")
            return {}

    def save_session(self, position: list[int], stock_data: list):
        """Save session cache"""
        try:
            import dataclasses

            from stock_monitor.utils.session_cache import save_session_cache

            serialized_stock_data = [
                dataclasses.asdict(item) if dataclasses.is_dataclass(item) else item
                for item in stock_data
            ]

            session_data = {
                "window_position": position,
                "stock_data": serialized_stock_data,
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

    def trigger_manual_report(self):
        """立即触发手动汇总复盘报告"""
        if self._quant_worker:
            app_logger.info("触发手动复盘报告生成...")
            self._quant_worker.generate_daily_summary_report("manual")
