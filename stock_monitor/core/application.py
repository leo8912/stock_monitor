"""
股票监控应用程序类

封装应用程序的生命周期管理逻辑，包括初始化、运行和退出。
"""

import sys

from PyQt6 import QtWidgets
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox

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

    def __init__(self) -> None:
        """初始化应用程序"""
        self._app = None
        self._window = None
        self._tray_icon = None

        # 设置异常钩子
        self._setup_exception_hook()

        # 安装自定义 Qt 消息处理器
        setup_qt_message_handler()

        app_logger.info("应用程序启动")

    def _setup_exception_hook(self) -> None:
        """设置全局异常钩子，记录未捕获的异常"""

        def exception_hook(exctype, value, traceback) -> None:
            """未捕获异常的全局兜底钩子：记录后交给默认钩子处理。"""
            app_logger.critical("未捕获的异常", exc_info=(exctype, value, traceback))
            sys.__excepthook__(exctype, value, traceback)

        sys.excepthook = exception_hook

    def _fix_ssl_cert_path(self) -> None:
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

    def _init_database(self) -> None:
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

            qss = load_global_stylesheet("Microsoft YaHei", 10)
            if qss:
                app.setStyleSheet(qss)
                app_logger.info("已成功应用基础全局样式表")
        except Exception as e:
            app_logger.error(f"应用基础全局样式表失败: {e}")

        return app

    def _log_config_info(self) -> None:
        """记录配置信息"""
        from stock_monitor.core.config_center import config_center

        font_size = config_center.get_int("font_size", 13)
        app_logger.info_ctx("当前配置信息", font_size=font_size)

    def _create_main_window(self) -> MainWindow:
        """创建主窗口"""
        return MainWindow()

    def _create_system_tray(self, window: MainWindow) -> SystemTray:
        """创建系统托盘图标"""
        tray_icon = SystemTray(window)
        tray_icon.show()
        return tray_icon

    def _run_health_check(self) -> None:
        """启动时执行健康检查"""
        try:
            from stock_monitor.utils.health_check import HealthStatus, run_health_check

            report = run_health_check()
            app_logger.info(report.summary())
            if report.status == HealthStatus.UNHEALTHY:
                app_logger.warning("健康检查发现严重问题，部分功能可能不可用")
        except Exception as e:
            app_logger.warning(f"健康检查执行失败: {e}")

    def _show_update_status_notification(self) -> None:
        """检查更新状态并显示相应提示"""
        try:
            from stock_monitor.version import __version__

            status, info = check_update_status()

            if status == "success":

                def show_success() -> None:
                    """弹出"更新完成"提示。"""
                    QMessageBox.information(
                        self._window,
                        "更新完成",
                        f"🎉 Stock Monitor 已成功更新至 v{__version__}",
                        QMessageBox.StandardButton.Ok,
                    )

                QTimer.singleShot(500, show_success)

            elif status == "failed":

                def show_failure() -> None:
                    """弹出"更新失败"提示。"""
                    QMessageBox.warning(
                        self._window,
                        "更新失败",
                        f"⚠️ 上次更新未能成功完成\n\n详细信息:\n{info}",
                        QMessageBox.StandardButton.Ok,
                    )

                QTimer.singleShot(500, show_failure)

        except Exception as e:
            app_logger.error(f"显示更新状态通知失败: {e}")

    def _schedule_auto_start_setup(self) -> None:
        """延迟设置开机自启动，避免阻塞启动"""
        QTimer.singleShot(2000, setup_auto_start)

    def _on_about_to_quit(self) -> None:
        """应用退出前置处理：释放主窗口资源并停止后台常驻服务。"""
        if self._window is not None:
            self._window._shutdown_resources()
        self._stop_background_services()

    def _stop_background_services(self) -> None:
        """停止后台常驻服务（暗盘资金服务等）。

        修复 G-8：``DarkTradeService.stop_service()`` 此前全项目无调用点，
        退出时服务线程会随进程被强制终止。这里在 ``aboutToQuit`` 阶段显式停止。
        同时关闭 StockManager / stock_fetcher 线程池（幂等；atexit 亦有兜底）。
        """
        try:
            from stock_monitor.services.dark_trade.service import (
                get_dark_trade_service,
            )

            get_dark_trade_service().stop_service()
            app_logger.info("暗盘资金服务已停止")
        except Exception as e:
            app_logger.error(f"停止暗盘资金服务失败: {e}", exc_info=True)

        # 释放行情相关线程池（与 StockDataFetcher 的 atexit 关闭路径互补）
        try:
            from stock_monitor.core.market.stock_manager import stock_manager

            stock_manager.close()
        except Exception as e:
            app_logger.error(f"关闭 StockManager 失败: {e}", exc_info=True)

        try:
            from stock_monitor.data.fetcher import stock_fetcher

            stock_fetcher.close()
        except Exception as e:
            app_logger.error(f"关闭 stock_fetcher 失败: {e}", exc_info=True)

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

            # 健康检查
            self._run_health_check()

            # 创建 Qt 应用
            self._app = self._create_qt_app()

            # 记录配置信息
            self._log_config_info()

            # 创建主窗口
            self._window = self._create_main_window()

            # 创建系统托盘
            self._tray_icon = self._create_system_tray(self._window)
            self._window.tray_icon = self._tray_icon

            # 退出流程统一接线（T03/G-8）：aboutToQuit 时释放主窗口资源并停止后台服务
            self._app.aboutToQuit.connect(self._on_about_to_quit)

            # 发布启动完成事件
            from stock_monitor.core.event_bus import Topics, event_bus

            event_bus.publish(Topics.APP_STARTUP, source="Application")

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
