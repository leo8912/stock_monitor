"""
股市状态条组件
显示整体股市涨跌情况的可视化状态条
"""

from PyQt6 import QtWidgets, QtGui, QtCore
from stock_monitor.utils.logger import app_logger
import threading


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
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        
        # 创建右键菜单
        self.menu = QtWidgets.QMenu(self)
        self.menu.setStyleSheet('''
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 14px;  /* 调大字体 */
                padding: 2px 0;   /* 减小内边距 */
                min-width: 100px; /* 缩小最小宽度 */
            }
            QMenu::item {
                padding: 4px 16px;
                border: none;
            }
            QMenu::item:selected {
                background-color: #444444;
            }
        ''')
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, position):
        """显示右键菜单"""
        # 清空现有动作
        self.menu.clear()
        
        # 添加"设置"动作
        action_settings = self.menu.addAction('设置')
        action_settings.triggered.connect(self.open_settings)
        
        # 添加分隔符
        self.menu.addSeparator()
        
        # 添加"退出"动作
        action_quit = self.menu.addAction('退出')
        action_quit.triggered.connect(self.quit_app)
        
        # 显示菜单
        self.menu.popup(QtGui.QCursor.pos())
        
    def open_settings(self):
        """打开设置窗口"""
        if self.parent():
            self.parent().open_settings()
            
    def quit_app(self):
        """退出应用"""
        QtWidgets.QApplication.quit()
        
    def update_status(self, up_count, down_count, flat_count, total_count):
        """更新状态条显示"""
        self.up_count = up_count
        self.down_count = down_count
        self.flat_count = flat_count
        self.total_count = total_count
        self.update()
        
    def paintEvent(self, event):
        """绘制状态条"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)  # type: ignore
        
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