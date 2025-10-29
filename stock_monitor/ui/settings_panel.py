import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from win32com.client import Dispatch

from ..config.manager import load_config, save_config
from ..utils.helpers import resource_path
from ..version import APP_VERSION


class SettingsPanel(QtWidgets.QWidget):
    """设置面板组件 - 管理刷新频率、开机启动等设置选项"""
    
    settings_changed = pyqtSignal(int, bool)  # refresh_interval, startup_enabled
    
    def __init__(self, parent=None):
        super(SettingsPanel, self).__init__(parent)
        self.refresh_interval = 5
        self.startup_enabled = False
        self.parent_dialog = None  # type: ignore
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """初始化设置界面"""
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(0, 24, 0, 0)
        
        # 刷新频率
        freq_label = QtWidgets.QLabel("刷新频率：")
        freq_label.setStyleSheet("font-size: 18px; color: #333333;")
        layout.addWidget(freq_label, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        self.freq_combo = QtWidgets.QComboBox()
        self.freq_combo.setMinimumWidth(120)
        self.freq_combo.setFixedHeight(32)
        self.freq_combo.setStyleSheet('''
            QComboBox { 
                font-size: 16px; 
                padding: 4px 8px; 
                min-width: 120px; 
                border-radius: 4px; 
                border: 1px solid #e0e0e0; 
                background: #ffffff; 
                color: #333333;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QComboBox QAbstractItemView { 
                color: #333333; 
                background: #ffffff; 
                selection-background-color: #2196f3; 
                selection-color: #ffffff; 
                border-radius: 4px; 
                font-size: 16px; 
                border: 1px solid #e0e0e0;
            }
            QComboBox::drop-down { 
                border: none; 
                width: 20px; 
            }
        ''')
        self.freq_combo.addItems([
            "2秒 (极速)",
            "5秒 (快速)",
            "10秒 (标准)",
            "30秒 (慢速)",
            "60秒 (极慢)"
        ])
        self.freq_combo.setCurrentIndex(1)
        self.freq_combo.currentIndexChanged.connect(self.on_freq_changed)  # type: ignore
        layout.addWidget(self.freq_combo, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # 开机启动
        self.startup_checkbox = QtWidgets.QCheckBox("开机自动启动")
        self.startup_checkbox.setChecked(self.is_startup_enabled())
        self.startup_checkbox.stateChanged.connect(self.on_startup_checkbox_changed)  # type: ignore
        self.startup_checkbox.setStyleSheet("""
            QCheckBox {
                color: #333333; 
                font-size: 16px; 
                font-weight: normal;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 2px;
                border: 1px solid #bdbdbd;
            }
            QCheckBox::indicator:checked {
                background: #2196f3;
                border: 1px solid #2196f3;
            }
        """)
        layout.addWidget(self.startup_checkbox, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # 版本号
        self.version_label = QtWidgets.QLabel(f"版本号：{APP_VERSION}")
        self.version_label.setStyleSheet("color: #666666; font-size: 16px;")
        layout.addWidget(self.version_label, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # 检查更新按钮
        self.update_btn = QtWidgets.QPushButton("检查更新")
        self.update_btn.setStyleSheet("""
            QPushButton {
                background: #4caf50;
                color: #ffffff;
                font-size: 16px;
                font-weight: normal;
                padding: 6px 16px;
                border-radius: 4px;
                border: none;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QPushButton:hover {
                background: #388e3c;
            }
            QPushButton:pressed {
                background: #2e7d32;
            }
        """)
        self.update_btn.setFixedHeight(32)
        self.update_btn.clicked.connect(self.check_update)  # type: ignore
        layout.addWidget(self.update_btn, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        layout.addStretch(1)
        self.setLayout(layout)
        
    def load_settings(self):
        """加载设置"""
        cfg = load_config()
        interval = cfg.get('refresh_interval', 5)
        self.refresh_interval = interval
        idx = {2:0, 5:1, 10:2, 30:3, 60:4}.get(interval, 1)
        self.freq_combo.setCurrentIndex(idx)
        
    def on_freq_changed(self, idx):
        """刷新频率改变"""
        interval = [2, 5, 10, 30, 60][idx]
        self.refresh_interval = interval
        self.settings_changed.emit(self.refresh_interval, self.startup_enabled)
        
    def is_startup_enabled(self):
        """检查是否已设置开机启动"""
        import os
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_dir, "StockMonitor.lnk")
        return os.path.exists(shortcut_path)
        
    def on_startup_checkbox_changed(self, state):
        """开机启动选项改变"""
        self.startup_enabled = (state == QtCore.Qt.CheckState.Checked)
        self.toggle_startup(self.startup_enabled)
        self.settings_changed.emit(self.refresh_interval, self.startup_enabled)
        
    def toggle_startup(self, enable):
        """切换开机启动状态"""
        import os
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        exe_path = sys.executable
        shortcut_path = os.path.join(startup_dir, "StockMonitor.lnk")
        if enable:
            # 添加快捷方式
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = exe_path
            shortcut.WorkingDirectory = os.path.dirname(exe_path)
            shortcut.IconLocation = exe_path
            shortcut.save()
        else:
            # 删除快捷方式
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                except Exception:
                    pass
                    
    def check_update(self):
        """检查更新"""
        if self.parent_dialog:
            self.parent_dialog._check_update_impl()
        
    def get_settings(self):
        """获取当前设置"""
        return {
            'refresh_interval': self.refresh_interval,
            'startup_enabled': self.startup_enabled
        }