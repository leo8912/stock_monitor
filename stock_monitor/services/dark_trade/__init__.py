"""暗盘资金统计模块

提供暗盘资金流向的统计计算、消息格式化、Excel导出和企业微信推送功能。

主要接口:
    - calculate_dark_trade_stats(): 计算暗盘统计数据
    - format_dark_trade_stats_message(): 格式化推送消息
    - export_dark_trade_stats_excel(): 导出Excel报表
    - push_dark_trade_stats(): 推送到企业微信
"""

from __future__ import annotations

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats
from stock_monitor.services.dark_trade.exporter import export_dark_trade_stats_excel
from stock_monitor.services.dark_trade.formatter import format_dark_trade_stats_message
from stock_monitor.services.dark_trade.pusher import push_dark_trade_stats

__all__ = [
    "calculate_dark_trade_stats",
    "format_dark_trade_stats_message",
    "export_dark_trade_stats_excel",
    "push_dark_trade_stats",
]
