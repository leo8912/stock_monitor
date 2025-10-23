import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt

from ..utils.logger import app_logger

def resource_path(relative_path):
    """获取资源文件路径，兼容PyInstaller打包和源码运行"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(getattr(sys, '_MEIPASS'), relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_stock_emoji(code, name):
    """根据股票代码和名称返回对应的emoji"""
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)  # 增加一列：封单手
        h_header = self.horizontalHeader()
        v_header = self.verticalHeader()
        if h_header is not None:
            h_header.setVisible(False)
            h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        if v_header is not None:
            v_header.setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)  # type: ignore
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # type: ignore
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # type: ignore
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
        try:
            self.setRowCount(len(stocks))
            for row, stock in enumerate(stocks):
                name, price, change, color, seal_vol, seal_type = stock
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
                        item.setForeground(QtGui.QColor('#e74c3f'))
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
                h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
                h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
                h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
                h_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            self.updateGeometry()
            QtWidgets.QApplication.processEvents()  # 强制刷新事件队列
            app_logger.debug(f"表格数据更新完成，共{len(stocks)}行")
        except Exception as e:
            error_msg = f"更新表格数据时发生错误: {e}"
            app_logger.error(error_msg)
            print(error_msg)