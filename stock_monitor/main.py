"""
股票监控主程序
用于监控A股股票实时行情
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import threading
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import time
import datetime

# 条件导入win32com
try:
    from win32com.client import Dispatch
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from stock_monitor.utils.logger import app_logger
from stock_monitor.data.market.updater import update_stock_database
from stock_monitor.ui.widgets.market_status import MarketStatusBar

from stock_monitor.config.manager import is_market_open, load_config, save_config

from stock_monitor.utils.helpers import resource_path, get_stock_emoji
from stock_monitor.utils.log_cleaner import schedule_log_cleanup
from stock_monitor.core.updater import app_updater

ICON_FILE = resource_path('icon.ico')  # 统一使用ICO格式图标

# 修改导入语句，使用设置对话框
from stock_monitor.ui.dialogs.settings_dialog import NewSettingsDialog
from stock_monitor.ui.components.stock_table import StockTable

# 导入后台刷新工作线程
from stock_monitor.core.refresh_worker import RefreshWorker

class MainWindow(QtWidgets.QWidget):
    """
    主窗口类
    负责显示股票行情、处理用户交互和管理应用状态
    """
    update_table_signal = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('A股行情监控')
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |  # type: ignore
            QtCore.Qt.FramelessWindowHint |  # type: ignore
            QtCore.Qt.Tool |  # type: ignore
            QtCore.Qt.WindowMaximizeButtonHint  # type: ignore
        )  # type: ignore
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)  # type: ignore
        self.resize(320, 160)
        self.drag_position = None
        
        app_logger.info("主窗口初始化开始")
        app_logger.debug(f"当前工作目录: {os.getcwd()}")
        
        # 启动日志定期清理任务
        schedule_log_cleanup(days_to_keep=7, interval_hours=24)
        
        # 初始化股市状态条
        self.market_status_bar = MarketStatusBar(self)
        
        # 初始化UI
        self.table = StockTable(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 移除边距，使表格紧贴窗口边缘
        layout.setSpacing(0)
        layout.addWidget(self.market_status_bar)  # 添加状态条
        layout.addWidget(self.table)

        self.setLayout(layout)
        
        # 设置样式
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)  # type: ignore

        font = QtGui.QFont('微软雅黑', 20)
        self.setFont(font)
        self.setStyleSheet('QWidget { font-family: "微软雅黑"; font-size: 20px; color: #fff; background: transparent; border: none; }')
        
        # 初始化菜单
        # 创建右键菜单，样式与设置界面保持一致
        self.menu = QtWidgets.QMenu(self)
        self.menu.setStyleSheet('''
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 16px;  /* 缩小字体 */
                padding: 2px 0;   /* 减小内边距 */
                min-width: 100px; /* 缩小最小宽度 */
            }
            QMenu::item {
                padding: 4px 16px;  /* 减小菜单项内边距 */
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QMenu::separator {
                height: 1px;
                background: #555555;
                margin: 2px 0;  /* 减小分隔符边距 */
            }
        ''')
        self.action_settings = self.menu.addAction('设置')
        self.menu.addSeparator()
        self.action_quit = self.menu.addAction('退出')
        self.action_settings.triggered.connect(self.open_settings)
        self.action_quit.triggered.connect(QtWidgets.QApplication.quit)
        
        # 确保菜单项连接正确，避免功能不稳定
        self.action_settings.setMenuRole(QtWidgets.QAction.MenuRole.NoRole)
        self.action_quit.setMenuRole(QtWidgets.QAction.MenuRole.NoRole)
        
        # 初始化数据
        self.settings_dialog = None
        cfg = load_config()
        self.refresh_interval = cfg.get('refresh_interval', 5)
        self.current_user_stocks = self.load_user_stocks()
        
        # 初始化后台刷新工作线程
        self.refresh_worker = RefreshWorker(
            update_callback=self._on_refresh_update,
            error_callback=self._on_refresh_error
        )
        
        # 加载状态指示器
        self.loading_label = QtWidgets.QLabel("⏳ 数据加载中...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #fff;
                font-size: 20px;
                background: rgba(30, 30, 30, 0.8);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.loading_label.hide()
        layout.addWidget(self.loading_label)
        
        app_logger.info(f"初始化配置: 刷新间隔={self.refresh_interval}, 自选股={self.current_user_stocks}")
        
        # 启动刷新线程和信号连接
        self.update_table_signal.connect(self.table.update_data)  # type: ignore
        
        # 不再在初始化时立即刷新，避免阻塞窗口显示
        # self.refresh_now(self.current_user_stocks)
        # 启动后台刷新线程
        self.refresh_worker.start(self.current_user_stocks, self.refresh_interval)
        self._start_database_update_thread()
        
        # 启动时立即更新一次数据库
        self._update_database_on_startup()
        
        # 显示窗口并加载位置
        self.show()
        self.load_position()
        self.raise_()
        self.activateWindow()
        # 为自身和子控件安装事件过滤器
        self.install_event_filters(self)
        # 但是排除菜单，避免菜单事件被拦截
        if hasattr(self, 'menu'):
            self.menu.removeEventFilter(self)
        
        # 立即更新市场状态条，提高优先级
        self._update_market_status_immediately()
        
        # 启动时不再自动检查更新，仅保留手动检查功能
        # 注释掉原来的自动检查更新代码
        
        app_logger.info("主窗口初始化完成")
        app_logger.debug("主窗口UI组件初始化完成")

    def _update_market_status_immediately(self):
        """立即更新市场状态条，提高优先级"""
        # 在新线程中立即更新市场状态，避免阻塞UI
        update_thread = threading.Thread(target=self._immediate_market_status_update, daemon=True)
        update_thread.start()
        
    def _immediate_market_status_update(self):
        """立即更新市场状态的实现"""
        try:
            # 增加延迟，确保网络连接初始化完成
            time.sleep(2)
            # 直接调用市场状态条的更新方法
            self.market_status_bar.update_market_status()
        except Exception as e:
            app_logger.error(f"立即更新市场状态失败: {e}")
            
    def _check_for_updates(self):
        """检查应用更新"""
        def check_and_update():
            try:
                # 检查是否有新版本
                if app_updater.check_for_updates():
                    # 显示更新对话框
                    if app_updater.show_update_dialog(self):
                        # 下载更新
                        update_file = app_updater.download_update(self)
                        if update_file:
                            # 应用更新
                            result = app_updater.apply_update(update_file)
                            if result:
                                # 重启应用
                                QtWidgets.QMessageBox.information(
                                    self, 
                                    "更新完成", 
                                    "应用更新完成，即将重启应用。",
                                    QtWidgets.QMessageBox.Ok
                                )
                                # 重启应用
                                app_updater.restart_application()
                            else:
                                QtWidgets.QMessageBox.warning(
                                    self, 
                                    "更新失败", 
                                    "应用更新失败，请稍后重试或手动更新。",
                                    QtWidgets.QMessageBox.Ok
                                )
                        else:
                            QtWidgets.QMessageBox.warning(
                                self, 
                                "下载失败", 
                                "更新包下载失败，请检查网络连接后重试。",
                                QtWidgets.QMessageBox.Ok
                            )
            except Exception as e:
                app_logger.error(f"检查更新时发生错误: {e}")
                # 不向用户显示错误，避免干扰正常使用
        
        # 在单独的线程中检查更新，避免阻塞UI
        update_thread = threading.Thread(target=check_and_update, daemon=True)
        update_thread.start()

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
        
        Args:
            a0: 事件对象
            a1: 事件参数
            
        Returns:
            bool: 是否处理了事件
        """
        event = a1
        if event.type() == QtCore.QEvent.MouseButtonPress:  # type: ignore
            if event.button() == QtCore.Qt.LeftButton:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                frame_top_left = self.frameGeometry().topLeft()
                self.drag_position = QtCore.QPoint(cursor_pos.x() - frame_top_left.x(), 
                                                  cursor_pos.y() - frame_top_left.y())
                self.setCursor(QtCore.Qt.SizeAllCursor)  # type: ignore
                event.accept()
                return True
            elif event.button() == QtCore.Qt.RightButton:
                # 弹出右键菜单
                # 使用事件位置而非光标位置，避免菜单跟随鼠标移动
                click_pos = self.mapToGlobal(event.pos())
                self.menu.popup(click_pos)
                event.accept()
                return True
        elif event.type() == QtCore.QEvent.MouseMove:  # type: ignore
            if event.buttons() == QtCore.Qt.LeftButton and self.drag_position is not None:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                self.move(cursor_pos.x() - self.drag_position.x(), 
                         cursor_pos.y() - self.drag_position.y())
                event.accept()
                return True
        elif event.type() == QtCore.QEvent.MouseButtonRelease:  # type: ignore
            self.drag_position = None
            self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
            self.save_position()  # 拖动结束时自动保存位置
            event.accept()
            return True
        return super().eventFilter(a0, a1)

    def mousePressEvent(self, event):  # type: ignore
        """
        鼠标按下事件处理
        
        Args:
            event: 鼠标事件对象
        """
        # 所有鼠标按键事件都在eventFilter中统一处理，避免重复处理
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # type: ignore
        """
        鼠标移动事件处理
        
        Args:
            event: 鼠标事件对象
        """
        if event.buttons() == QtCore.Qt.LeftButton and self.drag_position is not None:  # type: ignore
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):  # type: ignore
        """
        鼠标释放事件处理
        
        Args:
            event: 鼠标事件对象
        """
        self.drag_position = None
        self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
        self.save_position()  # 拖动结束时自动保存位置

    def closeEvent(self, a0):  # type: ignore
        """
        窗口关闭事件处理
        
        Args:
            a0: 关闭事件对象
        """
        # 停止后台刷新线程
        if hasattr(self, 'refresh_worker'):
            self.refresh_worker.stop()
            
        self.save_position()
        super().closeEvent(a0)

    def save_position(self):
        """保存窗口位置到配置文件"""
        cfg = load_config()
        pos = self.pos()
        cfg['window_pos'] = [pos.x(), pos.y()]
        save_config(cfg)

    def load_position(self):
        """从配置文件加载窗口位置"""
        cfg = load_config()
        pos = cfg.get('window_pos')
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(pos[0], pos[1])
        else:
            self.move_to_bottom_right()

    def move_to_bottom_right(self):
        """将窗口移动到屏幕右下角"""
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()  # type: ignore
        self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 40)

    def open_settings(self):
        """打开设置对话框"""
        if self.settings_dialog is None:
            self.settings_dialog = NewSettingsDialog(self, main_window=self)
        else:
            # 断开所有可能的信号连接
            try:
                self.settings_dialog.config_changed.disconnect()
            except Exception:
                pass
        # 使用QueuedConnection避免阻塞UI
        self.settings_dialog.config_changed.connect(self.on_user_stocks_changed, QtCore.Qt.QueuedConnection)
        
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def on_user_stocks_changed(self, user_stocks, refresh_interval):
        """
        用户股票列表改变时的处理函数
        
        Args:
            user_stocks (list): 用户股票列表
            refresh_interval (int): 刷新间隔
        """
        app_logger.info(f"用户股票列表变更: {user_stocks}, 刷新间隔: {refresh_interval}")
        self.current_user_stocks = user_stocks
        self.refresh_interval = refresh_interval  # 关键：更新刷新间隔
        # 更新后台刷新线程的配置
        self.refresh_worker.update_stocks(user_stocks)
        self.refresh_worker.update_interval(refresh_interval)
        self.refresh_now(user_stocks)

    def process_stock_data(self, data, stocks_list):
        """
        处理股票数据，返回格式化的股票列表
        
        Args:
            data: 原始股票数据
            stocks_list: 股票列表
            
        Returns:
            list: 格式化后的股票数据列表
        """
        from stock_monitor.data.market.quotation import process_stock_data as quotation_process_stock_data
        return quotation_process_stock_data(data, stocks_list)

    def refresh_now(self, stocks_list=None):
        """
        立即刷新数据
        
        Args:
            stocks_list (list, optional): 股票列表
        """
        if stocks_list is None:
            stocks_list = self.current_user_stocks
        try:
            # 显示加载状态
            self.loading_label.show()
            self.table.hide()
            QtWidgets.QApplication.processEvents()
            
            # 使用股票管理器获取数据
            from stock_monitor.core.stock_manager import stock_manager
            stocks = stock_manager.get_stock_list_data(stocks_list)
            
            # 显示数据
            self.table.setRowCount(0)
            self.table.clearContents()
            self.table.update_data(stocks)  # type: ignore
            
            self.table.viewport().update()
            self.table.repaint()
            self.adjust_window_height()  # 每次刷新后自适应高度
            app_logger.info(f"数据刷新完成")
            
            # 隐藏加载状态
            self.loading_label.hide()
            self.table.show()
        except Exception as e:
            app_logger.error(f'行情刷新异常: {e}')
            # 显示错误信息
            error_stocks = [("数据加载异常", "--", "--", "#e6eaf3", "", "")] * max(3, len(stocks_list) if stocks_list else 3)
            self.table.setRowCount(0)
            self.table.clearContents()
            self.table.update_data(error_stocks)  # type: ignore
            self.table.viewport().update()
            self.table.repaint()
            self.adjust_window_height()
            
            # 隐藏加载状态
            self.loading_label.hide()
            self.table.show()

    def _on_refresh_update(self, stocks, all_failed=False):
        """
        刷新更新回调函数
        
        Args:
            stocks: 股票数据列表
            all_failed: 是否所有股票都获取失败
        """
        if all_failed:
            app_logger.error("所有股票数据获取失败")
            error_stocks = [("数据加载失败", "--", "--", "#e6eaf3", "", "")] * len(stocks)
            self.update_table_signal.emit(error_stocks)
        else:
            self.update_table_signal.emit(stocks)

    def _on_refresh_error(self):
        """刷新错误回调函数"""
        app_logger.error("连续多次刷新失败")
        error_stocks = [("网络连接异常", "--", "--", "#e6eaf3", "", "")] * max(3, len(self.current_user_stocks))
        self.update_table_signal.emit(error_stocks)
        
    def paintEvent(self, a0):  # type: ignore
        """
        绘制事件处理，用于绘制窗口背景
        
        Args:
            a0: 绘制事件对象
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)  # type: ignore
        rect = self.rect()
        bg_color = QtGui.QColor(30, 30, 30, 220)  # 降低透明度，更不透明
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.NoPen)  # type: ignore
        painter.drawRect(rect)

    def _update_database_on_startup(self):
        """在启动时更新数据库"""
        def update_database():
            try:
                app_logger.info("应用启动时更新股票数据库...")
                # 添加网络连接检查和延迟，确保网络就绪
                time.sleep(10)  # 增加到10秒等待网络连接初始化
                success = update_stock_database()
                if success:
                    app_logger.info("启动时股票数据库更新完成")
                else:
                    app_logger.warning("启动时股票数据库更新失败")
            except Exception as e:
                app_logger.error(f"启动时数据库更新出错: {e}")
        
        # 在后台线程中执行数据库更新，避免阻塞UI
        update_thread = threading.Thread(target=update_database, daemon=True)
        update_thread.start()

    def _start_database_update_thread(self):
        """启动数据库更新线程"""
        self._database_update_thread = threading.Thread(target=self._database_update_loop, daemon=True)
        self._database_update_thread.start()

    def _database_update_loop(self):
        """数据库更新循环 - 每天更新一次股票数据库"""
        # 等待应用启动完成
        time.sleep(10)
        
        # 启动后立即更新一次市场状态
        self.market_status_bar.update_market_status()
        
        while True:
            try:
                # 检查是否是凌晨时段（2:00-4:00之间）
                now = datetime.datetime.now()
                if now.hour >= 2 and now.hour < 4:
                    app_logger.info("开始更新股票数据库...")
                    success = update_stock_database()
                    if success:
                        app_logger.info("股票数据库更新完成")
                        # 数据库更新完成后，更新市场状态
                        self.market_status_bar.update_market_status()
                    else:
                        app_logger.warning("股票数据库更新失败")
                    
                    # 等待到明天同一时间
                    tomorrow = now + datetime.timedelta(days=1)
                    tomorrow_update = tomorrow.replace(hour=3, minute=0, second=0, microsecond=0)
                    sleep_seconds = (tomorrow_update - now).total_seconds()
                    time.sleep(sleep_seconds)
                else:
                    # 每30秒更新一次市场状态
                    time.sleep(30)
                    self.market_status_bar.update_market_status()
            except Exception as e:
                app_logger.error(f"数据库更新循环出错: {e}")
                time.sleep(3600)  # 出错后等待1小时再重试

    def load_user_stocks(self):
        """
        加载用户自选股列表，包含完整的错误处理和格式规范化
        
        Returns:
            list: 用户股票列表
        """
        try:
            cfg = load_config()
            stocks = cfg.get('user_stocks', None)
            
            # 确保stocks是一个列表
            if not isinstance(stocks, list):
                app_logger.warning("配置文件中未找到有效的用户股票列表，使用默认值")
                stocks = []
            
            # 使用统一的工具函数处理股票代码提取
            from stock_monitor.utils import extract_stocks_from_list
            processed_stocks = extract_stocks_from_list(stocks)
            
            return processed_stocks
            
        except Exception as e:
            app_logger.error(f"加载用户股票列表时发生严重错误: {e}")
            # 返回空列表
            return []

    def _format_stock_code(self, code):
        """
        格式化股票代码，确保正确的前缀
        
        Args:
            code (str): 股票代码
            
        Returns:
            str: 格式化后的股票代码
        """
        # 使用工具函数处理股票代码格式化
        from stock_monitor.utils.stock_utils import StockCodeProcessor
        processor = StockCodeProcessor()
        return processor.format_stock_code(code)

    def load_theme_config(self):
        """
        加载主题配置
        
        Returns:
            dict: 主题配置字典
        """
        import json
        try:
            with open(resource_path("theme_config.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def adjust_window_height(self):
        """
        根据内容调整窗口高度和宽度
        """
        # 用真实行高自适应主窗口高度
        QtWidgets.QApplication.processEvents()
        vh = self.table.verticalHeader()
        if self.table.rowCount() > 0:
            row_height = vh.sectionSize(0)
        else:
            row_height = 36  # 默认
        layout_margin = 0  # 边距设为0
        table_height = self.table.rowCount() * row_height
        # 增加表头高度（4列时略增）
        new_height = table_height + layout_margin + self.market_status_bar.height()
        self.setFixedHeight(new_height)
        
        # 更精确地计算表格宽度
        table_width = sum(self.table.columnWidth(col) for col in range(self.table.columnCount()))
        self.setFixedWidth(table_width)
        
        # 强制更新布局
        self.layout().update()
        
        # 更新窗口几何形状
        self.updateGeometry()

class SystemTray(QtWidgets.QSystemTrayIcon):
    """
    系统托盘类
    负责处理系统托盘图标和相关菜单
    """
    def __init__(self, main_window):
        icon = QtGui.QIcon(ICON_FILE) if os.path.exists(ICON_FILE) else QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)  # type: ignore
        super().__init__(icon)
        self.main_window = main_window
        self.menu = QtWidgets.QMenu()
        self.action_settings = self.menu.addAction('设置')
        self.action_quit = self.menu.addAction('退出')
        self.setContextMenu(self.menu)
        self.action_settings.triggered.connect(self.open_settings)  # type: ignore
        self.action_quit.triggered.connect(QtWidgets.QApplication.quit)  # type: ignore
        self.activated.connect(self.on_activated)  # type: ignore


    def open_settings(self):
        """打开设置窗口"""
        self.main_window.open_settings()

    def on_activated(self, reason):
        """
        托盘图标激活事件处理
        
        Args:
            reason: 激活原因
        """
        if reason == QtWidgets.QSystemTrayIcon.Trigger:  # type: ignore
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        elif reason == QtWidgets.QSystemTrayIcon.Context:  # type: ignore
            self.contextMenu().exec_(QtGui.QCursor.pos())  # type: ignore

def clean_temp_files():
    """清理更新过程中产生的临时文件"""
    try:
        from stock_monitor.utils.logger import app_logger
        
        # 获取当前目录 - 确保始终使用程序所在目录
        if hasattr(sys, '_MEIPASS'):
            # 打包环境 - 使用可执行文件所在目录
            current_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境或普通生产环境 - 使用main.py所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 查找并删除所有的 .tmp 文件
        for filename in os.listdir(current_dir):
            if filename.endswith('.tmp'):
                tmp_file = os.path.join(current_dir, filename)
                try:
                    os.remove(tmp_file)
                    app_logger.info(f"已清理临时文件: {tmp_file}")
                except Exception as e:
                    app_logger.warning(f"无法删除临时文件 {tmp_file}: {e}")
                    
        # 检查并删除更新标记文件
        update_marker = os.path.join(current_dir, 'update_pending')
        if os.path.exists(update_marker):
            try:
                os.remove(update_marker)
                app_logger.info("已清理更新标记文件")
            except Exception as e:
                app_logger.warning(f"无法删除更新标记文件: {e}")
    except Exception as e:
        # 这里不能使用app_logger，因为它可能还未初始化
        print(f"清理临时文件时出错: {e}")

def main():
    """主函数"""
    # 清理更新过程中产生的临时文件
    clean_temp_files()
    
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    tray = SystemTray(main_window)
    tray.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()