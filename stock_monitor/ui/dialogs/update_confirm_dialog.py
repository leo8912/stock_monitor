"""更新确认对话框：可滚动更新说明，保证底部按钮始终可见。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)


class UpdateConfirmDialog(QDialog):
    """发现新版本时的确认框。

    用可滚动文本区展示完整更新说明，窗口尺寸限制在可用屏幕内，
    底部「立即更新 / 稍后」按钮始终可见可点。
    """

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        release_body: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("发现新版本")
        self.setModal(True)
        self.setObjectName("UpdateConfirmDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        info = QLabel(
            f"当前版本: {current_version}\n最新版本: {latest_version}\n\n是否现在更新？"
        )
        info.setWordWrap(True)
        root.addWidget(info)

        notes_label = QLabel("更新说明:")
        notes_label.setStyleSheet("color: #aaaaaa; font-weight: bold; border: none;")
        root.addWidget(notes_label)

        self.notes_edit = QPlainTextEdit(self)
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setPlainText(release_body or "暂无更新说明")
        # 不设死高度：由布局 + 窗口几何约束
        self.notes_edit.setMinimumHeight(160)
        self.notes_edit.setMaximumHeight(360)
        self.notes_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.notes_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.notes_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        root.addWidget(self.notes_edit, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        self.later_btn = QPushButton("稍后")
        self.later_btn.setObjectName("cancelButton")
        self.later_btn.setFixedHeight(34)
        self.later_btn.setMinimumWidth(96)
        self.update_btn = QPushButton("立即更新")
        self.update_btn.setObjectName("PrimaryButton")
        self.update_btn.setFixedHeight(34)
        self.update_btn.setMinimumWidth(96)
        self.update_btn.setDefault(True)
        btn_row.addWidget(self.later_btn)
        btn_row.addWidget(self.update_btn)
        root.addLayout(btn_row)

        self.later_btn.clicked.connect(self.reject)
        self.update_btn.clicked.connect(self.accept)

        # 轻量样式：避免过重 QSS 在离屏/部分环境下触发原生问题
        self.setStyleSheet(
            """
            QDialog#UpdateConfirmDialog { background-color: #1e1e1e; color: #e6eaf3; }
            QLabel { color: #e6eaf3; border: none; }
            QPlainTextEdit {
                background-color: #121212; color: #cccccc;
                border: 1px solid #333333; padding: 6px;
            }
            """
        )

        self._fit_to_screen()
        self.update_btn.setFocus()

    def _fit_to_screen(self) -> None:
        """按可用屏幕约束窗口，避免过大导致按钮不可见。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(560, 480)
            return
        geo = screen.availableGeometry()
        width = min(620, max(420, int(geo.width() * 0.45)))
        height = min(560, max(400, int(geo.height() * 0.72)))
        # 至少容下说明区 + 按钮行
        height = max(height, 400)
        width = max(width, 420)
        self.resize(width, height)
        max_h = max(400, geo.height() - 48)
        max_w = max(420, geo.width() - 48)
        if self.height() > max_h or self.width() > max_w:
            self.resize(min(self.width(), max_w), min(self.height(), max_h))
        x = geo.left() + max(0, (geo.width() - self.width()) // 2)
        y = geo.top() + max(0, (geo.height() - self.height()) // 2)
        self.move(x, y)


def show_update_confirm(
    parent,
    current_version: str,
    latest_version: str,
    release_body: str,
) -> bool:
    """展示更新确认框，用户点击「立即更新」返回 True。"""
    dlg = UpdateConfirmDialog(
        current_version, latest_version, release_body, parent=parent
    )
    return dlg.exec() == QDialog.DialogCode.Accepted
