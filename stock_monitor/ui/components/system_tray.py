import os

from PyQt6 import QtGui, QtWidgets

from stock_monitor.utils.helpers import resource_path

ICON_FILE = resource_path("icon.ico")


class SystemTray(QtWidgets.QSystemTrayIcon):
    """
    系统托盘类
    负责处理系统托盘图标和相关菜单
    """

    def __init__(self, main_window):
        icon = (
            QtGui.QIcon(ICON_FILE)
            if os.path.exists(ICON_FILE)
            else QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon
            )
        )
        super().__init__(icon)
        self.main_window = main_window
        self.menu = QtWidgets.QMenu()
        self.action_show = self.menu.addAction("显示")
        self.action_settings = self.menu.addAction("设置")
        self.menu.addSeparator()
        self.action_quit = self.menu.addAction("退出")
        self.setContextMenu(self.menu)

        self.action_show.triggered.connect(self.show_main_window)
        self.action_settings.triggered.connect(self.open_settings)
        self.action_quit.triggered.connect(self.quit_application)
        self.activated.connect(self.on_activated)

        # 添加一个状态消息，告知用户程序正在加载数据
        # self.showMessage("A股行情监控", "程序正在后台加载数据，请稍候...",
        #                  QtWidgets.QSystemTrayIcon.MessageIcon.Information, 3000)

    def show_main_window(self):
        """显示主窗口"""
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def open_settings(self):
        """打开设置窗口"""
        self.main_window.open_settings()

    def quit_application(self):
        """退出应用程序"""
        # 调用主窗口的退出方法
        self.main_window.quit_application()

    def on_activated(self, reason):
        """
        托盘图标激活事件处理

        Args:
            reason: 激活原因
        """
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            if self.main_window.isVisible():
                self.main_window.hide()
            else:
                self.main_window.show()
                self.main_window.raise_()
                self.main_window.activateWindow()
        elif reason == QtWidgets.QSystemTrayIcon.ActivationReason.Context:
            self.contextMenu().popup(QtGui.QCursor.pos())
