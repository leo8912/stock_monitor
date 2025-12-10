"""
股票表格UI组件
用于显示股票行情数据的表格组件

该模块包含StockTable类，用于在GUI中展示实时股票行情数据。
"""

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSlot

# 导入日志记录器
from stock_monitor.utils.logger import app_logger

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
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Preferred
        )
        
        self.setStyleSheet('''
            QTableWidget {
                background: transparent;
                border: none;
                outline: none;
                gridline-color: #aaa;
                selection-background-color: transparent;
                selection-color: #fff;
                font-family: "微软雅黑";
                font-size: 20px;
                font-weight: bold;
                color: #fff;
            }
            QTableWidget::item {
                border: none;
                padding: 0px;
                background: transparent;
            }
            QTableWidget::item:selected {
                background: transparent;
                color: #fff;
            }
            QHeaderView::section {
                background: transparent;
                border: none;
                color: transparent;
            }
            QScrollBar {
                background: transparent;
                width: 0px;
                height: 0px;
            }
            QScrollBar::handle {
                background: transparent;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: transparent;
                border: none;
            }
        ''')

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
            
            # 检查是否需要显示封单列
            show_seal_column = any(stock[5] for stock in stocks)  # stock[5]是seal_type
            
            column_count = 4 if show_seal_column else 3
            if self.columnCount() != column_count:
                self.setColumnCount(column_count)
            
            for row, stock in enumerate(stocks):
                name, price, change, color, seal_vol, seal_type = stock
                
                # 处理港股名称显示
                if name.startswith('hk') and ':' in name:
                    name = name.split(':')[1].strip()
                elif name.startswith('hk') and '-' in name:
                    name = name.split('-')[0].strip()
                
                # 总是创建新的表格项，避免"already owned"错误
                item_name = QtWidgets.QTableWidgetItem()
                item_price = QtWidgets.QTableWidgetItem()
                item_change = QtWidgets.QTableWidgetItem()
                
                # 更新文本和样式
                item_name.setText(f" {name}")
                item_price.setText(price)
                if not change.endswith('%'):
                    change = change + '%'
                item_change.setText(f"{change} ")
                
                # 涨停/跌停高亮
                if seal_type == 'up':
                    for item in [item_name, item_price, item_change]:
                        item.setBackground(QtGui.QColor('#ffecec'))
                        item.setForeground(QtGui.QColor(color))
                elif seal_type == 'down':
                    for item in [item_name, item_price, item_change]:
                        item.setBackground(QtGui.QColor('#e8f5e9'))
                        item.setForeground(QtGui.QColor('#27ae60'))
                else:
                    item_name.setForeground(QtGui.QColor(color))
                    item_price.setForeground(QtGui.QColor(color))
                    item_change.setForeground(QtGui.QColor(color))
                    
                item_name.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                item_price.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                item_change.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                
                # 设置项目
                self.setItem(row, 0, item_name)
                self.setItem(row, 1, item_price)
                self.setItem(row, 2, item_change)
                
                # 如果需要显示封单列
                if show_seal_column:
                    item_seal = QtWidgets.QTableWidgetItem()
                    if seal_vol and seal_type:
                        item_seal.setText(f"{seal_vol} ")
                    else:
                        item_seal.setText("")
                        
                    if seal_type == 'up':
                        item_seal.setBackground(QtGui.QColor('#ffecec'))
                        item_seal.setForeground(QtGui.QColor(color))
                    elif seal_type == 'down':
                        item_seal.setBackground(QtGui.QColor('#e8f5e9'))
                        item_seal.setForeground(QtGui.QColor('#27ae60'))
                    else:
                        item_seal.setForeground(QtGui.QColor('#888'))
                    item_seal.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                    self.setItem(row, 3, item_seal)
            
            h_header = self.horizontalHeader()
            if h_header is not None:
                # 设置列宽自适应内容
                for col in range(self.columnCount()):
                    h_header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
                h_header.setStretchLastSection(False)
                    
            self.updateGeometry()
            app_logger.debug(f"表格数据更新完成，共{len(stocks)}行")
            
            # 通知父窗口调整大小
            if self.parent():
                parent = self.parent()
                if hasattr(parent, 'adjust_window_height'):
                    parent.adjust_window_height()
        except Exception as e:
            error_msg = f"更新表格数据时发生错误: {e}"
            app_logger.error(error_msg)
            
    # 重写wheelEvent方法以完全禁用鼠标滚轮事件
    def wheelEvent(self, a0):
        """
        鼠标滚轮事件处理，禁用滚轮滚动
        
        Args:
            a0: 滚轮事件对象
        """
        # 不调用父类的wheelEvent，直接忽略事件
        # 这样可以完全防止鼠标滚轮引起的滚动
        pass