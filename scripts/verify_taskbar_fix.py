"""实测修复效果：行情条被可见窗口盖住后能否在 ~1s 内自行恢复显示。

流程：
1. 启动修复后的 TaskbarQuoteBar（Win11 悬浮模式）；
2. 记录其 hwnd 与中心点，确认初始 WindowFromPoint 命中自己；
3. 造一个 TOPMOST 测试窗口精确盖住行情条中心 → 模拟"被任务栏/其它窗口遮挡"；
4. 以 100ms 采样，等待行情条把 z-order 抢回（WindowFromPoint 重新命中自己）；
5. 汇报恢复耗时；超时 4 秒判失败；最后清理现场。
"""

import ctypes
import inspect
import sys
import time
from ctypes import wintypes
from pathlib import Path

# 以 `python scripts\xxx.py` 方式运行时 sys.path[0] 是 scripts/，仓库根不在
# 路径上，会误 import 到 venv site-packages 里的旧版快照——强制指回仓库源码
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt6 import QtCore, QtWidgets

from stock_monitor.ui.widgets.taskbar_quote_bar import TaskbarQuoteBar

print(f"模块来源: {inspect.getfile(TaskbarQuoteBar)}")
if not inspect.getfile(TaskbarQuoteBar).startswith(_REPO_ROOT):
    print("FAIL: import 到的不是仓库源码，验证结论不可信")
    sys.exit(4)

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

HWND_TOPMOST = -1
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10


def rect_of(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def center_of(rect):
    left, top, right, bottom = rect
    return (left + right) // 2, (top + bottom) // 2


def hits_bar(bar_hwnd, pt):
    hit = user32.WindowFromPoint(wintypes.POINT(*pt))
    return hit == bar_hwnd


def z_distance(bar_hwnd, other_hwnd):
    """从 topmost 带顶走到 bar 需要的步数（越小越靠上）。"""
    cur = user32.GetWindow(bar_hwnd, 0)
    steps = 0
    while cur and steps < 300:
        if cur == bar_hwnd:
            return steps, "bar_first" if steps == 0 else "below_others"
        cur = user32.GetWindow(cur, 2)
        steps += 1
    return -1, "not_found"


def main():
    app = QtWidgets.QApplication(sys.argv)
    bar = TaskbarQuoteBar()
    bar.configure(per_page=3, carousel_interval_sec=5, show_dark_flow=True)
    ok = bar.start()
    if not ok:
        print("FAIL: 行情条 start() 返回 False")
        return 1
    # 等首帧定位完成
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)
    bar_hwnd = int(bar.winId())
    bar_rect = rect_of(bar_hwnd)
    center = center_of(bar_rect)
    print(f"bar hwnd={hex(bar_hwnd)} rect={bar_rect} center={center}")
    print(
        f"初始命中自己: {hits_bar(bar_hwnd, center)}  z: {z_distance(bar_hwnd, bar_hwnd)}"
    )

    # ── 造遮挡窗口：精确盖住行情条，TOPMOST ──
    cover = QtWidgets.QWidget(None, QtCore.Qt.WindowType.WindowStaysOnTopHint)
    cover.setStyleSheet("background-color: rgba(255,0,0,200);")
    cover.resize(100, 50)  # 占位；真实位置用 Win32 物理坐标设置（Qt 逻辑坐标在
    cover.show()  # 150% DPI 下会偏移出屏，导致遮挡不生效）
    app.processEvents()
    cover_hwnd = int(cover.winId())
    bw, bh = bar_rect[2] - bar_rect[0], bar_rect[3] - bar_rect[1]
    user32.SetWindowPos(cover_hwnd, HWND_TOPMOST, bar_rect[0], bar_rect[1], bw, bh, 0)
    time.sleep(0.2)
    covered_hit = not hits_bar(bar_hwnd, center)
    covered_api = bar._is_covered()
    print(f"\n遮挡窗口 {hex(cover_hwnd)} 已定位到行情条物理矩形 {bar_rect}")
    print(f"  WindowFromPoint 不再命中自己: {covered_hit}")
    print(f"  bar._is_covered() = {covered_api} (期望 True)")
    if not (covered_hit and covered_api):
        print("FAIL: 遮挡未生效或 _is_covered 误判为未遮挡，测试无效")
        bar.stop()
        cover.close()
        return 3

    # ── 采样等待恢复（修复后 _keep_on_top 300ms 周期 + 0.5s 冷却 → 预期 ≤1.2s）──
    t0 = time.monotonic()
    recovered_at = None
    while time.monotonic() - t0 < 4.0:
        app.processEvents()
        if hits_bar(bar_hwnd, center):
            recovered_at = time.monotonic() - t0
            break
        time.sleep(0.1)

    print(f"\n恢复耗时: {f'{recovered_at:.2f}s' if recovered_at else '4s 内未恢复'}")
    if hits_bar(bar_hwnd, center):
        d = z_distance(bar_hwnd, cover_hwnd)
        print(
            f"恢复后 z-order: 距带顶 {d[0]} 步 (cover 距带顶 "
            f"{z_distance(cover_hwnd, cover_hwnd)[0]} 步)"
        )

    # ── 静默性检查：无遮挡时 2 秒内不应发生 z-order 抢占 ──
    cover.close()
    app.processEvents()
    time.sleep(0.6)  # 等一次 _keep_on_top 周期消化残余状态
    cleared = not bar._is_covered()
    print(
        f"遮挡移除后 _is_covered() = {bar._is_covered()} (期望 False, 正确复位={cleared})"
    )
    d1 = z_distance(bar_hwnd, bar_hwnd)[0]
    t0 = time.monotonic()
    while time.monotonic() - t0 < 2.0:
        app.processEvents()
        time.sleep(0.1)
    d2 = z_distance(bar_hwnd, bar_hwnd)[0]
    silent = d1 == d2
    print(
        f"无遮挡 2s 静默检查: 距带顶 {d1} → {d2} ({'静默(未盲抢)' if silent else 'z-order 有变动(可能被外部窗口穿插)'})"
    )

    bar.stop()
    del bar
    app.processEvents()

    if recovered_at is not None:
        print(
            f"\nPASS: 行情条被盖住后 {recovered_at:.2f}s 恢复显示"
            + ("；遮挡判定复位正常" if cleared else "；但遮挡判定未复位(警告)")
        )
        return 0
    print("\nFAIL: 行情条被盖住后未恢复")
    return 2


if __name__ == "__main__":
    sys.exit(main())
