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


def test_rect_center_uses_bounds_not_wh():
    """回归 v4.8.3：GetWindowRect 四边界不能按 (x, y, w, h) 解包算中心。

    旧实现把 ``(left, top, right, bottom)`` 当 ``(x, y, w, h)``，中心点
    ``(1616, 1552)`` 被算到屏幕之外，``WindowFromPoint`` 恒返回 NULL，
    遮挡命中测试完全失效（更新后行情条被任务栏盖住无法恢复的根因之一）。
    """
    rect = (1029, 1020, 1259, 1065)  # left, top, right, bottom
    assert TaskbarQuoteBar._rect_center(rect) == (1144, 1042)


def test_rect_center_odd_span():
    """奇数跨度取整不越界。"""
    assert TaskbarQuoteBar._rect_center((0, 0, 5, 7)) == (2, 3)


def test_rect_intersects_overlapping():
    """任务栏与压在其上的行情条矩形应判定为相交。"""
    taskbar = (0, 1019, 1707, 1067)
    bar = (1029, 1020, 1259, 1065)
    assert TaskbarQuoteBar._rect_intersects(taskbar, bar) is True


def test_rect_intersects_disjoint():
    """1x1 的 Shell 辅助窗口位于原点，与任务栏右下角的行情条不相交。"""
    helper = (0, 0, 1, 1)
    bar = (1029, 1020, 1259, 1065)
    assert TaskbarQuoteBar._rect_intersects(helper, bar) is False


def test_rect_intersects_touching_edges_not_counted():
    """仅边线接触（right == left）不算相交，避免贴边窗口误判遮挡。"""
    assert TaskbarQuoteBar._rect_intersects((0, 0, 10, 10), (10, 0, 20, 10)) is False
