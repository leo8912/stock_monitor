"""
现代化更新UI组件
提供美观的更新通知和进度显示
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QProgressBar, QTextEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class ModernProgressDialog(QDialog):
    """现代化进度对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在更新")
        self.setFixedSize(500, 250)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d2d2d, stop:1 #1e1e1e);
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-family: "Microsoft YaHei";
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 8px;
                text-align: center;
                background-color: #3d3d3d;
                color: white;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0078d4, stop:1 #00a8ff);
                border-radius: 6px;
            }
        """)
        
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
        self.setFixedSize(600, 450)
        
        # 美化样式
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
                font-family: "Microsoft YaHei";
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #108de6;
            }
            QPushButton#cancelButton {
                background-color: #555;
            }
            QPushButton#cancelButton:hover {
                background-color: #666;
            }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 10px;
                color: #ddd;
                font-size: 12px;
            }
        """)
        
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
        
        # 更新日志
        changelog_label = QLabel("更新内容：")
        changelog_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(changelog_label)
        
        changelog = QTextEdit()
        changelog.setReadOnly(True)
        changelog.setPlainText(version_info.get('changelog', '暂无更新日志'))
        layout.addWidget(changelog)
        
        # 按钮
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
