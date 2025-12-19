"""
股票表格UI组件
用于显示股票行情数据的表格组件

该模块包含StockTable类，用于在GUI中展示实时股票行情数据。
"""

from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import pyqtSlot

# 导入日志记录器
from stock_monitor.utils.logger import app_logger

__version__ = "2.2.4"

class StockTable(QtWidgets.QTableWidget):
    """
    股票表格控件
    用于显示股票行情数据
    """
    
    def __init__(self, parent=None):
        """初始化股票表格"""
        super().__init__(parent)
        self.setColumnCount(3)  # 默认3列：名称、价格、涨跌幅
        h_header = self.horizontalHeader()
        v_header = self.verticalHeader()
        if h_header is not None:
            h_header.setVisible(False)
            # 设置列宽自适应内容
            h_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            h_header.setStretchLastSection(False)
        if v_header is not None:
            v_header.setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)  # type: ignore
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # type: ignore
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # type: ignore
        
        # 设置大小策略，允许收缩
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred
        )
        
        # 从配置中读取字体大小
        from stock_monitor.utils.helpers import get_config_manager
        config_manager = get_config_manager()
        self.font_size = config_manager.get("font_size", 13)  # 默认13px
        
        self._set_table_style(self.font_size)

    def _set_table_style(self, font_size: int) -> None:
        """
        设置表格样式
        
        Args:
            font_size (int): 字体大小
        """
        self.setStyleSheet(f'''
            QTableWidget {{
                background: transparent;
                border: none;
                outline: none;
                gridline-color: #aaa;
                selection-background-color: transparent;
                selection-color: #fff;
                font-family: "微软雅黑";
                font-size: {font_size}px;
                font-weight: bold;
                color: #fff;
            }}
            QTableWidget::item {{
                border: none;
                padding: 0px;
                background: transparent;
            }}
            QTableWidget::item:selected {{
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
        ''')

    def _format_hk_stock_name(self, name: str) -> str:
        """
        格式化港股名称显示
        
        Args:
            name (str): 原始名称
            
        Returns:
            str: 格式化后的名称
        """
        if name.startswith('hk') and ':' in name:
            return name.split(':')[1].strip()
        elif name.startswith('hk') and '-' in name:
            return name.split('-')[0].strip()
        return name

    def _create_table_item(self, text: str, color: str, seal_type: str) -> QtWidgets.QTableWidgetItem:
        """
        创建并设置表格项
        
        Args:
            text (str): 显示文本
            color (str): 文本颜色
            seal_type (str): 封单类型
            
        Returns:
            QtWidgets.QTableWidgetItem: 表格项
        """
        item = QtWidgets.QTableWidgetItem()
        item.setText(text)
        
        # 根据封单类型设置背景和前景色
        if seal_type == 'up':
            item.setBackground(QtGui.QColor('#ffecec'))
            item.setForeground(QtGui.QColor(color))
        elif seal_type == 'down':
            item.setBackground(QtGui.QColor('#e8f5e9'))
            item.setForeground(QtGui.QColor('#27ae60'))
        else:
            item.setForeground(QtGui.QColor(color))
            
        return item

    def _create_seal_item(self, seal_vol: str, seal_type: str, color: str) -> QtWidgets.QTableWidgetItem:
        """
        创建封单项
        
        Args:
            seal_vol (str): 封单量
            seal_type (str): 封单类型
            color (str): 文本颜色
            
        Returns:
            QtWidgets.QTableWidgetItem: 表格项
        """
        item_seal = QtWidgets.QTableWidgetItem()
        # 对于有封单信息的股票显示封单数
        item_seal.setText(f"{seal_vol} " if seal_vol and seal_type else "")
        
        # 根据涨跌停类型设置封单列的颜色
        if seal_type == 'up':
            item_seal.setBackground(QtGui.QColor('#ffecec'))
            item_seal.setForeground(QtGui.QColor(color))
        elif seal_type == 'down':
            item_seal.setBackground(QtGui.QColor('#e8f5e9'))
            item_seal.setForeground(QtGui.QColor('#27ae60'))
        else:
            item_seal.setForeground(QtGui.QColor('#888'))
            
        return item_seal

    def _set_text_alignment(self, item: QtWidgets.QTableWidgetItem, alignment: QtCore.Qt.AlignmentFlag) -> None:
        """
        设置文本对齐方式
        
        Args:
            item (QtWidgets.QTableWidgetItem): 表格项
            alignment (QtCore.Qt.AlignmentFlag): 对齐方式
        """
        item.setTextAlignment(alignment | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore

    def _format_change_text(self, change: str) -> str:
        """
        格式化涨跌幅文本
        
        Args:
            change (str): 原始涨跌幅文本
            
        Returns:
            str: 格式化后的涨跌幅文本
        """
        if not change.endswith('%'):
            return change + '%'
        return f"{change} "

    def _resize_columns(self) -> None:
        """调整列宽"""
        h_header = self.horizontalHeader()
        if h_header is not None:
            # 设置列宽自适应内容
            for col in range(self.columnCount()):
                h_header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            h_header.setStretchLastSection(False)

    def _notify_parent_window_height_adjustment(self) -> None:
        """通知父窗口调整高度"""
        if self.parent():
            parent = self.parent()
            if hasattr(parent, 'adjust_window_height') and callable(getattr(parent, 'adjust_window_height')):
                parent.adjust_window_height()  # type: ignore

    @pyqtSlot(list)
    def update_data(self, stocks):
        """
        更新表格数据，优化性能
        
        Args:
            stocks (list): 股票数据列表
        """
        try:
            row_count = len(stocks)
            if self.rowCount() != row_count:
                self.setRowCount(row_count)
            
            # 检查是否需要显示封单列（检查是否有涨停或跌停的股票）
            show_seal_column = any(stock[5] for stock in stocks)  # stock[5]是seal_type
            
            column_count = 4 if show_seal_column else 3
            if self.columnCount() != column_count:
                self.setColumnCount(column_count)
            
            for row, stock in enumerate(stocks):
                name, price, change, color, seal_vol, seal_type = stock
                
                # 处理港股名称显示
                name = self._format_hk_stock_name(name)
                
                # 创建并设置表格项
                item_name = self._create_table_item(f" {name}", color, seal_type)
                item_price = self._create_table_item(price, color, seal_type)
                item_change = self._create_table_item(self._format_change_text(change), color, seal_type)
                
                # 设置文本对齐
                self._set_text_alignment(item_name, QtCore.Qt.AlignmentFlag.AlignLeft)
                self._set_text_alignment(item_price, QtCore.Qt.AlignmentFlag.AlignRight)
                self._set_text_alignment(item_change, QtCore.Qt.AlignmentFlag.AlignRight)
                
                # 设置项目
                self.setItem(row, 0, item_name)
                self.setItem(row, 1, item_price)
                self.setItem(row, 2, item_change)
                
                # 如果需要显示封单列
                if show_seal_column:
                    item_seal = self._create_seal_item(seal_vol, seal_type, color)
                    self._set_text_alignment(item_seal, QtCore.Qt.AlignmentFlag.AlignRight)
                    self.setItem(row, 3, item_seal)
            
            self._resize_columns()
            self.updateGeometry()
            app_logger.debug(f"表格数据更新完成，共{len(stocks)}行")
            
            # 通知父窗口调整大小
            self._notify_parent_window_height_adjustment()
        except Exception as e:
            error_msg = f"更新表格数据时发生错误: {e}"
            app_logger.error(error_msg)
            
    def wheelEvent(self, event):
        """
        鼠标滚轮事件处理，禁用滚轮滚动
        
        Args:
            event: 滚轮事件对象
        """
        # 不调用父类的wheelEvent，直接忽略事件
        # 这样可以完全防止鼠标滚轮引起的滚动
        pass