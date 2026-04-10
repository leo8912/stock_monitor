"""
股票数据模型模块
提供基于QAbstractTableModel的高效数据模型，用于QTableView显示
"""

import time
from typing import Any

from PyQt6 import QtCore, QtGui

from stock_monitor.ui.constants import COLORS


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
    COL_LARGE_ORDER = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list = []  # list of StockRowData
        self._header_labels = ["名称", "价格", "涨跌幅", "封单", "主动大单"]
        self._font_size = 13
        self._font_family = "微软雅黑"
        self._show_seal_column = False
        self._show_large_order_column = True  # 默认显示大单列，如果没数据则隐藏

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
        if self._show_large_order_column:
            count += 1
        return count

    def data(
        self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._data):
            return None

        row_data = self._data[index.row()]
        col = index.column()

        # 根据当前显示的列（Section）映射到逻辑数据
        # 逻辑列顺序：0:名称, 1:价格, 2:涨跌幅, 3:封单, 4:大单
        current_col_index = col
        if not self._show_seal_column and current_col_index >= self.COL_SEAL:
            current_col_index += 1

        if (
            not self._show_large_order_column
            and current_col_index >= self.COL_LARGE_ORDER
        ):
            # 这种情况理论上不会发生，因为 columnCount 已经限制了最大列数
            return None

        logical_col = current_col_index

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

            elif logical_col == self.COL_LARGE_ORDER:
                # [NEW] 集合竞价时段特殊展示 (09:15 - 09:30)
                now_hm = time.strftime("%H:%M")
                if "09:15" <= now_hm < "09:30" and row_data.auction_intensity > 0:
                    # 格式化竞价金额
                    vol = row_data.auction_vol
                    if vol >= 100000000:
                        vol_str = f"{vol / 100000000.0:.2f}亿"
                    elif vol >= 10000:
                        vol_str = f"{vol / 10000.0:.0f}万"
                    else:
                        vol_str = f"{int(vol)}"

                    return f"强:{row_data.auction_intensity:.1f}x ({vol_str}) "

                return (
                    f"{row_data.large_order_info} " if row_data.large_order_info else ""
                )

        # 文本颜色
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            # 封单列特殊处理（使用逻辑列号，避免封单列隐藏时误判）
            if logical_col == self.COL_SEAL:
                if row_data.seal_type == "up":
                    return QtGui.QColor(row_data.color_hex)
                elif row_data.seal_type == "down":
                    return QtGui.QColor("#27ae60")
                else:
                    return QtGui.QColor("#888")

            if logical_col == self.COL_LARGE_ORDER:
                # [NEW] 集合竞价时段颜色处理
                now_hm = time.strftime("%H:%M")
                if "09:15" <= now_hm < "09:30" and row_data.auction_intensity > 0:
                    # 抢筹信号：强度 > 10 用紫色，> 5 用深红
                    if row_data.auction_intensity >= 10.0:
                        return QtGui.QColor("#A020F0")  # 紫色 (Purple)
                    elif row_data.auction_intensity >= 5.0:
                        return QtGui.QColor("#FF0000")  # 纯红
                    else:
                        return QtGui.QColor("#CD5C5C")  # 印度红 (淡红)

                # 按照资金级别渐变色彩，统一复用系统的涨跌状态色卡
                s = str(row_data.large_order_info).strip()
                if not s or s == "--" or "NaN" in s:
                    return QtGui.QColor(COLORS.TEXT_DISABLED)

                # 直接通过后台传递的净流入判断，不需要从字符串再解析一次
                val = row_data.recent_net_out
                # val 是实际的手数，但如果是 50万 的大单门槛，此处我们沿用原本的代码逻辑：按 M 处理（或者根据原本的数值判断区间）
                # 这里为了和此前 UI 完全一致：将 +1.2K 拆解出数值，或者直接使用 val 判断
                if s.endswith("K"):
                    try:
                        val_str = s.replace("K", "").replace("+", "")
                        val = float(val_str)
                    except ValueError:
                        val = 0.0

                # 建立与原生涨跌停统一的大单阈值基准段
                if val >= 10.0:
                    return QtGui.QColor(COLORS.STOCK_UP_LIMIT)  # 极强流入 (>= 1亿)
                elif val >= 3.0:
                    return QtGui.QColor(COLORS.STOCK_UP_BRIGHT)  # 明显流入 (>= 3000万)
                elif val > 0:
                    return QtGui.QColor(COLORS.STOCK_UP)  # 普通红
                elif val <= -10.0:
                    return QtGui.QColor(COLORS.STOCK_DOWN_LIMIT)  # 极强流出 (<= -1亿)
                elif val <= -3.0:
                    return QtGui.QColor(COLORS.STOCK_DOWN_DEEP)  # 明显流出 (<= -3000万)
                elif val < 0:
                    return QtGui.QColor(COLORS.STOCK_DOWN)  # 普通绿
                else:
                    return QtGui.QColor(COLORS.STOCK_NEUTRAL)  # 灰白无数据

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

        # 检查是否需要显示大单列 (只要有任意一只股票有数据就显示)
        has_large_order = (
            any(
                item.large_order_info or item.auction_intensity > 0 for item in new_data
            )
            if new_data
            else False
        )

        # 布局变更检测
        layout_changed = (
            has_seal != self._show_seal_column
            or has_large_order != self._show_large_order_column
        )
        row_count_changed = len(new_data) != len(self._data)

        # 如果行数和布局都没变，使用增量更新（更快）
        if not layout_changed and not row_count_changed and self._data:
            self._data = new_data
            self._show_seal_column = has_seal
            self._show_large_order_column = has_large_order
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
            self._show_large_order_column = has_large_order
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
