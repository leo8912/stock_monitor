"""
股票数据模型模块
提供基于QAbstractTableModel的高效数据模型，用于QTableView显示
"""

from typing import Any

from PyQt6 import QtCore, QtGui


class StockTableModel(QtCore.QAbstractTableModel):
    """
    股票数据模型

    数据结构:
    List[Tuple[name, price, change, color, seal_vol, seal_type]]
    """

    # 定义列索引
    COL_NAME = 0
    COL_PRICE = 1
    COL_CHANGE = 2
    COL_SEAL = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple] = []
        self._header_labels = ["名称", "价格", "涨跌幅", "封单"]
        self._font_size = 13
        self._show_seal_column = False

    def rowCount(self, parent=None) -> int:
        if parent is None:
            parent = QtCore.QModelIndex()
        return len(self._data)

    def columnCount(self, parent=None) -> int:
        if parent is None:
            parent = QtCore.QModelIndex()
        return 4 if self._show_seal_column else 3

    def data(
        self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._data):
            return None

        row_data = self._data[index.row()]
        # row_data structure: (name, price, change, color, seal_vol, seal_type)
        col = index.column()

        name, price, change, color_hex, seal_vol, seal_type = row_data

        # 文本显示
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col == self.COL_NAME:
                # 处理港股名称显示
                if name.startswith("hk") and ":" in name:
                    display_name = name.split(":")[1].strip()
                elif name.startswith("hk") and "-" in name:
                    display_name = name.split("-")[0].strip()
                else:
                    display_name = name
                return f" {display_name}"

            elif col == self.COL_PRICE:
                return price

            elif col == self.COL_CHANGE:
                if not change.endswith("%"):
                    return change + "%"
                return f"{change} "

            elif col == self.COL_SEAL:
                return f"{seal_vol} " if seal_vol and seal_type else ""

        # 文本颜色
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            # 封单列特殊处理
            if col == self.COL_SEAL:
                if seal_type == "up":
                    return QtGui.QColor(color_hex)
                elif seal_type == "down":
                    return QtGui.QColor("#27ae60")
                else:
                    return QtGui.QColor("#888")

            # 其他列使用传进来的color
            return QtGui.QColor(color_hex)

        # 背景颜色 (涨跌停高亮)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if seal_type == "up":
                return QtGui.QColor("#ffecec")
            elif seal_type == "down":
                return QtGui.QColor("#e8f5e9")
            # 默认透明背景
            return None

        # 对齐方式
        elif role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if col == self.COL_NAME:
                return (
                    QtCore.Qt.AlignmentFlag.AlignLeft
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
            else:
                return (
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )

        # 恢复FontRole，以便QTableView.resizeColumnsToContents()能够正确计算实际文字宽度
        elif role == QtCore.Qt.ItemDataRole.FontRole:
            font = QtGui.QFont("微软雅黑")
            font.setPixelSize(self._font_size)
            font.setBold(True)
            return font

        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self._header_labels):
                return self._header_labels[section]
        return None

    def update_data(self, new_data: list[tuple]):
        """更新数据 - 优化为增量更新"""
        # 检查是否需要显示封单列
        has_seal = any(item[5] for item in new_data) if new_data else False

        # 布局变更检测
        layout_changed = has_seal != self._show_seal_column
        row_count_changed = len(new_data) != len(self._data)

        # 如果行数和布局都没变，使用增量更新（更快）
        if not layout_changed and not row_count_changed and self._data:
            self._data = new_data
            self._show_seal_column = has_seal
            # 仅发送 dataChanged 信号，避免全量刷新
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._data) - 1, self.columnCount() - 1),
            )
            return False
        else:
            # 行数或布局变化时才全量重置
            self.beginResetModel()
            self._data = new_data
            self._show_seal_column = has_seal
            self.endResetModel()
            return layout_changed or row_count_changed

    def set_font_size(self, size: int):
        self._font_size = size
        # 字体改变需要重绘
        self.force_refresh()

    def force_refresh(self):
        """强制刷新所有视图"""
        if self._data:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._data) - 1, self.columnCount() - 1),
                [QtCore.Qt.ItemDataRole.FontRole],
            )
