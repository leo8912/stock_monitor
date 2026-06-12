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
    List[StockRowData]
    """

    # 定义列索引
    COL_NAME = 0
    COL_PRICE = 1
    COL_CHANGE = 2
    COL_SEAL = 3
    COL_DARK_FLOW = 4  # 暗盘净流入（常显示）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list = []  # list of StockRowData
        self._header_labels = ["名称", "价格", "涨跌幅", "封单", "暗盘流"]
        self._font_size = 13
        self._font_family = "微软雅黑"
        self._show_seal_column = False

    def rowCount(self, parent=None) -> int:
        if parent is None:
            parent = QtCore.QModelIndex()
        return len(self._data)

    def columnCount(self, parent=None) -> int:
        if parent is None:
            parent = QtCore.QModelIndex()
        count = 3  # 名称, 价格, 涨跌幅
        if self._show_seal_column:
            count += 1
        count += 1  # COL_DARK_FLOW 始终显示
        return count

    def data(
        self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._data):
            return None

        row_data = self._data[index.row()]
        col = index.column()

        # 根据当前显示的列（Section）映射到逻辑数据
        # 逻辑列顺序：0:名称, 1:价格, 2:涨跌幅, 3:封单, 4:暗盘流
        # 封单列可隐藏，暗盘列始终展示
        # 封单隐藏时: col 0−2对应逻辑 0−2；col 3 对应暗盘(4)
        # 封单显示时: col 0−3对应逻辑 0−3；col 4 对应暗盘(4)
        if not self._show_seal_column:
            # col 3 = 暗盘列
            logical_col = col if col < self.COL_SEAL else self.COL_DARK_FLOW
        else:
            logical_col = col

        # 文本显示
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col == self.COL_NAME:
                # 处理港股名称显示
                name = row_data.name
                if name.startswith("hk") and ":" in name:
                    display_name = name.split(":")[1].strip()
                elif name.startswith("hk") and "-" in name:
                    display_name = name.split("-")[0].strip()
                else:
                    display_name = name
                return f" {display_name}"

            elif col == self.COL_PRICE:
                return row_data.price

            elif col == self.COL_CHANGE:
                change = row_data.change_str
                if not change.endswith("%"):
                    return change + "%"
                return f"{change} "

            elif logical_col == self.COL_SEAL:
                return (
                    f"{row_data.seal_vol} "
                    if row_data.seal_vol and row_data.seal_type
                    else ""
                )

            elif logical_col == self.COL_DARK_FLOW:
                if not row_data.dark_flow_valid:
                    return " -- "
                v = row_data.dark_flow_wan
                sign = "+" if v >= 0 else ""
                # 将小数按量级显示：>1万显整数，小数显1位
                if abs(v) >= 10000:
                    return f" {sign}{v/10000:.1f}亿 "
                elif abs(v) >= 1000:
                    return f" {sign}{v:.0f}万 "
                else:
                    return f" {sign}{v:.1f}万 "

        # 文本颜色
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            # 暗盘列独立颜色逻辑
            if logical_col == self.COL_DARK_FLOW:
                if not row_data.dark_flow_valid:
                    return QtGui.QColor("#888888")
                v = row_data.dark_flow_wan
                days = row_data.dark_flow_consecutive_days
                if v > 0:
                    # 连续3天流入 → 深红(#CC0000)，否则标准红(#e74c3f)
                    return (
                        QtGui.QColor("#CC0000")
                        if days >= 3
                        else QtGui.QColor("#e74c3f")
                    )
                elif v < 0:
                    # 连续3天流出 → 深绿(#145a32)，否则标准绿(#27ae60)
                    return (
                        QtGui.QColor("#145a32")
                        if days <= -3
                        else QtGui.QColor("#27ae60")
                    )
                return QtGui.QColor("#888888")

            # 封单列特殊处理（使用逻辑列号，避免封单列隐藏时误判）
            if logical_col == self.COL_SEAL:
                if row_data.seal_type == "up":
                    return QtGui.QColor(row_data.color_hex)
                elif row_data.seal_type == "down":
                    return QtGui.QColor("#27ae60")
                else:
                    return QtGui.QColor("#888")

            # 其他列使用传进来的color
            return QtGui.QColor(row_data.color_hex)

        # 背景颜色 (涨跌停高亮)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if row_data.seal_type == "up":
                return QtGui.QColor("#ffecec")
            elif row_data.seal_type == "down":
                return QtGui.QColor("#e8f5e9")
            # 默认透明背景
            return None

        # 对齐方式
        elif role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if logical_col == self.COL_NAME:
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
            font = QtGui.QFont(self._font_family)
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

    def update_data(self, new_data: list):
        """更新数据 - 优化为增量更新"""
        # 检查是否需要显示封单列
        has_seal = any(item.seal_type for item in new_data) if new_data else False

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

    def set_font_size(self, font_family: str, size: int):
        self._font_family = font_family
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
