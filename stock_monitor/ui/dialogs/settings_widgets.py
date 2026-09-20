"""设置对话框使用的自绘控件与列表管理器。

C4 结构治理（T13）：把原先内联在 ``settings_dialog.py`` 中的
``DraggableListWidget``（支持拖拽排序的列表控件）与 ``WatchListManager``
（自选股列表管理）抽到独立模块，降低对话框文件的体量与耦合。

两个类都不访问 ``NewSettingsDialog`` 的 ``self``：``DraggableListWidget``
纯粹是 ``QListWidget`` 子类，``WatchListManager`` 仅按构造参数持有控件引用，
因此搬迁风险最低。``settings_dialog`` 对这两个名字做 re-export 保持兼容。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QListWidget


class DraggableListWidget(QListWidget):
    """支持拖拽排序的列表控件"""

    def __init__(self, parent=None) -> None:
        """初始化支持内部拖拽排序的列表控件。"""
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def focusOutEvent(self, e) -> None:
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

    def mousePressEvent(self, e) -> None:
        """重写鼠标按下事件，处理空白区域点击"""
        # 检查点击位置是否在项目上
        item = self.itemAt(e.pos()) if e else None
        if item is None:
            # 点击在空白区域，取消所有选中
            self.clearSelection()

        super().mousePressEvent(e)


class WatchListManager:
    """自选股列表管理类"""

    def __init__(
        self, watch_list, remove_button, move_up_button, move_down_button
    ) -> None:
        """初始化自选股列表管理器并完成列表 UI 配置。

        Args:
            watch_list: 自选股列表控件。
            remove_button: 删除按钮。
            move_up_button: 上移按钮。
            move_down_button: 下移按钮。
        """
        self.watch_list = watch_list
        self.remove_button = remove_button
        self.move_up_button = move_up_button
        self.move_down_button = move_down_button
        self._setup_watch_list_ui()

    def _setup_watch_list_ui(self) -> None:
        """设置自选股列表UI"""
        self.watch_list.setObjectName("WatchListWidget")
        self.watch_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.watch_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.watch_list.setDragEnabled(True)
        self.watch_list.setAcceptDrops(True)
        self.watch_list.setDropIndicatorShown(True)

    def remove_selected_stocks(self) -> None:
        """删除选中的股票"""
        selected_items = self.watch_list.selectedItems()
        for item in selected_items:
            row = self.watch_list.row(item)
            self.watch_list.takeItem(row)
        self.update_remove_button_state()

        # 取消自选股列表的选中状态
        self.watch_list.clearSelection()

    def update_remove_button_state(self) -> None:
        """更新删除按钮的状态"""
        has_selection = len(self.watch_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)

    def move_up_selected_stock(self) -> None:
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

    def move_down_selected_stock(self) -> None:
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

    def _update_move_buttons_state(self) -> None:
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
