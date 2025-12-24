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

    def __init__(self, parent=None):
        """初始化股票表格"""
        super().__init__(parent)

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

        # 从配置中读取字体大小和字体族
        from stock_monitor.utils.helpers import get_config_manager

        config_manager = get_config_manager()
        self.font_size = config_manager.get("font_size", 13)
        self.font_family = config_manager.get("font_family", "微软雅黑")

        try:
            self.font_size = int(self.font_size)
        except (ValueError, TypeError):
            self.font_size = 13

        if self.font_size <= 0:
            self.font_size = 13

        # 设置模型字体大小
        self._model.set_font_size(self.font_size)
        self._set_table_style(self.font_family, self.font_size)

    def _set_table_style(self, font_family: str, font_size: int) -> None:
        """
        设置表格样式
        """
        try:
            font_size = int(font_size)
        except (ValueError, TypeError):
            font_size = 13

        if font_size <= 0:
            font_size = 13

        self.setStyleSheet(
            f"""
            QTableView {{
                background: transparent;
                border: none;
                outline: none;
                gridline-color: #aaa;
                selection-background-color: transparent;
                selection-color: #fff;
                font-family: "{font_family}";
                font-size: {font_size}px;
                font-weight: bold;
                color: #fff;
            }}
            QTableView::item {{
                border: none;
                padding: 0px;
                background: transparent;
            }}
            QTableView::item:selected {{
                background: transparent;
                color: #fff;
            }}
            QHeaderView::section {{
                background: transparent;
                border: none;
                color: transparent;
            }}
            QScrollBar {{
                background: transparent;
                width: 0px;
                height: 0px;
            }}
            QScrollBar::handle {{
                background: transparent;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: transparent;
                border: none;
            }}
        """
        )

    def _resize_columns(self) -> None:
        """调整列宽"""
        self.resizeColumnsToContents()
        h_header = self.horizontalHeader()
        if h_header is not None:
            h_header.setStretchLastSection(False)

    def _notify_parent_window_height_adjustment(self) -> None:
        """通知父窗口调整高度"""
        if self.parent():
            parent = self.parent()
            if hasattr(parent, "adjust_window_height") and callable(
                parent.adjust_window_height
            ):
                parent.adjust_window_height()

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

            # 如果列结构发生变化（如显示/隐藏封单列），重新调整列宽
            if layout_changed:
                self._resize_columns()
            else:
                # 即使结构没变，内容变了也可能需要微调列宽，但为了性能可以不每次都调
                # 为了防止数字跳动导致宽度变化过大，可以适当限制
                # 这里保持原逻辑：每次数据更新都调整列宽，确保内容完整显示
                self._resize_columns()

            # 通知父窗口调整大小 (因为行数可能变化)
            self._notify_parent_window_height_adjustment()

        except Exception as e:
            app_logger.error(f"更新表格数据时发生错误: {e}")

    def wheelEvent(self, event):
        """禁用滚轮"""
        pass

    def set_font_size(self, font_family: str, size: int):
        """提供给设置对话框调用的接口"""
        self.font_size = size
        self.font_family = font_family
        # 模型不再需要字体大小，因为字体由CSS控制
        # self._model.set_font_size(size)
        self._set_table_style(font_family, size)
        self._resize_columns()
        self._notify_parent_window_height_adjustment()
