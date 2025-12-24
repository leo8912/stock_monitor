import os
import threading
import time

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import (
    pyqtSignal,
)

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.container import container
from stock_monitor.core.market_worker import MarketStatsWorker
from stock_monitor.core.refresh_worker import RefreshWorker
from stock_monitor.ui.components.stock_table import StockTable
from stock_monitor.ui.constants import COLORS
from stock_monitor.ui.dialogs.settings_dialog import NewSettingsDialog
from stock_monitor.ui.styles import (
    get_loading_label_style,
    get_main_window_style,
    get_table_style,
)
from stock_monitor.ui.widgets.context_menu import AppContextMenu
from stock_monitor.ui.widgets.market_status import MarketStatusBar
from stock_monitor.utils.helpers import resource_path
from stock_monitor.utils.log_cleaner import schedule_log_cleanup
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.stock_utils import StockCodeProcessor

# 定义常量
ICON_FILE = resource_path("icon.ico")
MIN_BACKGROUND_ALPHA = 128  # 透明度0时的alpha值(半透明,相当于原来50%的透明度)
MAX_BACKGROUND_ALPHA = 255  # 透明度100时的alpha值(完全不透明)
ALPHA_RANGE = MAX_BACKGROUND_ALPHA - MIN_BACKGROUND_ALPHA


class MainWindow(QtWidgets.QWidget):
    """
    主窗口类
    负责显示股票行情、处理用户交互和管理应用状态
    """

    update_table_signal = pyqtSignal(list)
    # 添加用于跨线程更新UI的信号
    refresh_data_signal = pyqtSignal(list, bool)
    refresh_error_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        # 初始化依赖注入容器
        self._container = container
        self.setup_ui()
        # 尝试加载会话缓存
        if not self._try_load_session_cache():
            # 如果没有加载到缓存，确保窗口最终会显示
            pass

        # 连接跨线程信号
        self.refresh_data_signal.connect(self._handle_refresh_data)
        self.refresh_error_signal.connect(self._handle_refresh_error)

        # 初始化全市场统计工作线程
        self.market_stats_worker = MarketStatsWorker()
        self.market_stats_worker.stats_updated.connect(
            self.market_status_bar.update_status
        )
        self.market_stats_worker.start_worker()

    def quit_application(self):
        """退出应用程序"""
        try:
            # 1. 保存会话缓存 (包含位置和数据)
            try:
                from stock_monitor.utils.session_cache import save_session_cache

                session_data = {
                    "window_position": [self.x(), self.y()],
                    "stock_data": self._get_current_stock_data(),
                }
                save_session_cache(session_data)
            except Exception as e:
                app_logger.warning(f"保存会话缓存失败: {e}")
                # Fallback to simple position save if cache fails
                self.save_position()

            # 2. 隐藏界面
            self.hide()
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.hide()

            # 3. 停止所有工作线程
            if hasattr(self, "refresh_worker"):
                self.refresh_worker.stop_refresh()
                self.refresh_worker.wait()

            if hasattr(self, "market_stats_worker"):
                self.market_stats_worker.stop_worker()

            # 4. 清理快捷键
            if hasattr(self, "shortcuts"):
                for shortcut in self.shortcuts:
                    shortcut.setEnabled(False)
                    shortcut.setParent(None)

            # 5. 强制退出应用
            # 使用 os._exit(0) 立即终止进程，避免等待后台线程导致的挂起
            import os

            os._exit(0)
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
        self.setWindowFlags(
            QtCore.Qt.WindowType.WindowStaysOnTopHint  # type: ignore
            | QtCore.Qt.WindowType.FramelessWindowHint  # type: ignore
            | QtCore.Qt.WindowType.Tool  # type: ignore
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint  # type: ignore
        )  # type: ignore
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)  # type: ignore
        self.resize(320, 160)
        self.drag_position = None

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
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)  # type: ignore

        # 从配置中读取字体大小和字体族
        config_manager = self._container.get(ConfigManager)
        font_size = config_manager.get("font_size", 13)  # 默认13px
        font_family = config_manager.get("font_family", "微软雅黑")  # 默认微软雅黑

        try:
            font_size = int(font_size)
        except (ValueError, TypeError):
            font_size = 13

        # 确保字体大小大于0
        if font_size <= 0:
            font_size = 13  # 默认字体大小

        # 统一使用CSS设置字体，避免与QFont冲突
        # 不使用 setFont()，只使用样式表
        self.setStyleSheet(get_main_window_style(font_family, font_size))

        app_logger.debug(f"主窗口字体设置: {font_family}, {font_size}px")

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
        from stock_monitor.utils.helpers import get_config_manager

        config_manager = get_config_manager()
        self.refresh_interval = config_manager.get("refresh_interval", 5)
        self.current_user_stocks = self.load_user_stocks()

        # 初始化后台刷新工作线程
        # 初始化后台刷新工作线程（使用新的QThread实现）
        self.refresh_worker = RefreshWorker()

        # 连接信号
        self.refresh_worker.data_updated.connect(self._handle_refresh_data)
        self.refresh_worker.refresh_error.connect(self._handle_refresh_error)

        # 加载状态指示器，初始隐藏
        self.loading_label = QtWidgets.QLabel("⏳ 数据加载中...")
        self.loading_label.setStyleSheet(get_loading_label_style(font_size))
        self.loading_label.hide()
        layout.addWidget(self.loading_label)

        app_logger.info(
            f"初始化配置: 刷新间隔={self.refresh_interval}, 自选股={self.current_user_stocks}"
        )

        # 启动刷新线程和信号连接
        self.update_table_signal.connect(self.table.update_data)  # type: ignore

        # 启动后台刷新线程
        self.refresh_worker.start_refresh(
            self.current_user_stocks, self.refresh_interval
        )

        # 启动时立即更新一次数据库
        # 延迟一点时间再更新数据库，避免与市场状态更新冲突
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._update_database_on_startup)

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
            self.activateWindow()

        app_logger.info("主窗口初始化完成")
        app_logger.debug("主窗口UI组件初始化完成")

    def _setup_event_handlers(self):
        """设置事件处理器"""
        pass

    def setup_refresh_worker(self):
        """设置刷新工作线程"""
        # 启动后台刷新线程
        self.refresh_worker.start_refresh(
            self.current_user_stocks, self.refresh_interval
        )
        # 启动后立即刷新一次数据，确保界面显示
        self.refresh_now()

    def _handle_refresh_error(self):
        """处理刷新错误 - 在主线程中执行"""
        try:
            app_logger.error("连续多次刷新失败")
            error_stocks = [("网络连接异常", "--", "--", COLORS.STOCK_NEUTRAL, "", "")] * max(
                3, len(self.current_user_stocks)
            )
            self.update_table_signal.emit(error_stocks)

            # 即使出错也要显示窗口，避免一直隐藏
            if not self.isVisible():
                self.show()
                self.load_position()
                self.raise_()
                self.activateWindow()
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
                    self.activateWindow()
                self._first_show_done = True

            # 如果窗口可见，确保子组件也可见
            if self.isVisible():
                self.market_status_bar.show()
                self.table.show()

            # 隐藏加载状态
            self.loading_label.hide()

            # 调整窗口大小
            self.adjust_window_height()

            # 保存会话缓存
            try:
                from stock_monitor.utils.session_cache import save_session_cache

                session_data = {
                    "window_position": [self.pos().x(), self.pos().y()],
                    "stock_data": data,
                }
                save_session_cache(session_data)
            except Exception as e:
                app_logger.warning(f"保存会话缓存失败: {e}")
        except Exception as e:
            app_logger.error(f"刷新更新处理失败: {e}")

    def _try_load_session_cache(self):
        """尝试加载会话缓存以加快启动速度"""
        try:
            from stock_monitor.utils.session_cache import load_session_cache

            cached_session = load_session_cache()
            if cached_session:
                # 恢复窗口位置
                pos = cached_session.get("window_position")
                if pos and isinstance(pos, list) and len(pos) == 2:
                    self.move(pos[0], pos[1])

                # 显示缓存的股票数据
                stock_data = cached_session.get("stock_data")
                if stock_data:
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
                self.activateWindow()
                app_logger.info("窗口已强制显示")
        except Exception as e:
            app_logger.error(f"强制显示窗口时出错: {e}")

    def install_event_filters(self, widget):
        """
        为控件安装事件过滤器

        Args:
            widget: 需要安装事件过滤器的控件
        """
        if isinstance(widget, QtWidgets.QWidget):
            widget.installEventFilter(self)
            for child in widget.findChildren(QtWidgets.QWidget):
                self.install_event_filters(child)

    def eventFilter(self, a0, a1):
        """
        事件过滤器，处理鼠标事件
        """
        event = a1
        if event is not None and event.type() == QtCore.QEvent.Type.MouseButtonDblClick:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self.hide()
                event.accept()
                return True
        elif event is not None and event.type() == QtCore.QEvent.Type.MouseButtonPress:  # type: ignore
            if event.button() == QtCore.Qt.MouseButton.LeftButton:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                frame_top_left = self.frameGeometry().topLeft()
                self.drag_position = QtCore.QPoint(
                    cursor_pos.x() - frame_top_left.x(),
                    cursor_pos.y() - frame_top_left.y(),
                )
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)  # type: ignore
                event.accept()
                return True
            elif event.button() == QtCore.Qt.MouseButton.RightButton:
                # 弹出右键菜单
                click_pos = self.mapToGlobal(event.pos())
                self.menu.popup(click_pos)
                event.accept()
                return True
        elif event is not None and event.type() == QtCore.QEvent.Type.MouseMove:  # type: ignore
            if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                self.move(
                    cursor_pos.x() - self.drag_position.x(),
                    cursor_pos.y() - self.drag_position.y(),
                )
                event.accept()
                return True
        elif event is not None and event.type() == QtCore.QEvent.Type.MouseButtonRelease:  # type: ignore
            self.drag_position = None
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)  # type: ignore
            self.save_position()  # 拖动结束时自动保存位置
            event.accept()
            return True
        return super().eventFilter(a0, a1)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击隐藏窗口"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.hide()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:  # type: ignore
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)  # type: ignore
        # 只在没有隐藏的情况下保存位置
        if self.isVisible():
            self.save_position()

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.save_position()
        self.hide()
        event.ignore()

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

    def move_to_bottom_right(self):
        """将窗口移动到屏幕右下角"""
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()  # type: ignore
        self.move(
            screen.right() - self.width() - 20, screen.bottom() - self.height() - 40
        )

    def open_settings(self):
        """打开设置对话框"""
        if self.settings_dialog is None:
            self.settings_dialog = NewSettingsDialog(main_window=self)
            self.settings_dialog.config_changed.connect(self.on_config_changed)
        self.settings_dialog.show()

    # Method removed, merged into line 69

    def _get_current_stock_data(self):
        """获取当前显示的股票数据"""
        try:
            # 从表格中获取当前显示的数据
            if hasattr(self, "table") and self.table:
                # 获取表格的行数
                row_count = self.table.rowCount()
                stock_data = []

                # 遍历每一行，提取股票数据
                for row in range(row_count):
                    stock_item = []
                    # 遍历每一列
                    for col in range(self.table.columnCount()):
                        # 使用新的兼容性方法
                        text = self.table.get_data_at(row, col)
                        stock_item.append(text)

                    # 确保数据格式正确（6个字段）
                    while len(stock_item) < 6:
                        stock_item.append("")

                    # 处理股票名称（第1列），去除前后空格
                    if len(stock_item) >= 1:
                        name_str = stock_item[0].strip()  # 去除前后空格
                        stock_item[0] = name_str

                    # 处理涨跌幅数据（第3列），去除%符号和空格
                    if len(stock_item) >= 3:
                        change_str = stock_item[2].strip()  # 去除前后空格
                        if change_str.endswith("%"):
                            change_str = change_str[:-1]  # 去除%符号
                        stock_item[2] = change_str.strip()  # 再次去除可能的空格

                    # 添加颜色信息（第4列）- 从前台颜色获取
                    if len(stock_item) >= 4:
                        # 获取单元格的前台颜色（文字颜色）
                        fg_color = self.table.get_foreground_color_at(row, 0)
                        if fg_color:
                            stock_item[3] = fg_color

                    stock_data.append(stock_item)

                return stock_data

            return []
        except Exception as e:
            app_logger.warning(f"获取当前股票数据失败: {e}")
            return []

    def on_config_changed(self, stocks, refresh_interval):
        """当配置更改时的处理函数"""
        app_logger.info(f"接收到配置更改信号: 股票列表={stocks}, 刷新间隔={refresh_interval}")

        # 更新股票列表和刷新间隔
        self.current_user_stocks = stocks
        self.refresh_interval = refresh_interval

        # 更新后台刷新线程的配置
        self.refresh_worker.update_stocks(stocks)
        self.refresh_worker.update_interval(refresh_interval)

        # 强制刷新显示
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

            # 统一使用CSS设置字体
            self.setStyleSheet(get_main_window_style(font_family, font_size))

            # 更新表格字体
            if hasattr(self, "table") and self.table:
                self.table.setStyleSheet(get_table_style(font_family, font_size))
                # 强制刷新表格样式
                self.table.style().unpolish(self.table)
                self.table.style().polish(self.table)
                self.table.update()

            # 更新加载标签字体
            if hasattr(self, "loading_label") and self.loading_label:
                self.loading_label.setStyleSheet(get_loading_label_style(font_size))

            # 调整主窗口高度
            self.adjust_window_height()
        except Exception as e:
            app_logger.error(f"更新主窗口字体大小失败: {e}")

    def process_stock_data(self, data, stocks_list):
        """处理股票数据"""
        from stock_monitor.core.stock_service import stock_data_service

        return stock_data_service.process_stock_data(data, stocks_list)

    def refresh_now(self, stocks_list=None):
        """立即刷新数据"""
        if stocks_list is None:
            stocks_list = self.current_user_stocks
        try:
            self.loading_label.show()
            self.table.hide()
            QtWidgets.QApplication.processEvents()

            from stock_monitor.core.stock_manager import stock_manager

            stocks = stock_manager.get_stock_list_data(stocks_list)

            # 使用 update_data 更新数据，不需要手动清理
            self.table.update_data(stocks)

            self.adjust_window_height()

            self.loading_label.hide()
            self.table.show()
        except Exception as e:
            app_logger.error(f"行情刷新异常: {e}")
            error_stocks = [("数据加载异常", "--", "--", COLORS.STOCK_NEUTRAL, "", "")] * max(
                3, len(stocks_list) if stocks_list else 3
            )
            self.table.setRowCount(0)
            self.table.clearContents()
            self.table.update_data(error_stocks)  # type: ignore
            self.table.viewport().update()
            self.table.repaint()
            self.adjust_window_height()

            self.loading_label.hide()
            self.table.show()

    def paintEvent(self, event):
        """窗口绘制事件，用于绘制半透明背景"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)  # type: ignore
        rect = self.rect()

        config_manager = self._container.get(ConfigManager)
        transparency = config_manager.get("transparency", 80)

        if hasattr(self, "_preview_transparency"):
            transparency = self._preview_transparency

        alpha = int(MIN_BACKGROUND_ALPHA + (ALPHA_RANGE * transparency / 100))
        alpha = max(MIN_BACKGROUND_ALPHA, min(MAX_BACKGROUND_ALPHA, alpha))
        bg_color = QtGui.QColor(30, 30, 30, alpha)
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)  # type: ignore
        painter.drawRect(rect)

    def _update_database_on_startup(self):
        """启动时更新数据库"""
        try:
            config_manager = self._container.get(ConfigManager)
            last_update = config_manager.get("last_db_update", 0)
            current_time = time.time()

            if current_time - last_update > 86400 or last_update == 0:
                should_update = True
            else:
                # 检查数据库是否为空（应对路径变更情况）
                from stock_monitor.data.stock.stock_db import stock_db

                if stock_db.get_all_stocks_count() == 0:
                    app_logger.warning("检测到股票数据库为空，强制启动更新")
                    should_update = True
                else:
                    should_update = False

            if should_update:
                self._update_database_async()
                # 不在这里保存时间戳，等更新完成后再保存
                app_logger.info("启动时数据库更新已启动")
        except Exception as e:
            app_logger.error(f"启动时数据库更新检查失败: {e}")

    def _update_database_async(self):
        """异步更新数据库"""
        try:
            from stock_monitor.data.market.updater import update_stock_database

            update_thread = threading.Thread(target=update_stock_database, daemon=True)
            update_thread.start()
        except Exception as e:
            app_logger.error(f"异步更新数据库时出错: {e}")

    def _clean_stock_code(self, stock_code: str, processor) -> str:
        """
        清理股票代码,移除特殊字符并格式化

        Args:
            stock_code: 原始股票代码
            processor: StockCodeProcessor实例

        Returns:
            清理后的股票代码
        """
        # 移除emoji等特殊字符
        cleaned = stock_code.replace("⭐️", "").strip()

        # 如果为空,返回原始值
        if not cleaned:
            return stock_code

        # 尝试提取第一部分(处理 "code name" 格式)
        parts = cleaned.split()
        if not parts:
            return stock_code

        # 先尝试格式化第一部分
        formatted = processor.format_stock_code(parts[0])
        if formatted:
            return formatted

        # 如果第一部分格式化失败,尝试整个字符串
        formatted = processor.format_stock_code(cleaned)
        return formatted if formatted else stock_code

    def load_user_stocks(self):
        """加载用户自选股列表"""
        try:
            config_manager = self._container.get(ConfigManager)
            stocks = config_manager.get("user_stocks", [])

            # 早返回:如果列表为空,直接返回
            if not stocks:
                app_logger.info("自选股列表为空")
                return []

            # 清理可能的损坏数据
            from stock_monitor.utils.stock_utils import StockCodeProcessor

            processor = StockCodeProcessor()

            cleaned_stocks = []
            has_changes = False

            for stock in stocks:
                cleaned = self._clean_stock_code(stock, processor)
                cleaned_stocks.append(cleaned)

                if cleaned != stock:
                    has_changes = True

            # 如果有变化,保存清理后的数据
            if has_changes:
                app_logger.warning(f"检测到自选股列表包含脏数据，已自动修复: {stocks} -> {cleaned_stocks}")
                config_manager.set("user_stocks", cleaned_stocks)

            app_logger.info(f"加载自选股列表: {cleaned_stocks}")
            return cleaned_stocks

        except Exception as e:
            app_logger.error(f"加载自选股列表失败: {e}")
            return []

    def _format_stock_code(self, code):
        """格式化股票代码"""
        processor = StockCodeProcessor()
        return processor.format_stock_code(code)

    def load_theme_config(self):
        """加载主题配置"""
        import json

        try:
            with open(resource_path("theme_config.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def adjust_window_height(self):
        """根据内容调整窗口高度和宽度"""
        QtWidgets.QApplication.processEvents()
        vh = self.table.verticalHeader()
        if self.table.rowCount() > 0:
            row_height = vh.sectionSize(0)
        else:
            row_height = 36
        layout_margin = 0
        table_height = self.table.rowCount() * row_height
        new_height = table_height + layout_margin + self.market_status_bar.height()
        self.setFixedHeight(new_height)

        table_width = sum(
            self.table.columnWidth(col) for col in range(self.table.columnCount())
        )
        self.setFixedWidth(table_width)

        self.layout().update()
        self.updateGeometry()

    def _update_database_if_needed(self):
        """根据更新时间判断是否需要更新数据库"""
        try:
            from stock_monitor.utils.helpers import get_config_manager

            config_manager = get_config_manager()
            last_update = config_manager.get("last_db_update", 0)
            current_time = time.time()

            if current_time - last_update > 86400:
                self._update_database_async()
                config_manager.set("last_db_update", current_time)
        except Exception as e:
            app_logger.error(f"数据库更新检查失败: {e}")
