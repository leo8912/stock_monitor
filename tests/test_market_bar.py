"""任务栏行情条 —— 纯函数聚合逻辑测试。

历史问题：原用例构造真实 ``TaskbarQuoteBar()``，其 ``__init__`` 在 Windows 上
会创建原生顶层窗口，后续 ``start()`` 通过 Win32 ``SetParent`` 嵌入
``Shell_TrayWnd``；在无交互桌面会话的 pytest 进程中会触发解释器 native 崩溃
（exit 127）。现改为只断言纯函数 ``TaskbarQuoteBar.compute_market_stats``，
不再构造任何窗口，也不需要 ``QApplication``。
"""

from stock_monitor.ui.widgets.taskbar_quote_bar import TaskbarQuoteBar


def test_compute_market_stats_normal():
    """常规涨跌平家数应原样映射为 dict。"""
    stats = TaskbarQuoteBar.compute_market_stats(20, 15, 5, 40)
    assert stats == {"up": 20, "down": 15, "flat": 5, "total": 40}


def test_compute_market_stats_coerces_to_int():
    """字符串/浮点输入应被强制转为 int（与本组件历史行为一致）。"""
    stats = TaskbarQuoteBar.compute_market_stats("20", 15.9, 5, 40)
    assert stats["up"] == 20
    assert stats["down"] == 15
    assert stats["flat"] == 5
    assert stats["total"] == 40


def test_compute_market_stats_zero():
    """全零输入（未加载数据）应返回全零 dict，不抛异常。"""
    stats = TaskbarQuoteBar.compute_market_stats(0, 0, 0, 0)
    assert stats == {"up": 0, "down": 0, "flat": 0, "total": 0}
