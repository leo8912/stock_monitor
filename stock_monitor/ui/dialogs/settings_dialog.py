"""
设置对话框模块
"""

import os
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QSlider,
    QPushButton,
    QLineEdit,
    QApplication,
    QColorDialog,
    QMessageBox,
    QAbstractItemView,
    QGroupBox,
)

from stock_monitor.utils.helpers import resource_path
from stock_monitor.version import __version__
from stock_monitor.ui.view_models.settings_view_model import SettingsViewModel


def _safe_bool_conversion(value, default=False):
    """安全地将值转换为布尔值"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
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

    def focusOutEvent(self, e):
        """重写焦点丢失事件，取消所有选中项"""
        # 检查焦点转移到了哪个控件
        # 如果是删除按钮获得焦点，则不清除选中状态
        focused_widget = QApplication.focusWidget()
        if (
            focused_widget
            and hasattr(focused_widget, "objectName")
            and focused_widget.objectName() == "removeButton"
        ):
            super().focusOutEvent(e)
            # 不清除选中状态
        else:
            super().focusOutEvent(e)
            self.clearSelection()

    def mousePressEvent(self, e):
        """重写鼠标按下事件，处理空白区域点击"""
        # 检查点击位置是否在项目上
        item = self.itemAt(e.pos()) if e else None
        if item is None:
            # 点击在空白区域，取消所有选中
            self.clearSelection()

        super().mousePressEvent(e)


# StockSearchHandler and ConfigManagerHandler logic moved to ViewModel
# Keep WatchListManager as it is UI logic
class WatchListManager:
    """自选股列表管理类"""

    def __init__(self, watch_list, remove_button, move_up_button, move_down_button):
        self.watch_list = watch_list
        self.remove_button = remove_button
        self.move_up_button = move_up_button
        self.move_down_button = move_down_button
        self._setup_watch_list_ui()

    def _setup_watch_list_ui(self):
        """设置自选股列表UI"""
        self.watch_list.setStyleSheet(
            """
            QListWidget {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                border-radius: 4px;
                color: white;
                font-size: 12px;
                outline: 0;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """
        )
        self.watch_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.watch_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.watch_list.setDragEnabled(True)
        self.watch_list.setAcceptDrops(True)
        self.watch_list.setDropIndicatorShown(True)

    def remove_selected_stocks(self):
        """删除选中的股票"""
        selected_items = self.watch_list.selectedItems()
        for item in selected_items:
            row = self.watch_list.row(item)
            self.watch_list.takeItem(row)
        self.update_remove_button_state()

        # 取消自选股列表的选中状态
        self.watch_list.clearSelection()

    def update_remove_button_state(self):
        """更新删除按钮的状态"""
        has_selection = len(self.watch_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)

    def move_up_selected_stock(self):
        """将选中的股票上移"""
        selected_items = self.watch_list.selectedItems()
        if len(selected_items) != 1:
            return

        item = selected_items[0]
        row = self.watch_list.row(item)
        if row > 0:
            self.watch_list.takeItem(row)
            self.watch_list.insertItem(row - 1, item)
            self.watch_list.setCurrentItem(item)
            self._update_move_buttons_state()

    def move_down_selected_stock(self):
        """将选中的股票下移"""
        selected_items = self.watch_list.selectedItems()
        if len(selected_items) != 1:
            return

        item = selected_items[0]
        row = self.watch_list.row(item)
        if row < self.watch_list.count() - 1:
            self.watch_list.takeItem(row)
            self.watch_list.insertItem(row + 1, item)
            self.watch_list.setCurrentItem(item)
            self._update_move_buttons_state()

    def _update_move_buttons_state(self):
        """更新上移和下移按钮的状态"""
        selected_items = self.watch_list.selectedItems()
        if len(selected_items) != 1:
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
            return

        item = selected_items[0]
        row = self.watch_list.row(item)
        self.move_up_button.setEnabled(row > 0)
        self.move_down_button.setEnabled(row < self.watch_list.count() - 1)


# ConfigManagerHandler logic moved to ViewModel



class NewSettingsDialog(QDialog):
    """设置对话框类"""

    # 定义设置更改信号
    settings_changed = pyqtSignal()
    # 定义配置更改信号，参数为股票列表和刷新间隔
    config_changed = pyqtSignal(list, int)

    def __init__(self, main_window=None):
        # 不传递父窗口给QDialog,避免继承主窗口的置顶属性
        super().__init__(None)
        self.main_window = main_window
        
        # Initialize ViewModel
        self.viewModel = SettingsViewModel()

        # 设置窗口标题和图标
        self.setWindowTitle("A股行情监控设置")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # 同时设置任务栏图标
            import ctypes

            myappid = "stock.monitor.settings"  # 设置应用ID
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        # 设置窗口标志:移除帮助按钮,确保不置顶
        flags = Qt.WindowType.Window  # 使用普通窗口标志
        flags |= Qt.WindowType.WindowCloseButtonHint  # 添加关闭按钮
        flags |= Qt.WindowType.WindowMinimizeButtonHint  # 添加最小化按钮
        self.setWindowFlags(flags)

        # 设置窗口大小
        self.resize(900, 700)  # 进一步调大窗口尺寸

        # 设置窗口样式以匹配暗色主题
        self.setStyleSheet("QDialog { background-color: #1e1e1e; } ")

        # 在Windows上设置标题栏颜色
        try:
            # 尝试设置Windows 10/11标题栏颜色
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                35,  # DWMWA_CAPTION_COLOR
                ctypes.byref(ctypes.c_int(0x1E1E1E)),
                ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass

        # 为设置对话框设置固定字体，避免继承主窗口的动态字体
        # 使用独立的样式表覆盖继承的样式
        self.setStyleSheet(
            """
            QDialog {
                font-family: "Microsoft YaHei";
                font-size: 12px;
            }
            QLabel, QPushButton, QLineEdit, QListWidget, QGroupBox, QCheckBox, QComboBox, QSpinBox {
                font-family: "Microsoft YaHei";
                font-size: 12px;
            }
        """
        )

        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)

        # 构建UI界面
        self._setup_watchlist_ui(main_layout)
        self._setup_display_settings_ui(main_layout)
        self._setup_system_settings_ui(main_layout)

        # 初始化功能管理器（在UI组件创建之后）
        # self.stock_search_handler = StockSearchHandler(...) # Removed
        self.watch_list_manager = WatchListManager(
            self.watch_list,
            self.remove_button,
            self.move_up_button,
            self.move_down_button,
        )
        # self.config_manager_handler = ConfigManagerHandler(self.config_manager) # Removed

        # 添加字体预览防抖定时器
        from PyQt6.QtCore import QTimer

        self._font_preview_timer = QTimer()
        self._font_preview_timer.setSingleShot(True)
        self._font_preview_timer.timeout.connect(self._apply_font_preview)
        self._pending_font_family = None
        self._pending_font_size = None

        # 连接信号槽
        self._connect_signals()

        # 加载配置
        self._load_config_from_vm()

        # 保存原始自选股列表，用于取消操作时恢复
        self.original_watch_list = []
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                self.original_watch_list.append(item.text())

    def _connect_signals(self):
        """连接所有信号槽"""
        # ViewModel Signals
        self.viewModel.search_results_updated.connect(self._on_search_results_updated)
        self.viewModel.save_completed.connect(self.accept)
        
        # 连接搜索相关信号
        self.search_input.textChanged.connect(
            self.viewModel.search_stocks
        )
        self.search_input.returnPressed.connect(
            self._on_search_return_pressed
        )
        self.search_results.itemDoubleClicked.connect(self.add_stock_from_search)
        self.search_results.itemSelectionChanged.connect(
            lambda: self.add_button.setEnabled(
                len(self.search_results.selectedItems()) > 0
            )
        )

        # 连接自选股列表相关信号
        self.remove_button.clicked.connect(
            self.watch_list_manager.remove_selected_stocks
        )
        self.move_up_button.clicked.connect(
            self.watch_list_manager.move_up_selected_stock
        )
        self.move_down_button.clicked.connect(
            self.watch_list_manager.move_down_selected_stock
        )
        self.watch_list.itemSelectionChanged.connect(
            self.watch_list_manager._update_move_buttons_state
        )
        self.watch_list.itemSelectionChanged.connect(
            lambda: self.remove_button.setEnabled(
                len(self.watch_list.selectedItems()) > 0
            )
        )

        # 连接按钮信号
        self.add_button.clicked.connect(self.add_stock_from_search)
        self.ok_button.clicked.connect(self._save_config_via_vm)
        self.cancel_button.clicked.connect(self.reject)
        self.check_update_button.clicked.connect(self.check_for_updates)

        # 连接设置相关信号
        self.font_size_spinbox.valueChanged.connect(self.on_font_setting_changed)
        self.font_family_combo.currentTextChanged.connect(self.on_font_setting_changed)
        self.transparency_slider.valueChanged.connect(self.on_transparency_changed)

    def _setup_watchlist_ui(self, main_layout):
        """设置自选股管理UI"""
        # 自选股管理组
        watchlist_group = QGroupBox("自选股管理")
        watchlist_layout = QHBoxLayout()
        watchlist_layout.setContentsMargins(10, 10, 10, 10)
        watchlist_layout.setSpacing(15)
        watchlist_group.setLayout(watchlist_layout)

        # 左侧区域 - 搜索股票
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # 搜索框
        search_label = QLabel("搜索股票")
        search_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入股票代码或名称...")
        self.search_input.setStyleSheet(
            """
            QLineEdit {
                padding: 8px;
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3d3d3d;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """
        )

        left_layout.addWidget(search_label)
        left_layout.addWidget(self.search_input)

        # 搜索结果列表
        self.search_results = QListWidget()
        self.search_results.setStyleSheet(
            """
            QListWidget {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                border-radius: 4px;
                color: white;
                font-size: 12px;
                outline: 0;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """
        )
        left_layout.addWidget(self.search_results)

        # 添加按钮
        self.add_button = QPushButton("添加")
        self.add_button.setStyleSheet(
            """
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                min-width: 60px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #108de6;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """
        )
        self.add_button.setEnabled(False)

        # 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        left_layout.addLayout(button_layout)

        watchlist_layout.addLayout(left_layout, 1)

        # 右侧区域 - 自选股列表
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # 自选股列表标签
        watchlist_label = QLabel("自选股列表")
        watchlist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(watchlist_label)

        # 自选股列表
        self.watch_list = DraggableListWidget()
        self.watch_list.setStyleSheet(
            """
            QListWidget {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                border-radius: 4px;
                color: white;
                font-size: 14px;
                outline: 0;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """
        )

        # 启用拖拽排序
        self.watch_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.watch_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.watch_list.setDragEnabled(True)
        self.watch_list.setAcceptDrops(True)
        self.watch_list.setDropIndicatorShown(True)

        right_layout.addWidget(self.watch_list)

        # 操作按钮布局
        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)

        # 删除按钮
        self.remove_button = QPushButton("删除")
        self.remove_button.setObjectName("removeButton")
        self.remove_button.setStyleSheet(
            """
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                min-width: 60px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """
        )
        self.remove_button.setEnabled(False)

        # 上移按钮
        self.move_up_button = QPushButton("上移")
        self.move_up_button.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                min-width: 60px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """
        )
        self.move_up_button.setEnabled(False)

        # 下移按钮
        self.move_down_button = QPushButton("下移")
        self.move_down_button.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                min-width: 60px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """
        )
        self.move_down_button.setEnabled(False)

        action_layout.addWidget(self.remove_button)
        action_layout.addStretch()
        action_layout.addWidget(self.move_up_button)
        action_layout.addWidget(self.move_down_button)

        right_layout.addLayout(action_layout)
        watchlist_layout.addLayout(right_layout, 1)
        main_layout.addWidget(watchlist_group)

    def _setup_display_settings_ui(self, main_layout):
        """设置显示设置UI"""
        # 显示设置组
        display_group = QGroupBox("显示设置")
        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(10, 10, 10, 10)
        display_layout.setSpacing(10)
        display_group.setLayout(display_layout)

        # 显示设置行
        display_row_layout = QHBoxLayout()
        display_row_layout.setContentsMargins(0, 0, 0, 0)
        display_row_layout.setSpacing(10)

        # 字体大小设置
        font_layout = QHBoxLayout()
        font_layout.setSpacing(4)
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(10, 20)
        self.font_size_spinbox.setValue(13)  # 默认13px
        self.font_size_spinbox.setSuffix(" px")
        self.font_size_spinbox.setFixedWidth(80)
        font_layout.addWidget(QLabel("字体大小:"))
        font_layout.addWidget(self.font_size_spinbox)

        # 字体设置
        font_family_layout = QHBoxLayout()
        font_family_layout.setSpacing(4)
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["微软雅黑", "宋体", "黑体", "楷体", "仿宋"])
        self.font_family_combo.setFixedWidth(100)
        font_family_layout.addWidget(QLabel("字体:"))
        font_family_layout.addWidget(self.font_family_combo)

        # 透明度设置
        transparency_layout = QHBoxLayout()
        transparency_layout.setSpacing(4)
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(80)
        self.transparency_slider.setFixedWidth(130)  # 缩小宽度

        # 极简滑块样式
        self.transparency_slider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #3d3d3d;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #1084d8;
            }
        """
        )

        self.transparency_value_label = QLabel("80%")
        self.transparency_slider.valueChanged.connect(
            lambda v: self.transparency_value_label.setText(f"{v}%")
        )
        transparency_layout.addWidget(QLabel("透明度:"))
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_value_label)

        display_row_layout.addLayout(font_layout)
        display_row_layout.addSpacing(10)
        display_row_layout.addLayout(font_family_layout)
        display_row_layout.addSpacing(10)
        display_row_layout.addLayout(transparency_layout)
        display_row_layout.addSpacing(15)

        # 添加恢复默认值按钮
        self.reset_display_button = QPushButton("恢复默认")
        self.reset_display_button.setFixedWidth(80)
        self.reset_display_button.setStyleSheet(
            """
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #444;
            }
        """
        )
        self.reset_display_button.clicked.connect(self.reset_display_settings)
        display_row_layout.addWidget(self.reset_display_button)

        display_row_layout.addStretch()

        display_layout.addLayout(display_row_layout)
        main_layout.addWidget(display_group)

    def _setup_system_settings_ui(self, main_layout):
        """设置系统设置UI"""
        # 系统设置行（移出分组框）
        system_layout = QHBoxLayout()
        system_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        system_layout.setSpacing(6)  # 调整为6px间距
        system_layout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
        )  # 垂直居中对齐，确保与按钮视觉齐平

        # 开机启动
        self.auto_start_checkbox = QCheckBox()
        self.auto_start_checkbox.setToolTip("开机自动启动")
        # 添加鼠标悬停反馈
        # 注意：大部分样式已在全局样式表中定义，这里只需要补充悬停效果

        # 刷新频率
        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["1秒", "2秒", "5秒", "10秒", "30秒"])
        self.refresh_combo.setFixedWidth(100)  # 缩小宽度
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
        button_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )  # 右对齐并垂直居中

        # 确定和取消按钮
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelButton")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        # 创建底部布局，包含系统设置和按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addLayout(system_layout, 1)
        bottom_layout.addLayout(button_layout)

        main_layout.addLayout(bottom_layout)

    def check_for_updates(self):
        """检查更新"""
        try:
            from stock_monitor.core.updater import app_updater

            # 使用统一的更新流程
            result = app_updater.check_for_updates()
            if result is True:
                # 有新版本，执行更新
                app_updater.perform_update(self)
            elif result is False:
                # 确认没有新版本
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.information(
                    self,
                    "无更新",
                    "当前已是最新版本，无需更新",
                    QMessageBox.StandardButton.Ok,
                )
            else:
                # 网络错误或其他问题
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.critical(
                    self,
                    "检查更新失败",
                    "检查更新失败：网络连接异常，请稍后重试",
                    QMessageBox.StandardButton.Ok,
                )
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"检查更新失败: {e}")

    def _on_search_results_updated(self, results):
        """Update search results from ViewModel"""
        self.search_results.clear()
        if not results:
            return

        for item_data in results:
            display_text = item_data['display']
            item = QListWidgetItem(display_text)
            # Store code in user role
            item.setData(Qt.ItemDataRole.UserRole, item_data['code'])
            self.search_results.addItem(item)

        # Clear main selection
        self.watch_list.clearSelection()

    def _on_search_return_pressed(self):
        """Handle return pressed in search"""
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            self.add_stock_from_search(item)
            self.search_input.clear()
            self.search_results.clear()

    def _load_config_from_vm(self):
        """Load config via ViewModel"""
        try:
            settings = self.viewModel.load_settings()
            
            # User Stocks
            self.watch_list.clear()
            user_stocks = settings.get("user_stocks", [])
            for stock_code in user_stocks:
                # Use clean code directly if VM handles display info
                # But we need display text.
                display_text = self.viewModel.get_stock_display_info(stock_code)
                item = QListWidgetItem(display_text)
                
                # Ensure we store clean code
                # If display text is "Emoji Name (Code)", we need Code.
                # get_stock_display_info logic reconstructs it.
                # But here we assume stock_code IS the code.
                cleaned_code = stock_code.strip()
                if " " in stock_code: # Minimal cleaning check if config has dirty data
                     cleaned_code = stock_code.split(" ")[0] # Fallback
                
                # Actually, viewModel load_user_stocks already cleans it in MainWindowViewModel. 
                # Does ConfigManager store clean codes? Yes, mostly.
                item.setData(Qt.ItemDataRole.UserRole, stock_code)
                self.watch_list.addItem(item)
                
            # Other settings
            self.auto_start_checkbox.setChecked(settings.get("auto_start", False))
            
            # Refresh interval logic
            ri = settings.get("refresh_interval", 5)
            map_val_to_text = {2: "2秒", 5: "5秒", 10: "10秒", 30: "30秒"}
            text = map_val_to_text.get(ri, "5秒")
            index = self.refresh_combo.findText(text)
            if index >= 0:
                self.refresh_combo.setCurrentIndex(index)
            else:
                self.refresh_combo.setCurrentIndex(1)
                
            # Font size
            fs = settings.get("font_size", 13)
            self.font_size_spinbox.setValue(int(fs))
            
            # Font family
            ff = settings.get("font_family", "微软雅黑")
            index = self.font_family_combo.findText(ff)
            if index >= 0:
                self.font_family_combo.setCurrentIndex(index)
                
            # Transparency
            tp = settings.get("transparency", 80)
            self.transparency_slider.setValue(int(tp))
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"Failed to load config from VM: {e}")

    def _save_config_via_vm(self):
        """Save config via VM"""
        try:
            stocks = self.get_stocks_from_list(self.watch_list) 
            
            # Map refresh text to int
            map_text_to_val = {"2秒": 2, "5秒": 5, "10秒": 10, "30秒": 30}
            ri_text = self.refresh_combo.currentText()
            ri = map_text_to_val.get(ri_text, 5)
            
            settings = {
                "user_stocks": stocks,
                "auto_start": self.auto_start_checkbox.isChecked(),
                "refresh_interval": ri,
                "font_size": self.font_size_spinbox.value(),
                "font_family": self.font_family_combo.currentText(),
                "transparency": self.transparency_slider.value()
            }
            
            self.viewModel.save_settings(settings)
        except Exception as e:
            from stock_monitor.utils.logger import app_logger
            app_logger.error(f"Failed to save config via VM: {e}")

    def get_stocks_from_list(self, watch_list):
        """
        从列表中提取股票代码
        Args:
            watch_list: 自选股列表控件
        Returns:
            list: 股票代码列表
        """
        stocks = []
        for i in range(watch_list.count()):
            item = watch_list.item(i)
            if item:
                # 优先从UserRole获取代码
                user_data = item.data(Qt.ItemDataRole.UserRole)
                if user_data:
                    stocks.append(user_data)
                    continue

                text = item.text()
                # 提取括号中的股票代码
                import re

                match = re.search(r"\(([^)]+)\)", text)
                if match:
                    stocks.append(match.group(1))
                else:
                    # 如果没有找到括号中的代码，尝试清理文本
                    clean_text = text.replace("⭐️", "").strip()
                    parts = clean_text.split()
                    if parts:
                        stocks.append(parts[0])
                    else:
                        stocks.append(text)
        return stocks



    def add_stock_from_search(self, item):
        """将股票添加到自选股列表"""
        # 检查是否已经存在于自选股列表中
        # 解析item文本以提取股票代码
        item_text = item.text()
        import re

        match = re.search(r"\(([^)]+)\)", item_text)
        if match:
            stock_code = match.group(1)
        else:
            # 如果找不到括号中的代码，尝试从文本中提取代码
            # 处理类似 "sz000063 中兴通讯" 这样的格式
            parts = item_text.split()
            if parts:
                # 使用股票代码处理器来验证和格式化代码
                from stock_monitor.utils.stock_utils import StockCodeProcessor

                processor = StockCodeProcessor()
                stock_code = processor.format_stock_code(parts[0])
                if not stock_code:
                    # 如果第一部分不是有效的代码，尝试整个文本
                    stock_code = processor.format_stock_code(item_text)
            else:
                stock_code = item_text

        for i in range(self.watch_list.count()):
            watch_item = self.watch_list.item(i)
            if watch_item is not None:
                # 检查watch_item中是否包含相同的股票代码
                watch_text = watch_item.text()
                watch_match = re.search(r"\(([^)]+)\)", watch_text)
                if watch_match:
                    watch_code = watch_match.group(1)
                else:
                    # 处理类似 "sz000063 中兴通讯" 这样的格式
                    watch_parts = watch_text.split()
                    if watch_parts:
                        # 使用股票代码处理器来验证和格式化代码
                        from stock_monitor.utils.stock_utils import StockCodeProcessor

                        processor = StockCodeProcessor()
                        watch_code = processor.format_stock_code(watch_parts[0])
                        if not watch_code:
                            # 如果第一部分不是有效的代码，尝试整个文本
                            watch_code = processor.format_stock_code(watch_text)
                    else:
                        watch_code = watch_text

                if watch_code == stock_code:
                    # 已存在，不重复添加，给出提示
                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.information(self, "提示", "股票已在自选股列表中")
                    return

        # 添加到自选股列表，确保格式化显示
        # 解析股票代码和名称用于格式化显示
        item_text = item.text()
        match = re.search(r"\(([^)]+)\)", item_text)
        if match:
            # 标准格式 "名称 (code)"
            code = match.group(1)
            # 提取名称部分
            name = item_text.replace(f" ({code})", "").split()[-1]
        else:
            # 非标准格式，尝试解析
            parts = item_text.split()
            if len(parts) >= 2:
                code = parts[0]
                name = " ".join(parts[1:])
            else:
                code = item_text
                name = ""

        # 使用股票代码处理器获取emoji并格式化显示
        from stock_monitor.utils.helpers import get_stock_emoji
        from stock_monitor.utils.stock_utils import StockCodeProcessor

        processor = StockCodeProcessor()
        clean_code = processor.format_stock_code(code)
        if clean_code:
            code = clean_code

        emoji = get_stock_emoji(code, name)
        if name:
            display_text = f"{emoji} {name} ({code})"
        else:
            display_text = f"{emoji} {code}"

        from PyQt6.QtWidgets import QListWidgetItem

        new_item = QListWidgetItem(display_text)
        new_item.setData(Qt.ItemDataRole.UserRole, code)
        self.watch_list.addItem(new_item)
        self.watch_list_manager.update_remove_button_state()

        # 取消自选股列表的选中状态
        self.watch_list.clearSelection()

    def remove_selected_stocks(self):
        """删除选中的股票"""
        selected_items = self.watch_list.selectedItems()
        for item in selected_items:
            row = self.watch_list.row(item)
            self.watch_list.takeItem(row)
        self.update_remove_button_state()

        # 取消自选股列表的选中状态
        self.watch_list.clearSelection()

    def update_remove_button_state(self):
        """更新删除按钮的状态"""
        has_selection = len(self.watch_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)

    def move_up_selected_stock(self):
        """将选中的股票上移"""
        selected_items = self.watch_list.selectedItems()
        if len(selected_items) != 1:
            return

        item = selected_items[0]
        row = self.watch_list.row(item)
        if row > 0:
            self.watch_list.takeItem(row)
            self.watch_list.insertItem(row - 1, item)
            self.watch_list.setCurrentItem(item)
            self._update_move_buttons_state()

    def move_down_selected_stock(self):
        """将选中的股票下移"""
        selected_items = self.watch_list.selectedItems()
        if len(selected_items) != 1:
            return

        item = selected_items[0]
        row = self.watch_list.row(item)
        if row < self.watch_list.count() - 1:
            self.watch_list.takeItem(row)
            self.watch_list.insertItem(row + 1, item)
            self.watch_list.setCurrentItem(item)
            self._update_move_buttons_state()

    def _update_move_buttons_state(self):
        """更新上移和下移按钮的状态"""
        selected_items = self.watch_list.selectedItems()
        if len(selected_items) != 1:
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
            return

        item = selected_items[0]
        row = self.watch_list.row(item)
        self.move_up_button.setEnabled(row > 0)
        self.move_down_button.setEnabled(row < self.watch_list.count() - 1)



    def _set_auto_start(self, enabled):
        """
        设置开机启动

        Args:
            enabled (bool): 是否启用开机启动
        """
        try:
            import os
            import sys

            from stock_monitor.utils.logger import app_logger

            # 获取启动文件夹路径
            startup_folder = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "Startup",
            )

            # 检查启动文件夹是否存在
            if not os.path.exists(startup_folder):
                app_logger.warning(f"启动文件夹不存在: {startup_folder}")
                return

            shortcut_path = os.path.join(startup_folder, "StockMonitor.lnk")

            if enabled:
                # 获取应用程序路径
                if hasattr(sys, "_MEIPASS"):
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

                if target_path.endswith(".py"):
                    # 如果是Python脚本，创建批处理文件
                    batch_content = f'@echo off\npython "{target_path}"\n'
                    batch_path = shortcut_path.replace(".lnk", ".bat")
                    with open(batch_path, "w") as f:
                        f.write(batch_content)
                else:
                    # 如果是exe文件，直接复制
                    shutil.copy2(target_path, shortcut_path.replace(".lnk", ".exe"))
            except Exception as e:
                from stock_monitor.utils.logger import app_logger

                app_logger.error(f"创建快捷方式失败: {e}")

    def accept(self):
        """点击确定按钮时保存设置"""
        # Save is handled by ViewModel via _save_config_via_vm connected to OK button
        # self.save_config()

        # 实际设置开机启动
        auto_start_enabled = self.auto_start_checkbox.isChecked()
        self._set_auto_start(auto_start_enabled)

        # 清除预览透明度并恢复主窗口的默认状态
        if self.main_window:
            if hasattr(self.main_window, "_preview_transparency"):
                delattr(self.main_window, "_preview_transparency")
            self.main_window.update()
            # 恢复主窗口菜单的默认样式
            if hasattr(self.main_window, "menu") and self.main_window.menu:
                self.main_window.menu.restore_default_style()

        # 确保配置更改信号发出
        if self.main_window:
            stocks = self.get_stocks_from_list(self.watch_list)
            refresh_interval = self._map_refresh_text_to_value(
                self.refresh_combo.currentText()
            )
            # 添加调试信息
            from stock_monitor.utils.logger import app_logger

            app_logger.info(
                f"发送配置更改信号: 股票列表={stocks}, 刷新间隔={refresh_interval}"
            )
            self.config_changed.emit(stocks, refresh_interval)

            # 立即刷新数据
            self.main_window.refresh_now(stocks)

        # 更新原始列表为当前列表
        self.original_watch_list = []
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                self.original_watch_list.append(item.text())

        # 使用hide()替代accept()避免可能的退出问题
        self.hide()

    def reject(self):
        """点击取消按钮时恢复原始设置"""
        # 恢复原始自选股列表
        self.watch_list.clear()
        for item in self.original_watch_list:
            self.watch_list.addItem(item)

        # 恢复主窗口的原始字体设置
        if self.main_window:
            self.main_window.update_font_size()
            # 清除预览透明度并恢复主窗口的默认状态
            if hasattr(self.main_window, "_preview_transparency"):
                delattr(self.main_window, "_preview_transparency")
            self.main_window.update()
            # 恢复主窗口菜单的默认样式
            if hasattr(self.main_window, "menu") and self.main_window.menu:
                self.main_window.menu.restore_default_style()

        # 隐藏窗口而不是关闭
        self.hide()

    def showEvent(self, a0):  # type: ignore
        """重写showEvent以设置初始位置"""
        super().showEvent(a0)

        # 居中显示窗口
        self.center_on_screen()

    def center_on_screen(self):
        """将窗口居中显示在屏幕中央"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(max(screen_geo.left(), x), max(screen_geo.top(), y))

    def _map_refresh_text_to_value(self, text):
        """将刷新频率文本映射为数值"""
        mapping = {"1秒": 1, "2秒": 2, "5秒": 5, "10秒": 10, "30秒": 30}
        return mapping.get(text, 2)

    def _map_refresh_value_to_text(self, value):
        """将刷新频率数值映射为文本"""
        mapping = {1: "1秒", 2: "2秒", 5: "5秒", 10: "10秒", 30: "30秒"}
        return mapping.get(value, "2秒")

    def on_display_setting_changed(self):
        """当显示设置更改时，实时预览效果"""
        # 注释掉实时预览功能，仅在用户点击确定后应用设置
        # 发送信号通知主窗口更新样式
        # self.settings_changed.emit()
        pass

    def on_font_setting_changed(self):
        """字体设置变化时的处理函数，用于实时预览（带防抖）"""
        if not self.main_window:
            return

        try:
            # 获取当前字体设置
            font_size = self.font_size_spinbox.value()
            font_family = self.font_family_combo.currentText()

            # 保存待预览的值
            self._pending_font_family = font_family
            self._pending_font_size = font_size

            # 重启防抖定时器（300ms延迟）
            self._font_preview_timer.stop()
            self._font_preview_timer.start(300)

        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"字体设置变化处理失败: {e}")

    def _apply_font_preview(self):
        """应用字体预览（防抖后实际执行）"""
        if not self.main_window or self._pending_font_family is None:
            return

        try:
            font_family = self._pending_font_family
            font_size = self._pending_font_size

            from stock_monitor.utils.logger import app_logger

            if font_size <= 0:
                app_logger.warning(f"检测到非法的字体大小: {font_size}，自动修正为 13")
            app_logger.debug(f"预览字体设置: {font_family}, {font_size}px")

            # 保存当前字体设置到配置（临时，用于预览）
            from stock_monitor.config.manager import ConfigManager

            config_manager = ConfigManager()

            # 临时设置新字体
            config_manager.set("font_family", font_family)
            config_manager.set("font_size", font_size)

            # 调用主窗口的字体更新方法（会更新所有组件）
            self.main_window.update_font_size()

        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"应用字体预览失败: {e}")

    def on_transparency_changed(self):
        """透明度设置变化时的处理函数，用于实时预览"""
        if self.main_window:
            # 使用窗口级别的属性传递预览透明度值，触发主窗口重绘以预览背景透明度
            # 这样可以确保只改变背景透明度，不影响文字清晰度
            self.main_window._preview_transparency = self.transparency_slider.value()
            self.main_window.update()

    def reset_display_settings(self):
        """恢复显示设置为默认值"""
        try:
            from stock_monitor.utils.logger import app_logger

            app_logger.info("恢复显示设置为默认值")

            # 恢复默认值
            self.font_size_spinbox.setValue(13)
            self.font_family_combo.setCurrentText("微软雅黑")
            self.transparency_slider.setValue(80)

            # 显示提示（可选）
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "恢复默认",
                "显示设置已恢复为默认值",
                QMessageBox.StandardButton.Ok,
            )
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"恢复默认设置失败: {e}")



    def closeEvent(self, a0):  # type: ignore
        """处理窗口关闭事件"""
        self.hide()
        if a0:
            a0.ignore()  # 阻止窗口真正关闭

    def on_activated(self, reason):
        """
        托盘图标激活事件处理

        Args:
            reason: 激活原因
        """
        from PyQt6 import QtGui, QtWidgets

        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:  # type: ignore
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        elif reason == QtWidgets.QSystemTrayIcon.ActivationReason.Context:  # type: ignore
            self.contextMenu().exec(QtGui.QCursor.pos())  # type: ignore
