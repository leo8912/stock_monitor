"""
设置对话框模块
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QLineEdit, QLabel, QWidget, QCheckBox,
                             QComboBox, QAbstractItemView, QGroupBox, QFormLayout,
                             QSpinBox, QSlider, QGridLayout, QRadioButton, QButtonGroup,
                             QApplication)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon, QColor
import easyquotation
import os
import ctypes
from typing import Dict, Any
from stock_monitor.utils.helpers import resource_path  # 导入获取配置文件路径的工具函数
from stock_monitor.version import __version__  # 导入版本号


def _safe_bool_conversion(value, default=False):
    """安全地将值转换为布尔值"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == 'true'
    return default


def _safe_int_conversion(value, default=0):
    """安全地将值转换为整数"""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return default


class DraggableListWidget(QListWidget):
    """支持拖拽排序的列表控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        
        
class NewSettingsDialog(QDialog):
    """设置对话框类"""
    
    # 定义设置更改信号
    settings_changed = pyqtSignal()
    # 定义配置更改信号，参数为股票列表和刷新间隔
    config_changed = pyqtSignal(list, int)
    
    def __init__(self, parent=None, main_window=None):
        """初始化设置对话框"""
        super().__init__(parent)
        # 保存主窗口引用
        self.main_window = main_window
        
        # 设置窗口图标
        icon_path = resource_path('icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 移除右上角的问号帮助按钮，只保留关闭按钮
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowContextHelpButtonHint
        self.setWindowFlags(Qt.WindowFlags(flags))  # type: ignore
        
        # 设置窗口样式以匹配暗色主题
        self.setStyleSheet("QDialog { background-color: #1e1e1e; } ")
        
        # 在Windows上设置标题栏颜色
        try:
            import platform
            if platform.system() == "Windows":
                # Windows 10/11 暗色模式支持
                import ctypes
                from ctypes import c_int, c_uint, c_char_p, POINTER, windll
                # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                hwnd = self.winId().__int__()
                value = c_int(1)  # 启用暗色模式
                windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            # 忽略DWM API调用异常
            pass
        
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("设置")
        self.setFixedSize(1400, 900)  # 增大窗口尺寸以适应更多内容
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: white;
                font-family: 'Microsoft YaHei';
                font-size: 20px;
            }
            /* 标题栏样式 */
            QTitleBar {
                background-color: #1e1e1e;
                color: white;
            }
            QTitleBar QLabel {
                color: white;
            }
            QTitleBar QToolButton {
                background-color: transparent;
                border: none;
                color: white;
            }
            QTitleBar QToolButton:hover {
                background-color: #3d3d3d;
            }
            QTitleBar QToolButton:pressed {
                background-color: #0078d4;
            }
            
            /* Windows 标题栏按钮样式 */
            QMenuBar::item {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
                font-size: 20px;
                margin-bottom: 5px;
                font-family: 'Microsoft YaHei';
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 20px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 20px;
                outline: 0;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QCheckBox {
                color: white;
                font-family: 'Microsoft YaHei';
                font-size: 19px;
                spacing: 5px;
                min-height: 22px;
                padding: 2px 0;
                alignment: center;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;  /* 圆形复选框 */
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #0078d4;
                background-color: #0078d4;
            }
            QCheckBox:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 2px 4px;
                font-family: 'Microsoft YaHei';
                font-size: 19px;
                min-height: 22px;
                alignment: center;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox:hover {
                border: 1px solid #0078d4;
            }
            QComboBox:focus {
                border: 1px solid #0078d4;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                selection-background-color: #0078d4;
                text-align: center;
                padding: 2px 4px;
            }
            QSpinBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 2px 4px;
                font-family: 'Microsoft YaHei';
                font-size: 20px;
                min-height: 22px;
            }
            QSpinBox:hover {
                border: 1px solid #0078d4;
            }
            QSpinBox:focus {
                border: 1px solid #0078d4;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #555555;
                width: 18px;
                height: 18px;
                border-radius: 9px;
                margin: -6px 0;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;  /* 增大按钮内边距使视觉更平衡 */
                font-family: 'Microsoft YaHei';
                font-size: 20px;
                min-width: 0px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QPushButton#cancelButton {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                padding: 4px 8px;  /* 增大按钮内边距使视觉更平衡 */
                min-height: 22px;
            }
            QPushButton#cancelButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton#checkUpdateButton {
                min-width: 0px;
                min-height: 22px;
                padding: 4px 8px;  /* 增大按钮内边距使视觉更平衡 */
            }
            QGroupBox {
                font-family: 'Microsoft YaHei';
                font-size: 22px;
                font-weight: bold;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 1ex;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
            QScrollBar:vertical {
                background: #2d2d2d;
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: none;
            }
            /* 标题栏样式 */
            QMenuBar {
                background-color: #1e1e1e;
                color: white;
                border: none;
            }
            QMenuBar::item {
                background-color: #1e1e1e;
                color: white;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background-color: #3d3d3d;
            }
            QMenuBar::item:pressed {
                background-color: #0078d4;
            }
            QToolBar {
                background-color: #1e1e1e;
                border: none;
            }
            /* 标题栏按钮样式 */
            QToolButton {
                background-color: transparent;
                border: none;
                color: white;
            }
            QToolButton:hover {
                background-color: #3d3d3d;
            }
            QToolButton:pressed {
                background-color: #0078d4;
            }
        """)
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 0)  # 最大限度减小底部边距
        main_layout.setSpacing(10)  # 减少间距到10px
        self.setLayout(main_layout)
        
        # 创建自选股管理组
        watchlist_group = QGroupBox("自选股管理")
        watchlist_layout = QHBoxLayout()
        watchlist_layout.setContentsMargins(10, 10, 10, 10)
        watchlist_layout.setSpacing(15)
        watchlist_group.setLayout(watchlist_layout)
        
        # 左侧区域 - 搜索添加自选股
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        # 搜索框
        search_label = QLabel("搜索股票")
        search_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入股票代码或名称...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self._on_search_return_pressed)
        
        left_layout.addWidget(search_label)
        left_layout.addWidget(self.search_input)
        
        # 搜索结果列表
        self.search_results = QListWidget()
        # 样式已在全局样式表中定义
        self.search_results.itemDoubleClicked.connect(self.add_to_watchlist)
        search_results_label = QLabel("搜索结果 (双击添加)")
        search_results_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        left_layout.addWidget(search_results_label)
        left_layout.addWidget(self.search_results)
        
        # 右侧区域 - 已添加自选股列表
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # 创建包含标签和按钮的水平布局
        watchlist_header_layout = QHBoxLayout()
        watchlist_header_layout.setContentsMargins(0, 0, 0, 0)
        watchlist_header_layout.setSpacing(4)
        
        watchlist_label = QLabel("自选股列表 (拖拽排序)")
        watchlist_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)  # type: ignore
        
        # 添加删除按钮
        self.remove_button = QPushButton("删除选中")
        self.remove_button.setFixedWidth(120)
        self.remove_button.clicked.connect(self.remove_selected_stocks)
        
        watchlist_header_layout.addWidget(watchlist_label)
        watchlist_header_layout.addStretch()
        watchlist_header_layout.addWidget(self.remove_button)
        
        right_layout.addLayout(watchlist_header_layout)
        self.watch_list = DraggableListWidget()
        # 样式已在全局样式表中定义
        right_layout.addWidget(self.watch_list)
        
        # 初始化删除按钮状态
        self.update_remove_button_state()
        
        # 添加左右区域到自选股管理组
        watchlist_layout.addLayout(left_layout, 1)
        watchlist_layout.addLayout(right_layout, 1)
        
        # 显示设置组
        display_group = QGroupBox("显示设置")
        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(10, 10, 10, 10)
        display_layout.setSpacing(5)  # 减少间距
        display_group.setLayout(display_layout)
        
        # 显示设置行 - 字体、主题、透明度
        display_row_layout = QHBoxLayout()
        display_row_layout.setSpacing(5)  # 减少间距
        
        # 字体设置
        font_layout = QHBoxLayout()
        font_layout.setSpacing(4)
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Microsoft YaHei", "Segoe UI", "Arial", "SimSun", "SimHei"])
        self.font_combo.setFixedWidth(180)  # 调整宽度确保完整显示字体名称
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(9, 24)
        self.font_size_spinbox.setValue(12)
        self.font_size_spinbox.setFixedWidth(100)  # 调整宽度确保完整显示最大字号
        font_layout.addWidget(QLabel("字体:"))
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(self.font_size_spinbox)
        
        # 主题设置
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(4)
        self.dark_theme_radio = QRadioButton("深色")
        self.light_theme_radio = QRadioButton("浅色")
        self.theme_group = QButtonGroup()
        self.theme_group.addButton(self.dark_theme_radio)
        self.theme_group.addButton(self.light_theme_radio)
        self.dark_theme_radio.setChecked(True)
        theme_layout.addWidget(QLabel("主题:"))
        theme_layout.addWidget(self.dark_theme_radio)
        theme_layout.addWidget(self.light_theme_radio)
        
        # 透明度设置
        transparency_layout = QHBoxLayout()
        transparency_layout.setSpacing(4)
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(80)
        self.transparency_slider.setFixedWidth(130)  # 缩小宽度
        self.transparency_value_label = QLabel("80%")
        self.transparency_slider.valueChanged.connect(
            lambda v: self.transparency_value_label.setText(f"{v}%")
        )
        transparency_layout.addWidget(QLabel("透明度:"))
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_value_label)
        
        display_row_layout.addLayout(font_layout)
        display_row_layout.addSpacing(10)
        display_row_layout.addLayout(theme_layout)
        display_row_layout.addSpacing(10)
        display_row_layout.addLayout(transparency_layout)
        display_row_layout.addStretch()
        
        display_layout.addLayout(display_row_layout)
        
        # 系统设置行（移出分组框）
        system_layout = QHBoxLayout()
        system_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        system_layout.setSpacing(6)  # 调整为6px间距
        system_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # 垂直居中对齐，确保与按钮视觉齐平
        
        # 开机启动
        self.auto_start_checkbox = QCheckBox()
        self.auto_start_checkbox.setToolTip("开机自动启动")
        # 添加鼠标悬停反馈
        # 注意：大部分样式已在全局样式表中定义，这里只需要补充悬停效果
        
        # 刷新频率
        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["2秒", "5秒", "10秒", "30秒"])
        self.refresh_combo.setFixedWidth(110)  # 缩小宽度
        # 样式已在全局样式表中定义
        
        # 检查更新
        update_layout = QHBoxLayout()
        update_layout.setSpacing(4)
        self.version_label = QLabel(f"v{__version__}")
        self.check_update_button = QPushButton("检查更新")
        self.check_update_button.setObjectName("checkUpdateButton")
        update_layout.addWidget(self.version_label)
        update_layout.addWidget(self.check_update_button)
        
        # 添加开机启动标签和复选框
        self.auto_start_label = QLabel("开机启动:")
        system_layout.addWidget(self.auto_start_label)
        system_layout.addWidget(self.auto_start_checkbox)
        system_layout.addSpacing(6)  # 调整为6px间距
        system_layout.addWidget(QLabel("刷新频率:"))
        system_layout.addWidget(self.refresh_combo)
        system_layout.addSpacing(6)  # 调整为6px间距
        
        # 添加版本号标签
        version_label_text = QLabel("版本号:")
        system_layout.addWidget(version_label_text)
        # 从配置文件读取版本号
        self.version_label.setText(f"v{__version__}")
        system_layout.addLayout(update_layout)
        system_layout.addStretch()
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        button_layout.setSpacing(10)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # 垂直居中对齐
        
        # 确定和取消按钮
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelButton")
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        # 添加应用按钮
        self.apply_button = QPushButton("应用")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.insertWidget(1, self.apply_button)
        
        # 创建底部布局，包含系统设置和按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 8)  # 增加底部边距3px，从5px到8px
        bottom_layout.addLayout(system_layout)
        bottom_layout.addStretch()
        bottom_layout.addLayout(button_layout)
        
        # 调整底部布局的对齐方式，使文字和按钮视觉上更齐平
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # 添加所有组件到主布局，调整顺序：自选股管理组、显示设置组、底部布局
        main_layout.addWidget(watchlist_group)
        main_layout.addWidget(display_group)
        main_layout.addLayout(bottom_layout)
        
        # 连接信号和槽
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.watch_list.itemSelectionChanged.connect(self.update_remove_button_state)
        self.check_update_button.clicked.connect(self.check_for_updates)
        
    def check_for_updates(self):
        """检查更新"""
        try:
            from stock_monitor.core.updater import app_updater
            
            # 使用统一的更新流程
            if app_updater.check_for_updates():
                app_updater.perform_update(self)
            else:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "无更新",
                    "当前已是最新版本。",
                    QMessageBox.Ok
                )
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"检查更新时发生错误: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "检查更新失败",
                f"检查更新时发生错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def on_search_text_changed(self, text):
        """搜索文本变化时的处理"""
        if len(text) < 1:
            self.search_results.clear()
            return
            
        try:
            # 从本地缓存加载股票数据
            from stock_monitor.data.stock.stocks import load_stock_data
            all_stocks_list = load_stock_data()
            
            # 转换为字典格式以匹配原有逻辑
            all_stocks: Dict[str, Any] = {}
            for stock in all_stocks_list:
                all_stocks[stock['code']] = stock
            
            if not all_stocks:
                return
                
            self.search_results.clear()
            
            # 过滤匹配的股票并计算优先级
            matched_stocks = []
            for code, stock in all_stocks.items():
                if text.lower() in code.lower() or text.lower() in stock.get('name', '').lower():
                    # 计算优先级，A股优先
                    priority = 0
                    if code.startswith(('sh', 'sz')) and not code.startswith(('sh000', 'sz399')):
                        priority = 10  # A股最高优先级
                    elif code.startswith(('sh000', 'sz399')):
                        priority = 5   # 指数次优先级
                    elif code.startswith('hk'):
                        priority = 1   # 港股较低优先级
                    matched_stocks.append((priority, code, stock))
            
            # 按优先级排序，优先级高的在前
            matched_stocks.sort(key=lambda x: (-x[0], x[1]))
            
            # 显示前20个匹配结果
            for _, code, stock in matched_stocks[:20]:
                item_text = f"{code} {stock.get('name', '')}"
                self.search_results.addItem(item_text)
        except Exception as e:
            from stock_monitor.utils.error_handler import app_logger
            app_logger.error(f"搜索股票时出错: {e}")
            
    def _on_search_return_pressed(self):
        """处理搜索框回车键按下事件"""
        # 如果有搜索结果，添加第一个结果
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            self.add_to_watchlist(item)
            # 清空搜索框
            self.search_input.clear()
            self.search_results.clear()
            
    def add_to_watchlist(self, item):
        """将股票添加到自选股列表"""
        # 检查是否已经存在于自选股列表中
        for i in range(self.watch_list.count()):
            watch_item = self.watch_list.item(i)
            if watch_item is not None and item is not None:
                if watch_item.text() == item.text():
                    # 已存在，不重复添加，给出提示
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(self, "提示", "股票已在自选股列表中")
                    return
                
        # 添加到自选股列表
        self.watch_list.addItem(item.text())
        self.update_remove_button_state()
        
    def remove_selected_stocks(self):
        """删除选中的股票"""
        selected_items = self.watch_list.selectedItems()
        for item in selected_items:
            row = self.watch_list.row(item)
            self.watch_list.takeItem(row)
        self.update_remove_button_state()
        
    def update_remove_button_state(self):
        """更新删除按钮的状态"""
        has_selection = len(self.watch_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)
        
    def load_settings(self):
        """加载设置"""
        # 完全从主配置文件加载设置，不再使用本地ini配置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            
            # 加载自选股列表
            watch_list = config_manager.get('user_stocks', [])
            
            # 转换为显示格式
            formatted_watch_list = []
            from stock_monitor.utils import extract_stocks_from_list
            from stock_monitor.data.stock.stocks import load_stock_data
            
            # 加载股票数据以便获取名称
            all_stocks = {stock['code']: stock for stock in load_stock_data()}
            
            for code in watch_list:
                if code in all_stocks:
                    stock_info = all_stocks[code]
                    formatted_watch_list.append(f"{code} {stock_info['name']}")
                else:
                    formatted_watch_list.append(code)
        except Exception as e:
            # 出错时使用空列表
            formatted_watch_list = []
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"加载自选股列表时出错: {e}")
                
        self.watch_list.clear()
        for item in formatted_watch_list:
            if isinstance(item, str):
                self.watch_list.addItem(item)
            
        # 加载开机启动设置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            auto_start = config_manager.get("auto_start", False)
            self.auto_start_checkbox.setChecked(_safe_bool_conversion(auto_start))
        except Exception as e:
            self.auto_start_checkbox.setChecked(False)
        
        # 加载刷新频率设置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            refresh_interval = config_manager.get("refresh_interval", 5)
            refresh_interval = _safe_int_conversion(refresh_interval, 5)
            self.refresh_combo.setCurrentText(self._map_refresh_value_to_text(refresh_interval))
        except Exception as e:
            self.refresh_combo.setCurrentText(self._map_refresh_value_to_text(5))
            
        # 加载字体设置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            font_family = config_manager.get("font_family", "Microsoft YaHei")
            if isinstance(font_family, str):
                font_index = self.font_combo.findText(font_family)
                if font_index >= 0:
                    self.font_combo.setCurrentIndex(font_index)
        except Exception as e:
            pass
            
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            font_size = config_manager.get("font_size", 12)
            font_size = _safe_int_conversion(font_size, 12)
            self.font_size_spinbox.setValue(font_size)
        except Exception as e:
            self.font_size_spinbox.setValue(12)
        
        # 加载主题设置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            theme = config_manager.get("theme", "dark")
            if isinstance(theme, str) and theme == "light":
                self.light_theme_radio.setChecked(True)
            else:
                self.dark_theme_radio.setChecked(True)
        except Exception as e:
            self.dark_theme_radio.setChecked(True)
            
        # 加载透明度设置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            transparency = config_manager.get("transparency", 80)
            transparency = _safe_int_conversion(transparency, 80)
            self.transparency_slider.setValue(transparency)
        except Exception as e:
            self.transparency_slider.setValue(80)
        
        # 加载拖拽灵敏度设置
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            drag_sensitivity = config_manager.get("drag_sensitivity", 5)
            drag_sensitivity = _safe_int_conversion(drag_sensitivity, 5)
        except Exception as e:
            pass
            
    def save_settings(self):
        """保存设置"""
        # 保存所有设置到主配置文件
        try:
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            
            # 保存自选股列表
            user_stocks = self.get_stocks_from_list()
            config_manager.set('user_stocks', user_stocks)
            
            # 保存开机启动设置
            auto_start_enabled = self.auto_start_checkbox.isChecked()
            config_manager.set("auto_start", auto_start_enabled)
            
            # 实际设置开机启动
            self._set_auto_start(auto_start_enabled)
            
            # 保存刷新频率设置
            refresh_text = self.refresh_combo.currentText()
            refresh_interval = self._map_refresh_text_to_value(refresh_text)
            config_manager.set("refresh_interval", refresh_interval)
            
            # 保存字体设置
            config_manager.set("font_family", self.font_combo.currentText())
            config_manager.set("font_size", self.font_size_spinbox.value())
            
            # 保存主题设置
            if self.light_theme_radio.isChecked():
                config_manager.set("theme", "light")
            else:
                config_manager.set("theme", "dark")
                
            # 保存透明度设置
            config_manager.set("transparency", self.transparency_slider.value())
            
            # 保存拖拽灵敏度设置
            config_manager.set("drag_sensitivity", 5)  # 当前固定为5ms
            
            # 添加调试信息
            from stock_monitor.utils.logger import app_logger
            app_logger.info(f"保存设置时的自选股列表: {user_stocks}")
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"保存设置时出错: {e}")
    
    def _set_auto_start(self, enabled):
        """
        设置开机启动
        
        Args:
            enabled (bool): 是否启用开机启动
        """
        try:
            from stock_monitor.utils.logger import app_logger
            import os
            import sys
            
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
            
            if enabled:
                # 获取应用程序路径
                if hasattr(sys, '_MEIPASS'):
                    # PyInstaller打包环境
                    app_path = sys.executable
                else:
                    # 开发环境
                    app_path = os.path.abspath(sys.argv[0])
                
                # 创建快捷方式
                self._create_shortcut(app_path, shortcut_path)
                app_logger.info(f"已创建开机启动快捷方式: {shortcut_path}")
            else:
                # 删除快捷方式（如果存在）
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                    app_logger.info(f"已删除开机启动快捷方式: {shortcut_path}")
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"设置开机启动失败: {e}")

    def _create_shortcut(self, target_path, shortcut_path):
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
            shortcut.save()
        except ImportError:
            # win32com不可用时的备选方案
            try:
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

    def accept(self):
        """点击确定按钮时保存设置"""
        self.save_settings()
        self.save_position()  # 保存位置
        
        # 确保配置更改信号发出
        if self.main_window:
            stocks = self.get_stocks_from_list()
            refresh_interval = self._map_refresh_text_to_value(self.refresh_combo.currentText())
            # 添加调试信息
            from stock_monitor.utils.logger import app_logger
            app_logger.info(f"发送配置更改信号: 股票列表={stocks}, 刷新间隔={refresh_interval}")
            self.config_changed.emit(stocks, refresh_interval)
            
        super().accept()
        
    def apply_settings(self):
        """应用设置但不关闭对话框"""
        self.save_settings()
        self.save_position()  # 保存位置
        
        # 确保配置更改信号发出
        if self.main_window:
            stocks = self.get_stocks_from_list()
            refresh_interval = self._map_refresh_text_to_value(self.refresh_combo.currentText())
            # 添加调试信息
            from stock_monitor.utils.logger import app_logger
            app_logger.info(f"应用设置并发送配置更改信号: 股票列表={stocks}, 刷新间隔={refresh_interval}")
            self.config_changed.emit(stocks, refresh_interval)
        
    def reject(self):
        """点击取消按钮时恢复原始设置"""
        self.save_position()  # 保存位置
        super().reject()
        
    def save_position(self):
        """保存对话框位置"""
        if self.main_window:
            # 保存位置到主窗口的配置中
            from stock_monitor.config.manager import ConfigManager
            config_manager = ConfigManager()
            pos = [self.x(), self.y()]
            config_manager.set('settings_dialog_pos', pos)
    
    def showEvent(self, a0):  # type: ignore
        """重写showEvent以设置初始位置"""
        super().showEvent(a0)
        
        # 每次显示时都重新设置位置，确保不遮挡主窗口
        self.set_initial_position()
    
    def set_initial_position(self):
        """设置初始位置，避免遮挡主窗口"""
        if self.main_window:
            # 获取主窗口位置和尺寸
            main_geo = self.main_window.geometry()
            
            # 检查位置是否在屏幕范围内
            screen = QApplication.primaryScreen()
            if screen:
                available_geo = screen.availableGeometry()
                
                # 尝试不同的位置，优先级依次为：右侧、左侧、下方、上方
                positions = []
                
                # 右侧位置
                right_x = main_geo.x() + main_geo.width() + 20
                right_y = main_geo.y()
                positions.append((right_x, right_y, "右侧"))
                
                # 左侧位置
                left_x = main_geo.x() - self.width() - 20
                left_y = main_geo.y()
                positions.append((left_x, left_y, "左侧"))
                
                # 下方位置
                bottom_x = main_geo.x()
                bottom_y = main_geo.y() + main_geo.height() + 20
                positions.append((bottom_x, bottom_y, "下方"))
                
                # 上方位置
                top_x = main_geo.x()
                top_y = main_geo.y() - self.height() - 20
                positions.append((top_x, top_y, "上方"))
                
                # 选择第一个完全适合的位置
                x, y = None, None
                chosen_position = None
                for pos_x, pos_y, pos_name in positions:
                    # 检查位置是否在屏幕范围内
                    if (available_geo.left() <= pos_x and 
                        pos_x + self.width() <= available_geo.right() and
                        available_geo.top() <= pos_y and
                        pos_y + self.height() <= available_geo.bottom()):
                        x, y = pos_x, pos_y
                        chosen_position = pos_name
                        break
                
                # 如果没有找到完全适合的位置，计算最小遮挡的位置
                if x is None or y is None:
                    min_overlap_area = float('inf')
                    best_x, best_y = None, None
                    best_position = None
                    
                    for pos_x, pos_y, pos_name in positions:
                        # 计算窗口在屏幕内的部分
                        visible_x1 = max(available_geo.left(), pos_x)
                        visible_y1 = max(available_geo.top(), pos_y)
                        visible_x2 = min(available_geo.right(), pos_x + self.width())
                        visible_y2 = min(available_geo.bottom(), pos_y + self.height())
                        
                        # 检查是否有可见部分
                        if visible_x1 < visible_x2 and visible_y1 < visible_y2:
                            # 计算可见面积
                            visible_area = (visible_x2 - visible_x1) * (visible_y2 - visible_y1)
                            # 计算遮挡面积
                            overlap_area = (self.width() * self.height()) - visible_area
                            
                            # 选择遮挡面积最小的位置
                            if overlap_area < min_overlap_area:
                                min_overlap_area = overlap_area
                                best_x, best_y = pos_x, pos_y
                                best_position = pos_name
                    
                    # 如果找到了最小遮挡的位置
                    if best_x is not None and best_y is not None:
                        x, y = best_x, best_y
                        chosen_position = f"{best_position}(最小遮挡)"
                    else:
                        # 如果还是没有合适的位置，使用默认位置并进行边界调整
                        x = main_geo.x() + main_geo.width() + 20
                        y = main_geo.y()
                        chosen_position = "右侧(调整后)"
                        
                        # 确保设置窗口不会超出右边界
                        if x + self.width() > available_geo.right():
                            x = available_geo.right() - self.width()
                        
                        # 确保设置窗口不会超出左边界
                        if x < available_geo.left():
                            x = available_geo.left()
                        
                        # 确保设置窗口不会超出下边界
                        if y + self.height() > available_geo.bottom():
                            y = available_geo.bottom() - self.height()
                        
                        # 确保设置窗口不会超出上边界
                        if y < available_geo.top():
                            y = available_geo.top()
                
                self.move(x, y)
        
    def _map_refresh_text_to_value(self, text):
        """将刷新频率文本映射为数值"""
        mapping = {"2秒": 2, "5秒": 5, "10秒": 10, "30秒": 30}
        return mapping.get(text, 2)
    
    def _map_refresh_value_to_text(self, value):
        """将刷新频率数值映射为文本"""
        mapping = {2: "2秒", 5: "5秒", 10: "10秒", 30: "30秒"}
        return mapping.get(value, "2秒")
    
    def on_display_setting_changed(self):
        """当显示设置更改时，实时预览效果"""
        # 注释掉实时预览功能，仅在用户点击确定后应用设置
        # 发送信号通知主窗口更新样式
        # self.settings_changed.emit()
        pass

    def get_stocks_from_list(self):
        """
        从股票列表中提取股票代码
        
        Returns:
            list: 股票代码列表
        """
        # 使用count()方法获取项目数量，然后逐个处理
        items = []
        for i in range(self.watch_list.count()):
            items.append(self.watch_list.item(i))
            
        # 使用统一的工具函数处理股票代码提取
        from stock_monitor.utils import extract_stocks_from_list
        return extract_stocks_from_list(items)
