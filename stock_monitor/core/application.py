"""
股票监控应用程序类

封装应用程序的生命周期管理逻辑，包括初始化、运行和退出。
"""

import sys

from PyQt6 import QtWidgets
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.config.container import container
from stock_monitor.core.config.startup import (
    apply_pending_updates,
    check_update_status,
    setup_auto_start,
)
from stock_monitor.data.stock.stock_db import StockDatabase
from stock_monitor.ui.components.system_tray import SystemTray
from stock_monitor.ui.main_window import MainWindow
from stock_monitor.ui.utils import setup_qt_message_handler
from stock_monitor.utils.logger import app_logger


class StockMonitorApp:
    """
    股票监控应用程序

    负责管理应用程序的完整生命周期：
    - 初始化 Qt 应用和相关配置
    - 创建主窗口和系统托盘
    - 处理更新状态通知
    - 设置开机自启动
    - 运行事件循环
    """

    def __init__(self):
        """初始化应用程序"""
        self._app: QtWidgets.QApplication | None = None
        self._window: MainWindow | None = None
        self._tray_icon: SystemTray | None = None

        # 设置异常钩子
        self._setup_exception_hook()

        # 安装自定义 Qt 消息处理器
        setup_qt_message_handler()

        app_logger.info("应用程序启动")

    def _setup_exception_hook(self):
        """设置全局异常钩子，记录未捕获的异常"""

        def exception_hook(exctype, value, traceback):
            app_logger.critical("未捕获的异常", exc_info=(exctype, value, traceback))
            sys.__excepthook__(exctype, value, traceback)

        sys.excepthook = exception_hook

    def _fix_ssl_cert_path(self):
        """修复 SSL 证书路径 (PyInstaller 环境)"""
        if hasattr(sys, "_MEIPASS"):
            import os

            ssl_cert_path = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
            if os.path.exists(ssl_cert_path):
                os.environ["REQUESTS_CA_BUNDLE"] = ssl_cert_path
                os.environ["SSL_CERT_FILE"] = ssl_cert_path
                app_logger.info(f"已设置 SSL 证书路径: {ssl_cert_path}")
            else:
                app_logger.warning(f"未找到 SSL 证书文件: {ssl_cert_path}")

    def _init_database(self):
        """确保数据库已初始化"""
        _ = container.get(StockDatabase)

    def _create_qt_app(self) -> QtWidgets.QApplication:
        """创建并配置 Qt 应用程序"""
        app = QtWidgets.QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # 窗口关闭时不退出程序

        # 设置全局默认字体
        app.setFont(QFont("Microsoft YaHei", 10))

        # 应用全局样式表 (仅保留静态基础样式，动态部分移至 MainWindow)
        try:
            from stock_monitor.ui.styles import load_global_stylesheet

            # 使用默认字体加载基础全局样式
            qss = load_global_stylesheet("Microsoft YaHei", 10)
            if qss:
                # 移除其中关于字体的全局设定，防止影响 SettingsDialog
                import re

                # 仅替换最前面的通配符字体设置
                qss = re.sub(
                    r"\* \{(.*?)\}",
                    r"/* Font settings moved to MainWindow */",
                    qss,
                    count=1,
                    flags=re.DOTALL,
                )

                app.setStyleSheet(qss)
                app_logger.info("已成功应用基础全局样式表")
        except Exception as e:
            app_logger.error(f"应用基础全局样式表失败: {e}")

        return app

    def _log_config_info(self):
        """记录配置信息"""
        config_manager = container.get(ConfigManager)
        font_size = config_manager.get("font_size", 13)
        app_logger.info(f"当前配置字体大小: {font_size}")

    def _create_main_window(self) -> MainWindow:
        """创建主窗口"""
        return MainWindow()

    def _create_system_tray(self, window: MainWindow) -> SystemTray:
        """创建系统托盘图标"""
        tray_icon = SystemTray(window)
        tray_icon.show()
        return tray_icon

    def _show_update_status_notification(self):
        """检查更新状态并显示相应提示"""
        try:
            from stock_monitor.version import __version__

            status, info = check_update_status()

            if status == "success":

                def show_success():
                    QMessageBox.information(
                        self._window,
                        "更新完成",
                        f"🎉 Stock Monitor 已成功更新至 v{__version__}",
                        QMessageBox.StandardButton.Ok,
                    )

                QTimer.singleShot(500, show_success)

            elif status == "failed":

                def show_failure():
                    QMessageBox.warning(
                        self._window,
                        "更新失败",
                        f"⚠️ 上次更新未能成功完成\n\n详细信息:\n{info}",
                        QMessageBox.StandardButton.Ok,
                    )

                QTimer.singleShot(500, show_failure)

        except Exception as e:
            app_logger.error(f"显示更新状态通知失败: {e}")

    def _schedule_auto_start_setup(self):
        """延迟设置开机自启动，避免阻塞启动"""
        QTimer.singleShot(2000, setup_auto_start)

    def run(self) -> int:
        """
        运行应用程序

        Returns:
            int: 应用程序退出码
        """
        try:
            # 修复 SSL 证书路径
            self._fix_ssl_cert_path()

            # 应用待处理的更新
            apply_pending_updates()

            # 初始化数据库
            self._init_database()

            # 创建 Qt 应用
            self._app = self._create_qt_app()

            # 记录配置信息
            self._log_config_info()

            # 创建主窗口
            self._window = self._create_main_window()

            # 创建系统托盘
            self._tray_icon = self._create_system_tray(self._window)
            self._window.tray_icon = self._tray_icon

            # 检查更新状态并显示提示
            self._show_update_status_notification()

            # 设置开机自启动
            self._schedule_auto_start_setup()

            # 运行事件循环
            return self._app.exec()

        except Exception as e:
            app_logger.critical(f"应用程序启动失败: {e}")
            import traceback

            app_logger.critical(f"详细错误信息: {traceback.format_exc()}")
            return 1
