from PyQt6 import QtCore, QtGui, QtWidgets
from typing import Optional

class DraggableWindowMixin:
    """
    Mixin class to provide draggable window functionality and window control.
    Expects the host class to be a QWidget or subclass.
    """
    
    def __init__(self, *args, **kwargs):
        # We don't call super().__init__ here because we don't know the MRO
        # The host class should handle its own initialization
        self.drag_position: Optional[QtCore.QPoint] = None

    def setup_draggable_window(self):
        """Initialize draggable window properties"""
        if isinstance(self, QtWidgets.QWidget):
            self.setWindowFlags(
                QtCore.Qt.WindowType.WindowStaysOnTopHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.Tool
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
            
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
                if hasattr(self, 'handle_context_menu'):
                    if self.handle_context_menu(event):
                        return True
                elif hasattr(self, 'menu') and hasattr(self.menu, 'popup'):
                    if isinstance(self, QtWidgets.QWidget):
                        click_pos = self.mapToGlobal(event.pos())
                        self.menu.popup(click_pos)
                        event.accept()
                        return True
                        
        elif event.type() == QtCore.QEvent.Type.MouseMove:
            if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:
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
                if hasattr(self, 'save_position'):
                    self.save_position()
                elif hasattr(self, 'isVisible') and self.isVisible():
                     # Fallback simple save if needed? Or just ignore.
                     pass
                event.accept()
                return True
                
        # Forward to super if possible, but pure Mixin can't super() easily without cooperative inheritance
        # Here we return False to indicate event not filtered if we didn't handle it
        return False
        
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
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:
            if isinstance(self, QtWidgets.QWidget):
                self.move(event.globalPos() - self.drag_position)
                event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        if isinstance(self, QtWidgets.QWidget):
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            if isinstance(self, QtWidgets.QWidget) and self.isVisible():
                if hasattr(self, 'save_position'):
                    self.save_position()

    def closeEvent(self, event):
        if hasattr(self, 'save_position'):
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
