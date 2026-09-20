"""自选股管理页（P1）。

从 ``NewSettingsDialog`` 抽出的「📋 自选股管理」标签页：搜索、添加、去重、
拖拽排序与列表读写。本页持有 ``WatchListManager`` 与原始列表快照，仅依赖本页
控件 + ``ctx.view_model``（用于展示名解析）。
"""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..settings_widgets import DraggableListWidget, WatchListManager
from .base import SettingsPage
from .context import SettingsContext


class WatchlistPage(SettingsPage):
    """自选股管理页：搜索 / 添加 / 去重 / 排序。"""

    SETTINGS_KEYS = ("user_stocks",)

    def __init__(self, ctx: SettingsContext, parent=None) -> None:
        """初始化自选股页（列表管理器在 ``build`` 完成后创建）。"""
        super().__init__(ctx, parent)
        self.watch_list_manager = None
        self.original_watch_list = []

    def build(self, parent_widget) -> None:
        """在 ``parent_widget`` 上构建自选股管理 UI [UI OPTIMIZATION - 左右布局]"""
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

        # 初始化功能管理器（在 UI 组件创建之后）
        self.watch_list_manager = WatchListManager(
            self.watch_list,
            self.remove_button,
            self.move_up_button,
            self.move_down_button,
        )

        # 页内信号（自选股搜索 / 列表 / 排序按钮）收敛进本页
        view_model = self.ctx.view_model
        if view_model is not None:
            view_model.search_results_updated.connect(self._on_search_results_updated)
            self.search_input.textChanged.connect(view_model.search_stocks)
        self.search_input.returnPressed.connect(self._on_search_return_pressed)
        self.search_results.itemDoubleClicked.connect(self.add_stock_from_search)
        self.search_results.itemSelectionChanged.connect(
            lambda: self.add_button.setEnabled(
                len(self.search_results.selectedItems()) > 0
            )
        )
        self.watch_list.itemSelectionChanged.connect(
            self.watch_list_manager._update_move_buttons_state
        )
        self.watch_list.itemSelectionChanged.connect(
            lambda: self.remove_button.setEnabled(
                len(self.watch_list.selectedItems()) > 0
            )
        )
        self.remove_button.clicked.connect(
            self.watch_list_manager.remove_selected_stocks
        )
        self.move_up_button.clicked.connect(
            self.watch_list_manager.move_up_selected_stock
        )
        self.move_down_button.clicked.connect(
            self.watch_list_manager.move_down_selected_stock
        )
        self.add_button.clicked.connect(self.add_stock_from_search)

    def restore(self) -> None:
        """取消时回滚到原始自选股列表快照。"""
        self.watch_list.clear()
        for item in self.original_watch_list:
            self.watch_list.addItem(item)

    def cleanup(self) -> None:
        """关闭事件：断开本页连接（best-effort，忽略未连接错误）。"""
        try:
            view_model = self.ctx.view_model
            if view_model is not None:
                view_model.search_results_updated.disconnect(
                    self._on_search_results_updated
                )
                self.search_input.textChanged.disconnect(view_model.search_stocks)
            self.search_input.returnPressed.disconnect(self._on_search_return_pressed)
            self.search_results.itemDoubleClicked.disconnect(self.add_stock_from_search)
        except Exception:
            pass  # 忽略信号未连接的错误

    def load(self, settings: dict) -> None:
        """把配置中的自选股列表灌入列表控件。"""
        self.watch_list.clear()
        user_stocks = settings.get("user_stocks", [])
        for stock_code in user_stocks:
            # Use clean code directly if VM handles display info
            # But we need display text.
            display_text = self.ctx.view_model.get_stock_display_info(stock_code)
            item = QListWidgetItem(display_text)

            # Ensure we store clean code
            # viewModel load_user_stocks already cleans it in MainWindowViewModel.
            # ConfigManager stores clean codes.
            item.setData(Qt.ItemDataRole.UserRole, stock_code)
            self.watch_list.addItem(item)

    def collect(self, settings: dict) -> None:
        """把列表控件中的股票代码写回配置字典。"""
        settings["user_stocks"] = self.get_stocks_from_list(self.watch_list)

    def get_stocks_from_list(self, watch_list) -> list:
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

    def _handle_stock_search_added(self, code: str, name: str) -> None:
        """处理来自搜索组件传来的添加订阅信号"""
        self.add_stock_from_search((code, name))

    def add_stock_from_search(self, item=None) -> None:
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

    def _parse_item_text(self, item) -> tuple:
        """从 item 文本中解析股票代码和名称"""
        try:
            item_text = item.text()
        except AttributeError:
            from stock_monitor.utils.logger import app_logger

            app_logger.warning(f"无效的 item 类型：{type(item)}")
            return None, None

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

    def _is_duplicate(self, code) -> bool:
        """检查股票是否已在列表中"""
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                user_data = item.data(Qt.ItemDataRole.UserRole)
                if user_data == code or f"({code})" in item.text():
                    return True
        return False

    def _show_duplicate_warning(self, name) -> None:
        """显示重复警告"""
        QMessageBox.information(self, "提示", f"股票 {name} 已在自选股列表中")

    def _add_to_watchlist(self, code, name) -> None:
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

        new_item = QListWidgetItem(display_text)
        new_item.setData(Qt.ItemDataRole.UserRole, code)
        self.watch_list.addItem(new_item)

        self.watch_list_manager.update_remove_button_state()
        self.watch_list.clearSelection()

    def _on_search_results_updated(self, results) -> None:
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

    def _on_search_return_pressed(self) -> None:
        """Handle return pressed in search"""
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            self.add_stock_from_search(item)
            self.search_input.clear()
            self.search_results.clear()

    def _update_original_watch_list(self) -> None:
        """更新原始自选股列表"""
        self.original_watch_list = []
        for i in range(self.watch_list.count()):
            item = self.watch_list.item(i)
            if item:
                self.original_watch_list.append(item.text())
