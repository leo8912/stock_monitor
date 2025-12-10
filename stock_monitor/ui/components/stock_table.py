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
        更新表格数据
        
        Args:
            stocks (list): 股票数据列表
        """
        try:
            self.setRowCount(len(stocks))
            
            # 检查是否需要显示封单列
            show_seal_column = any(stock[5] for stock in stocks)  # stock[5]是seal_type
            
            if show_seal_column:
                self.setColumnCount(4)  # 显示封单列
            else:
                self.setColumnCount(3)  # 隐藏封单列
            
            for row, stock in enumerate(stocks):
                name, price, change, color, seal_vol, seal_type = stock
                # 处理港股名称显示，只显示中文部分
                if name.startswith('hk') and ':' in name:
                    # 处理从行情数据获取的名称格式（hk09988:阿里巴巴）
                    name = name.split(':')[1].strip()
                elif name.startswith('hk') and '-' in name:
                    # 处理从本地数据获取的名称，去除"-"及之后的部分，只保留中文名称
                    name = name.split('-')[0].strip()
                # ======= 表格渲染 =======
                # 在股票名称前添加空格，涨跌幅后添加空格
                item_name = QtWidgets.QTableWidgetItem(f" {name}")
                item_price = QtWidgets.QTableWidgetItem(price)
                if not change.endswith('%'):
                    change = change + '%'
                item_change = QtWidgets.QTableWidgetItem(f"{change} ")
                
                # 涨停/跌停高亮
                if seal_type == 'up':
                    for item in [item_name, item_price, item_change]:
                        item.setBackground(QtGui.QColor('#ffecec'))
                        # 使用与个股红盘一致的颜色，超过5%的用深红色
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
                
                self.setItem(row, 0, item_name)
                self.setItem(row, 1, item_price)
                self.setItem(row, 2, item_change)
                
                # 如果需要显示封单列
                if show_seal_column:
                    item_seal = QtWidgets.QTableWidgetItem(seal_vol if seal_type else "")
                    # 在封单量后添加空格
                    if seal_vol and seal_type:
                        item_seal = QtWidgets.QTableWidgetItem(f"{seal_vol} ")
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