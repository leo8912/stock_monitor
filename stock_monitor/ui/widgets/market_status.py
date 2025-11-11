"""
股市状态条组件
显示整体股市涨跌情况的可视化状态条
"""

from PyQt5 import QtWidgets, QtGui, QtCore
from stock_monitor.utils.logger import app_logger


class MarketStatusBar(QtWidgets.QWidget):
    """股市状态条，显示整体涨跌情况"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.up_count = 100    # 上涨股票数，默认全红
        self.down_count = 0    # 下跌股票数
        self.flat_count = 0    # 平盘股票数
        self.total_count = 100 # 总股票数
        self.setMinimumHeight(3)
        self.setMaximumHeight(3)
        
    def update_status(self, up_count, down_count, flat_count, total_count):
        """更新状态条显示"""
        self.up_count = up_count
        self.down_count = down_count
        self.flat_count = flat_count
        self.total_count = total_count
        self.update()
        
    @QtCore.pyqtSlot(int, int, int, int)
    def _update_status_internal(self, up_count, down_count, flat_count, total_count):
        """内部方法，用于在主线程中更新状态"""
        self.up_count = up_count
        self.down_count = down_count
        self.flat_count = flat_count
        self.total_count = total_count
        self.update()
        
    def update_market_status(self):
        """
        获取全市场数据并更新状态条显示
        """
        try:
            # 检查是否已经有正在运行的线程
            if hasattr(self, '_fetch_thread') and self._fetch_thread.is_alive():
                app_logger.debug("市场状态更新线程已在运行，跳过本次更新")
                return
                
            # 在新线程中获取全市场数据，避免阻塞UI
            from threading import Thread
            self._fetch_thread = Thread(target=self._fetch_market_data, daemon=True)
            self._fetch_thread.start()
        except Exception as e:
            app_logger.error(f"获取市场数据时出错: {e}")
        
    def _fetch_market_data(self):
        """
        获取全市场数据并更新状态条
        """
        try:
            import easyquotation
            import json
            import os
            
            # 获取股票列表
            quotation = easyquotation.use('sina')
            # type: ignore 是因为pyright无法正确识别这个方法
            stock_list = quotation.market_snapshot(prefix=True)  # type: ignore
            
            if not stock_list:
                return
                
            up_count = 0
            down_count = 0
            flat_count = 0
            total_count = 0
            
            # 遍历所有股票，统计涨跌情况
            for code, data in stock_list.items():
                if not data:
                    continue
                    
                try:
                    # 跳过指数类数据，只统计个股
                    name = data.get('name', '')
                    if '指数' in name or 'Ａ股' in name:
                        continue
                        
                    close = float(data.get('close', 0))
                    now = float(data.get('now', 0))
                    
                    if close == 0:
                        flat_count += 1
                    elif now > close:
                        up_count += 1
                    elif now < close:
                        down_count += 1
                    else:
                        flat_count += 1
                        
                    total_count += 1
                except (ValueError, TypeError):
                    flat_count += 1
                    total_count += 1
            
            # 在主线程中更新UI
            from PyQt5.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self, 
                "_update_status_internal", 
                Qt.QueuedConnection,  # type: ignore
                QtCore.Q_ARG(int, up_count),
                QtCore.Q_ARG(int, down_count),
                QtCore.Q_ARG(int, flat_count),
                QtCore.Q_ARG(int, total_count)
            )
            
        except Exception as e:
            app_logger.error(f"获取全市场数据时出错: {e}")
        
    def paintEvent(self, event):  # type: ignore
        """绘制状态条"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)  # type: ignore
        
        if self.total_count == 0:
            # 如果没有数据，显示红色
            painter.fillRect(self.rect(), QtGui.QColor(231, 76, 60, 200))
            return
            
        # 计算各部分宽度
        total_width = self.width()
        up_width = int(total_width * self.up_count / self.total_count)
        down_width = int(total_width * self.down_count / self.total_count)
        flat_width = total_width - up_width - down_width  # 剩余部分为平盘
        
        # 按照 红色(上涨) - 灰色(平盘) - 绿色(下跌) 的顺序绘制
        x_pos = 0
        
        # 绘制上涨部分（红色）
        if up_width > 0:
            painter.fillRect(x_pos, 0, up_width, self.height(), QtGui.QColor(231, 76, 60, 200))
            x_pos += up_width
            
        # 绘制平盘部分（灰色）
        if flat_width > 0:
            painter.fillRect(x_pos, 0, flat_width, self.height(), QtGui.QColor(128, 128, 128, 100))
            x_pos += flat_width
            
        # 绘制下跌部分（绿色）
        if down_width > 0:
            painter.fillRect(x_pos, 0, down_width, self.height(), QtGui.QColor(39, 174, 96, 200))