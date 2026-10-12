"""
股票监控主程序入口

用于监控A股股票实时行情
"""

import sys

from PyQt6 import QtCore, QtWidgets

# 设置高DPI缩放策略 (必须在 QApplication 创建前设置)
QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
    QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

from stock_monitor.core.application import StockMonitorApp


def main():
    """主函数"""
    app = StockMonitorApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
