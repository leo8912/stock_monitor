import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import (
    pyqtSignal,
)

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.container import container
from stock_monitor.models.stock_data import StockRowData

# Workers are now managed by ViewModel
from stock_monitor.ui.components.stock_table import StockTable
from stock_monitor.ui.constants import COLORS
from stock_monitor.ui.dialogs.settings_dialog import NewSettingsDialog
from stock_monitor.ui.mixins.draggable_window import DraggableWindowMixin

# Removed obsolete styles import
from stock_monitor.ui.view_models.main_window_view_model import MainWindowViewModel
from stock_monitor.ui.widgets.context_menu import AppContextMenu
from stock_monitor.ui.widgets.market_status import MarketStatusBar
from stock_monitor.utils.config_helper import ConfigHelper, ConfigKeys
from stock_monitor.utils.helpers import resource_path
from stock_monitor.utils.log_cleaner import schedule_log_cleanup
from stock_monitor.utils.logger import app_logger

# 定义常量
ICON_FILE = resource_path("icon.ico")
MIN_BACKGROUND_ALPHA = 128  # 透明度0时的alpha值(半透明,相当于原来50%的透明度)
MAX_BACKGROUND_ALPHA = 255  # 透明度100时的alpha值(完全不透明)
ALPHA_RANGE = MAX_BACKGROUND_ALPHA - MIN_BACKGROUND_ALPHA


class MainWindow(QtWidgets.QWidget, DraggableWindowMixin):
    """
    主窗口类
    负责显示股票行情、处理用户交互和管理应用状态
    """

    update_table_signal = pyqtSignal(list)
    # 添加用于跨线程更新UI的信号
    refresh_data_signal = pyqtSignal(list, bool)
    refresh_error_signal = pyqtSignal()

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        DraggableWindowMixin.__init__(self)
        # 初始化依赖注入容器
        self._container = container
        # 初始化ViewModel
        self.viewModel = MainWindowViewModel()

        self.setup_ui()
        # 尝试加载会话缓存
        if not self._try_load_session_cache():
            # 如果没有加载到缓存，确保窗口最终会显示
            pass

        # 连接 ViewModel 信号
        self.viewModel.market_stats_updated.connect(
            self.market_status_bar.update_status
        )
        self.viewModel.stock_data_updated.connect(self._handle_refresh_data)
        self.viewModel.refresh_error_occurred.connect(self._handle_refresh_error)

        # 初始化加载超时计时器 (10s 收敛)
        self._loading_timer = QtCore.QTimer(self)
        self._loading_timer.setSingleShot(True)
        self._loading_timer.timeout.connect(self._on_loading_timeout)

        # UI 更新节流计时器（合并连续的重绘请求）
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)  # 50ms 节流窗口
        self._update_timer.timeout.connect(self._do_update)
        self._pending_update = False

        # 启动 Workers (在 UI 设置完成后)
        # 这里的 start_workers 会在 setup_refresh_worker 中被调用，或者我们可以在这里调用
        # 但考虑到 setup_refresh_worker 可能会用到 config，我们稍后在 setup_refresh_worker 中统一启动

    def quit_application(self):
        """退出应用程序"""
        try:
            # 1. 保存会话缓存 (包含位置和数据)
            try:
                self.viewModel.save_session(
                    [self.x(), self.y()], self.viewModel.get_latest_stock_data()
                )
            except Exception as e:
                app_logger.warning(f"保存会话缓存失败: {e}")
                # Fallback to simple position save if cache fails
                self.save_position()

            # 2. 隐藏界面
            self.hide()
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.hide()

            # 3. 停止所有工作线程
            self.viewModel.stop_workers()

            # 4. 清理快捷键
            if hasattr(self, "shortcuts"):
                for shortcut in self.shortcuts:
                    shortcut.setEnabled(False)
                    shortcut.setParent(None)

            # 5. 优雅退出应用
            # 使用 QApplication.quit() 替代 os._exit(0)，允许 Qt 清理资源
            QtWidgets.QApplication.instance().quit()
        except Exception as e:
            app_logger.error(f"退出程序时出错: {e}")
            import os

            os._exit(1)

    def setup_ui(self):
        """设置主窗口UI"""
        self._setup_window_properties()
        self._setup_ui_components()
        self._setup_event_handlers()

        # 初始化数据缓存，用于即时重排交互
        self._last_data = []

    def _setup_window_properties(self):
        """设置窗口属性"""
        self.setWindowTitle("A股行情监控")
        self.setup_draggable_window()
        self.resize(320, 160)

        # Ensure we always have an arrow cursor initially
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

        # 设置窗口图标
        if os.path.exists(ICON_FILE):
            self.setWindowIcon(QtGui.QIcon(ICON_FILE))

        app_logger.info("主窗口初始化开始")
        app_logger.debug(f"当前工作目录: {os.getcwd()}")

        # 启动日志定期清理任务
        schedule_log_cleanup(days_to_keep=7, interval_hours=24)

    def _setup_ui_components(self):
        """初始化UI组件"""
        # 初始化股市状态条，初始隐藏
        self.market_status_bar = MarketStatusBar(self)
        self.market_status_bar.hide()

        # 初始化UI，初始隐藏
        self.table = StockTable(self)
        self.table.hide()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 移除边距，使表格紧贴窗口边缘
        layout.setSpacing(0)
        layout.addWidget(self.market_status_bar)  # 添加状态条
        layout.addWidget(self.table)

        self.setLayout(layout)

        # 设置样式
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )  # type: ignore

        # 初始化透明度缓存，避免 paintEvent 高频读取配置
        config_manager = self._container.get(ConfigManager)
        self._config_helper = ConfigHelper(config_manager)
        self._transparency = self._config_helper.get_int(ConfigKeys.TRANSPARENCY, 80)

        # 从配置中读取字体大小和字体族并更新表格
        self.update_font_size()

        # 初始化菜单
        # 创建右键菜单，使用独立的菜单类确保样式不会被其他界面影响
        self.menu = AppContextMenu(self)
        self.action_settings = self.menu.addAction("设置")
        self.menu.addSeparator()
        self.action_quit = self.menu.addAction("退出")
        if self.action_settings is not None:
            self.action_settings.triggered.connect(self.open_settings)
        if self.action_quit is not None:
            self.action_quit.triggered.connect(self.quit_application)

        # 确保菜单项连接正确，避免功能不稳定
        if self.action_settings is not None:
            self.action_settings.setMenuRole(
                QtGui.QAction.MenuRole.ApplicationSpecificRole
            )
        if self.action_quit is not None:
            self.action_quit.setMenuRole(QtGui.QAction.MenuRole.ApplicationSpecificRole)

        # 初始化数据
        self.settings_dialog = None
        self.refresh_interval = self._config_helper.get_int(
            ConfigKeys.REFRESH_INTERVAL, 5
        )
        self.current_user_stocks = self.viewModel.load_user_stocks()

        # Workers 初始化移动到了 ViewModel，这里不需要初始化 RefreshWorker
        # 信号连接也在 __init__ 中完成了
        # self.viewModel.stock_data_updated.connect(self._handle_refresh_data)
        # self.viewModel.refresh_error_occurred.connect(self._handle_refresh_error)

        # 初始化状态条，连接本地信号
        self.update_table_signal.connect(self.table.update_data)
        self.table.height_adjustment_requested.connect(self.adjust_window_height)

        # 加载状态指示器，初始隐藏
        self.loading_label = QtWidgets.QLabel("⏳ 数据加载中...")
        self.loading_label.setObjectName("LoadingLabel")
        self.loading_label.hide()
        layout.addWidget(self.loading_label)

        app_logger.info(
            f"初始化配置: 刷新间隔={self.refresh_interval}, 自选股={self.current_user_stocks}"
        )

        # 启动刷新线程和信号连接
        # 启动后台刷新线程 (通过 ViewModel)
        self.setup_refresh_worker()

        # 启动时立即更新一次数据库
        # 延迟一点时间再更新数据库，避免与市场状态更新冲突
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self.viewModel.check_and_update_database)
        timer.start(2000)

        # 不再在这里显示窗口，而是在_try_load_session_cache或_on_refresh_update中显示
        # 为自身和子控件安装事件过滤器
        self.install_event_filters(self)
        # 但是排除菜单，避免菜单事件被拦截
        if hasattr(self, "menu"):
            self.menu.removeEventFilter(self)

        # 立即更新市场状态条，提高优先级
        # 确保窗口尽快显示，然后再更新市场状态
        if not self.isVisible():
            self.show()
            self.load_position()
            self.raise_()

        app_logger.info("主窗口初始化完成")
        app_logger.debug("主窗口UI组件初始化完成")

    def _setup_event_handlers(self):
        """设置事件处理器"""
        pass

    def setup_refresh_worker(self):
        """设置刷新工作线程"""
        # 启动后台刷新线程 (通过 ViewModel)，数据由后台线程获取后通过信号推送
        # 注意：不在主线程中同步调用 refresh_now()，避免阻塞界面弹出
        self.viewModel.start_workers(self.current_user_stocks, self.refresh_interval)

    def _handle_refresh_error(self):
        """处理刷新错误 - 在主线程中执行"""
        try:
            app_logger.error("连续多次刷新失败")
            error_stocks = [
                StockRowData(
                    code="网络连接异常",
                    name="网络连接异常",
                    price="--",
                    change_str="--",
                    color_hex=COLORS.STOCK_NEUTRAL,
                    seal_vol="",
                    seal_type="",
                )
            ] * max(3, len(self.current_user_stocks))
            self.update_table_signal.emit(error_stocks)

            # 即使出错也要显示窗口，避免一直隐藏
            if not self.isVisible():
                self.show()
                self.load_position()
                self.raise_()
        except Exception as e:
            app_logger.error(f"处理刷新错误时出错: {e}")

    def _handle_refresh_data(self, data, all_failed=False):
        """
        处理刷新数据更新 - 在主线程中执行

        Args:
            data: 股票数据列表
            all_failed: 是否所有股票都获取失败
        """
        try:
            # 1. 停止加载超时计时器
            self._loading_timer.stop()

            # 缓存最新数据副本，用于即时重排交互优化
            self._last_data = data

            # 2. 对返回的数据进行强制排序以同步 UI 列表顺序
            stock_order_map = {
                code: i for i, code in enumerate(self.current_user_stocks)
            }
            data = sorted(
                data,
                key=lambda x: stock_order_map.get(
                    x.code if hasattr(x, "code") else getattr(x, "name", ""), 999
                ),
            )

            # 3. 更新表格数据
            self.update_table_signal.emit(data)

            # 仅在首次加载数据且窗口未显示时才强制显示
            if not hasattr(self, "_first_show_done") or not self._first_show_done:
                if not self.isVisible():
                    self.show()
                    self.load_position()
                    self.raise_()
                self._first_show_done = True

            # 如果窗口可见，确保子组件也可见
            if self.isVisible():
                self.market_status_bar.show()
                self.table.show()

            # 隐藏加载状态 (由于有了 QTimer，这里仅作为成功时的正常关闭)
            self.loading_label.hide()

            # 调整窗口大小
            self.adjust_window_height()

            # 保存会话缓存（仅当数据有效时）
            # 如果所有股票都获取失败，不保存缓存，避免下次启动加载到无效数据
            if not all_failed:
                try:
                    self.viewModel.save_session([self.pos().x(), self.pos().y()], data)
                except Exception as e:
                    app_logger.warning(f"保存会话缓存失败: {e}")
        except Exception as e:
            app_logger.error(f"刷新更新处理失败: {e}")

    def _try_load_session_cache(self):
        """尝试加载会话缓存以加快启动速度"""
        try:
            cached_session = self.viewModel.load_session()
            if cached_session:
                # 恢复窗口位置
                pos = cached_session.get("window_position")
                if pos and isinstance(pos, list) and len(pos) == 2:
                    self.move(pos[0], pos[1])

                # 显示缓存的股票数据
                stock_data = cached_session.get("stock_data")
                if stock_data:
                    self.viewModel.set_latest_stock_data(stock_data)
                    self.update_table_signal.emit(stock_data)

                # 显示窗口和所有组件
                self.market_status_bar.show()
                self.table.show()
                self.show()
                self.raise_()
                self.activateWindow()

                app_logger.info("使用会话缓存快速启动界面")
                return True
            else:
                # 没有缓存：立即显示加载中状态，不再等待数据
                self.show()
                self.load_position()
                self.raise_()
                self.loading_label.show()
                app_logger.info("无会话缓存，立即显示窗口，等待后台数据")

        except Exception as e:
            app_logger.warning(f"加载会话缓存失败: {e}")
            # 出错时也立即显示窗口，不阻塞用户
            self.show()
            self.load_position()
            self.raise_()
            self.loading_label.show()

        return False

    def _ensure_window_visible(self):
        """确保窗口可见"""
        try:
            # 如果窗口仍然隐藏，则显示它
            if not self.isVisible():
                self.show()
                self.load_position()
                self.raise_()
                app_logger.info("窗口已强制显示")
        except Exception as e:
            app_logger.error(f"强制显示窗口时出错: {e}")

    def save_position(self):
        """保存窗口位置到配置文件"""
        pos = self.pos()
        self._config_helper.set("window_pos", [pos.x(), pos.y()])

    def load_position(self):
        """从配置文件加载窗口位置"""
        pos = self._config_helper.get("window_pos")
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(pos[0], pos[1])
        else:
            self.move_to_bottom_right()

    def open_settings(self):
        """打开设置对话框"""
        if self.settings_dialog is None:
            self.settings_dialog = NewSettingsDialog(main_window=self)
            self.settings_dialog.config_changed.connect(self.on_config_changed)
            # 连接手动复盘请求信号
            self.settings_dialog.manual_report_requested.connect(
                self.on_manual_report_requested
            )
        self.settings_dialog.show()

    def on_manual_report_requested(self):
        """处理来自设置界面的手动复盘请求"""
        self.viewModel.trigger_manual_report()

    def on_config_changed(self, stocks, refresh_interval):
        """当配置更改时的处理函数"""
        app_logger.info(
            f"接收到配置更改信号: 股票列表={stocks}, 刷新间隔={refresh_interval}"
        )

        # 更新股票列表和刷新间隔
        self.current_user_stocks = stocks
        self.refresh_interval = refresh_interval

        # 更新后台刷新线程的配置 (通过 ViewModel)
        self.viewModel.update_workers_config(stocks, refresh_interval)

        # UX 优化：在触发异步刷新前，先利用上一次缓存数据按照新顺序进行本地即时重排，实现“零延迟”响应
        if hasattr(self, "_last_data") and self._last_data:
            stock_order_map = {code: i for i, code in enumerate(stocks)}
            # 1. 过滤并重排现有数据
            resorted_data = sorted(
                [
                    d
                    for d in self._last_data
                    if (d.code if hasattr(d, "code") else getattr(d, "name", ""))
                    in stock_order_map
                ],
                key=lambda x: stock_order_map.get(
                    x.code if hasattr(x, "code") else getattr(x, "name", ""), 999
                ),
            )
            # 2. 补齐新加入股票的占位
            existing_codes = {
                (d.code if hasattr(d, "code") else getattr(d, "name", ""))
                for d in resorted_data
            }
            for code in stocks:
                if code not in existing_codes:
                    resorted_data.insert(
                        stock_order_map[code],
                        StockRowData(
                            code=code,
                            name="加载中",
                            price="--",
                            change_str="--",
                            color_hex=COLORS.STOCK_NEUTRAL,
                            seal_vol="",
                            seal_type="",
                        ),
                    )
            # 立即渲染，消除 2s 等待感
            self.update_table_signal.emit(resorted_data)

        # 更新主题透明度缓存
        new_transparency = self._config_helper.get_int(ConfigKeys.TRANSPARENCY, 80)
        if new_transparency != getattr(self, "_transparency", None):
            self._transparency = new_transparency
            self.request_update()  # 节流重绘请求

        # 立即同步刷新显示（跳过占位，因为上面已经完成了更有意义的本地重排渲染）
        self.refresh_now(stocks, skip_placeholders=True)

        # 更新主窗口字体大小
        self.update_font_size()

    def request_update(self):
        """请求 UI 更新（节流模式，合并 50ms 内的多次请求）"""
        # [SAFETY] 检查属性是否已初始化，避免初始化顺序问题
        if not hasattr(self, "_pending_update"):
            return

        if not self._pending_update:
            self._pending_update = True
            self._update_timer.start()

    def _do_update(self):
        """执行实际的 UI 更新（由节流计时器触发）"""
        # [SAFETY] 检查属性是否已初始化
        if hasattr(self, "_pending_update"):
            self._pending_update = False
        self.update()
        app_logger.debug("UI 更新已节流合并")

    def update_font_size(self):
        """更新主窗口字体大小"""
        try:
            # 从配置中读取字体大小和字体族
            font_size = self._config_helper.get_int(ConfigKeys.FONT_SIZE, 13)
            font_family = self._config_helper.get_str(
                ConfigKeys.FONT_FAMILY, "微软雅黑"
            )

            try:
                font_size = int(font_size)
            except (ValueError, TypeError):
                font_size = 13

            # 确保字体大小大于0
            if font_size <= 0:
                font_size = 13

            app_logger.info(f"更新主窗口字体: {font_family}, {font_size}px")

            # 主窗口字体
            self.setObjectName("MainWindow")

            # 更新表格字体
            if hasattr(self, "table") and self.table:
                self.table.set_font_size(font_family, font_size)
                # 触发窗口更新样式
                from stock_monitor.ui.styles import load_global_stylesheet

                qss = load_global_stylesheet(font_family, font_size)
                if qss:
                    self.setStyleSheet(qss)

            # 更新加载标签字体
            if hasattr(self, "loading_label") and self.loading_label:
                pass

            # 调整主窗口高度
            self.adjust_window_height()
        except Exception as e:
            app_logger.error(f"更新主窗口字体大小失败: {e}")

    def refresh_now(self, stocks_list=None, skip_placeholders=False):
        """
        发起立即刷新请求（异步）
        不再阻塞 UI 线程，实际更新由 _handle_refresh_data 信号处理器完成
        """
        if stocks_list is None:
            stocks_list = self.current_user_stocks

        try:
            # 更新本地缓存的列表
            self.current_user_stocks = stocks_list

            # 开启 10s 超时强制收敛，解决“数据加载中”状态残留问题
            self._loading_timer.start(10000)

            # 仅在非跳过模式下发送占位数据 (UX 优化: 防止覆盖本地重排的结果)
            if not skip_placeholders:
                placeholder_data = []
                for code in stocks_list:
                    # 填充符合 StockRowData 定义的数据
                    placeholder_data.append(
                        StockRowData(
                            code=code,
                            name="加载中",
                            price="--",
                            change_str="--",
                            color_hex=COLORS.STOCK_NEUTRAL,
                            seal_vol="",
                            seal_type="",
                        )
                    )
                self.update_table_signal.emit(placeholder_data)
                # 显示加载状态提示
                self.loading_label.show()

            # 通过 ViewModel 向后台 Worker 发放刷新指令
            app_logger.debug(f"请求手动异步刷新: {len(stocks_list)} 只股票")
            self.viewModel.request_immediate_refresh(stocks_list)

        except Exception as e:
            app_logger.error(f"发起异步刷新请求失败: {e}")
            self.loading_label.hide()
            self._loading_timer.stop()

    def _on_loading_timeout(self):
        """加载状态超时处理"""
        if hasattr(self, "loading_label") and self.loading_label.isVisible():
            self.loading_label.hide()
            app_logger.warning("刷新请求超时 (10s)，强制收敛加载状态")

    def paintEvent(self, event):
        """窗口绘制事件，用于绘制半透明背景"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)  # type: ignore
        rect = self.rect()

        # 读取缓存的透明度配置，不进行昂贵的容器获取和IO查找
        transparency = getattr(self, "_transparency", 80)

        if hasattr(self, "_preview_transparency"):
            transparency = self._preview_transparency

        alpha = int(MIN_BACKGROUND_ALPHA + (ALPHA_RANGE * transparency / 100))
        alpha = max(MIN_BACKGROUND_ALPHA, min(MAX_BACKGROUND_ALPHA, alpha))
        bg_color = QtGui.QColor(30, 30, 30, alpha)
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)  # type: ignore
        painter.drawRect(rect)

    def adjust_window_height(self):
        """根据内容调整窗口高度和宽度"""
        if self.table.rowCount() == 0:
            return  # 无数据时不调整，避免窗口高度异常

        vh = self.table.verticalHeader()
        row_height = vh.sectionSize(0)
        layout_margin = 0
        table_height = self.table.rowCount() * row_height
        new_height = table_height + layout_margin + self.market_status_bar.height()
        # 不使用绝对高度限制，改用 resize 让窗口可以自适应内容

        table_width = sum(
            self.table.columnWidth(col) for col in range(self.table.columnCount())
        )

        # 预留一点额外空间避免滚动条闪烁
        target_width = table_width + 5
        target_height = new_height + 5

        # 不要使用 setFixedSize，这样在高分辨率或不同字体时会导致窗口卡死，允许用户自由调整
        self.setMinimumSize(target_width, min(target_height, 200))
        self.resize(target_width, target_height)

        self.request_update()  # 节流布局更新
        self.updateGeometry()

    def load_theme_config(self):
        """加载主题配置"""
        import json

        from stock_monitor.utils.helpers import resource_path

        try:
            with open(resource_path("theme_config.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _format_stock_code(self, code):
        """格式化股票代码"""
        from stock_monitor.utils.stock_utils import StockCodeProcessor

        processor = StockCodeProcessor()
        return processor.format_stock_code(code)

    def load_user_stocks(self):
        """加载用户自选股列表"""
        return self.viewModel.load_user_stocks()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """
        窗口关闭事件处理
        清理 Qt 对象、断开信号连接、保存状态
        """
        try:
            app_logger.info("主窗口关闭，开始清理资源...")

            # 1. 停止所有计时器
            if hasattr(self, "_loading_timer") and self._loading_timer:
                self._loading_timer.stop()
                self._loading_timer.deleteLater()

            # 2. 断开 ViewModel 信号连接
            if hasattr(self, "viewModel"):
                self.viewModel.market_stats_updated.disconnect()
                self.viewModel.stock_data_updated.disconnect()
                self.viewModel.refresh_error_occurred.disconnect()

            # 3. 清理自定义信号
            self.update_table_signal.disconnect()
            self.refresh_data_signal.disconnect()
            self.refresh_error_signal.disconnect()

            # 4. 保存会话缓存和位置
            try:
                self.viewModel.save_session(
                    [self.x(), self.y()], self.viewModel.get_latest_stock_data()
                )
            except Exception as e:
                app_logger.warning(f"保存会话缓存失败：{e}")
                self.save_position()

            # 5. 隐藏系统托盘
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.hide()
                self.tray_icon.deleteLater()

            # 6. 停止 Workers
            if hasattr(self, "viewModel"):
                self.viewModel.stop_workers()

            app_logger.info("主窗口资源清理完成")

        except Exception as e:
            app_logger.error(f"closeEvent 清理失败：{e}")

        finally:
            # 调用父类实现
            super().closeEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent):
        """
        窗口隐藏事件处理
        保存当前状态以便快速恢复
        """
        try:
            # 保存窗口位置（用于下次启动时快速恢复）
            self.save_position()
        except Exception as e:
            app_logger.warning(f"hideEvent 保存位置失败：{e}")

        super().hideEvent(event)
