"""
任务栏内嵌行情条组件

复刻 TrafficMonitor 的实现思路：通过 Win32 API 将一个无边框 QWidget
使用 SetParent 嵌入到系统任务栏窗口（Shell_TrayWnd）内部，
在通知区（TrayNotifyWnd）左侧显示滚动的股票行情。

- 一次显示可配置数量（默认 3）只股票，支持自动轮播 + 滚轮/点击手动翻页
- 使用 QPainter 绘制（替代 TrafficMonitor 的 GDI/D2D）
- 监听 explorer 重启（TaskbarCreated），自动重新嵌入
- 嵌入失败时通过信号通知外部降级到托盘图标

仅在 Windows 平台生效，其它平台所有操作静默跳过。
"""

from __future__ import annotations

import sys
import time

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import pyqtSignal

from stock_monitor.models.stock_data import StockRowData
from stock_monitor.ui.constants import COLORS
from stock_monitor.utils.logger import app_logger

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        _dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        _dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
        _dwmapi.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
    except OSError:
        _dwmapi = None

    # 显式声明 Win32 函数原型，避免 64 位下句柄(HWND/LONG_PTR)被默认 c_int 截断
    _user32.FindWindowW.restype = wintypes.HWND
    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.FindWindowExW.restype = wintypes.HWND
    _user32.FindWindowExW.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    ]
    _user32.SetParent.restype = wintypes.HWND
    _user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    _user32.IsWindow.restype = wintypes.BOOL
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.RegisterWindowMessageW.restype = wintypes.UINT
    _user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    _user32.BringWindowToTop.restype = wintypes.BOOL
    _user32.BringWindowToTop.argtypes = [wintypes.HWND]
    _user32.WindowFromPoint.restype = wintypes.HWND
    _user32.WindowFromPoint.argtypes = [wintypes.POINT]
    _user32.IsChild.restype = wintypes.BOOL
    _user32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
    _user32.GetWindow.restype = wintypes.HWND
    _user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]

    # GetWindowLongPtrW/SetWindowLongPtrW 仅在 64 位存在；32 位回退到 Long 版本
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _GetWindowLong = _user32.GetWindowLongPtrW
        _SetWindowLong = _user32.SetWindowLongPtrW
        _long_ptr_t = ctypes.c_longlong
    else:
        _GetWindowLong = _user32.GetWindowLongW
        _SetWindowLong = _user32.SetWindowLongW
        _long_ptr_t = ctypes.c_long
    _GetWindowLong.restype = _long_ptr_t
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _SetWindowLong.restype = _long_ptr_t
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, _long_ptr_t]


def _is_windows_11() -> bool:
    """Win11 起 build >= 22000，任务栏为 XAML 合成层，SetParent 子窗口不可见。"""
    if not _IS_WINDOWS:
        return False
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return False


# Win32 常量
_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_WS_CHILD = 0x40000000
_WS_POPUP = 0x80000000
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_LAYERED = 0x00080000
_WS_EX_TOPMOST = 0x00000008
_WS_EX_NOACTIVATE = 0x08000000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020
_SWP_SHOWWINDOW = 0x0040
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
# Win11 DWM 圆角策略：DWMWA_WINDOW_CORNER_PREFERENCE=33, DWMWCP_DONOTROUND=1
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_DONOTROUND = 1

# 列布局：列间距与左右内边距（像素）
_COL_GAP = 10
_EDGE_PAD = 4

# z-order 探测上限（从 topmost 带顶走到自身的最大步数，防御性截断）
_MAX_Z_PROBE = 128
# 被遮挡时两次重抢 z-order 的最小间隔（秒）：既避免旧版每 300ms 盲抢造成
# 的桌面闪烁，又保证任务栏压住行情条后最迟约 1 秒内必定恢复显示
_REASSERT_COOLDOWN_SEC = 0.5


class TaskbarQuoteBar(QtWidgets.QWidget):
    """嵌入任务栏显示行情的窄条窗口。"""

    # 嵌入任务栏失败时发出，参数为失败原因，供外部降级处理
    embed_failed = pyqtSignal(str)
    # 成功嵌入任务栏时发出
    embed_succeeded = pyqtSignal()
    # 右键菜单动作请求（供主窗口连接）
    show_main_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        """初始化任务栏行情条：窗口标志、动画/定时器与 Win32 消息注册。"""
        super().__init__(None)  # 顶层窗口，稍后 SetParent 到任务栏
        self._all_stocks: list[StockRowData] = []
        self._page = 0
        self._per_page = 3
        self._show_price = True
        self._show_change = True
        self._show_dark_flow = False
        self._carousel_enabled = True
        self._embedded = False
        self._taskbar_hwnd = 0
        self._notify_hwnd = 0
        self._market_up_count = 0
        self._market_down_count = 0
        self._market_flat_count = 0
        self._market_total_count = 0
        # Win11 任务栏为 XAML 合成层，SetParent 子窗口会被 DesktopWindowContentBridge
        # 覆盖而不可见，改用置顶悬浮窗覆盖在任务栏通知区左侧
        self._overlay_mode = _is_windows_11()

        # 无边框 + 透明背景，融入任务栏。悬浮模式(Win11)一次性设好置顶/不抢焦点
        # 标志，避免 start 时再次 setWindowFlags 触发原生窗口重建而闪烁。
        flags = QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Tool
        if self._overlay_mode:
            flags |= (
                QtCore.Qt.WindowType.WindowStaysOnTopHint
                | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            )
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setObjectName("TaskbarQuoteBar")
        self.setMouseTracking(True)

        # 翻页过渡动画：上下滑动 + 淡入，避免硬切换
        self._prev_page_stocks: list[StockRowData] = []
        self._anim_progress = 1.0  # 1.0=静止；<1.0 过渡中
        self._anim_direction = 1  # 1=下一页(上滑)，-1=上一页(下滑)
        self._page_anim = QtCore.QVariantAnimation(self)
        self._page_anim.setDuration(220)
        self._page_anim.setStartValue(0.0)
        self._page_anim.setEndValue(1.0)
        self._page_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._page_anim.valueChanged.connect(self._on_page_anim_value)

        # 轮播定时器
        self._carousel_timer = QtCore.QTimer(self)
        self._carousel_timer.timeout.connect(self._next_page)

        # 位置维持定时器：任务栏尺寸/DPI 变化或 explorer 重启后重新定位
        self._reposition_timer = QtCore.QTimer(self)
        self._reposition_timer.setInterval(2000)
        self._reposition_timer.timeout.connect(self._maintain_embed)

        # 置顶维持定时器（仅悬浮模式）：点击任务栏会使 XAML 合成层盖住本窗口，
        # 高频、低开销地重新抢占最顶层 z-order，避免行情条被点“消失”。
        self._topmost_timer = QtCore.QTimer(self)
        self._topmost_timer.setInterval(300)
        self._topmost_timer.timeout.connect(self._keep_on_top)

        # explorer 重建任务栏的广播消息
        self._wm_taskbar_created = 0
        if _IS_WINDOWS:
            self._wm_taskbar_created = _user32.RegisterWindowMessageW("TaskbarCreated")

        self._bar_width = 220
        self._bar_height = 40
        # 置顶维持冷却：两次重抢 z-order 的最小间隔（秒，见 _keep_on_top）
        self._last_reassert_ts = 0.0
        # 上次 SetWindowPos 的几何，未变化时跳过重定位（见 _reposition）
        self._last_rect: tuple[int, int, int, int] | None = None

    # ── 公共 API ────────────────────────────────────────────────

    def configure(
        self,
        per_page: int = 3,
        carousel_interval_sec: int = 5,
        carousel_enabled: bool = True,
        show_price: bool = True,
        show_change: bool = True,
        show_dark_flow: bool = False,
    ) -> None:
        """应用显示配置。"""
        self._per_page = max(1, per_page)
        self._show_price = show_price
        self._show_change = show_change
        self._show_dark_flow = show_dark_flow
        self._carousel_enabled = carousel_enabled
        if carousel_enabled:
            self._carousel_timer.start(max(1, carousel_interval_sec) * 1000)
        else:
            self._carousel_timer.stop()
        self._clamp_page()
        self._recalc_width()
        self.update()

    def set_stocks(self, stocks: list[StockRowData]) -> None:
        """更新行情数据并重绘。"""
        self._all_stocks = list(stocks or [])
        self._clamp_page()
        self._recalc_width()
        self.update()

    @staticmethod
    def compute_market_stats(
        up_count: int, down_count: int, flat_count: int, total_count: int
    ) -> dict:
        """归一化全市场涨跌家数，供任务栏红绿盘比例条绘制使用。

        抽为纯函数以便单元测试（构造真实 ``TaskbarQuoteBar`` 会在无交互桌面
        会话中触发 Win32 ``SetParent`` native 崩溃）。

        Args:
            up_count: 上涨家数。
            down_count: 下跌家数。
            flat_count: 平盘家数。
            total_count: 总家数。

        Returns:
            含 ``up`` / ``down`` / ``flat`` / ``total`` 四个 ``int`` 字段的字典。
        """
        return {
            "up": int(up_count),
            "down": int(down_count),
            "flat": int(flat_count),
            "total": int(total_count),
        }

    def update_market_stats(
        self, up_count: int, down_count: int, flat_count: int, total_count: int
    ) -> None:
        """同步全市场涨跌比例并更新任务栏顶部红绿盘条。"""
        stats = self.compute_market_stats(up_count, down_count, flat_count, total_count)
        self._market_up_count = stats["up"]
        self._market_down_count = stats["down"]
        self._market_flat_count = stats["flat"]
        self._market_total_count = stats["total"]
        self.update()

    def start(self) -> bool:
        """显示并尝试嵌入任务栏。返回是否成功显示。

        Win10 及更早：SetParent 嵌入任务栏子窗口。
        Win11：任务栏为 XAML 合成层，SetParent 子窗口被 DesktopWindowContentBridge
        覆盖不可见，改用置顶悬浮窗覆盖在通知区左侧。
        """
        if not _IS_WINDOWS:
            self.embed_failed.emit("非 Windows 平台，任务栏嵌入不可用")
            return False
        if self._overlay_mode:
            ok = self._start_overlay()
        else:
            self.show()
            ok = self._embed_into_taskbar()
        if ok:
            self._reposition_timer.start()
            if self._overlay_mode:
                self._topmost_timer.start()
            self.embed_succeeded.emit()
        return ok

    def _start_overlay(self) -> bool:
        """Win11：以置顶、不抢焦点的悬浮窗覆盖在任务栏通知区左侧。"""
        try:
            if not self._find_taskbar():
                self.embed_failed.emit("未找到任务栏窗口 Shell_TrayWnd")
                return False
            # 窗口标志已在 __init__ 中设好（置顶+工具窗+不抢焦点），此处不再
            # setWindowFlags，避免重建原生窗口导致首次启动窗口闪现消失再出现。
            self.show()
            hwnd = int(self.winId())
            # 追加 NOACTIVATE 扩展样式，点击不夺取前台
            ex_style = _GetWindowLong(hwnd, _GWL_EXSTYLE)
            ex_style |= _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE
            _SetWindowLong(hwnd, _GWL_EXSTYLE, ex_style)
            self._disable_dwm_round_corners(hwnd)
            self._embedded = True
            # 重新嵌入（首次启动或 explorer 重启）时作废几何缓存，强制
            # 重新定位并带 HWND_TOPMOST 抬升一次
            self._last_rect = None
            self._reposition()
            app_logger.info("[TaskbarQuoteBar] 已启用任务栏悬浮模式(Win11)")
            return True
        except Exception as e:
            app_logger.warning(f"[TaskbarQuoteBar] 悬浮模式启动异常: {e}")
            self.embed_failed.emit(str(e))
            return False

    def stop(self) -> None:
        """停止轮播并从任务栏分离、隐藏。"""
        self._carousel_timer.stop()
        self._reposition_timer.stop()
        self._topmost_timer.stop()
        self._detach_from_taskbar()
        self.hide()
        # 复位几何/冷却缓存，下次 start 后重新定位
        self._last_rect = None
        self._last_reassert_ts = 0.0

    # ── 翻页 ────────────────────────────────────────────────────

    def _page_count(self) -> int:
        """返回当前每页只数下的总页数（无数据时视为 1 页）。"""
        if not self._all_stocks:
            return 1
        return (len(self._all_stocks) + self._per_page - 1) // self._per_page

    def _clamp_page(self) -> None:
        """把当前页号约束到 [0, 页数) 范围内。"""
        count = self._page_count()
        if self._page >= count:
            self._page = 0
        if self._page < 0:
            self._page = count - 1

    def _next_page(self) -> None:
        """切换到下一页（循环），仅多于 1 页时生效。"""
        if self._page_count() <= 1:
            return
        self._begin_page_transition(1)
        self._page = (self._page + 1) % self._page_count()
        self.update()

    def _prev_page(self) -> None:
        """切换到上一页（循环），仅多于 1 页时生效。"""
        if self._page_count() <= 1:
            return
        self._begin_page_transition(-1)
        self._page = (self._page - 1) % self._page_count()
        self.update()

    def _begin_page_transition(self, direction: int) -> None:
        """记录当前页作为旧页，启动上下滑动+淡入过渡动画。"""
        self._prev_page_stocks = self._current_page_stocks()
        self._anim_direction = direction
        self._page_anim.stop()
        self._anim_progress = 0.0
        self._page_anim.start()

    def _on_page_anim_value(self, value) -> None:
        """翻页动画帧回调：更新过渡进度并触发重绘。"""
        self._anim_progress = float(value)
        self.update()

    def _current_page_stocks(self) -> list[StockRowData]:
        """返回当前页应显示的股票切片。"""
        start = self._page * self._per_page
        return self._all_stocks[start : start + self._per_page]

    # ── 交互 ────────────────────────────────────────────────────

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        """滚轮滚动：向上翻上一页，向下翻下一页。"""
        if event.angleDelta().y() > 0:
            self._prev_page()
        else:
            self._next_page()
        event.accept()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        """鼠标点击：左键翻页，右键弹菜单。"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._next_page()
            event.accept()
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def _show_context_menu(self, global_pos: QtCore.QPoint) -> None:
        """在光标位置弹出右键菜单。"""
        menu = QtWidgets.QMenu(self)
        act_show = menu.addAction("显示主界面")
        act_settings = menu.addAction("设置")
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_show.triggered.connect(self.show_main_requested.emit)
        act_settings.triggered.connect(self.settings_requested.emit)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.exec(global_pos)

    # ── 绘制 ────────────────────────────────────────────────────

    def _recalc_width(self) -> None:
        """根据全部股票各列的最大文本宽度估算固定窗口宽度。

        用全部股票（而非当前页）计算，保证轮播翻页时宽度恒定，
        避免行情条左右位置随内容变化而抖动。
        """
        col_widths = self._column_widths()
        total = sum(col_widths) + _COL_GAP * max(0, len(col_widths) - 1)
        new_width = max(120, int(total) + 2 * _EDGE_PAD)
        if new_width == self._bar_width:
            return
        self._bar_width = new_width
        if self._embedded:
            self._reposition()

    def _make_font(self) -> QtGui.QFont:
        """返回行情条统一使用的加粗字体。"""
        font = QtGui.QFont("Microsoft YaHei", 9)
        font.setBold(True)
        return font

    def _stock_columns(self, stock: StockRowData) -> list[str]:
        """按启用的列返回该股票各列文本（缺失填空串以保持列数一致）。"""
        cols = [stock.name or ""]
        if self._show_price:
            cols.append(stock.price or "")
        if self._show_change:
            cols.append(stock.change_str or "")
        if self._show_dark_flow:
            cols.append(self._format_dark_flow(stock))
        return cols

    def _column_widths(self) -> list[int]:
        """各列在所有股票中的最大文本宽度（像素）。"""
        n_cols = 1 + int(self._show_price) + int(self._show_change)
        n_cols += int(self._show_dark_flow)
        widths = [0] * n_cols
        metrics = QtGui.QFontMetrics(self._make_font())
        for stock in self._all_stocks:
            for i, text in enumerate(self._stock_columns(stock)):
                widths[i] = max(widths[i], metrics.horizontalAdvance(text))
        return widths

    @staticmethod
    def _format_dark_flow(stock: StockRowData) -> str:
        """暗盘净流入短文本；无有效数据时返回空串（不占位）。"""
        if not stock.dark_flow_valid:
            return ""
        v = stock.dark_flow_wan
        sign = "+" if v >= 0 else ""
        if abs(v) >= 10000:
            return f"{sign}{v / 10000:.1f}亿"
        elif abs(v) >= 1000:
            return f"{sign}{v:.0f}万"
        else:
            return f"{sign}{v:.1f}万"

    @staticmethod
    def _dark_flow_color(stock: StockRowData) -> QtGui.QColor:
        """暗盘列颜色：流入红、流出绿，连续≥3天用深色（与表格一致）。"""
        if not stock.dark_flow_valid:
            return QtGui.QColor("#888888")
        v = stock.dark_flow_wan
        days = stock.dark_flow_consecutive_days
        if v > 0:
            return QtGui.QColor("#CC0000") if days >= 3 else QtGui.QColor("#e74c3f")
        elif v < 0:
            return QtGui.QColor("#145a32") if days <= -3 else QtGui.QColor("#27ae60")
        return QtGui.QColor("#888888")

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        """绘制行情条：底色、大盘比例条与当前页（含翻页过渡动画）。"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._make_font())

        # 铺一层几乎不可见(alpha=1)的底色，使整个窗口区域都能接收鼠标点击。
        # 否则每像素 alpha=0 的透明区域会被 Windows 视为点击穿透，导致
        # 只有绘制了文字的像素才响应点击。
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 1))

        self._paint_market_summary(painter)

        stocks = self._current_page_stocks()
        if not stocks:
            painter.setPen(QtGui.QColor(COLORS.STOCK_NEUTRAL))
            painter.drawText(
                self.rect(),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "行情加载中…",
            )
            painter.end()
            return

        height = self.height()
        # 过渡中：旧页向 direction 方向滑出并淡出，新页从反方向滑入并淡入
        if self._anim_progress < 1.0 and self._prev_page_stocks:
            p = self._anim_progress
            offset = height * (1.0 - p)
            # 新页
            self._paint_page(painter, stocks, self._anim_direction * offset, p)
            # 旧页
            self._paint_page(
                painter,
                self._prev_page_stocks,
                -self._anim_direction * (height - offset),
                1.0 - p,
            )
        else:
            self._paint_page(painter, stocks, 0.0, 1.0)

        painter.end()

    def _paint_market_summary(self, painter: QtGui.QPainter) -> None:
        """在任务栏行情条顶部绘制全市场红绿盘比例条。"""
        if self._market_total_count <= 0:
            return

        strip_height = 2
        width = self.width()
        total_width = max(1, width)

        up_width = int(total_width * self._market_up_count / self._market_total_count)
        down_width = int(
            total_width * self._market_down_count / self._market_total_count
        )
        flat_width = total_width - up_width - down_width

        x_pos = 0
        if up_width > 0:
            gradient = QtGui.QLinearGradient(x_pos, 0, x_pos + up_width, 0)
            gradient.setColorAt(0, QtGui.QColor(255, 69, 0, 220))
            gradient.setColorAt(1, QtGui.QColor(231, 76, 60, 200))
            painter.fillRect(x_pos, 0, up_width, strip_height, gradient)
            x_pos += up_width

        if flat_width > 0:
            painter.fillRect(
                x_pos,
                0,
                flat_width,
                strip_height,
                QtGui.QColor(128, 128, 128, 120),
            )
            x_pos += flat_width

        if down_width > 0:
            gradient = QtGui.QLinearGradient(x_pos, 0, x_pos + down_width, 0)
            gradient.setColorAt(0, QtGui.QColor(39, 174, 96, 200))
            gradient.setColorAt(1, QtGui.QColor(30, 132, 73, 220))
            painter.fillRect(x_pos, 0, down_width, strip_height, gradient)

    def _paint_page(
        self,
        painter: QtGui.QPainter,
        stocks: list[StockRowData],
        y_offset: float,
        opacity: float,
    ) -> None:
        """绘制单页股票（上下堆叠），带垂直偏移与不透明度用于过渡动画。"""
        painter.setOpacity(max(0.0, min(1.0, opacity)))
        if not stocks:  # 除零防护（T12）：避免 len(stocks)=0 时除零
            return
        total_h = self.height()
        row_h = total_h / len(stocks)
        col_widths = self._column_widths()
        # 各列起始 x（名称左对齐，其余数字列右对齐）
        col_x = []
        x = float(_EDGE_PAD)
        for w in col_widths:
            col_x.append(x)
            x += w + _COL_GAP
        for i, stock in enumerate(stocks):
            base_color = QtGui.QColor(stock.color_hex or COLORS.STOCK_NEUTRAL)
            y = i * row_h + y_offset
            cols = self._stock_columns(stock)
            dark_idx = len(cols) - 1 if self._show_dark_flow else -1
            for j, text in enumerate(cols):
                align = (
                    QtCore.Qt.AlignmentFlag.AlignLeft
                    if j == 0
                    else QtCore.Qt.AlignmentFlag.AlignRight
                )
                if j == dark_idx:
                    painter.setPen(self._dark_flow_color(stock))
                else:
                    painter.setPen(base_color)
                rect = QtCore.QRectF(col_x[j], y, col_widths[j], row_h)
                painter.drawText(
                    rect,
                    QtCore.Qt.AlignmentFlag.AlignVCenter | align,
                    text,
                )
        painter.setOpacity(1.0)

    # ── Win32 嵌入 ──────────────────────────────────────────────

    def _find_taskbar(self) -> bool:
        """查找任务栏及通知区句柄。"""
        self._taskbar_hwnd = _user32.FindWindowW("Shell_TrayWnd", None)
        if not self._taskbar_hwnd:
            return False
        # 通知区（时间/托盘图标区域），行情条定位到它左侧
        self._notify_hwnd = _user32.FindWindowExW(
            self._taskbar_hwnd, 0, "TrayNotifyWnd", None
        )
        return True

    def _embed_into_taskbar(self) -> bool:
        """Win10 及更早：以 SetParent 将窗口嵌入任务栏子窗口。"""
        try:
            if not self._find_taskbar():
                self.embed_failed.emit("未找到任务栏窗口 Shell_TrayWnd")
                return False

            hwnd = int(self.winId())

            # 设为子窗口样式，去掉弹出窗口标志
            style = _GetWindowLong(hwnd, _GWL_STYLE)
            style = (style | _WS_CHILD) & ~_WS_POPUP
            _SetWindowLong(hwnd, _GWL_STYLE, style)

            ex_style = _GetWindowLong(hwnd, _GWL_EXSTYLE)
            ex_style |= _WS_EX_TOOLWINDOW
            _SetWindowLong(hwnd, _GWL_EXSTYLE, ex_style)

            # 关键：把窗口设置为任务栏的子窗口
            ctypes.set_last_error(0)
            result = _user32.SetParent(hwnd, self._taskbar_hwnd)
            # SetParent 返回原父句柄，顶层窗口原父为桌面(NULL)时成功也返回 0，
            # 因此以 GetLastError 判断是否真失败
            if not result:
                err = ctypes.get_last_error()
                if err:
                    self.embed_failed.emit(f"SetParent 失败 (err={err})")
                    return False

            self._embedded = True
            self._reposition()
            app_logger.info("[TaskbarQuoteBar] 已嵌入任务栏")
            return True
        except Exception as e:
            app_logger.warning(f"[TaskbarQuoteBar] 嵌入任务栏异常: {e}")
            self.embed_failed.emit(str(e))
            return False

    def _detach_from_taskbar(self) -> None:
        """从任务栏分离（移除子窗口样式/父句柄），仅 Windows 嵌入态需要。"""
        if not (_IS_WINDOWS and self._embedded):
            return
        try:
            if self._overlay_mode:
                # 悬浮模式无 SetParent，直接标记分离
                self._embedded = False
                return
            hwnd = int(self.winId())
            _user32.SetParent(hwnd, 0)
            style = _GetWindowLong(hwnd, _GWL_STYLE)
            style = (style & ~_WS_CHILD) | _WS_POPUP
            _SetWindowLong(hwnd, _GWL_STYLE, style)
        except Exception as e:
            app_logger.warning(f"[TaskbarQuoteBar] 分离任务栏异常: {e}")
        finally:
            self._embedded = False

    def _get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        """返回窗口的 (left, top, right, bottom) 物理像素矩形。"""
        rect = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    def _disable_dwm_round_corners(self, hwnd: int) -> None:
        """关闭 Win11 DWM 为窗口自动添加的圆角，消除任务栏条的圆角边框。"""
        if not _IS_WINDOWS or _dwmapi is None:
            return
        try:
            pref = ctypes.c_int(_DWMWCP_DONOTROUND)
            _dwmapi.DwmSetWindowAttribute(
                hwnd,
                _DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(pref),
                ctypes.sizeof(pref),
            )
        except Exception as e:
            app_logger.debug(f"[TaskbarQuoteBar] 关闭圆角失败: {e}")

    def _reposition(self) -> None:
        """将行情条定位到通知区左侧、任务栏内垂直居中。

        嵌入后窗口是任务栏的 WS_CHILD，几何完全交给 Win32 SetWindowPos
        （物理像素，坐标相对父窗口）。不调用 Qt 的 resize/move，避免 Qt
        以过时的屏幕坐标覆盖，产生 setGeometry 警告并把窗口移出屏幕。

        悬浮模式(Win11)下窗口是顶层窗口，坐标为屏幕绝对坐标，并每次抬到最顶层。
        """
        if not (_IS_WINDOWS and self._embedded and self._taskbar_hwnd):
            return
        try:
            tb_l, tb_t, tb_r, tb_b = self._get_window_rect(self._taskbar_hwnd)
            tb_w = tb_r - tb_l
            tb_h = tb_b - tb_t

            dpr = self.devicePixelRatioF() or 1.0
            # _bar_width 来自字体度量（逻辑像素），转成物理像素用于原生定位
            bar_w_phys = int(round(self._bar_width * dpr))
            bar_h_phys = max(int(24 * dpr), tb_h - 4)

            # 通知区左边界，定位行情条到其左侧
            if self._notify_hwnd:
                n_l, _n_t, _n_r, _n_b = self._get_window_rect(self._notify_hwnd)
            else:
                n_l = tb_r  # 兜底：贴任务栏右侧

            if self._overlay_mode:
                # 顶层窗口用屏幕绝对坐标
                x = n_l - bar_w_phys - int(6 * dpr)
                if x < tb_l:
                    x = tb_l
                y = tb_t + (tb_h - bar_h_phys) // 2
                if y < tb_t:
                    y = tb_t
                hwnd = int(self.winId())
                new_rect = (int(x), int(y), int(bar_w_phys), int(bar_h_phys))
                if new_rect == self._last_rect:
                    return  # 几何未变：跳过 SetWindowPos，避免高频打扰 DWM 合成
                _user32.SetWindowPos(
                    hwnd,
                    _HWND_TOPMOST,
                    new_rect[0],
                    new_rect[1],
                    new_rect[2],
                    new_rect[3],
                    _SWP_NOACTIVATE | _SWP_SHOWWINDOW,
                )
                self._last_rect = new_rect
                return

            # 嵌入模式：坐标相对任务栏父窗口
            notify_left = n_l - tb_l if self._notify_hwnd else tb_w
            x = notify_left - bar_w_phys - int(6 * dpr)
            if x < 0:
                x = 0
            y = (tb_h - bar_h_phys) // 2
            if y < 0:
                y = 0

            hwnd = int(self.winId())
            new_rect = (int(x), int(y), int(bar_w_phys), int(bar_h_phys))
            if new_rect == self._last_rect:
                return  # 几何未变：跳过 SetWindowPos
            _user32.SetWindowPos(
                hwnd,
                0,
                new_rect[0],
                new_rect[1],
                new_rect[2],
                new_rect[3],
                _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_SHOWWINDOW,
            )
            self._last_rect = new_rect
        except Exception as e:
            app_logger.debug(f"[TaskbarQuoteBar] 重定位异常: {e}")

    @staticmethod
    def _rect_intersects(
        a: tuple[int, int, int, int], b: tuple[int, int, int, int]
    ) -> bool:
        """判断两个 ``(left, top, right, bottom)`` 矩形是否真实相交。"""
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    @staticmethod
    def _rect_center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
        """返回 ``(left, top, right, bottom)`` 矩形的中心点坐标。

        历史缺陷（v4.8.3 回归根因之一）：调用处把 ``GetWindowRect`` 返回的
        四个边界误按 ``(x, y, w, h)`` 解包，中心点被算到屏幕之外，
        ``WindowFromPoint`` 恒返回 NULL，命中测试完全失效。
        """
        left, top, right, bottom = rect
        return (left + right) // 2, (top + bottom) // 2

    def _is_covered(self) -> bool:
        """检测行情条当前是否真的被其它**可见**窗口遮挡（仅查询，无副作用）。

        两个视角同时判断：
        1. z-order：从 topmost 带顶走到自己，若途中存在**可见且与行情条矩形
           相交**的窗口 → 被遮挡。带顶常年驻留输入法/Shell 的隐藏窗口
           （IME、ForegroundStaging 等）必须跳过——否则"被遮挡"恒为真，
           冷却机制因无遮挡期可复位而彻底失效（v4.8.3 回归根因之一）；
        2. 命中测试：行情条中心点 ``WindowFromPoint`` 命中的不是自己（也不是
           自己的子窗口）且该窗口可见 → 有可见窗口盖在上面。

        两者都干净时说明未被遮挡，置顶维持应完全静默。
        """
        try:
            hwnd = int(self.winId())
            my_rect = self._get_window_rect(hwnd)
            # 1. z-order 检查（GW_HWNDFIRST=0 取带顶，GW_HWNDNEXT=2 下行遍历）
            cur = _user32.GetWindow(hwnd, 0)
            steps = 0
            while cur and cur != hwnd and steps < _MAX_Z_PROBE:
                if _user32.IsWindowVisible(cur) and self._rect_intersects(
                    self._get_window_rect(cur), my_rect
                ):
                    return True
                cur = _user32.GetWindow(cur, 2)
                steps += 1
            # 2. 命中测试检查（覆盖层不是独立窗口时 z-order 查不出来）
            cx, cy = self._rect_center(my_rect)
            hit = _user32.WindowFromPoint(wintypes.POINT(cx, cy))
            if (
                hit
                and hit != hwnd
                and not _user32.IsChild(hwnd, hit)
                and _user32.IsWindowVisible(hit)
            ):
                return True
            return False
        except Exception:
            # 查询失败时保持旧行为（重抢一次），宁可多一次也不让行情条消失
            return True

    def _keep_on_top(self) -> None:
        """仅悬浮模式：被真正可见的窗口遮挡时按冷却重抢 z-order。

        点击开始菜单/搜索等沉浸式 UI 会盖住本窗口，关闭后 Windows 不会主动把
        本窗口重新抬起；Win11 任务栏重建 Z 序时也可能把本窗口压到下面，行情条
        整个被任务栏盖住、在桌面上"消失"（全屏时任务栏隐藏、遮挡源消失，反而
        能显示）。

        演进：
        - 最初：每 300ms 无条件 ``NOTOPMOST→TOPMOST`` 翻转 → 持续打断 DWM
          合成，整个桌面一闪一闪；
        - v4.8.3：改为"遮挡检测 + 同一遮挡期只重抢一次"，但检测把带顶隐藏
          窗口误判为遮挡、命中点又算到屏幕外，标志永不清零 → 任务栏压住后
          **再无任何抬升**；
        - 现在：检测只认**可见且与行情条相交**的窗口；未遮挡完全静默；被遮挡
          时按 ``_REASSERT_COOLDOWN_SEC`` 冷却重抢——既消除高频盲抢闪烁，又
          保证遮挡源持续存在时最迟约 1 秒恢复一次显示。
        """
        if not (_IS_WINDOWS and self._embedded and self._overlay_mode):
            return
        if QtWidgets.QApplication.activePopupWidget():
            return  # 右键菜单弹出中：不与其争抢 z-order，避免菜单被压住
        if not self._is_covered():
            return  # 未被遮挡：不碰 z-order
        now = time.monotonic()
        if now - self._last_reassert_ts < _REASSERT_COOLDOWN_SEC:
            return  # 冷却中：避免退化回每 300ms 高频盲抢
        try:
            hwnd = int(self.winId())
            flags = _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE
            # 已是 topmost 时 HWND_TOPMOST 是 no-op，必须 NOTOPMOST→TOPMOST
            # 强制切换才能把窗口重新插入 topmost band 顶部并重绘。
            _user32.SetWindowPos(hwnd, _HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            _user32.SetWindowPos(
                hwnd, _HWND_TOPMOST, 0, 0, 0, 0, flags | _SWP_SHOWWINDOW
            )
            self._last_reassert_ts = now
        except Exception as e:
            app_logger.debug(f"[TaskbarQuoteBar] 置顶维持异常: {e}")

    def _maintain_embed(self) -> None:
        """周期性检查嵌入状态：任务栏重建则重新嵌入，否则维持位置。"""
        if not _IS_WINDOWS:
            return
        # 任务栏句柄失效（explorer 重启）→ 重新嵌入
        if not self._taskbar_hwnd or not _user32.IsWindow(self._taskbar_hwnd):
            self._embedded = False
            if self._overlay_mode:
                if self._start_overlay():
                    self.embed_succeeded.emit()
            elif self._embed_into_taskbar():
                self.embed_succeeded.emit()
            return
        self._reposition()
