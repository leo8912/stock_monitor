"""
UI组件模块
包含股票表格等UI组件的实现
"""

import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot

# 导入日志记录器
from ..utils.logger import app_logger
from ..data.quotation import get_name_by_code

def resource_path(relative_path):
    """
    获取资源文件路径，兼容PyInstaller打包和源码运行
    
    Args:
        relative_path (str): 相对路径
        
    Returns:
        str: 资源文件的绝对路径
    """
    try:
        # PyInstaller创建的临时文件夹
        base_path = getattr(sys, '_MEIPASS', None)
        if base_path is None:
            raise AttributeError("_MEIPASS not found")
    except Exception:
        base_path = "."
    return QtCore.QDir(base_path).absoluteFilePath(relative_path)

def get_stock_emoji(code, name):
    """
    根据股票代码和名称返回对应的emoji
    
    Args:
        code (str): 股票代码
        name (str): 股票名称
        
    Returns:
        str: 对应的emoji字符
    """
    try:
        if code.startswith(('sh000', 'sz399', 'sz159', 'sh510')) or (name and ('指数' in name or '板块' in name)):
            return '📈'
        elif name and '银行' in name:
            return '🏦'
        elif name and '保险' in name:
            return '🛡️'
        elif name and '板块' in name:
            return '📊'
        elif name and ('能源' in name or '石油' in name or '煤' in name):
            return '⛽️'
        elif name and ('汽车' in name or '车' in name):
            return '🚗'
        elif name and ('科技' in name or '半导体' in name or '芯片' in name):
            return '💻'
        elif name and '银行' in name:
            return '🏦'
        else:
            return '⭐️'
    except Exception as e:
        app_logger.debug(f"获取股票emoji时出错: {e}")
        return '⭐️'

class StockTable(QtWidgets.QTableWidget):
    """
    股票表格控件
    用于显示股票行情数据
    """
    
    def __init__(self, parent=None):
        """初始化股票表格"""
        super().__init__(parent)
        self.setColumnCount(4)  # 增加一列：封单手
        h_header = self.horizontalHeader()
        v_header = self.verticalHeader()
        if h_header is not None:
            h_header.setVisible(False)
            h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            # 设置最小列宽，防止名称过长撑大表格
            h_header.setMinimumSectionSize(80)  # 名称列最小宽度
            h_header.setMaximumSectionSize(150)  # 名称列最大宽度
        if v_header is not None:
            v_header.setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)  # type: ignore
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # type: ignore
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # type: ignore
        
        # 设置表格的最大宽度，防止超出父容器
        self.setMaximumWidth(400)
        
        self.setStyleSheet('''
            QTableWidget {
                background: transparent;
                border: none;
                outline: none;
                gridline-color: transparent;
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
                item_name = QtWidgets.QTableWidgetItem(name)
                item_price = QtWidgets.QTableWidgetItem(price)
                if not change.endswith('%'):
                    change = change + '%'
                item_change = QtWidgets.QTableWidgetItem(change)
                item_seal = QtWidgets.QTableWidgetItem(seal_vol)
                # 涨停/跌停高亮
                if seal_type == 'up':
                    for item in [item_name, item_price, item_change, item_seal]:
                        item.setBackground(QtGui.QColor('#ffecec'))
                        # 使用与个股红盘一致的颜色，超过5%的用深红色
                        item.setForeground(QtGui.QColor(color))
                elif seal_type == 'down':
                    for item in [item_name, item_price, item_change, item_seal]:
                        item.setBackground(QtGui.QColor('#e8f5e9'))
                        item.setForeground(QtGui.QColor('#27ae60'))
                else:
                    item_name.setForeground(QtGui.QColor(color))
                    item_price.setForeground(QtGui.QColor(color))
                    item_change.setForeground(QtGui.QColor(color))
                    item_seal.setForeground(QtGui.QColor('#888'))
                item_name.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                item_price.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                item_change.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                item_seal.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
                self.setItem(row, 0, item_name)
                self.setItem(row, 1, item_price)
                self.setItem(row, 2, item_change)
                self.setItem(row, 3, item_seal)
            h_header = self.horizontalHeader()
            if h_header is not None:
                h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
                h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
                h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
                h_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            self.updateGeometry()
            QtWidgets.QApplication.processEvents()  # 强制刷新事件队列
            app_logger.debug(f"表格数据更新完成，共{len(stocks)}行")
        except Exception as e:
            error_msg = f"更新表格数据时发生错误: {e}"
            app_logger.error(error_msg)
            print(error_msg)
            
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