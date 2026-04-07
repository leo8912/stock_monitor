"""
设置对话框模块
"""

import os
import time

from PyQt6 import QtGui
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,  # [ADDED] 用于列表视图模式
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from stock_monitor.ui.view_models.settings_view_model import SettingsViewModel
from stock_monitor.utils.helpers import (
    resource_path,
)
from stock_monitor.version import __version__


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


class UpdateCheckThread(QThread):
    """更新检查线程（从 check_for_updates 方法提取）"""

    finished_check = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            from stock_monitor.core.updater import app_updater

            result = app_updater.check_for_updates()
            self.finished_check.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


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
        self.watch_list.setObjectName("WatchListWidget")
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
    # 增加手动复盘信号
    manual_report_requested = pyqtSignal()

    def __init__(self, main_window=None):
        # 不传递父窗口给 QDialog，避免继承主窗口的置顶属性
        super().__init__(None)
        self.main_window = main_window

        # Initialize ViewModel
        self.viewModel = SettingsViewModel()

        # [P1 FIX] 添加速率限制，防止 Webhook 测试被滥用
        self._last_webhook_test_time = 0
        self._webhook_test_cooldown = 60  # 60 秒冷却时间

        # 设置窗口标题和图标
        self.setWindowTitle("A 股行情监控设置")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # 同时设置任务栏图标
            self._setup_windows_taskbar_icon()

        # 设置窗口标志：移除帮助按钮，确保不置顶
        flags = Qt.WindowType.Window  # 使用普通窗口标志
        flags |= Qt.WindowType.WindowCloseButtonHint  # 添加关闭按钮
        flags |= Qt.WindowType.WindowMinimizeButtonHint  # 添加最小化按钮
        self.setWindowFlags(flags)

        # 设置窗口大小
        self.resize(900, 700)  # 进一步调大窗口尺寸

        # 设置窗口样式以匹配暗色主题
        self.setObjectName("NewSettingsDialog")

        # 在 Windows 上设置标题栏颜色
        self._setup_windows_caption_color()

        # 为设置对话框设置固定字体，避免继承主窗口的动态字体
        # 使用独立的样式表覆盖继承的样式，此时已经由全局掌控

        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)

        # === [UI OPTIMIZATION] 创建标签页结构 ===
        self._setup_tabs(main_layout)

        # === 底部：系统设置和按钮 ===
        self._setup_bottom_bar(main_layout)

        # 初始化功能管理器（在 UI 组件创建之后）
        self.watch_list_manager = WatchListManager(
            self.watch_list,
            self.remove_button,
            self.move_up_button,
            self.move_down_button,
        )

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

    def _setup_windows_taskbar_icon(self):
        """设置 Windows 任务栏图标（仅 Windows 平台）"""
        import sys

        if sys.platform != "win32":
            return

        try:
            import ctypes

            myappid = "stock.monitor.settings"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    def _setup_windows_caption_color(self):
        """设置 Windows 10/11 标题栏颜色（仅 Windows 平台）"""
        import sys

        if sys.platform != "win32":
            return

        try:
            import ctypes

            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                35,  # DWMWA_CAPTION_COLOR
                ctypes.byref(ctypes.c_int(0x1E1E1E)),
                ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass

    def _connect_signals(self):
        """连接所有信号槽"""
        # ViewModel Signals
        self.viewModel.search_results_updated.connect(self._on_search_results_updated)
        self.viewModel.save_completed.connect(self.accept)

        # 连接搜索相关信号
        self.search_input.textChanged.connect(self.viewModel.search_stocks)
        self.search_input.returnPressed.connect(self._on_search_return_pressed)
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
        self.ok_button.clicked.connect(
            self._on_ok_clicked
        )  # [FIXED] 直接连接到处理函数
        self.cancel_button.clicked.connect(self.reject)
        self.check_update_button.clicked.connect(self.check_for_updates)
        self.test_push_button.clicked.connect(self._on_test_push_clicked)
        self.test_app_button.clicked.connect(self._on_test_app_clicked)
        self.btn_manual_report.clicked.connect(self.manual_report_requested.emit)
        self.push_mode_combo.currentIndexChanged.connect(self._on_push_mode_changed)
        self.viewModel.error_occurred.connect(self._on_vm_error)

        # 连接设置相关信号
        self.font_size_slider.valueChanged.connect(self.on_font_setting_changed)
        self.font_family_combo.currentTextChanged.connect(self.on_font_setting_changed)
        self.transparency_slider.valueChanged.connect(self.on_transparency_changed)

    def _setup_tabs(self, main_layout):
        """创建标签页结构 [UI OPTIMIZATION]"""
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")

        # 创建各个标签页容器
        self.tab_watchlist = QWidget()
        self.tab_display = QWidget()
        self.tab_quant = QWidget()

        # 构建各标签页内容
        self._setup_watchlist_ui(self.tab_watchlist)
        self._setup_display_settings_ui(self.tab_display)
        self._setup_quant_settings_ui(self.tab_quant)

        # 添加到标签页
        self.tabs.addTab(self.tab_watchlist, "📋 自选股管理")
        self.tabs.addTab(self.tab_display, "🎨 显示设置")
        self.tabs.addTab(self.tab_quant, "📊 量化预警")

        main_layout.addWidget(self.tabs)

    def _setup_bottom_bar(self, main_layout):
        """设置底部工具栏（系统设置 + 按钮）[UI OPTIMIZATION]"""
        # 系统设置行（移出分组框）
        system_layout = QHBoxLayout()
        system_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        system_layout.setSpacing(6)  # 调整为 6px 间距
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
        self.refresh_combo.addItems(["1 秒", "2 秒", "5 秒", "10 秒", "30 秒"])
        self.refresh_combo.setMinimumWidth(80)
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
        system_layout.addSpacing(6)  # 调整为 6px 间距
        system_layout.addWidget(QLabel("刷新频率:"))
        system_layout.addWidget(self.refresh_combo)
        system_layout.addSpacing(6)  # 调整为 6px 间距

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

    def _setup_watchlist_ui(self, parent_widget):
        """设置自选股管理 UI [UI OPTIMIZATION - 左右布局，展示更多股票]"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        parent_widget.setLayout(main_layout)

        # === 使用左右分栏布局，增加列表横向展示空间 ===
        watchlist_row_layout = QHBoxLayout()
        watchlist_row_layout.setSpacing(20)  # 增加分组间距

        # === 左侧：搜索区域 (占 50%) ===
        search_group = QGroupBox("🔍 搜索股票")
        search_layout = QVBoxLayout()
        search_layout.setContentsMargins(10, 10, 10, 10)
        search_layout.setSpacing(8)

        # 搜索输入框（增加高度）
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入股票代码或名称，按回车快速添加...")
        self.search_input.setFixedHeight(40)  # [OPTIMIZATION] 增加高度
        self.search_input.setObjectName("SettingsSearchInput")

        # 搜索结果列表（限制最大高度）
        self.search_results = QListWidget()
        self.search_results.setMaximumHeight(200)  # [OPTIMIZATION] 适当增加最大高度
        self.search_results.setObjectName("SettingsSearchResults")

        # 添加按钮
        self.add_button = QPushButton("➕ 添加到自选股")
        self.add_button.setObjectName("PrimaryButton")
        self.add_button.setFixedHeight(36)  # [OPTIMIZATION] 统一按钮高度
        self.add_button.setEnabled(False)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_results)
        search_layout.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignCenter)
        search_group.setLayout(search_layout)

        # === 右侧：自选股列表 (占 50%，展示更多股票) ===
        list_group = QGroupBox("📋 自选股列表 (可拖拽排序)")
        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(10, 10, 10, 10)
        list_layout.setSpacing(8)

        self.watch_list = DraggableListWidget()
        self.watch_list.setObjectName("SettingsWatchList")
        # [FIX] 设置列表项居中对齐 - 保持垂直列表形式
        self.watch_list.setFlow(QListView.Flow.TopToBottom)  # 从上到下排列（垂直列表）
        self.watch_list.setWrapping(False)  # 不自动换行
        self.watch_list.setViewMode(QListView.ViewMode.ListMode)  # 列表模式，一行一个
        self.watch_list.setMovement(
            QListView.Movement.Snap
        )  # Snap 模式：项对齐网格且允许拖拽排序
        self.watch_list.setStyleSheet(
            "QListWidget::item { text-align: center; }"
        )  # 文本居中对齐
        # ... 拖拽配置保持不变 ...
        self.watch_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.watch_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.watch_list.setDragEnabled(True)
        self.watch_list.setAcceptDrops(True)
        self.watch_list.setDropIndicatorShown(True)

        list_layout.addWidget(self.watch_list)
        list_group.setLayout(list_layout)

        # === 底部：操作按钮 ===
        button_group = QGroupBox("🛠️ 操作")
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 10, 10, 10)
        button_layout.setSpacing(12)

        # 删除按钮
        self.remove_button = QPushButton("🗑 删除")
        self.remove_button.setObjectName("removeButton")
        self.remove_button.setFixedHeight(36)  # [OPTIMIZATION] 统一按钮高度
        self.remove_button.setEnabled(False)

        # 上移按钮
        self.move_up_button = QPushButton("↑ 上移")
        self.move_up_button.setObjectName("move_up_button")
        self.move_up_button.setFixedHeight(36)  # [OPTIMIZATION] 统一按钮高度
        self.move_up_button.setEnabled(False)

        # 下移按钮
        self.move_down_button = QPushButton("↓ 下移")
        self.move_down_button.setObjectName("move_down_button")
        self.move_down_button.setFixedHeight(36)  # [OPTIMIZATION] 统一按钮高度
        self.move_down_button.setEnabled(False)

        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.move_up_button)
        button_layout.addWidget(self.move_down_button)
        button_group.setLayout(button_layout)

        # 添加到主布局 - 左右对称 50%:50%
        watchlist_row_layout.addWidget(search_group, stretch=1)  # 左侧 50%
        watchlist_row_layout.addWidget(list_group, stretch=1)  # 右侧 50%

        main_layout.addLayout(watchlist_row_layout)
        main_layout.addWidget(button_group)

    def _setup_display_settings_ui(self, parent_widget):
        """设置显示设置 UI [UI OPTIMIZATION - 标签页适配]"""
        # [UI OPTIMIZATION] 添加图标，优化间距
        display_group = QGroupBox("🎨 显示设置")
        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(15, 15, 15, 15)
        display_layout.setSpacing(12)
        display_group.setLayout(display_layout)

        # === 显示设置行 ===
        display_row_layout = QHBoxLayout()
        display_row_layout.setContentsMargins(0, 0, 0, 0)
        display_row_layout.setSpacing(15)  # [OPTIMIZATION] 增加间距

        # 字体大小设置
        font_layout = QHBoxLayout()
        font_layout.setSpacing(8)  # [OPTIMIZATION] 增加元素间距
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(10, 40)
        self.font_size_slider.setValue(13)  # 默认 13px
        self.font_size_slider.setMinimumWidth(120)  # [OPTIMIZATION] 统一滑块长度
        self.font_size_slider.setObjectName("FontSizeSlider")

        self.font_size_value_label = QLabel("13px")
        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_value_label.setText(f"{v}px")
        )

        font_layout.addWidget(QLabel("字体大小:"))
        font_layout.addWidget(self.font_size_slider)
        font_layout.addWidget(self.font_size_value_label)

        # 字体设置
        font_family_layout = QHBoxLayout()
        font_family_layout.setSpacing(8)  # [OPTIMIZATION] 增加元素间距
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["微软雅黑", "宋体", "黑体", "楷体", "仿宋"])
        self.font_family_combo.setMinimumWidth(120)
        font_family_layout.addWidget(QLabel("字    体:"))
        font_family_layout.addWidget(self.font_family_combo)

        # 透明度设置
        transparency_layout = QHBoxLayout()
        transparency_layout.setSpacing(8)  # [OPTIMIZATION] 增加元素间距
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(80)
        self.transparency_slider.setMinimumWidth(120)  # [OPTIMIZATION] 统一滑块长度

        # 极简滑块样式
        self.transparency_slider.setObjectName("TransparencySlider")

        self.transparency_value_label = QLabel("80%")
        self.transparency_slider.valueChanged.connect(
            lambda v: self.transparency_value_label.setText(f"{v}%")
        )
        transparency_layout.addWidget(QLabel("透明度:"))
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_value_label)

        display_row_layout.addLayout(font_layout)
        display_row_layout.addSpacing(20)  # [OPTIMIZATION] 增加分组间距
        display_row_layout.addLayout(font_family_layout)
        display_row_layout.addSpacing(20)  # [OPTIMIZATION] 增加分组间距
        display_row_layout.addLayout(transparency_layout)
        display_row_layout.addSpacing(20)  # [OPTIMIZATION] 增加分组间距

        # 添加恢复默认值按钮
        self.reset_display_button = QPushButton("↺ 恢复默认")
        self.reset_display_button.setMinimumWidth(100)  # [OPTIMIZATION] 增加按钮宽度
        self.reset_display_button.setObjectName("reset_display_button")
        self.reset_display_button.clicked.connect(self.reset_display_settings)
        display_row_layout.addWidget(self.reset_display_button)

        display_row_layout.addStretch()

        display_layout.addLayout(display_row_layout)

        # [FIXED] 添加到父 widget 的 layout
        container_layout = QVBoxLayout()
        container_layout.addWidget(display_group)
        parent_widget.setLayout(container_layout)

    def _setup_quant_settings_ui(self, parent_widget):
        """设置量化分析与预警 UI [UI OPTIMIZATION - 标签页适配]"""
        # [UI OPTIMIZATION] 简化标题，移除冗余文字
        quant_group = QGroupBox("📊 量化分析预警")
        quant_layout = QVBoxLayout()
        quant_layout.setContentsMargins(15, 15, 15, 15)
        quant_layout.setSpacing(12)
        quant_group.setLayout(quant_layout)

        # 启动开关
        # [UI OPTIMIZATION] 精简复选框标签，移除技术细节
        self.quant_enabled_checkbox = QCheckBox("开启智能扫描")
        self.quant_enabled_checkbox.setToolTip(
            "开启后将在后台静默拉取 15m/30m/60m/日线 等数据并执行底层复杂算力运算。\n"
            "包括：MACD 底背离 / BBands 收口变盘 / 主力碎步吸筹等信号检测"
        )
        quant_layout.addWidget(self.quant_enabled_checkbox)

        # --- 推送通道选择 ---
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("通知渠道:"))
        self.push_mode_combo = QComboBox()
        self.push_mode_combo.addItem("群机器人 (Webhook)", "webhook")
        self.push_mode_combo.addItem("企业自建应用 (Agent)", "app")
        self.push_mode_combo.setFixedWidth(150)
        channel_layout.addWidget(self.push_mode_combo)
        channel_layout.addStretch()
        quant_layout.addLayout(channel_layout)

        # --- Webhook 配置区域 ---
        self.webhook_container = QWidget()
        webhook_sub_layout = QVBoxLayout(self.webhook_container)
        webhook_sub_layout.setContentsMargins(0, 5, 0, 5)
        webhook_sub_layout.setSpacing(8)

        h_layout = QHBoxLayout()
        label = QLabel("Webhook 地址:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度
        h_layout.addWidget(label)
        self.wecom_webhook_input = QLineEdit()
        self.wecom_webhook_input.setPlaceholderText(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
        )
        h_layout.addWidget(self.wecom_webhook_input)

        self.test_push_button = QPushButton("🧪 测试推送")
        self.test_push_button.setObjectName("PrimaryButton")
        self.test_push_button.setFixedWidth(100)
        h_layout.addWidget(self.test_push_button)
        webhook_sub_layout.addLayout(h_layout)
        quant_layout.addWidget(self.webhook_container)

        # --- 企业应用配置区域 ---
        self.app_container = QWidget()
        app_sub_layout = QVBoxLayout(self.app_container)
        app_sub_layout.setContentsMargins(0, 5, 0, 5)
        app_sub_layout.setSpacing(8)

        # CorpID
        corp_layout = QHBoxLayout()
        label = QLabel("企业 ID:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度，简化文字
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        corp_layout.addWidget(label)
        self.wecom_corpid_input = QLineEdit()
        self.wecom_corpid_input.setPlaceholderText("请输入企业 ID")
        corp_layout.addWidget(self.wecom_corpid_input)

        # Secret
        secret_layout = QHBoxLayout()
        label = QLabel("应用密钥:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        secret_layout.addWidget(label)
        self.wecom_corpsecret_input = QLineEdit()
        self.wecom_corpsecret_input.setPlaceholderText("请输入应用密钥")
        self.wecom_corpsecret_input.setEchoMode(QLineEdit.EchoMode.Password)
        secret_layout.addWidget(self.wecom_corpsecret_input)

        # AgentID
        agent_layout = QHBoxLayout()
        label = QLabel("应用 ID:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        agent_layout.addWidget(label)
        self.wecom_agentid_input = QLineEdit()
        self.wecom_agentid_input.setPlaceholderText("请输入应用 ID")
        agent_layout.addWidget(self.wecom_agentid_input)

        self.test_app_button = QPushButton("🧪 测试应用")
        self.test_app_button.setObjectName("PrimaryButton")
        self.test_app_button.setFixedWidth(100)
        agent_layout.addWidget(self.test_app_button)

        app_sub_layout.addLayout(corp_layout)
        app_sub_layout.addLayout(secret_layout)
        app_sub_layout.addLayout(agent_layout)
        quant_layout.addWidget(self.app_container)

        # 全量复盘按钮
        self.btn_manual_report = QPushButton("🧩 立即执行全量复盘")
        self.btn_manual_report.setObjectName("PrimaryButton")
        self.btn_manual_report.setFixedWidth(180)
        self.btn_manual_report.setToolTip(
            "立即对所有自选股执行技术面分析并推送到企业微信"
        )
        quant_layout.addWidget(self.btn_manual_report, 0, Qt.AlignmentFlag.AlignCenter)

        # [FIXED] 添加到父 widget 的 layout
        container_layout = QVBoxLayout()
        container_layout.addWidget(quant_group)
        parent_widget.setLayout(container_layout)

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
        self.refresh_combo.setMinimumWidth(80)
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
            self.check_update_button.setEnabled(False)
            self.check_update_button.setText("检查中...")

            # [P2 FIX] 使用提取的线程类，避免内联定义
            self._update_thread = UpdateCheckThread()
            self._update_thread.finished_check.connect(self._on_update_check_result)
            self._update_thread.error_occurred.connect(
                lambda e: self._on_update_check_result(None, error_msg=e)
            )
            self._update_thread.finished.connect(self._update_thread.deleteLater)
            self._update_thread.start()

        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"启动自动更新检查失败：{e}")
            self._on_update_check_result(None, error_msg=str(e))

    def _on_update_check_result(self, result, error_msg=None):
        """处理更新检查结果"""
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("检查更新")

        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

        from stock_monitor.core.updater import app_updater

        if error_msg:
            QMessageBox.critical(
                self,
                "检查更新失败",
                f"检查更新失败：{error_msg}",
                QMessageBox.StandardButton.Ok,
            )
            return

        try:
            if result is True:
                # 有新版本，显示提示框
                latest_version = (
                    app_updater.latest_release_info.get("tag_name", "")
                    .replace("stock_monitor_", "")
                    .replace("v", "")
                )
                release_body = app_updater.latest_release_info.get(
                    "body", "暂无更新说明"
                )

                message = f"发现新版本!\n\n当前版本: {app_updater.current_version}\n最新版本: {latest_version}\n\n更新说明:\n{release_body}\n\n是否现在更新?"

                reply = QMessageBox.question(
                    self,
                    "发现新版本",
                    message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    progress_dialog = QProgressDialog(
                        "正在下载更新...", "取消", 0, 100, self
                    )
                    progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                    progress_dialog.setWindowTitle("下载更新")
                    progress_dialog.setAutoClose(True)
                    progress_dialog.setAutoReset(True)
                    progress_dialog.show()

                    def progress_cb(percent):
                        progress_dialog.setValue(percent)
                        QApplication.processEvents()

                    def is_cancelled_cb():
                        QApplication.processEvents()
                        return progress_dialog.wasCanceled()

                    def security_warn_cb(warn_msg):
                        reply_warn = QMessageBox.warning(
                            self,
                            "安全提示",
                            warn_msg,
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.Yes,
                        )
                        return reply_warn == QMessageBox.StandardButton.Yes

                    def error_cb(err_msg):
                        QMessageBox.critical(
                            self, "更新错误", err_msg, QMessageBox.StandardButton.Ok
                        )

                    # 下载更新
                    update_file = app_updater.download_update(
                        progress_callback=progress_cb,
                        is_cancelled_callback=is_cancelled_cb,
                        security_warning_callback=security_warn_cb,
                        error_callback=error_cb,
                    )

                    progress_dialog.close()

                    if update_file:
                        # 应用更新
                        if not app_updater.apply_update(update_file):
                            QMessageBox.critical(
                                self,
                                "更新失败",
                                "应用更新包时发生错误",
                                QMessageBox.StandardButton.Ok,
                            )
                    else:
                        if not progress_dialog.wasCanceled():
                            QMessageBox.warning(
                                self,
                                "下载失败",
                                "更新包下载失败,请检查网络连接后重试。",
                                QMessageBox.StandardButton.Ok,
                            )
            elif result is False:
                QMessageBox.information(
                    self,
                    "无更新",
                    "当前已是最新版本，无需更新",
                    QMessageBox.StandardButton.Ok,
                )
            else:
                QMessageBox.critical(
                    self,
                    "检查更新失败",
                    "检查更新失败：网络连接异常，请稍后重试",
                    QMessageBox.StandardButton.Ok,
                )
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"处理更新结果失败: {e}")

    def _on_test_push_clicked(self):
        """测试 Webhook 推送"""
        import time

        # [P1 FIX] 检查冷却时间
        current_time = time.time()
        if current_time - self._last_webhook_test_time < self._webhook_test_cooldown:
            remaining = int(
                self._webhook_test_cooldown
                - (current_time - self._last_webhook_test_time)
            )
            QMessageBox.warning(self, "请求过于频繁", f"请在 {remaining} 秒后再试")
            return

        webhook = self.wecom_webhook_input.text().strip()
        if not webhook:
            QMessageBox.warning(self, "提示", "请先输入 Webhook 地址")
            return

        from ...services.notifier import NotifierService

        success = NotifierService.send_wecom_webhook_text(
            webhook, "这是一条来自股票监控系统的 Webhook 测试消息 🚀"
        )

        if success:
            self._last_webhook_test_time = current_time
            QMessageBox.information(self, "成功", "测试消息已发出，请检查企业微信通知")
        else:
            QMessageBox.critical(self, "失败", "发送失败，请检查 Webhook 地址是否正确")

    def _on_test_app_clicked(self):
        """测试企业应用推送"""
        config = {
            "wecom_corpid": self.wecom_corpid_input.text().strip(),
            "wecom_corpsecret": self.wecom_corpsecret_input.text().strip(),
            "wecom_agentid": self.wecom_agentid_input.text().strip(),
        }

        if not all(config.values()):
            QMessageBox.warning(self, "提示", "请完整填写企业 ID、Secret 和 AgentID")
            return

        from ...services.notifier import NotifierService

        success = NotifierService.send_wecom_app_message(
            config,
            "🚀 企业应用测试成功",
            "您的股票监控系统已成功通过企业自建应用通道连接！\n当前时间: "
            + time.strftime("%H:%M:%S"),
        )

        if success:
            QMessageBox.information(
                self, "成功", "测试应用卡片已发出，请检查手机企业微信"
            )
        else:
            QMessageBox.critical(self, "失败", "发送失败，请检查配置参数及网络状态")

    def _on_push_mode_changed(self):
        """根据推送模式切换 UI 显示"""
        mode = self.push_mode_combo.currentData()
        self.webhook_container.setVisible(mode == "webhook")
        self.app_container.setVisible(mode == "app")

    def _on_vm_error(self, message: str):
        """处理来自 ViewModel 的错误信号"""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(self, "预警测试", message)

    def _on_search_results_updated(self, results):
        """Update search results from ViewModel"""
        self.search_results.clear()
        if not results:
            return

        for item_data in results:
            display_text = item_data["display"]
            item = QListWidgetItem(display_text)
            # Store code in user role
            item.setData(Qt.ItemDataRole.UserRole, item_data["code"])
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
                # viewModel load_user_stocks already cleans it in MainWindowViewModel.
                # ConfigManager stores clean codes.
                item.setData(Qt.ItemDataRole.UserRole, stock_code)
                self.watch_list.addItem(item)

            # Other settings
            self.auto_start_checkbox.setChecked(settings.get("auto_start", False))

            # Refresh interval logic
            ri = settings.get("refresh_interval", 5)
            map_val_to_text = {1: "1秒", 2: "2秒", 5: "5秒", 10: "10秒", 30: "30秒"}
            text = map_val_to_text.get(ri, "5秒")
            index = self.refresh_combo.findText(text)
            if index >= 0:
                self.refresh_combo.setCurrentIndex(index)
            else:
                self.refresh_combo.setCurrentIndex(1)

            # Font size
            fs = settings.get("font_size", 13)
            self.font_size_slider.setValue(int(fs))

            # Font family
            ff = settings.get("font_family", "微软雅黑")
            index = self.font_family_combo.findText(ff)
            if index >= 0:
                self.font_family_combo.setCurrentIndex(index)

            # Transparency
            tp = settings.get("transparency", 80)
            self.transparency_slider.setValue(int(tp))

            # Quant settings
            self.quant_enabled_checkbox.setChecked(settings.get("quant_enabled", False))
            self.wecom_webhook_input.setText(settings.get("wecom_webhook", ""))

            # 新增企微应用配置加载
            push_mode = settings.get("push_mode", "webhook")
            index = self.push_mode_combo.findData(push_mode)
            if index >= 0:
                self.push_mode_combo.setCurrentIndex(index)

            self.wecom_corpid_input.setText(settings.get("wecom_corpid", ""))
            self.wecom_corpsecret_input.setText(settings.get("wecom_corpsecret", ""))
            self.wecom_agentid_input.setText(settings.get("wecom_agentid", ""))

            self._on_push_mode_changed()
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"Failed to load config from VM: {e}")

    def _save_config_via_vm(self):
        """Save config via VM"""
        try:
            stocks = self.get_stocks_from_list(self.watch_list)

            # Map refresh text to int
            map_text_to_val = {
                "1 秒": 1,
                "2 秒": 2,
                "5 秒": 5,
                "10 秒": 10,
                "30 秒": 30,
            }
            ri_text = self.refresh_combo.currentText()
            ri = map_text_to_val.get(ri_text, 5)

            settings = {
                "user_stocks": stocks,
                "auto_start": self.auto_start_checkbox.isChecked(),
                "refresh_interval": ri,
                "font_size": self.font_size_slider.value(),
                "font_family": self.font_family_combo.currentText(),
                "transparency": self.transparency_slider.value(),
                "quant_enabled": self.quant_enabled_checkbox.isChecked(),
                "wecom_webhook": self.wecom_webhook_input.text().strip(),
            }

            # 新增企微应用配置保存
            settings["push_mode"] = self.push_mode_combo.currentData()
            settings["wecom_corpid"] = self.wecom_corpid_input.text().strip()
            settings["wecom_corpsecret"] = self.wecom_corpsecret_input.text().strip()
            settings["wecom_agentid"] = self.wecom_agentid_input.text().strip()

            from stock_monitor.utils.logger import app_logger

            # [P1 FIX] 保存前先验证配置有效性
            if not self.viewModel.validate_settings(settings):
                return False  # 验证失败，阻止保存

            self.viewModel.save_settings(settings)
            return True
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"Failed to save config via VM: {e}")
            return False

    def _on_ok_clicked(self):
        """点击确定按钮的处理函数"""
        # 1. 保存配置
        if self._save_config_via_vm():
            # 2. 保存成功，执行接受操作
            self.accept()

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

    def _handle_stock_search_added(self, code: str, name: str):
        """处理来自搜索组件传来的添加订阅信号"""
        # 1. 检查自选股是否已存在
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                # 优先从UserRole获取代码
                user_data = item.data(Qt.ItemDataRole.UserRole)
                if user_data == code:
                    from PyQt6 import QtWidgets

                    QtWidgets.QMessageBox.information(
                        self, "提示", f"股票 {name} 已在自选股列表中"
                    )
                    return
                # 如果UserRole没有，尝试从显示文本中解析
                elif f"({code})" in item.text():
                    from PyQt6 import QtWidgets

                    QtWidgets.QMessageBox.information(
                        self, "提示", f"股票 {name} 已在自选股列表中"
                    )
                    return

        # 2. 从视图底层添加新的元素
        from stock_monitor.utils.helpers import get_stock_emoji

        emoji = get_stock_emoji(code, name)

        display_text = f"{emoji} {name} ({code})"
        if code.startswith("hk") and name:
            if "-" in name:
                name = name.split("-")[0].strip()
            display_text = f"{emoji} {name} ({code})"
        elif not name:
            display_text = f"{emoji} {code}"

        from PyQt6.QtWidgets import QListWidgetItem

        new_item = QListWidgetItem(display_text)
        new_item.setData(Qt.ItemDataRole.UserRole, code)
        self.watch_list.addItem(new_item)

        # 3. 触发与后端数据同步 (如果需要，这里可以调用保存配置的方法)
        # self._save_config_via_vm() # 暂时不在这里保存，由accept统一保存
        self.watch_list_manager.update_remove_button_state()
        self.watch_list.clearSelection()  # 取消自选股列表的选中状态

    def add_stock_from_search(self, item=None):
        """将股票添加到自选股列表"""
        # [P2 FIX] 重构为多个小方法，降低复杂度
        item = self._resolve_item(item)
        if item is None:
            return

        code, name = self._parse_item_text(item)
        if not code:
            return

        clean_code = self._format_and_validate_code(code)
        if not clean_code:
            return

        if self._is_duplicate(clean_code):
            self._show_duplicate_warning(name)
            return

        self._add_to_watchlist(clean_code, name)

    def _resolve_item(self, item):
        """解析 item 参数，确保是有效的 QListWidgetItem"""
        if item is None or isinstance(item, bool):
            selected_items = self.search_results.selectedItems()
            if not selected_items:
                return None
            return selected_items[0]
        return item

    def _parse_item_text(self, item):
        """从 item 文本中解析股票代码和名称"""
        try:
            item_text = item.text()
        except AttributeError:
            from stock_monitor.utils.logger import app_logger

            app_logger.warning(f"无效的 item 类型：{type(item)}")
            return None, None

        import re

        match = re.search(r"\(([^)]+)\)", item_text)
        if match:
            code = match.group(1)
            name = item_text.replace(f" ({code})", "").strip()
            if name.endswith(code):
                name = name[: -len(code)].strip()
        else:
            parts = item_text.split()
            if len(parts) >= 2:
                code = parts[0]
                name = " ".join(parts[1:])
            else:
                code = item_text
                name = ""
        return code, name

    def _format_and_validate_code(self, code):
        """格式化并验证股票代码"""
        from stock_monitor.utils.stock_utils import StockCodeProcessor

        processor = StockCodeProcessor()
        clean_code = processor.format_stock_code(code)
        return clean_code if clean_code else None

    def _is_duplicate(self, code):
        """检查股票是否已在列表中"""
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                user_data = item.data(Qt.ItemDataRole.UserRole)
                if user_data == code or f"({code})" in item.text():
                    return True
        return False

    def _show_duplicate_warning(self, name):
        """显示重复警告"""
        from PyQt6 import QtWidgets

        QtWidgets.QMessageBox.information(self, "提示", f"股票 {name} 已在自选股列表中")

    def _add_to_watchlist(self, code, name):
        """将股票添加到列表"""
        from stock_monitor.utils.helpers import get_stock_emoji

        emoji = get_stock_emoji(code, name)

        display_text = f"{emoji} {name} ({code})"
        if code.startswith("hk") and name:
            if "-" in name:
                name = name.split("-")[0].strip()
            display_text = f"{emoji} {name} ({code})"
        elif not name:
            display_text = f"{emoji} {code}"

        from PyQt6.QtWidgets import QListWidgetItem

        new_item = QListWidgetItem(display_text)
        new_item.setData(Qt.ItemDataRole.UserRole, code)
        self.watch_list.addItem(new_item)

        self.watch_list_manager.update_remove_button_state()
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
            # win32com 不可用时的备选方案
            from stock_monitor.utils.logger import app_logger

            app_logger.warning(
                "pywin32 未安装，无法创建开机启动快捷方式。"
                "建议运行：pip install pywin32"
            )
            # 不再创建批处理文件作为备选，因为安全性和用户体验较差
            return False

    def accept(self):
        """点击确定按钮时保存设置"""
        # [P1 FIX] 拆分为多个小方法，遵循单一职责原则
        self._apply_auto_start()
        self._cleanup_preview_state()
        self._emit_config_changed_signal()
        self._update_original_watch_list()
        self.hide()

    def _apply_auto_start(self):
        """应用开机启动设置"""
        auto_start_enabled = self.auto_start_checkbox.isChecked()
        self._set_auto_start(auto_start_enabled)

    def _cleanup_preview_state(self):
        """清理预览状态并恢复主窗口默认状态"""
        if self.main_window:
            if hasattr(self.main_window, "_preview_transparency"):
                delattr(self.main_window, "_preview_transparency")
            self.main_window.update()
            if hasattr(self.main_window, "menu") and self.main_window.menu:
                self.main_window.menu.restore_default_style()

    def _emit_config_changed_signal(self):
        """发送配置更改信号"""
        if self.main_window:
            stocks = self.get_stocks_from_list(self.watch_list)
            refresh_interval = self._map_refresh_text_to_value(
                self.refresh_combo.currentText()
            )
            from stock_monitor.utils.logger import app_logger

            app_logger.info(
                f"发送配置更改信号：股票列表={stocks}, 刷新间隔={refresh_interval}"
            )
            self.config_changed.emit(stocks, refresh_interval)

    def _update_original_watch_list(self):
        """更新原始自选股列表"""
        self.original_watch_list = []
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                self.original_watch_list.append(item.text())

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
        mapping = {1: "1 秒", 2: "2 秒", 5: "5 秒", 10: "10 秒", 30: "30 秒"}
        return mapping.get(value, "2 秒")

    # [DEPRECATED] on_display_setting_changed 已移除，实时预览功能被禁用

    def on_font_setting_changed(self):
        """字体设置变化时的处理函数，用于实时预览（带防抖）"""
        if not self.main_window:
            return

        try:
            # 获取当前字体设置
            font_size = self.font_size_slider.value()
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
            self.font_size_slider.setValue(13)
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

    def closeEvent(self, event: QtGui.QCloseEvent):
        """设置对话框关闭事件 - 清理资源、断开信号连接"""
        try:
            # 1. 停止并清理定时器
            if hasattr(self, "_font_preview_timer") and self._font_preview_timer:
                try:
                    self._font_preview_timer.stop()
                    # 不立即调用 deleteLater()，避免后续访问已删除对象
                    self._font_preview_timer = None
                except Exception:
                    pass  # 忽略定时器已删除的错误

            # 2. 断开 ViewModel 信号（只断开由本实例连接的）
            if hasattr(self, "viewModel"):
                try:
                    self.viewModel.search_results_updated.disconnect(
                        self._on_search_results_updated
                    )
                    self.viewModel.save_completed.disconnect(self.accept)
                    self.viewModel.error_occurred.disconnect(self._on_vm_error)
                except Exception:
                    pass  # 忽略信号未连接的错误

            # 3. 断开 UI 组件信号（只断开关键信号，避免重复断开）
            # 注意：Qt 的 disconnect 在信号未连接时会抛出异常，因此需要 try-except
            # 但我们应该只断开确实由我们连接的信号
            try:
                # 搜索相关
                self.search_input.textChanged.disconnect(self.viewModel.search_stocks)
                self.search_input.returnPressed.disconnect(
                    self._on_search_return_pressed
                )
                self.search_results.itemDoubleClicked.disconnect(
                    self.add_stock_from_search
                )
                # 按钮相关
                self.ok_button.clicked.disconnect(self._save_config_via_vm)
                self.cancel_button.clicked.disconnect(self.reject)
                # 设置相关
                self.font_size_slider.valueChanged.disconnect(
                    self.on_font_setting_changed
                )
                self.font_family_combo.currentTextChanged.disconnect(
                    self.on_font_setting_changed
                )
                self.transparency_slider.valueChanged.disconnect(
                    self.on_transparency_changed
                )
            except Exception:
                pass  # 忽略信号未连接的错误

            from stock_monitor.utils.logger import app_logger

            app_logger.info("设置对话框资源清理完成")
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"设置对话框 closeEvent 清理失败：{e}")
        finally:
            # 隐藏窗口而不是真正关闭
            self.hide()
            if event:
                event.ignore()  # 阻止窗口真正关闭

    def hideEvent(self, event: QtGui.QHideEvent):
        """设置对话框隐藏事件 - 清理预览状态"""
        try:
            # 清除主窗口的预览透明度
            if self.main_window:
                if hasattr(self.main_window, "_preview_transparency"):
                    delattr(self.main_window, "_preview_transparency")
                if hasattr(self.main_window, "menu") and self.main_window.menu:
                    self.main_window.menu.restore_default_style()
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"设置对话框 hideEvent 处理失败：{e}")
        finally:
            super().hideEvent(event)

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
