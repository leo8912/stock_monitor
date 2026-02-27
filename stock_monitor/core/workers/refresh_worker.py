import time

from PyQt6 import QtCore

from stock_monitor.core.market_manager import MarketManager
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.stock_utils import StockCodeProcessor


class RefreshWorker(QtCore.QThread):
    """
    后台刷新工作线程

    负责在后台定期获取股票数据并更新UI。
    使用独立线程避免阻塞主UI线程。

    Signals:
        data_updated: 数据更新信号，参数为(股票列表, 是否全部失败)
        refresh_error: 刷新错误信号，连续失败时触发

    Attributes:
        refresh_interval: 刷新间隔（秒）
        current_user_stocks: 当前用户自选股列表
    """

    # 定义信号
    data_updated = QtCore.pyqtSignal(list, bool)  # 数据列表, 是否全部失败
    refresh_error = QtCore.pyqtSignal()

    def __init__(self):
        """初始化刷新工作线程"""
        super().__init__()
        self._is_running = False
        self.refresh_interval = 5
        self.current_user_stocks: list[str] = []
        self._lock = QtCore.QMutex()  # 使用Qt互斥锁
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._max_startup_retries = 10  # 开机启动时首次获取数据的最大重试次数
        self._processor = StockCodeProcessor()
        # self._data_change_detector = DataChangeDetector() # 使用StockManager的检测器
        self._last_successful_update = 0
        self._closing_data_fetched = False  # 当日收盘数据是否已获取
        self._closing_data_date = None  # 记录获取收盘数据的日期，用于次日重置

    def start_refresh(self, user_stocks: list[str], refresh_interval: int):
        """
        启动刷新

        Args:
            user_stocks: 用户股票列表
            refresh_interval: 刷新间隔（秒）
        """
        self._lock.lock()
        self.current_user_stocks = user_stocks
        self.refresh_interval = refresh_interval
        self._lock.unlock()

        if not self.isRunning():
            self._is_running = True
            self.start()

        app_logger.info("后台刷新线程已启动")
        app_logger.debug(f"刷新间隔: {self.refresh_interval}秒")

    def stop_refresh(self):
        """停止刷新线程"""
        self._is_running = False
        self.wait(2000)  # 等待线程结束
        app_logger.info("后台刷新线程已停止")

    def update_stocks(self, user_stocks: list[str]):
        """更新用户股票列表"""
        self._lock.lock()
        self.current_user_stocks = user_stocks
        self._lock.unlock()
        app_logger.info(f"刷新线程股票列表已更新: {user_stocks}")

    def update_interval(self, refresh_interval: int):
        """更新刷新间隔"""
        self._lock.lock()
        self.refresh_interval = refresh_interval
        self._lock.unlock()
        app_logger.info(f"刷新线程间隔已更新: {refresh_interval}")

    def run(self):
        """线程执行入口"""
        # 快速预热，首次数据获取时自然完成初始化
        app_logger.info("后台刷新线程启动...")
        self.msleep(200)

        if not self._is_running:
            return

        # 首次启动标记：无论是否开市，都先获取一次数据
        first_fetch_done = False
        startup_retry_count = 0  # 首次获取重试计数

        while self._is_running:
            try:
                # 获取当前配置
                self._lock.lock()
                local_user_stocks = self.current_user_stocks[:]
                local_refresh_interval = self.refresh_interval
                self._lock.unlock()

                # 检查是否需要等待下次刷新（无股票时）
                if not local_user_stocks:
                    app_logger.debug("没有自选股，休眠等待...")
                    self._smart_sleep(5)
                    continue

                # 检查市场状态（首次启动跳过此检查，确保至少获取一次数据）
                market_open = MarketManager.is_market_open()

                # 每日重置收盘数据获取标记
                import datetime

                today = datetime.date.today()
                if self._closing_data_date != today:
                    self._closing_data_fetched = False
                    self._closing_data_date = today

                # 如果市场关闭且不是首次启动，则尝试获取收盘数据或休眠等待
                if not market_open and first_fetch_done:
                    # 休市后尝试获取一次收盘数据
                    if not self._closing_data_fetched:
                        app_logger.info("市场已关闭，尝试获取收盘数据...")
                        self._fetch_closing_data(local_user_stocks)
                    sleep_duration = self._get_pre_market_sleep_time()
                    if sleep_duration < 60:
                        app_logger.debug(f"临近开市，缩短休眠至{sleep_duration}秒")
                    else:
                        app_logger.debug("市场已关闭，休眠等待开市...")
                    self._smart_sleep(sleep_duration, check_interval=True)
                    continue

                # 获取数据
                # app_logger.debug(f"开始刷新 {len(local_user_stocks)} 只股票数据")

                # 使用 stock_manager 获取和处理数据
                from stock_monitor.core.stock_manager import stock_manager

                stocks, failed_count = stock_manager.fetch_and_process_stocks(
                    local_user_stocks
                )

                # 检查变化并更新
                force_update = not hasattr(self, "_initial_update_done")
                # 使用 stock_manager 进行变更检测
                if force_update or stock_manager.has_stock_data_changed(stocks):
                    stock_manager.update_last_stock_data(stocks)
                    if not hasattr(self, "_initial_update_done"):
                        self._initial_update_done = True
                        app_logger.info("首次数据更新完成")

                    # 发送信号
                    self.data_updated.emit(
                        stocks,
                        failed_count == len(local_user_stocks)
                        and len(local_user_stocks) > 0,
                    )
                    self._last_successful_update = time.time()

                self._consecutive_failures = 0

                # 标记首次获取已完成（仅当成功获取到数据时）
                # 如果全部失败，不标记完成，继续重试获取数据
                if not first_fetch_done:
                    # 检查是否全部获取失败
                    all_failed = (
                        failed_count == len(local_user_stocks)
                        and len(local_user_stocks) > 0
                    )

                    if all_failed:
                        startup_retry_count += 1

                        if startup_retry_count < self._max_startup_retries:
                            # 全部失败时，不标记完成，短暂休眠后重试
                            # 这通常发生在开机启动时网络尚未就绪
                            app_logger.warning(
                                f"首次行情获取失败（共{failed_count}只股票），"
                                f"第{startup_retry_count}/{self._max_startup_retries}次重试..."
                            )
                            self._smart_sleep(5)
                            continue  # 跳过后续休眠，立即重试
                        else:
                            # 达到最大重试次数，放弃重试
                            app_logger.error(
                                f"首次行情获取失败，已达最大重试次数({self._max_startup_retries})，"
                                "放弃重试，将等待下次刷新周期"
                            )
                            first_fetch_done = True
                    else:
                        first_fetch_done = True
                        app_logger.info(
                            "首次行情获取完成，后续将根据市场状态决定是否刷新"
                        )

                # 休眠
                sleep_time = local_refresh_interval
                if sleep_time < 1:
                    sleep_time = 1

                self._smart_sleep(sleep_time, check_interval=True)

            except Exception as e:
                app_logger.error(f"行情刷新异常: {e}")
                self._consecutive_failures += 1

                if self._consecutive_failures >= self._max_consecutive_failures:
                    self.refresh_error.emit()
                    self._consecutive_failures = 0

                self.sleep(5)

    def _smart_sleep(self, duration, check_interval=False):
        """
        智能休眠，支持快速响应停止信号和配置变更

        Args:
            duration: 休眠时长(秒)
            check_interval: 是否检查刷新间隔变更
        """
        # 将时长转换为0.5秒的时间片
        steps = int(duration * 2)
        if steps < 1:
            steps = 1

        current_interval = self.refresh_interval

        for _ in range(steps):
            if not self._is_running:
                return

            # 如果需要检查配置变更
            if check_interval:
                self._lock.lock()
                new_interval = self.refresh_interval
                self._lock.unlock()

                # 如果刷新间隔变小了，立即结束休眠以应用新配置
                # 如果变大了，当前循环结束后下一次自然会应用
                if new_interval < current_interval:
                    # app_logger.info(f"检测到刷新间隔变短 ({current_interval}->{new_interval})，立即唤醒")
                    return
                # 更新当前参考间隔
                current_interval = new_interval

            self.msleep(500)

    def _get_pre_market_sleep_time(self):
        """
        获取盘前休眠时间

        临近开市时缩短休眠时间，确保能快速响应开盘

        Returns:
            int: 休眠时间（秒）
        """
        import datetime

        now = datetime.datetime.now()
        t = now.time()

        # 周末直接返回长休眠
        if now.weekday() >= 5:
            return 60

        # 9:10-9:15 临近上午开市（9:15开始获取行情）
        if datetime.time(9, 10) <= t < datetime.time(9, 15):
            return 5

        # 12:55-13:00 临近下午开市
        if datetime.time(12, 55) <= t < datetime.time(13, 0):
            return 5

        # 其他时间使用正常休眠时间
        return 60

    def _fetch_closing_data(self, user_stocks: list[str]):
        """
        休市后尝试获取一次收盘数据

        如果数据源仍能返回有效数据，则用最新数据覆盖本地数据，
        确保收盘价被正确记录。获取成功后标记已完成，不再重复获取。

        Args:
            user_stocks: 用户股票列表
        """
        try:
            from stock_monitor.core.stock_manager import stock_manager

            stocks, failed_count = stock_manager.fetch_and_process_stocks(user_stocks)

            # 判断是否获取到了有效数据
            all_failed = failed_count == len(user_stocks) and len(user_stocks) > 0

            if not all_failed and stocks:
                # 有有效数据，用最新数据覆盖本地
                stock_manager.update_last_stock_data(stocks)
                self.data_updated.emit(stocks, False)
                self._closing_data_fetched = True
                app_logger.info(
                    f"收盘数据获取完成，已更新 {len(stocks)} 只股票的收盘行情"
                )
            else:
                # 获取失败，也标记为已完成，避免反复尝试
                self._closing_data_fetched = True
                app_logger.warning("收盘数据获取失败，无有效数据返回")

        except Exception as e:
            # 异常时也标记为已完成，不影响后续闭市休眠
            self._closing_data_fetched = True
            app_logger.error(f"收盘数据获取异常: {e}")
