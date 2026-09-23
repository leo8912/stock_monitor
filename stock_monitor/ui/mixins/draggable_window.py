from PyQt6 import QtCore, QtGui, QtWidgets

# Windows API 结构体定义（模块级别，避免在热路径中重复创建）
try:
    import ctypes
    from ctypes import wintypes

    class _WINDOWPOS(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("hwndInsertAfter", wintypes.HWND),
            ("x", ctypes.c_int),
            ("y", ctypes.c_int),
            ("cx", ctypes.c_int),
            ("cy", ctypes.c_int),
            ("flags", ctypes.c_uint),
        ]

    # GetWindow(GW_HWNDFIRST)：查询自己是否处于同层 Z 序最顶端，
    # 供 _ensure_topmost 判断是否真的需要重抢置顶（纯查询，无副作用）
    _user32 = ctypes.windll.user32
    _user32.GetWindow.restype = wintypes.HWND
    _user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
except Exception:
    _WINDOWPOS = None  # 非 Windows 平台
    _user32 = None


class DraggableWindowMixin:
    """
    Mixin class to provide draggable window functionality and window control.
    Expects the host class to be a QWidget or subclass.
    """

    def __init__(self, *args, **kwargs):
        # We don't call super().__init__ here because we don't know the MRO
        # The host class should handle its own initialization
        self.drag_position: QtCore.QPoint | None = None

    def _apply_windows_11_corner_fix(self):
        """通过 Windows API 强制禁用 Windows 11 的窗口圆角（支持重试）"""
        try:
            import ctypes

            # Windows 11 DWM API 常量
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_DONOTROUND = 1  # 1: 不圆角

            hwnd = int(self.winId())
            if hwnd == 0:
                return False

            # 调用 DwmSetWindowAttribute 禁用圆角
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)),
                ctypes.sizeof(ctypes.c_int),
            )
            return result == 0  # S_OK
        except Exception:
            return False

    def setup_draggable_window(self):
        """Initialize draggable window properties"""
        if isinstance(self, QtWidgets.QWidget):
            # 1. 核心标志位：绕过窗口管理器是防止系统自动加圆角的关键
            self.setWindowFlags(
                QtCore.Qt.WindowType.WindowStaysOnTopHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.BypassWindowManagerHint
            )

            # 2. 必须在 setWindowFlags 之后立即设置，否则可能失效
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)

            # 3. 预先设置对象名和直角样式，防止初始闪烁
            self.setObjectName("MainWindow")
            self.setStyleSheet("""
                #MainWindow {
                    background-color: transparent;
                    border: none;
                    border-radius: 0px;
                }
            """)

            # 4. 【关键修复】立即尝试禁用圆角
            self._apply_windows_11_corner_fix()

            # 5. 【双重保险】延迟 50ms 再次执行，确保在 DWM 完成初始渲染后强制覆盖
            # 这能解决本地源码运行时偶尔出现的“先圆后直”现象
            QtCore.QTimer.singleShot(50, self._apply_windows_11_corner_fix)

            # 使用 Windows API 隐藏任务栏按钮（替代 Qt 的 Tool 标志，避免其副作用）
            self._hide_from_taskbar()

            # Install event filter on self and children
            self.install_event_filters(self)

    def install_event_filters(self, widget):
        """Recursively install event filters on widget and its children"""
        if isinstance(widget, QtWidgets.QWidget):
            widget.installEventFilter(self)
            for child in widget.findChildren(QtWidgets.QWidget):
                self.install_event_filters(child)

    def eventFilter(self, obj, event):
        """Handle mouse events for dragging and window control"""
        if event is None:
            return False

        if event.type() == QtCore.QEvent.Type.MouseButtonDblClick:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                if isinstance(self, QtWidgets.QWidget):
                    self.hide()
                    event.accept()
                    return True

        elif event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                if isinstance(self, QtWidgets.QWidget):
                    cursor_pos = QtGui.QCursor.pos()
                    frame_top_left = self.frameGeometry().topLeft()
                    self.drag_position = QtCore.QPoint(
                        cursor_pos.x() - frame_top_left.x(),
                        cursor_pos.y() - frame_top_left.y(),
                    )
                    self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
                    event.accept()
                    return True
            elif event.button() == QtCore.Qt.MouseButton.RightButton:
                # Let the host class handle context menu if it has one
                if hasattr(self, "handle_context_menu"):
                    if self.handle_context_menu(event):
                        return True
                elif hasattr(self, "menu") and hasattr(self.menu, "popup"):
                    if isinstance(self, QtWidgets.QWidget):
                        click_pos = self.mapToGlobal(event.position().toPoint())
                        self.menu.popup(click_pos)
                        event.accept()
                        return True

        elif event.type() == QtCore.QEvent.Type.MouseMove:
            if (
                event.buttons() == QtCore.Qt.MouseButton.LeftButton
                and self.drag_position is not None
            ):
                if isinstance(self, QtWidgets.QWidget):
                    cursor_pos = QtGui.QCursor.pos()
                    self.move(
                        cursor_pos.x() - self.drag_position.x(),
                        cursor_pos.y() - self.drag_position.y(),
                    )
                    event.accept()
                    return True

        elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            self.drag_position = None
            if isinstance(self, QtWidgets.QWidget):
                self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
                # Save position if the host class has such method
                if hasattr(self, "save_position"):
                    self.save_position()
                elif hasattr(self, "isVisible") and self.isVisible():
                    # Fallback simple save if needed? Or just ignore.
                    pass
                event.accept()
                return True

        # Forward to super if possible, but pure Mixin can't super() easily without cooperative inheritance
        # Here we return False to indicate event not filtered if we didn't handle it
        return False

    def showEvent(self, event):
        """窗口显示时确保置顶标志有效"""
        if isinstance(self, QtWidgets.QWidget):
            # 检查窗口标志是否仍包含置顶
            flags = self.windowFlags()
            if not (flags & QtCore.Qt.WindowType.WindowStaysOnTopHint):
                # 标志丢失，重新设置
                self.setWindowFlags(flags | QtCore.Qt.WindowType.WindowStaysOnTopHint)
            # 使用 Windows API 兜底确保置顶
            self._ensure_topmost()
            # 确保任务栏按钮保持隐藏
            self._hide_from_taskbar()

    def changeEvent(self, event):
        """方案二：监听窗口激活状态变化，失去焦点时重新置顶"""
        if isinstance(self, QtWidgets.QWidget):
            if event.type() == QtCore.QEvent.Type.ActivationChange:
                if not self.isActiveWindow():
                    # 窗口失去焦点，延迟 100ms 重新置顶（避免干扰用户正在进行的操作）
                    QtCore.QTimer.singleShot(100, self._ensure_topmost)

    def _ensure_topmost(self):
        """使用 Windows 原生 API 确保窗口置顶（兜底方案）。

        仅在“置顶位丢失”或“被同层其它置顶窗口压住”时才调用 SetWindowPos，
        且不再携带 ``SWP_FRAMECHANGED``——它会强制重建无边框半透明窗的整个
        帧并整帧重绘，在高频调用（失焦/刷新 resize）下是桌面闪烁的来源之一。
        已处于同层 Z 序顶端时直接返回，不做任何原生调用。
        """
        if isinstance(self, QtWidgets.QWidget):
            # 菜单保护：如果当前有活跃的弹出窗口（如右键菜单），跳过置顶纠正，避免干扰交互
            if QtWidgets.QApplication.activePopupWidget():
                return

            try:
                import ctypes

                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                GWL_EXSTYLE = -20
                WS_EX_TOPMOST = 0x00000008

                hwnd = int(self.winId())

                # 1. 检查当前样式，如果置顶位丢失，则强行补全并重新应用
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if not (style & WS_EX_TOPMOST):
                    ctypes.windll.user32.SetWindowLongW(
                        hwnd, GWL_EXSTYLE, style | WS_EX_TOPMOST
                    )
                    ctypes.windll.user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                    )
                    return

                # 2. 已是 topmost：先做廉价 z-order 查询，处于同层最顶端就
                #    直接返回。高频的无效 SetWindowPos 会持续打扰 DWM 桌面
                #    合成，造成“桌面一直一闪一闪”（独全屏游戏绕过 DWM 所以
                #    看不出）。仅当确实被压在下面时才重新声明置顶。
                if _user32 is not None and _user32.GetWindow(hwnd, 0) == hwnd:
                    return  # 同层 Z 序最高：无需任何操作

                # 被压在下面：重新应用位置（不激活窗口，仅强制置顶）。
                # 注意：不再带 SWP_FRAMECHANGED，避免整帧重建导致闪烁。
                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
            except Exception:
                pass  # 非 Windows 平台静默忽略

    def nativeEvent(self, event_type, message):
        """处理 Windows 原生事件，在消息循环级别锁定置顶状态"""
        if event_type == b"windows_generic_msg" and _WINDOWPOS is not None:
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(message.__int__())

            # 消息拦截：0x0046 = WM_WINDOWPOSCHANGING
            # 当窗口层级试图改变时（例如点击其他窗口导致焦点移动），将其强制拉回到 TOPMOST
            if msg.message == 0x0046:
                # hwndInsertAfter = HWND_TOPMOST (-1)
                pos = _WINDOWPOS.from_address(msg.lParam)
                pos.hwndInsertAfter = -1
                # 这里不需要执行额外的 SetWindowPos，系统会根据修改后的 pos 继续动作

            # 消息拦截：0x0006 = WM_ACTIVATE
            # 监听激活态，在失去焦点时立刻重新声明主权
            elif msg.message == 0x0006:
                # LOWORD(wParam) == WA_INACTIVE (0)
                if (msg.wParam & 0xFFFF) == 0:
                    # 延迟一小会儿执行，让系统完成正常的焦点切换链
                    QtCore.QTimer.singleShot(10, self._ensure_topmost)

            # 消息拦截：0x001C = WM_ACTIVATEAPP
            elif msg.message == 0x001C:
                QtCore.QTimer.singleShot(20, self._ensure_topmost)

        return False, 0

    def _hide_from_taskbar(self):
        """使用 Windows API 隐藏任务栏按钮（不使用 Qt Tool 标志，避免其副作用）"""
        try:
            import ctypes

            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TOPMOST = 0x00000008
            hwnd = int(self.winId())
            # 获取当前扩展样式
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # 核心修正：添加隐藏标志时，必须保留置顶标志位
            new_style = style | WS_EX_TOOLWINDOW
            if style & WS_EX_TOPMOST:
                new_style |= WS_EX_TOPMOST

            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            # 通知系统样式已更改
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        except Exception:
            pass  # 非 Windows 平台静默忽略

    # Standard widget event overrides
    def mousePressEvent(self, event):
        # We rely on eventFilter mostly, but if this is called directly:
        pass

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if isinstance(self, QtWidgets.QWidget):
                self.hide()
                event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() == QtCore.Qt.MouseButton.LeftButton
            and self.drag_position is not None
        ):
            if isinstance(self, QtWidgets.QWidget):
                self.move(event.globalPosition().toPoint() - self.drag_position)
                event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        if isinstance(self, QtWidgets.QWidget):
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            if isinstance(self, QtWidgets.QWidget) and self.isVisible():
                if hasattr(self, "save_position"):
                    self.save_position()

    def moveEvent(self, event):
        """移动位置。不再在此重抢置顶：移动不改变 z-order，而旧实现里的
        SetWindowPos(FRAMECHANGED) 会触发半透明窗整帧重绘（桌面闪烁源）。"""
        if hasattr(super(), "moveEvent"):
            super().moveEvent(event)

    def resizeEvent(self, event):
        """大小改变。不再在此重抢置顶：行情刷新每轮都会 resize，旧实现的
        高频 SetWindowPos(FRAMECHANGED) 是桌面闪烁的主因之一。"""
        if hasattr(super(), "resizeEvent"):
            super().resizeEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "save_position"):
            self.save_position()
        if isinstance(self, QtWidgets.QWidget):
            self.hide()
        event.ignore()

    def move_to_bottom_right(self):
        """Move window to bottom right corner of the screen"""
        if isinstance(self, QtWidgets.QWidget):
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            self.move(
                screen.right() - self.width() - 20, screen.bottom() - self.height() - 40
            )
