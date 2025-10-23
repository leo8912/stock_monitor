"""
股市状态条组件
显示整体股市涨跌情况的可视化状态条
"""

from PyQt5 import QtWidgets, QtGui, QtCore


class MarketStatusBar(QtWidgets.QWidget):
    """股市状态条，显示整体涨跌情况"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.up_count = 0      # 上涨股票数
        self.down_count = 0    # 下跌股票数
        self.flat_count = 0    # 平盘股票数
        self.total_count = 0   # 总股票数
        self.setMinimumHeight(3)
        self.setMaximumHeight(3)
        
    def update_status(self, up_count, down_count, flat_count, total_count):
        """更新状态条显示"""
        self.up_count = up_count
        self.down_count = down_count
        self.flat_count = flat_count
        self.total_count = total_count
        self.update()
        
    def paintEvent(self, event):  # type: ignore
        """绘制状态条"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        if self.total_count == 0:
            # 如果没有数据，显示灰色
            painter.fillRect(self.rect(), QtGui.QColor(128, 128, 128, 100))
            return
            
        # 计算各部分宽度
        total_width = self.width()
        up_width = int(total_width * self.up_count / self.total_count)
        down_width = int(total_width * self.down_count / self.total_count)
        flat_width = total_width - up_width - down_width  # 剩余部分为平盘
        
        # 红盘数横线部分使用红色
        up_ratio = self.up_count / self.total_count if self.total_count > 0 else 0
        up_color = QtGui.QColor(231, 76, 60, 200)  # 统一使用红色
        
        # 绘制上涨部分
        if up_width > 0:
            painter.fillRect(0, 0, up_width, self.height(), up_color)
            
        # 绘制下跌部分（绿色）
        if down_width > 0:
            painter.fillRect(up_width, 0, down_width, self.height(), QtGui.QColor(39, 174, 96, 200))  # 绿色
            
        # 绘制平盘部分（灰色）
        if flat_width > 0:
            painter.fillRect(up_width + down_width, 0, flat_width, self.height(), QtGui.QColor(128, 128, 128, 100))  # 灰色