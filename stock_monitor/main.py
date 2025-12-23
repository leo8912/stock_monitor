"""
股票监控主程序
用于监控A股股票实时行情
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6 import QtCore, QtWidgets

# 设置高DPI缩放策略
QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
    QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

from stock_monitor.core.container import container
from stock_monitor.core.startup import apply_pending_updates, setup_auto_start
from stock_monitor.ui.components.system_tray import SystemTray
from stock_monitor.ui.main_window import MainWindow
from stock_monitor.ui.utils import setup_qt_message_handler
from stock_monitor.utils.logger import app_logger

# 安装自定义Qt消息处理器
setup_qt_message_handler()


def main():
    """主函数"""
    try:
        # 设置异常钩子，记录未捕获的异常
        def exception_hook(exctype, value, traceback):
            app_logger.critical("未捕获的异常", exc_info=(exctype, value, traceback))
            sys.__excepthook__(exctype, value, traceback)

        sys.excepthook = exception_hook

        app_logger.info("应用程序启动")

        # 应用待处理的更新
        apply_pending_updates()

        # 确保数据库已初始化
        from stock_monitor.data.stock.stock_db import stock_db

        # 访问实例以确保初始化
        _ = stock_db

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

        # 设置开机自启动
        setup_auto_start()

        # 启动预加载调度器
        try:
            pass

            # start_preload_scheduler()
        except Exception as e:
            app_logger.error(f"启动预加载调度器失败: {e}")

        # 运行应用
        sys.exit(app.exec())

    except Exception as e:
        app_logger.critical(f"应用程序启动失败: {e}")
        import traceback

        app_logger.critical(f"详细错误信息: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
