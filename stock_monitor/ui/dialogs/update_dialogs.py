"""
现代化更新UI组件
提供美观的更新通知和进度显示
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

# 导入UI常量


class ModernProgressDialog(QDialog):
    """现代化进度对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在更新")
        self.setMinimumSize(400, 200)
        self.resize(500, 250)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint)

        # 设置样式
        self.setObjectName("ModernProgressDialog")

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 标题
        title = QLabel("🚀 正在更新应用")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 状态标签
        self.status_label = QLabel("正在下载更新包...")
        self.status_label.setStyleSheet("font-size: 14px; color: #aaa;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(30)
        layout.addWidget(self.progress_bar)

        # 详细信息
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("font-size: 12px; color: #666;")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_label)

        layout.addStretch()
        self.setLayout(layout)

    def update_status(self, status, progress, detail=""):
        """更新状态"""
        self.status_label.setText(status)
        self.progress_bar.setValue(progress)
        self.detail_label.setText(detail)


class UpdateNotificationDialog(QDialog):
    """更新通知对话框"""

    def __init__(self, version_info, current_version, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发现新版本")

        # 使用最小/最大尺寸而不是固定尺寸,允许窗口自适应但有合理限制
        self.setMinimumSize(600, 400)
        self.setMaximumSize(800, 700)
        self.resize(600, 500)  # 默认尺寸

        # 美化样式
        self.setObjectName("UpdateNotificationDialog")

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 图标和标题
        header_layout = QHBoxLayout()
        icon_label = QLabel("🎉")
        icon_label.setStyleSheet("font-size: 48px;")
        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title = QLabel(f"发现新版本 v{version_info.get('version', 'Unknown')}")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        subtitle = QLabel(f"当前版本: v{current_version}")
        subtitle.setStyleSheet("font-size: 12px; color: #888;")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 更新日志标签
        changelog_label = QLabel("更新内容：")
        changelog_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(changelog_label)

        # 更新日志 - 使用固定高度并允许滚动
        changelog = QTextEdit()
        changelog.setReadOnly(True)
        changelog.setPlainText(version_info.get("changelog", "暂无更新日志"))
        # 设置最小和最大高度,确保内容可滚动
        changelog.setMinimumHeight(150)
        changelog.setMaximumHeight(350)
        layout.addWidget(changelog, 1)  # stretch factor = 1,允许扩展但受限于最大高度

        # 按钮布局 - 固定在底部
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("稍后提醒")
        cancel_button.setObjectName("cancelButton")
        cancel_button.clicked.connect(self.reject)

        update_button = QPushButton("立即更新")
        update_button.clicked.connect(self.accept)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(update_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)
