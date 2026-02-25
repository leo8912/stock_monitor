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
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 优化性能显示
        # self.setWordWrap(False) # 股票信息不需要换行
        # self.cornerWidget().setVisible(False)

        # 设置大小策略
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        self._model.set_font_size(self.font_family, self.font_size)
        self._set_table_style(self.font_family, self.font_size)

        # 首次显示标记，用于确保窗口显示后重新计算列宽
        self._first_show_done = False

    def _set_table_style(self, font_family: str, font_size: int) -> None:
        """设置表格样式。现在依赖全局QSS，此方法可以为空或设置动态变化的样式"""
        pass

    def _resize_columns(self) -> None:
        """调整列宽"""
        self.resizeColumnsToContents()
        h_header = self.horizontalHeader()
        if h_header is not None:
            h_header.setStretchLastSection(False)

    def _notify_parent_window_height_adjustment(self) -> None:
        """触发布局调整请求信号以通知父窗口调整高度"""
        self.height_adjustment_requested.emit()

    def rowCount(self):
        """兼容性接口：获取行数"""
        return self._model.rowCount()

    def columnCount(self):
        """兼容性接口：获取列数"""
        return self._model.columnCount()

    def get_data_at(self, row, col):
        """获取指定位置的文本数据"""
        index = self._model.index(row, col)
        if index.isValid():
            return self._model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)
        return ""

    def get_foreground_color_at(self, row, col):
        """获取指定位置的前景色"""
        index = self._model.index(row, col)
        if index.isValid():
            color = self._model.data(index, QtCore.Qt.ItemDataRole.ForegroundRole)
            if isinstance(color, QtGui.QColor):
                return color.name()
        return ""

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

            # 仅在布局变化时调整列宽（如显示/隐藏封单列，或行数变化）
            if layout_changed:
                self._resize_columns()
                # 布局变化时通知父窗口调整大小
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
            # 强制处理事件队列，确保布局完成
            QtWidgets.QApplication.processEvents()
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
        self._set_table_style(font_family, size)
        self._resize_columns()
        self._notify_parent_window_height_adjustment()
