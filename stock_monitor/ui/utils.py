"""
UI工具模块
包含通用UI辅助函数和Qt消息处理逻辑
"""

from PyQt6 import QtCore

# 主窗口背景透明度常量
MIN_BACKGROUND_ALPHA = 128  # 透明度0时的alpha值(半透明,相当于原来50%的透明度)
MAX_BACKGROUND_ALPHA = 255  # 透明度100时的alpha值(完全不透明)
ALPHA_RANGE = MAX_BACKGROUND_ALPHA - MIN_BACKGROUND_ALPHA


def compute_background_alpha(transparency) -> int:
    """将 0-100 的透明度配置映射为背景 alpha 值（128-255，区间截断）。"""
    alpha = int(MIN_BACKGROUND_ALPHA + (ALPHA_RANGE * transparency / 100))
    return max(MIN_BACKGROUND_ALPHA, min(MAX_BACKGROUND_ALPHA, alpha))


def sanitize_font_size(value, default: int = 13) -> int:
    """解析字体大小配置：非法值或非正值回退为默认值。"""
    try:
        size = int(value)
    except (ValueError, TypeError):
        return default
    return size if size > 0 else default


def sort_stocks_by_user_order(data: list, user_stocks: list) -> list:
    """按用户自选股顺序对刷新数据排序，未匹配的项排在末尾。"""
    stock_order_map = {code: i for i, code in enumerate(user_stocks)}
    return sorted(
        data,
        key=lambda x: stock_order_map.get(
            x.code if hasattr(x, "code") else getattr(x, "name", ""), 999
        ),
    )


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

    # 避免日志噪音，只在严重错误时定向输出到应用日志系统
    if mode in (
        QtCore.QtMsgType.QtWarningMsg,
        QtCore.QtMsgType.QtCriticalMsg,
        QtCore.QtMsgType.QtFatalMsg,
    ):
        from stock_monitor.utils.logger import app_logger

        log_msg = f"Qt {msg_type}: {message}"
        if mode == QtCore.QtMsgType.QtWarningMsg:
            app_logger.warning(log_msg)
        elif mode == QtCore.QtMsgType.QtCriticalMsg:
            app_logger.error(log_msg)
        elif mode == QtCore.QtMsgType.QtFatalMsg:
            app_logger.critical(log_msg)


def setup_qt_message_handler():
    """安装自定义Qt消息处理器"""
    QtCore.qInstallMessageHandler(qt_message_handler)
