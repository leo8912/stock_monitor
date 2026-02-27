import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import (
    pyqtSignal,
)

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.container import container

# Workers are now managed by ViewModel
from stock_monitor.ui.components.stock_table import StockTable
from stock_monitor.ui.constants import COLORS
from stock_monitor.ui.dialogs.settings_dialog import NewSettingsDialog
from stock_monitor.ui.mixins.draggable_window import DraggableWindowMixin

# Removed obsolete styles import
from stock_monitor.ui.view_models.main_window_view_model import MainWindowViewModel
from stock_monitor.ui.widgets.context_menu import AppContextMenu
from stock_monitor.ui.widgets.market_status import MarketStatusBar
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
        self._transparency = config_manager.get("transparency", 80)

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
        config_manager = self._container.get(ConfigManager)
        self.refresh_interval = config_manager.get("refresh_interval", 5)
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
        # 启动后台刷新线程 (通过 ViewModel)
        self.viewModel.start_workers(self.current_user_stocks, self.refresh_interval)

        # 启动后立即刷新一次数据，确保界面显示
        self.refresh_now()

    def _handle_refresh_error(self):
        """处理刷新错误 - 在主线程中执行"""
        try:
            app_logger.error("连续多次刷新失败")
            error_stocks = [
                ("网络连接异常", "--", "--", COLORS.STOCK_NEUTRAL, "", "")
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
            # 更新表格数据
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

            # 隐藏加载状态
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
                # 没有缓存，隐藏窗口直到获取到数据
                self.hide()
                # 同时隐藏所有组件
                self.market_status_bar.hide()
                self.table.hide()
        except Exception as e:
            app_logger.warning(f"加载会话缓存失败: {e}")
            # 出错时也隐藏窗口
            self.hide()
            # 同时隐藏所有组件
            self.market_status_bar.hide()
            self.table.hide()

        # 确保在没有缓存的情况下也能最终显示窗口
        # 使用 QTimer 在短时间内显示窗口，确保初始化完成
        QtCore.QTimer.singleShot(100, self._ensure_window_visible)
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
        config_manager = self._container.get(ConfigManager)
        config_manager.set("window_pos", [pos.x(), pos.y()])

    def load_position(self):
        """从配置文件加载窗口位置"""
        config_manager = self._container.get(ConfigManager)
        pos = config_manager.get("window_pos")
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(pos[0], pos[1])
        else:
            self.move_to_bottom_right()

    def open_settings(self):
        """打开设置对话框"""
        if self.settings_dialog is None:
            self.settings_dialog = NewSettingsDialog(main_window=self)
            self.settings_dialog.config_changed.connect(self.on_config_changed)
        self.settings_dialog.show()

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

        # 更新主题透明度缓存
        config_manager = self._container.get(ConfigManager)
        new_transparency = config_manager.get("transparency", 80)
        if new_transparency != getattr(self, "_transparency", None):
            self._transparency = new_transparency
            self.update()  # 触发重绘

        # 立即同步刷新显示（只触发一次，settings_dialog 中已不再重复调用）
        self.refresh_now(stocks)

        # 更新主窗口字体大小
        self.update_font_size()

    def update_font_size(self):
        """更新主窗口字体大小"""
        try:
            # 从配置中读取字体大小和字体族
            config_manager = self._container.get(ConfigManager)
            font_size = config_manager.get("font_size", 13)
            font_family = config_manager.get("font_family", "微软雅黑")

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

    def refresh_now(self, stocks_list=None):
        """立即刷新数据"""
        if stocks_list is None:
            stocks_list = self.current_user_stocks
        try:
            self.loading_label.show()
            self.table.hide()
            QtWidgets.QApplication.processEvents()

            # 更新当前股票列表
            self.current_user_stocks = stocks_list

            stocks = self.viewModel.get_stock_list_data(stocks_list)

            # 使用 update_data 更新数据
            self.table.update_data(stocks)

            self.adjust_window_height()

            self.loading_label.hide()
            self.table.show()
        except Exception as e:
            app_logger.error(f"行情刷新异常: {e}")
            error_stocks = [
                ("数据加载异常", "--", "--", COLORS.STOCK_NEUTRAL, "", "")
            ] * max(3, len(stocks_list) if stocks_list else 3)
            self.table.update_data(error_stocks)
            self.adjust_window_height()
            self.loading_label.hide()
            self.table.show()

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

        self.layout().update()
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
