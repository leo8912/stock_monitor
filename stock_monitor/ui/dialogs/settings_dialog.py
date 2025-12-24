"""
设置对话框模块
"""

import os
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
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
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from stock_monitor.utils.helpers import resource_path
from stock_monitor.version import __version__


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


class StockSearchHandler:
    """股票搜索处理类"""

    def __init__(self, search_input, search_results, watch_list, parent_dialog=None):
        self.search_input = search_input
        self.search_results = search_results
        self.watch_list = watch_list
        self.parent_dialog = parent_dialog
        self._setup_search_ui()

    def _setup_search_ui(self):
        """设置搜索UI组件"""
        self.search_input.setPlaceholderText("输入股票代码或名称...")
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

    def on_search_text_changed(self, text):
        """
        搜索框文本改变时的处理函数

        Args:
            text (str): 输入的文本
        """
        text = text.strip()
        if len(text) < 1:
            self.search_results.clear()
            return

        try:
            # 从本地缓存加载股票数据
            from stock_monitor.data.stock.stocks import load_stock_data

            all_stocks_list = load_stock_data()

            # 转换为字典格式以匹配原有逻辑
            all_stocks: dict[str, Any] = {}
            for stock in all_stocks_list:
                all_stocks[stock["code"]] = stock

            if not all_stocks:
                return

            self.search_results.clear()

            # 过滤匹配的股票并计算优先级
            matched_stocks = []
            for code, stock in all_stocks.items():
                if (
                    text.lower() in code.lower()
                    or text.lower() in stock.get("name", "").lower()
                ):
                    # 计算优先级，A股优先
                    priority = 0
                    if code.startswith(("sh", "sz")) and not code.startswith(
                        ("sh000", "sz399")
                    ):
                        priority = 10  # A股最高优先级
                    elif code.startswith(("sh000", "sz399")):
                        priority = 5  # 指数次优先级
                    elif code.startswith("hk"):
                        priority = 1  # 港股较低优先级
                    matched_stocks.append((priority, code, stock))

            # 按优先级排序，优先级高的在前
            matched_stocks.sort(key=lambda x: (-x[0], x[1]))

            # 显示前20个匹配结果，使用标准格式化显示
            for _, code, stock in matched_stocks[:20]:
                # 使用统一的格式化方法显示搜索结果
                from stock_monitor.utils.helpers import get_stock_emoji

                emoji = get_stock_emoji(code, stock.get("name", ""))
                display_text = f"{emoji} {stock.get('name', '')} ({code})"
                self.search_results.addItem(display_text)

            # 取消自选股列表的选中状态
            self.watch_list.clearSelection()
        except Exception as e:
            from stock_monitor.utils.error_handler import app_logger

            app_logger.error(f"搜索股票时出错: {e}")

    def _on_search_return_pressed(self):
        """处理搜索框回车键按下事件"""
        # 如果有搜索结果，添加第一个结果
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            # 通过外部引用来调用add_stock_from_search方法
            if self.parent_dialog:
                self.parent_dialog.add_stock_from_search(item)
            # 清空搜索框
            self.search_input.clear()
            self.search_results.clear()

        # 取消自选股列表的选中状态
        self.watch_list.clearSelection()


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


class ConfigManagerHandler:
    """配置管理处理类"""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def load_config(
        self,
        watch_list,
        auto_start_checkbox,
        refresh_combo,
        font_size_spinbox,
        font_family_combo,
        transparency_slider,
    ):
        """加载配置"""
        # 加载自选股列表
        try:
            # 使用依赖注入容器获取配置管理器
            from stock_monitor.config.manager import ConfigManager
            from stock_monitor.core.container import container

            config_manager = container.get(ConfigManager)

            # 加载自选股列表
            user_stocks = config_manager.get("user_stocks", [])
            watch_list.clear()

            # 加载股票数据用于显示股票名称
            from stock_monitor.data.stock.stocks import load_stock_data

            all_stocks_list = load_stock_data()
            all_stocks_dict = {stock["code"]: stock for stock in all_stocks_list}

            for stock_code in user_stocks:
                # 确保股票代码是干净的，不含额外文本
                # 提取股票代码部分（处理可能存在的"code name"格式或"⭐️ code"格式）
                clean_code = stock_code
                if "⭐️" in stock_code:
                    clean_code = stock_code.replace("⭐️", "").strip()

                # 再次尝试清理，提取第一部分
                if clean_code.split():
                    clean_code = clean_code.split()[0]

                # 尝试查找股票的完整信息
                from stock_monitor.utils.stock_utils import StockCodeProcessor

                processor = StockCodeProcessor()
                formatted_code = processor.format_stock_code(clean_code)
                if formatted_code:
                    clean_code = formatted_code

                stock_info = all_stocks_dict.get(clean_code)
                if stock_info:
                    from stock_monitor.utils.helpers import get_stock_emoji

                    emoji = get_stock_emoji(clean_code, stock_info.get("name", ""))
                    name = stock_info.get("name", "")
                    if name:
                        display_text = f"{emoji} {name} ({clean_code})"
                    else:
                        display_text = f"{emoji} {clean_code}"
                else:
                    # 如果找不到股票信息，只显示代码
                    from stock_monitor.utils.helpers import get_stock_emoji

                    emoji = get_stock_emoji(clean_code, "")
                    display_text = f"{emoji} {clean_code}"

                # 创建Item并存储原始代码到UserRole
                from PyQt6.QtWidgets import QListWidgetItem

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, clean_code)
                watch_list.addItem(item)
        except Exception:
            watch_list.clear()

        # 加载开机启动设置
        try:
            # 使用依赖注入容器获取配置管理器
            from stock_monitor.config.manager import ConfigManager
            from stock_monitor.core.container import container

            config_manager = container.get(ConfigManager)
            auto_start = config_manager.get("auto_start", False)
            auto_start = _safe_bool_conversion(auto_start, False)
            auto_start_checkbox.setChecked(auto_start)
        except Exception:
            auto_start_checkbox.setChecked(False)

        # 加载刷新频率设置
        try:
            # 使用依赖注入容器获取配置管理器
            from stock_monitor.config.manager import ConfigManager
            from stock_monitor.core.container import container

            config_manager = container.get(ConfigManager)
            config_manager.get("refresh_interval", 5)
        except Exception:
            refresh_combo.setCurrentIndex(1)  # 默认5秒

        # 加载字体设置
        try:
            font_size = self.config_manager.get("font_size", 13)  # 默认改为13
            font_size = _safe_int_conversion(font_size, 13)
            # 确保即使配置文件中有错误值，字体大小也是正数
            if font_size <= 0:
                font_size = 13
            font_size_spinbox.setValue(font_size)

            # 加载字体族设置
            font_family = self.config_manager.get("font_family", "微软雅黑")
            index = font_family_combo.findText(font_family)
            if index >= 0:
                font_family_combo.setCurrentIndex(index)
            else:
                font_family_combo.setCurrentIndex(0)  # 默认微软雅黑
        except Exception:
            font_size_spinbox.setValue(13)  # 默认13px
            font_family_combo.setCurrentIndex(0)  # 默认微软雅黑

        # 加载透明度设置
        try:
            transparency = self.config_manager.get("transparency", 80)
            transparency = _safe_int_conversion(transparency, 80)
            transparency_slider.setValue(transparency)
        except Exception:
            transparency_slider.setValue(80)

        # 加载拖拽灵敏度设置
        try:
            drag_sensitivity = self.config_manager.get("drag_sensitivity", 5)
            drag_sensitivity = _safe_int_conversion(drag_sensitivity, 5)
        except Exception:
            pass

    def save_config(
        self,
        watch_list,
        auto_start_checkbox,
        refresh_combo,
        font_size_spinbox,
        font_family_combo,
        transparency_slider,
    ):
        """保存配置"""
        try:
            # 保存自选股列表
            user_stocks = self.get_stocks_from_list(watch_list)
            self.config_manager.set("user_stocks", user_stocks)

            # 保存开机启动设置
            auto_start_enabled = auto_start_checkbox.isChecked()
            self.config_manager.set("auto_start", auto_start_enabled)

            # 保存刷新频率设置
            refresh_text = refresh_combo.currentText()
            refresh_interval = self._map_refresh_text_to_value(refresh_text)
            self.config_manager.set("refresh_interval", refresh_interval)

            # 保存字体设置 - 直接使用spinbox的值
            font_size = font_size_spinbox.value()
            self.config_manager.set("font_size", font_size)

            # 保存字体族设置
            font_family = font_family_combo.currentText()
            self.config_manager.set("font_family", font_family)

            # 保存透明度设置
            self.config_manager.set("transparency", transparency_slider.value())

            # 添加调试信息
            from stock_monitor.utils.logger import app_logger

            app_logger.info(f"保存设置时的自选股列表: {user_stocks}")
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"保存设置时出错: {e}")

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

    def _map_refresh_text_to_value(self, text):
        """将刷新频率文本映射为数值"""
        mapping = {"2秒": 2, "5秒": 5, "10秒": 10, "30秒": 30}
        return mapping.get(text, 5)  # 默认5秒

    def _map_refresh_value_to_text(self, value):
        """将刷新频率数值映射为文本"""
        mapping = {2: "2秒", 5: "5秒", 10: "10秒", 30: "30秒"}
        return mapping.get(value, "5秒")  # 默认5秒


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
        # 使用依赖注入容器获取配置管理器
        from stock_monitor.config.manager import ConfigManager
        from stock_monitor.core.container import container

        self.config_manager = container.get(ConfigManager)

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
        self.stock_search_handler = StockSearchHandler(
            self.search_input, self.search_results, self.watch_list, self
        )
        self.watch_list_manager = WatchListManager(
            self.watch_list,
            self.remove_button,
            self.move_up_button,
            self.move_down_button,
        )
        self.config_manager_handler = ConfigManagerHandler(self.config_manager)

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
        self.load_config()

        # 保存原始自选股列表，用于取消操作时恢复
        self.original_watch_list = []
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                self.original_watch_list.append(item.text())

    def _connect_signals(self):
        """连接所有信号槽"""
        # 连接搜索相关信号
        self.search_input.textChanged.connect(
            self.stock_search_handler.on_search_text_changed
        )
        self.search_input.returnPressed.connect(
            self.stock_search_handler._on_search_return_pressed
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
        self.ok_button.clicked.connect(self.accept)
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

            app_logger.error(f"检查更新时发生错误: {e}")
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "检查更新失败",
                "检查更新失败：网络连接异常，请稍后重试",
                QMessageBox.StandardButton.Ok,
            )

    def on_search_text_changed(self, text):
        """
        搜索框文本改变时的处理函数

        Args:
            text (str): 输入的文本
        """
        text = text.strip()
        if len(text) < 1:
            self.search_results.clear()
            return

        try:
            # 使用数据库直接搜索，无需加载全部数据
            from stock_monitor.data.stock.stock_db import stock_db

            matched_stocks = stock_db.search_stocks(text, limit=30)

            self.search_results.clear()

            if not matched_stocks:
                # 显示"无结果"提示
                from PyQt6 import QtGui
                from PyQt6.QtCore import Qt
                from PyQt6.QtWidgets import QListWidgetItem

                no_result_item = QListWidgetItem("未找到匹配的股票")
                no_result_item.setFlags(Qt.ItemFlag.NoItemFlags)  # 不可选中
                no_result_item.setForeground(QtGui.QColor("#888"))  # 灰色文字
                self.search_results.addItem(no_result_item)
                return

            # 显示搜索结果
            for stock in matched_stocks:
                code = stock["code"]
                name = stock["name"]
                # 使用统一的格式化方法显示搜索结果
                from stock_monitor.utils.helpers import get_stock_emoji

                emoji = get_stock_emoji(code, name)
                display_text = f"{emoji} {name} ({code})"
                self.search_results.addItem(display_text)

            # 取消自选股列表的选中状态
            self.watch_list.clearSelection()
        except Exception as e:
            from stock_monitor.utils.error_handler import app_logger

            app_logger.error(f"搜索股票时出错: {e}")

    def _on_search_return_pressed(self):
        """处理搜索框回车键按下事件"""
        # 如果有搜索结果，添加第一个结果
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            self.add_stock_from_search(item)
            # 清空搜索框
            self.search_input.clear()
            self.search_results.clear()

        # 取消自选股列表的选中状态
        self.watch_list.clearSelection()

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

    def load_config(self):
        """加载配置"""
        self.config_manager_handler.load_config(
            self.watch_list,
            self.auto_start_checkbox,
            self.refresh_combo,
            self.font_size_spinbox,
            self.font_family_combo,
            self.transparency_slider,
        )

    def save_config(self):
        """保存配置"""
        self.config_manager_handler.save_config(
            self.watch_list,
            self.auto_start_checkbox,
            self.refresh_combo,
            self.font_size_spinbox,
            self.font_family_combo,
            self.transparency_slider,
        )

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
        self.save_config()

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
            stocks = self.get_stocks_from_list()
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

    def _extract_stock_code(self, text: str) -> str:
        """
        从显示文本中提取股票代码

        Args:
            text (str): 显示的文本

        Returns:
            str: 股票代码
        """
        import re

        match = re.search(r"\(([^)]+)\)", text)
        if match:
            return match.group(1)
        else:
            # 如果没有找到括号中的代码，尝试从文本中提取代码
            # 处理类似 "sz000063 中兴通讯" 这样的格式
            parts = text.split()
            if parts:
                # 使用股票代码处理器来验证和格式化代码
                from stock_monitor.utils.stock_utils import StockCodeProcessor

                processor = StockCodeProcessor()
                code = processor.format_stock_code(parts[0])
                if code:
                    return code
                else:
                    # 如果第一部分不是有效的代码，尝试整个文本
                    code = processor.format_stock_code(text)
                    if code:
                        return code
            return text

    def get_stocks_from_list(self):
        """
        从股票列表中提取股票代码

        Returns:
            list: 股票代码列表
        """
        stocks = []
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                # 优先从UserRole获取代码
                user_data = item.data(Qt.ItemDataRole.UserRole)
                if user_data:
                    stocks.append(user_data)
                    continue

                code = self._extract_stock_code(item.text())
                stocks.append(code)
        return stocks

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
