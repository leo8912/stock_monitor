"""
股票监控主程序
用于监控A股股票实时行情
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import threading
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import pyqtSignal, pyqtSlot

# 设置高DPI缩放策略
QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

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
from stock_monitor.utils.stock_utils import StockCodeProcessor
from stock_monitor.utils.log_cleaner import schedule_log_cleanup
from stock_monitor.core.updater import app_updater

# 依赖注入容器
from stock_monitor.core.container import container, DIContainer

ICON_FILE = resource_path('icon.ico')  # 统一使用ICO格式图标

# 修改导入语句，使用设置对话框
from stock_monitor.ui.dialogs.settings_dialog import NewSettingsDialog
from stock_monitor.ui.components.stock_table import StockTable
from stock_monitor.ui.widgets.context_menu import AppContextMenu

# 导入后台刷新工作线程
from stock_monitor.core.refresh_worker import RefreshWorker

# 定义透明度计算相关的常量
MIN_BACKGROUND_ALPHA = 200
MAX_BACKGROUND_ALPHA = 255
ALPHA_RANGE = MAX_BACKGROUND_ALPHA - MIN_BACKGROUND_ALPHA

class MainWindow(QtWidgets.QWidget):
    """
    主窗口类
    负责显示股票行情、处理用户交互和管理应用状态
    """
    update_table_signal = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        # 初始化依赖注入容器
        self._container = container
        self.setup_ui()
        # 尝试加载会话缓存
        if not self._try_load_session_cache():
            # 如果没有加载到缓存，则隐藏窗口直到数据加载完成
            self.hide()
        # 移除这里重复的初始化和刷新调用
        # self.current_user_stocks = []
        # self.refresh_interval = 2
        # self.setup_refresh_worker()
        # 移除自动检查更新功能，只在设置中提供手动检查更新选项

    def setup_ui(self):
        """设置主窗口UI"""
        self._setup_window_properties()
        self._setup_ui_components()
        self._setup_event_handlers()
        
    def _setup_window_properties(self):
        """设置窗口属性"""
        self.setWindowTitle('A股行情监控')
        self.setWindowFlags(
            QtCore.Qt.WindowType.WindowStaysOnTopHint |  # type: ignore
            QtCore.Qt.WindowType.FramelessWindowHint |  # type: ignore
            QtCore.Qt.WindowType.Tool |  # type: ignore
            QtCore.Qt.WindowType.WindowMaximizeButtonHint  # type: ignore
        )  # type: ignore
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)  # type: ignore
        self.resize(320, 160)
        self.drag_position = None
        
        # 设置窗口图标
        icon_path = resource_path('icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        
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
        from stock_monitor.config.manager import ConfigManager
        config_manager = self._container.get(ConfigManager)
        font_size = config_manager.get("font_size", 13)  # 默认13px
        font_family = config_manager.get("font_family", "微软雅黑")  # 默认微软雅黑
        
        # 确保字体大小大于0
        if font_size <= 0:
            font_size = 13  # 默认字体大小
            
        font = QtGui.QFont(font_family, font_size)
        self.setFont(font)
        # 只设置主窗口本身的字体，不使用全局样式表影响子控件
        self.setStyleSheet(f'font-family: "{font_family}"; font-size: {font_size}px;')
        
        # 初始化菜单
        # 创建右键菜单，使用独立的菜单类确保样式不会被其他界面影响
        self.menu = AppContextMenu(self)
        self.action_settings = self.menu.addAction('设置')
        self.menu.addSeparator()
        self.action_quit = self.menu.addAction('退出')
        if self.action_settings is not None:
            self.action_settings.triggered.connect(self.open_settings)
        if self.action_quit is not None:
            self.action_quit.triggered.connect(self.quit_application)
        
        # 确保菜单项连接正确，避免功能不稳定
        if self.action_settings is not None:
            self.action_settings.setMenuRole(QtGui.QAction.MenuRole.ApplicationSpecificRole)
        if self.action_quit is not None:
            self.action_quit.setMenuRole(QtGui.QAction.MenuRole.ApplicationSpecificRole)
        
        # 初始化数据
        self.settings_dialog = None
        from stock_monitor.utils.helpers import get_config_manager
        config_manager = get_config_manager()
        self.refresh_interval = config_manager.get('refresh_interval', 5)
        self.current_user_stocks = self.load_user_stocks()
        
        # 初始化后台刷新工作线程
        self.refresh_worker = RefreshWorker(
            update_callback=self._on_refresh_update,
            error_callback=self._on_refresh_error
        )
        
        # 加载状态指示器，初始隐藏
        self.loading_label = QtWidgets.QLabel("⏳ 数据加载中...")
        self.loading_label.setStyleSheet(f"""
            QLabel {{
                color: #fff;
                font-size: {font_size}px;
                background: rgba(30, 30, 30, 0.8);
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        self.loading_label.hide()
        layout.addWidget(self.loading_label)
        
        app_logger.info(f"初始化配置: 刷新间隔={self.refresh_interval}, 自选股={self.current_user_stocks}")
        
        # 启动刷新线程和信号连接
        self.update_table_signal.connect(self.table.update_data)  # type: ignore
        
        # 启动后台刷新线程
        self.refresh_worker.start(self.current_user_stocks, self.refresh_interval)
        
        # 启动时立即更新一次数据库
        self._update_database_on_startup()
        
        # 不再在这里显示窗口，而是在_try_load_session_cache或_on_refresh_update中显示
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
        
    def _setup_event_handlers(self):
        """设置事件处理器"""
        # 这里可以添加事件处理器的设置
        pass

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
            
    def setup_refresh_worker(self):
        """设置刷新工作线程"""
        # 启动后台刷新线程
        self.refresh_worker.start(self.current_user_stocks, self.refresh_interval)
        
        # 启动后立即刷新一次数据，确保界面显示
        self.refresh_now()
    
    def _on_refresh_error(self):
        """刷新错误回调函数"""
        try:
            # 显示错误信息到状态栏
            self.status_label.setText("❌ 数据刷新失败")
            app_logger.error("行情数据刷新失败")
            
            # 即使出错也要显示窗口，避免一直隐藏
            if not self.isVisible():
                self.show()
                self.load_position()
                self.raise_()
                self.activateWindow()
        except Exception as e:
            app_logger.error(f"处理刷新错误时出错: {e}")

    def _try_show_cached_data(self):
        """尝试显示缓存的数据以加快启动速度"""
        try:
            from stock_monitor.utils.cache import cache_get
            cached_data = cache_get("last_stock_data")
            if cached_data:
                # 显示缓存数据
                self.update_table_signal.emit(cached_data)
                # 显示窗口
                self.show()
                self.load_position()
                self.raise_()
                self.activateWindow()
                app_logger.info("使用缓存数据快速启动界面")
        except Exception as e:
            app_logger.warning(f"加载缓存数据失败: {e}")

    def _try_load_session_cache(self):
        """尝试加载会话缓存以加快启动速度"""
        try:
            from stock_monitor.utils.session_cache import load_session_cache
            cached_session = load_session_cache()
            if cached_session:
                # 恢复窗口位置
                pos = cached_session.get('window_position')
                if pos and isinstance(pos, list) and len(pos) == 2:
                    self.move(pos[0], pos[1])
                
                # 显示缓存的股票数据
                stock_data = cached_session.get('stock_data')
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
        return False

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
        if event is not None and event.type() == QtCore.QEvent.Type.MouseButtonPress:  # type: ignore
            if event.button() == QtCore.Qt.MouseButton.LeftButton:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                frame_top_left = self.frameGeometry().topLeft()
                self.drag_position = QtCore.QPoint(cursor_pos.x() - frame_top_left.x(), 
                                                  cursor_pos.y() - frame_top_left.y())
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)  # type: ignore
                event.accept()
                return True
            elif event.button() == QtCore.Qt.MouseButton.RightButton:
                # 弹出右键菜单
                # 使用事件位置而非光标位置，避免菜单跟随鼠标移动
                click_pos = self.mapToGlobal(event.pos())
                self.menu.popup(click_pos)
                event.accept()
                return True
        elif event is not None and event.type() == QtCore.QEvent.Type.MouseMove:  # type: ignore
            if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                self.move(cursor_pos.x() - self.drag_position.x(), 
                         cursor_pos.y() - self.drag_position.y())
                event.accept()
                return True
        elif event is not None and event.type() == QtCore.QEvent.Type.MouseButtonRelease:  # type: ignore
            self.drag_position = None
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)  # type: ignore
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
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:  # type: ignore
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):  # type: ignore
        """
        鼠标释放事件处理
        
        Args:
            event: 鼠标事件对象
        """
        self.drag_position = None
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)  # type: ignore
        self.save_position()  # 拖动结束时自动保存位置

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 保存窗口位置
        self.save_position()
        # 隐藏窗口而不是真正关闭
        self.hide()
        event.ignore()  # 忽略关闭事件，使应用程序继续运行

    def save_position(self):
        """保存窗口位置到配置文件"""
        pos = self.pos()
        from stock_monitor.config.manager import ConfigManager
        config_manager = self._container.get(ConfigManager)
        config_manager.set('window_pos', [pos.x(), pos.y()])
        
    def load_position(self):
        """从配置文件加载窗口位置"""
        from stock_monitor.config.manager import ConfigManager
        config_manager = self._container.get(ConfigManager)
        pos = config_manager.get('window_pos')
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
            self.settings_dialog = NewSettingsDialog(main_window=self)  # 不再将主窗口作为父窗口
            # 连接配置更改信号
            self.settings_dialog.config_changed.connect(self.on_config_changed)
        self.settings_dialog.show()

    def quit_application(self):
        """退出应用程序"""
        # 保存会话缓存
        try:
            from stock_monitor.utils.session_cache import save_session_cache
            # 获取当前窗口位置和股票数据
            session_data = {
                'window_position': [self.x(), self.y()],
                'stock_data': self._get_current_stock_data()
            }
            save_session_cache(session_data)
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.warning(f"保存会话缓存失败: {e}")
        
        # 隐藏主窗口
        self.hide()
        
        # 隐藏系统托盘图标
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
        
        # 退出应用程序
        QtWidgets.QApplication.quit()
        
    def _get_current_stock_data(self):
        """
        获取当前显示的股票数据
        
        Returns:
            list: 当前显示的股票数据列表
        """
        try:
            # 从表格中获取当前显示的数据
            if hasattr(self, 'table') and self.table:
                # 获取表格的行数
                row_count = self.table.rowCount()
                stock_data = []
                
                # 遍历每一行，提取股票数据
                for row in range(row_count):
                    stock_item = []
                    # 遍历每一列
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            stock_item.append(item.text())
                        else:
                            stock_item.append("")
                    
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
                        if change_str.endswith('%'):
                            change_str = change_str[:-1]  # 去除%符号
                        stock_item[2] = change_str.strip()  # 再次去除可能的空格
                    
                    # 添加颜色信息（第4列）- 从前台颜色获取
                    if len(stock_item) >= 4:
                        # 获取单元格的前台颜色（文字颜色）
                        item = self.table.item(row, 0)
                        if item:
                            fg_color = item.foreground().color().name()
                            stock_item[3] = fg_color
                    
                    stock_data.append(stock_item)
                
                return stock_data
            
            # 如果无法从表格获取数据，返回空列表
            return []
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.warning(f"获取当前股票数据失败: {e}")
            return []
        
    def on_config_changed(self, stocks, refresh_interval):
        """
        当配置更改时的处理函数
        
        Args:
            stocks: 股票列表
            refresh_interval: 刷新间隔
        """
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
            from stock_monitor.config.manager import ConfigManager
            config_manager = self._container.get(ConfigManager)
            font_size = config_manager.get("font_size", 13)  # 默认13px
            font_family = config_manager.get("font_family", "微软雅黑")  # 默认微软雅黑            
            # 确保字体大小大于0
            if font_size <= 0:
                font_size = 13  # 默认字体大小
            
            # 更新主窗口字体
            font = QtGui.QFont(font_family, font_size)
            self.setFont(font)
            # 只设置主窗口本身的字体，不使用全局样式表影响子控件
            self.setStyleSheet(f'font-family: "{font_family}"; font-size: {font_size}px;')
            
            # 更新表格字体
            if hasattr(self, 'table') and self.table:
                self.table.setStyleSheet(f'''
                    QTableWidget {{
                        background: transparent;
                        border: none;
                        outline: none;
                        gridline-color: #aaa;
                        selection-background-color: transparent;
                        selection-color: #fff;
                        font-family: "{font_family}";
                        font-size: {font_size}px;
                        font-weight: bold;
                        color: #fff;
                    }}
                    QTableWidget::item {{
                        border: none;
                        padding: 0px;
                        background: transparent;
                    }}
                    QTableWidget::item:selected {{
                        background: transparent;
                        color: #fff;
                    }}
                    QHeaderView::section {{
                        background: transparent;
                        border: none;
                        color: transparent;
                    }}
                    QScrollBar {{
                        background: transparent;
                        width: 0px;
                        height: 0px;
                    }}
                    QScrollBar::handle {{
                        background: transparent;
                    }}
                    QScrollBar::add-line, QScrollBar::sub-line {{
                        background: transparent;
                        border: none;
                    }}
                ''')

            # 更新加载标签字体
            if hasattr(self, 'loading_label') and self.loading_label:
                self.loading_label.setStyleSheet(f"""
                    QLabel {{
                        color: #fff;
                        font-size: {max(1, font_size)}px;  # 确保字体大小至少为1
                        background: rgba(30, 30, 30, 0.8);
                        border-radius: 10px;
                        padding: 10px;
                    }}
                """)

            # 调整主窗口高度
            self.adjust_window_height()
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"更新主窗口字体大小失败: {e}")

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

    def _on_refresh_update(self, data, all_failed=False):
        """
        刷新更新回调函数
        当后台线程获取到新数据时调用此函数更新UI
        
        Args:
            data: 股票数据列表
            all_failed: 是否所有股票都获取失败
        """
        try:
            # 更新表格数据
            self.update_table_signal.emit(data)
            
            # 显示窗口和所有组件
            if not self.isVisible():
                self.show()
                self.load_position()
                self.raise_()
                self.activateWindow()
            
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
                    'window_position': [self.pos().x(), self.pos().y()],
                    'stock_data': data
                }
                save_session_cache(session_data)
                app_logger.info("会话缓存保存成功")
            except Exception as e:
                app_logger.warning(f"保存会话缓存失败: {e}")
        except Exception as e:
            app_logger.error(f"刷新更新处理失败: {e}")
            
    def _on_refresh_error(self):
        """刷新错误回调函数"""
        app_logger.error("连续多次刷新失败")
        error_stocks = [("网络连接异常", "--", "--", "#e6eaf3", "", "")] * max(3, len(self.current_user_stocks))
        self.update_table_signal.emit(error_stocks)
        
    def paintEvent(self, event):
        """
        窗口绘制事件，用于绘制半透明背景
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)  # type: ignore
        rect = self.rect()
        # 从配置中读取透明度设置
        from stock_monitor.config.manager import ConfigManager
        config_manager = self._container.get(ConfigManager)
        transparency = config_manager.get("transparency", 80)
        # 在实时预览时，使用滑块的当前值
        if hasattr(self, '_preview_transparency'):
            transparency = self._preview_transparency
            
        # 将透明度值(0-100)转换为alpha值(0-255)
        # 0%透明度对应200 alpha(较透明)，100%透明度对应255 alpha(最不透明)
        alpha = int(MIN_BACKGROUND_ALPHA + (ALPHA_RANGE * transparency / 100))
        # 确保alpha值在有效范围内
        alpha = max(MIN_BACKGROUND_ALPHA, min(MAX_BACKGROUND_ALPHA, alpha))
        bg_color = QtGui.QColor(30, 30, 30, alpha)
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)  # type: ignore
        painter.drawRect(rect)

    def _update_database_on_startup(self):
        """启动时更新数据库"""
        try:
            # 使用依赖注入容器获取配置管理器
            from stock_monitor.config.manager import ConfigManager
            config_manager = self._container.get(ConfigManager)
            last_update = config_manager.get('last_db_update', 0)
            current_time = time.time()
            
            # 检查是否超过24小时未更新，或者从未更新过
            if current_time - last_update > 86400 or last_update == 0:
                # 在新线程中更新数据库，避免阻塞UI
                self._update_database_async()
                # 更新配置中的最后更新时间
                config_manager.set('last_db_update', current_time)
                app_logger.info("启动时数据库更新已启动")
            else:
                app_logger.debug("启动时数据库更新检查: 距离上次更新不足24小时，跳过更新")
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

    def load_user_stocks(self):
        """加载用户自选股列表"""
        try:
            # 使用依赖注入容器获取配置管理器
            from stock_monitor.config.manager import ConfigManager
            config_manager = self._container.get(ConfigManager)
            stocks = config_manager.get('user_stocks', [])
            app_logger.info(f"加载自选股列表: {stocks}")
            return stocks
        except Exception as e:
            app_logger.error(f"加载自选股列表失败: {e}")
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

    def _update_database_if_needed(self):
        """根据更新时间判断是否需要更新数据库"""
        try:
            # 使用工具函数获取配置管理器
            from stock_monitor.utils.helpers import get_config_manager
            config_manager = get_config_manager()
            last_update = config_manager.get('last_db_update', 0)
            current_time = time.time()
            
            # 检查是否超过24小时(86400秒)未更新
            if current_time - last_update > 86400:
                self._update_database_async()
                # 更新配置中的最后更新时间
                config_manager.set('last_db_update', current_time)
                app_logger.info("数据库更新检查完成并启动更新")
            else:
                app_logger.debug("数据库更新检查: 距离上次更新不足24小时，跳过更新")
        except Exception as e:
            app_logger.error(f"数据库更新检查失败: {e}")

    def _update_database_async(self):
        """异步更新数据库"""
        try:
            from stock_monitor.data.market.updater import update_stock_database
            update_thread = threading.Thread(target=update_stock_database, daemon=True)
            update_thread.start()
        except Exception as e:
            app_logger.error(f"异步更新数据库时出错: {e}")

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
        self.action_quit.triggered.connect(self.quit_application)  # type: ignore
        self.activated.connect(self.on_activated)  # type: ignore
        # 添加一个状态消息，告知用户程序正在加载数据
        self.showMessage("A股行情监控", "程序正在后台加载数据，请稍候...", 
                         QtWidgets.QSystemTrayIcon.MessageIcon.Information, 3000)

    def open_settings(self):
        """打开设置窗口"""
        self.main_window.open_settings()
        
    def quit_application(self):
        """退出应用程序"""
        # 调用主窗口的退出方法
        self.main_window.quit_application()
        
    def on_activated(self, reason):
        """
        托盘图标激活事件处理
        
        Args:
            reason: 激活原因
        """
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        elif reason == QtWidgets.QSystemTrayIcon.ActivationReason.Context:
            self.contextMenu().popup(QtGui.QCursor.pos())

def apply_pending_updates():
    """在应用启动时应用待处理的更新"""
    try:
        from stock_monitor.utils.logger import app_logger
        from stock_monitor.core.updater import app_updater
        
        # 获取当前目录 - 确保始终使用程序所在目录
        if hasattr(sys, '_MEIPASS'):
            # 打包环境 - 使用可执行文件所在目录
            current_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境或普通生产环境 - 使用main.py所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 检查更新标记文件
        update_marker = os.path.join(current_dir, 'update_pending')
        if os.path.exists(update_marker):
            try:
                # 读取更新文件路径
                with open(update_marker, 'r') as f:
                    update_file_path = f.read().strip()
                # 删除标记文件
                os.remove(update_marker)
                app_logger.info("检测到待处理的更新，正在应用...")
                # 应用更新，跳过锁定检查
                if app_updater.apply_update(update_file_path, skip_lock_check=True):
                    app_logger.info("更新应用完成")
                else:
                    app_logger.error("更新应用失败")
            except Exception as e:
                app_logger.error(f"应用待处理更新时出错: {e}")
                
        # 查找并删除所有的 .tmp 文件
        for filename in os.listdir(current_dir):
            if filename.endswith('.tmp'):
                tmp_file = os.path.join(current_dir, filename)
                try:
                    os.remove(tmp_file)
                    app_logger.info(f"已清理临时文件: {tmp_file}")
                except Exception as e:
                    app_logger.warning(f"无法删除临时文件 {tmp_file}: {e}")
    except Exception as e:
        # 这里不能使用app_logger，因为它可能还未初始化
        print(f"应用待处理更新时出错: {e}")

def main():
    """主函数"""
    try:
        app = QtWidgets.QApplication(sys.argv)
        
        # 设置应用图标
        icon_path = resource_path('icon.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QtGui.QIcon(icon_path))
        
        # 初始化数据库
        try:
            from stock_monitor.utils.db_initializer import initialize_database
            initialize_database()
        except Exception as e:
            app_logger.error(f"数据库初始化失败: {e}")
        
        # 初始化配置管理器
        from stock_monitor.config.manager import ConfigManager
        config_manager = ConfigManager()
        
        # 初始化股票服务
        from stock_monitor.core.stock_service import StockDataService
        stock_service = StockDataService()
        
        # 初始化股票管理器
        from stock_monitor.core.stock_manager import StockManager
        stock_manager = StockManager()
        
        # 初始化行情数据获取器
        from stock_monitor.data.market.quotation import get_quotation_engine
        quotation_engine = get_quotation_engine()
        if quotation_engine is None:
            app_logger.error("无法初始化行情引擎")
            sys.exit(1)
        
        # 创建主窗口
        from stock_monitor.ui.widgets.market_status import MarketStatusBar
        window = MainWindow()
        
        # 创建系统托盘图标
        tray_icon = SystemTray(window)
        tray_icon.show()
        # 保存托盘图标引用到主窗口
        window.tray_icon = tray_icon
        
        # 设置开机自启动
        _setup_auto_start()
        
        # 不再在这里显示窗口，而是等数据加载完成后再显示
        
        # 启动预加载调度器
        try:
            from stock_monitor.data.market.updater import start_preload_scheduler
            start_preload_scheduler()
        except Exception as e:
            app_logger.error(f"启动预加载调度器失败: {e}")
        
        # 运行应用
        sys.exit(app.exec())
        
    except Exception as e:
        app_logger.critical(f"应用程序启动失败: {e}")
        import traceback
        app_logger.critical(f"详细错误信息: {traceback.format_exc()}")
        sys.exit(1)


def _setup_auto_start():
    """
    设置开机自启动功能
    通过在用户启动文件夹中创建/删除快捷方式实现
    """
    try:
        from stock_monitor.config.manager import ConfigManager
        from stock_monitor.utils.logger import app_logger
        import os
        import sys
        
        # 获取配置
        config_manager = ConfigManager()
        auto_start = config_manager.get("auto_start", False)
        
        # 获取启动文件夹路径
        startup_folder = os.path.join(
            os.environ.get('APPDATA', ''),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        
        # 检查启动文件夹是否存在
        if not os.path.exists(startup_folder):
            app_logger.warning(f"启动文件夹不存在: {startup_folder}")
            return
            
        shortcut_path = os.path.join(startup_folder, 'StockMonitor.lnk')
        
        # 如果启用开机启动
        if auto_start:
            # 获取应用程序路径
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller打包环境
                app_path = sys.executable
            else:
                # 开发环境
                app_path = os.path.abspath(sys.argv[0])
            
            # 创建快捷方式
            _create_shortcut(app_path, shortcut_path)
            app_logger.info(f"已创建开机启动快捷方式: {shortcut_path}")
        else:
            # 如果禁用开机启动且快捷方式存在，则删除
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                app_logger.info(f"已删除开机启动快捷方式: {shortcut_path}")
    except Exception as e:
        from stock_monitor.utils.logger import app_logger
        app_logger.error(f"设置开机启动失败: {e}")


def _create_shortcut(target_path, shortcut_path):
    """
    创建快捷方式
    
    Args:
        target_path (str): 目标文件路径
        shortcut_path (str): 快捷方式保存路径
    """
    try:
        # 尝试使用win32com创建快捷方式
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.IconLocation = target_path
        shortcut.save()
    except ImportError:
        # win32com不可用时的备选方案
        try:
            # 尝试只使用内置模块
            import shutil
            if target_path.endswith('.py'):
                # 如果是Python脚本，创建批处理文件
                batch_content = f'@echo off\npython "{target_path}"\n'
                batch_path = shortcut_path.replace('.lnk', '.bat')
                with open(batch_path, 'w') as f:
                    f.write(batch_content)
            else:
                # 如果是exe文件，直接复制
                shutil.copy2(target_path, shortcut_path.replace('.lnk', '.exe'))
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"创建快捷方式失败: {e}")


if __name__ == '__main__':
    main()
