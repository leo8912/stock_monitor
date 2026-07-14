"""
股票表格UI组件
用于显示股票行情数据的表格组件
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import pyqtSlot

# 导入数据模型
from stock_monitor.ui.models.stock_model import StockTableModel

# 导入日志记录器
from stock_monitor.utils.logger import app_logger


class NoElideDelegate(QtWidgets.QStyledItemDelegate):
    """
    自定义表格项委托：禁用文本省略(Ellipsis)。

    Qt 默认在单元格宽度不足时会将文本截断并追加 "..."。
    本委托通过在 paint 时关闭 QTextOption.TextElideMode，
    保证完整文本始终可见（溢出部分自然裁剪，不会追加省略号）。
    """

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        # 先让系统完成基本绘制（背景、选中态等）
        widget = option.widget
        if widget is not None:
            style = widget.style()
            if style is not None:
                style.drawControl(
                    QtWidgets.QStyle.ControlElement.CE_ItemViewItem,
                    option,
                    painter,
                    widget,
                )

        # 获取要绘制的文本
        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole)
        if not text:
            return

        # 获取对齐方式（模型中的 TextAlignmentRole）
        alignment = index.data(QtCore.Qt.ItemDataRole.TextAlignmentRole)
        if alignment is None:
            alignment = (
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )

        # 获取字体（模型中的 FontRole）
        font = index.data(QtCore.Qt.ItemDataRole.FontRole)
        if font is None:
            font = QtGui.QFont()

        painter.setFont(font)
        painter.setPen(
            index.data(QtCore.Qt.ItemDataRole.ForegroundRole) or QtGui.QColor("#ffffff")
        )

        # 构造文本绘制矩形，内部留少量 padding
        rect = option.rect.adjusted(4, 0, -4, 0)

        # 关键：禁用文本省略，完整显示
        text_option = QtGui.QTextOption()
        text_option.setAlignment(alignment)

        painter.drawText(rect, text, text_option)


class StockTable(QtWidgets.QTableView):
    """
    股票表格组件

    用于显示股票行情数据的表格视图。
    支持自定义列宽、行高、样式等。
    使用 StockTableModel 作为数据模型。

    Attributes:
        model: StockTableModel 实例，用于管理表格数据
    """

    height_adjustment_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None, font_family: str = "微软雅黑", font_size: int = 13):
        """初始化股票表格"""
        super().__init__(parent)

        # 保存字体配置
        self.font_family = font_family
        self.font_size = font_size

        # 初始化数据模型
        self._model = StockTableModel()
        self.setModel(self._model)

        # UI设置
        h_header = self.horizontalHeader()
        v_header = self.verticalHeader()
        if h_header is not None:
            h_header.setVisible(False)
            h_header.setStretchLastSection(False)
        if v_header is not None:
            v_header.setVisible(False)

        self.setShowGrid(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(QtWidgets.QScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtWidgets.QScrollBarPolicy.ScrollBarAlwaysOff)

        # 设置大小策略
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        # 禁用文本省略 — 使用自定义委托，防止列宽不足时出现 "..." 省略号
        self.setItemDelegate(NoElideDelegate(self))

        self._model.set_font_size(self.font_family, self.font_size)

        # 首次显示标记，用于确保窗口显示后重新计算列宽
        self._first_show_done = False

    # 各列最小宽度（像素），防止内容被压缩到无法阅读
    _MIN_COL_WIDTHS: dict[int, int] = {
        StockTableModel.COL_NAME: 90,
        StockTableModel.COL_PRICE: 60,
        StockTableModel.COL_CHANGE: 70,
        StockTableModel.COL_SEAL: 70,
        StockTableModel.COL_DARK_FLOW: 80,
    }

    def _resize_columns(self) -> None:
        """调整列宽，确保每列不小于最小宽度"""
        self.resizeColumnsToContents()
        h_header = self.horizontalHeader()
        if h_header is not None:
            h_header.setStretchLastSection(False)
            # 对所有列应用最小宽度
            for col in range(self._model.columnCount()):
                min_w = self._MIN_COL_WIDTHS.get(col, 60)
                if h_header.sectionSize(col) < min_w:
                    h_header.resizeSection(col, min_w)

    def _notify_parent_window_height_adjustment(self) -> None:
        """触发布局调整请求信号以通知父窗口调整高度"""
        self.height_adjustment_requested.emit()

    def rowCount(self):
        """兼容性接口：获取行数"""
        return self._model.rowCount()

    def columnCount(self):
        """兼容性接口：获取列数"""
        return self._model.columnCount()

    @pyqtSlot(list)
    def update_data(self, stocks: list[tuple]) -> None:
        """
        更新表格数据

        Args:
            stocks (list): 股票数据列表
        """
        try:
            # 委托给模型更新
            layout_changed = self._model.update_data(stocks)

            # 布局变化或行数变化时重新计算列宽并调整窗口尺寸
            # 即使布局未变，数据内容可能变宽（如封单从 "123" → "123456k"），
            # 也需要重新计算列宽以防止文本截断
            self._resize_columns()
            if layout_changed:
                self._notify_parent_window_height_adjustment()

        except Exception as e:
            app_logger.error(f"更新表格数据时发生错误: {e}")

    def wheelEvent(self, event):
        """禁用滚轮"""
        pass

    def showEvent(self, event):
        """窗口显示事件 - 确保首次显示后列宽正确"""
        super().showEvent(event)
        # 首次显示时，延迟重新计算列宽
        # 这解决了开机启动时 Qt 事件循环未完全就绪导致列宽计算错误的问题
        if not self._first_show_done:
            self._first_show_done = True
            # 使用 QTimer 延迟执行，确保窗口完全渲染后再计算列宽
            QtCore.QTimer.singleShot(100, self._delayed_resize_columns)

    def _delayed_resize_columns(self):
        """延迟重新计算列宽"""
        try:
            self._resize_columns()
            self._notify_parent_window_height_adjustment()
            app_logger.debug("首次显示后列宽已重新计算")
        except Exception as e:
            app_logger.warning(f"延迟计算列宽失败: {e}")

    def set_font_size(self, font_family: str, size: int):
        """提供给设置对话框调用的接口"""
        self.font_size = size
        self.font_family = font_family
        # 模型需要同步字体大小以便 FontRole 进行测量
        self._model.set_font_size(font_family, size)
        self._resize_columns()
        self._notify_parent_window_height_adjustment()
