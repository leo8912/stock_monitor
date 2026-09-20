"""
托盘行情降级面板

当任务栏内嵌（SetParent 方式）失败时，回退方案：
在系统托盘图标上动态绘制轮播的股票行情文字/图标，
并在鼠标悬停时通过 ToolTip 展示当前页的完整信息。

该组件不创建独立窗口，而是驱动一个已有的 QSystemTrayIcon：
- 定时轮播，重绘托盘图标（名称首字 + 涨跌色）
- 更新 ToolTip 为当前页多只股票的文字
"""

from __future__ import annotations

from PyQt6 import QtCore, QtGui

from stock_monitor.models.stock_data import StockRowData
from stock_monitor.ui.constants import COLORS
from stock_monitor.utils.logger import app_logger


class TrayQuotePanel(QtCore.QObject):
    """驱动系统托盘图标轮播显示行情的降级方案。"""

    def __init__(self, tray_icon, parent=None) -> None:
        """初始化托盘面板。

        Args:
            tray_icon: 目标 QSystemTrayIcon（可为 None）。
            parent: QObject 父对象。
        """
        super().__init__(parent)
        self._tray = tray_icon
        self._all_stocks: list[StockRowData] = []
        self._page = 0
        self._per_page = 3
        self._active = False

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._next_page)

        self._original_icon = tray_icon.icon() if tray_icon else None

    def configure(self, per_page: int = 3, carousel_interval_sec: int = 5) -> None:
        """设置每页只数与轮播间隔（秒）。"""
        self._per_page = max(1, per_page)
        self._interval_ms = max(1, carousel_interval_sec) * 1000
        if self._active:
            self._timer.start(self._interval_ms)

    def start(self, stocks: list[StockRowData] | None = None) -> None:
        """启动托盘轮播降级。"""
        if stocks is not None:
            self._all_stocks = list(stocks)
        self._active = True
        self._page = 0
        interval = getattr(self, "_interval_ms", 5000)
        self._timer.start(interval)
        self._render()
        app_logger.info("[TrayQuotePanel] 托盘行情降级已启用")

    def stop(self) -> None:
        """停止轮播并恢复托盘原始图标。"""
        self._active = False
        self._timer.stop()
        if self._tray and self._original_icon is not None:
            self._tray.setIcon(self._original_icon)

    def set_stocks(self, stocks: list[StockRowData]) -> None:
        """更新行情数据；运行中则立即重绘。"""
        self._all_stocks = list(stocks or [])
        self._clamp_page()
        if self._active:
            self._render()

    # ── 内部 ──────────────────────────────────────────────────

    def _page_count(self) -> int:
        """返回总页数（无数据时视为 1 页；已做除零防护）。"""
        if not self._all_stocks:
            return 1
        per_page = self._per_page or 1  # 除零防护（T12）
        return (len(self._all_stocks) + per_page - 1) // per_page

    def _clamp_page(self) -> None:
        """把当前页号约束到有效范围内。"""
        count = self._page_count()
        if self._page >= count:
            self._page = 0

    def _next_page(self) -> None:
        """切换到下一页（循环）并重绘。"""
        self._page = (self._page + 1) % self._page_count()
        self._render()

    def _current_page_stocks(self) -> list[StockRowData]:
        """返回当前页的股票切片。"""
        start = self._page * self._per_page
        return self._all_stocks[start : start + self._per_page]

    def _render(self) -> None:
        """重绘托盘图标（首字 + 涨跌色）并更新 ToolTip。"""
        if not self._tray:
            return
        stocks = self._current_page_stocks()
        if not stocks:
            self._tray.setToolTip("行情加载中…")
            return

        # ToolTip：多行完整信息
        lines = []
        for s in stocks:
            lines.append(f"{s.name} {s.price} {s.change_str}")
        self._tray.setToolTip("\n".join(lines))

        # 图标：绘制第一只股票的名称首字，用其涨跌色
        first = stocks[0]
        self._tray.setIcon(self._make_icon(first))

    def _make_icon(self, stock: StockRowData) -> QtGui.QIcon:
        """按股票名称首字与其涨跌色生成 32×32 托盘图标。"""
        size = 32
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        color = QtGui.QColor(stock.color_hex or COLORS.STOCK_NEUTRAL)
        painter.setPen(color)
        font = QtGui.QFont("Microsoft YaHei", 14)
        font.setBold(True)
        painter.setFont(font)
        text = stock.name[0] if stock.name else "?"
        painter.drawText(
            pixmap.rect(),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            text,
        )
        painter.end()
        return QtGui.QIcon(pixmap)
