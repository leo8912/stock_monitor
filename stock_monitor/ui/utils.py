"""
UI工具模块
包含通用UI辅助函数和Qt消息处理逻辑
"""

import sys

from PyQt6 import QtCore


def qt_message_handler(mode, context, message):
    """
    自定义Qt消息处理程序，屏蔽特定的无关警告

    Args:
        mode: 消息类型
        context: 上下文信息
        message: 消息内容
    """
    # 屏蔽 QFont::setPointSize: Point size <= 0 警告
    # 这个警告通常由于Qt内部样式计算导致，不影响功能
    if "QFont::setPointSize: Point size <= 0" in message:
        return

    msg_type = "Debug"
    if mode == QtCore.QtMsgType.QtInfoMsg:
        msg_type = "Info"
    elif mode == QtCore.QtMsgType.QtWarningMsg:
        msg_type = "Warning"
    elif mode == QtCore.QtMsgType.QtCriticalMsg:
        msg_type = "Critical"
    elif mode == QtCore.QtMsgType.QtFatalMsg:
        msg_type = "Fatal"

    # 避免日志噪音，只在严重错误时打印到stderr
    if mode >= QtCore.QtMsgType.QtWarningMsg:
        print(f"Qt {msg_type}: {message}", file=sys.stderr)


def setup_qt_message_handler():
    """安装自定义Qt消息处理器"""
    QtCore.qInstallMessageHandler(qt_message_handler)
