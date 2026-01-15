"""
股票监控主程序
用于监控A股股票实时行情
"""

import sys

# 添加项目根目录到Python路径
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PyQt6 import QtCore, QtWidgets

# 设置高DPI缩放策略
QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
    QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

from stock_monitor.core.container import container
from stock_monitor.core.startup import (
    apply_pending_updates,
    check_update_status,
    setup_auto_start,
)
from stock_monitor.ui.components.system_tray import SystemTray
from stock_monitor.ui.main_window import MainWindow
from stock_monitor.ui.utils import setup_qt_message_handler
from stock_monitor.utils.logger import app_logger

# 安装自定义Qt消息处理器
setup_qt_message_handler()


def _show_update_status_notification(window):
    """检查更新状态并显示相应提示"""
    try:
        from stock_monitor.version import __version__

        status, info = check_update_status()

        if status == "success":
            # 使用 QTimer 延迟显示，避免阻塞启动
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QMessageBox

            def show_success():
                QMessageBox.information(
                    window,
                    "更新完成",
                    f"🎉 Stock Monitor 已成功更新至 v{__version__}",
                    QMessageBox.StandardButton.Ok,
                )

            QTimer.singleShot(500, show_success)

        elif status == "failed":
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QMessageBox

            def show_failure():
                QMessageBox.warning(
                    window,
                    "更新失败",
                    f"⚠️ 上次更新未能成功完成\n\n详细信息:\n{info}",
                    QMessageBox.StandardButton.Ok,
                )

            QTimer.singleShot(500, show_failure)

    except Exception as e:
        app_logger.error(f"显示更新状态通知失败: {e}")


def main():
    """主函数"""
    try:
        # 设置异常钩子，记录未捕获的异常
        def exception_hook(exctype, value, traceback):
            app_logger.critical("未捕获的异常", exc_info=(exctype, value, traceback))
            sys.__excepthook__(exctype, value, traceback)

        sys.excepthook = exception_hook

        app_logger.info("应用程序启动")

        # 修复 SSL 证书路径 (PyInstaller 环境)
        if hasattr(sys, "_MEIPASS"):
            import os

            # 尝试查找 bundled certifi pem
            # PyInstaller --collect-all certifi 会将其放在 _MEIPASS/certifi 目录中
            ssl_cert_path = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
            if os.path.exists(ssl_cert_path):
                os.environ["REQUESTS_CA_BUNDLE"] = ssl_cert_path
                os.environ["SSL_CERT_FILE"] = ssl_cert_path
                app_logger.info(f"已设置 SSL 证书路径: {ssl_cert_path}")
            else:
                app_logger.warning(f"未找到 SSL 证书文件: {ssl_cert_path}")

        # 应用待处理的更新
        apply_pending_updates()

        # 确保数据库已初始化
        from stock_monitor.data.stock.stock_db import StockDatabase

        # 访问实例以确保初始化
        _ = container.get(StockDatabase)

        app = QtWidgets.QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # 窗口关闭时不退出程序

        # 设置全局默认字体，防止 QFont 报警
        from PyQt6.QtGui import QFont

        app.setFont(QFont("Microsoft YaHei", 10))

        # 再次确认配置
        from stock_monitor.config.manager import ConfigManager

        config_manager = container.get(ConfigManager)
        font_size = config_manager.get("font_size", 13)
        app_logger.info(f"当前配置字体大小: {font_size}")

        # 初始化主窗口
        window = MainWindow()

        # 创建系统托盘图标
        tray_icon = SystemTray(window)
        tray_icon.show()
        # 保存托盘图标引用到主窗口
        window.tray_icon = tray_icon

        # 检查更新状态并显示提示
        _show_update_status_notification(window)

        # 设置开机自启动（延迟执行，避免阻塞启动）
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(2000, setup_auto_start)

        # 预加载调度器（已移除，不再使用）

        # 运行应用
        sys.exit(app.exec())

    except Exception as e:
        app_logger.critical(f"应用程序启动失败: {e}")
        import traceback

        app_logger.critical(f"详细错误信息: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
