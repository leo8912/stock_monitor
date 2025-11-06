import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from win32com.client import Dispatch

from ..config.manager import load_config, save_config
from ..utils.helpers import resource_path
from ..version import __version__


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
        self.version_label = QtWidgets.QLabel(f"版本号：{__version__}")
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
        else:
            # 如果parent_dialog未设置，直接在当前类中实现检查更新功能
            self._check_update_impl()
            
    def _check_update_impl(self):
        """检查更新的实际实现"""
        import requests, re, os, sys, zipfile, tempfile, subprocess
        from packaging import version
        from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
        from PyQt5 import QtGui
        from ..network.manager import NetworkManager
        from ..config.manager import CONFIG_DIR
        from ..version import __version__
        from ..utils.logger import app_logger
        GITHUB_API = "https://api.github.com/repos/leo8912/stock_monitor/releases/latest"
        GITHUB_API_BACKUP = "https://ghfast.top/https://api.github.com/repos/leo8912/stock_monitor/releases/latest"
        try:
            # 使用新的网络管理器
            network_manager = NetworkManager()
            data = network_manager.github_api_request(GITHUB_API)
            
            # 如果主地址失败，尝试备用地址
            if not data:
                app_logger.warning("主GitHub地址访问失败，尝试使用备用地址")
                data = network_manager.github_api_request(GITHUB_API_BACKUP)
            
            if not data:
                app_logger.warning("无法获取GitHub发布信息")
                QMessageBox.warning(self, "检查更新", "无法获取GitHub发布信息。")
                return
                
            tag = data.get('tag_name', '')
            m = re.search(r'v(\d+\.\d+\.\d+)', tag)
            latest_ver = m.group(0) if m else None
            asset_url = None
            for asset in data.get('assets', []):
                if asset['name'] == 'stock_monitor.zip':
                    asset_url = asset['browser_download_url']
                    break
            if not latest_ver or not asset_url:
                app_logger.warning("未检测到新版本信息")
                QMessageBox.warning(self, "检查更新", "未检测到新版本信息。")
                return
            if version.parse(latest_ver) <= version.parse(__version__):
                app_logger.info("当前已是最新版本")
                QMessageBox.information(self, "检查更新", f"当前已是最新版本：{__version__}")
                return
            reply = QMessageBox.question(
                self, "发现新版本",
                f"检测到新版本 {latest_ver}，是否自动下载并升级？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)  # type: ignore
            if reply != QMessageBox.StandardButton.Yes:
                return
            # 美化进度对话框
            progress = QProgressDialog("正在下载新版本...", "", 0, 100, self)
            progress.setWindowTitle("自动升级进度")
            progress.setMinimumWidth(420)
            progress.setStyleSheet("""
                QProgressDialog {
                    background: #23272e;
                    color: #fff;
                    font-size: 18px;
                    border-radius: 10px;
                }
                QLabel {
                    color: #fff;
                    font-size: 18px;
                }
                QProgressBar {
                    border: 1px solid #bbb;
                    border-radius: 8px;
                    background: #333;
                    height: 32px;
                    text-align: center;
                    color: #fff;
                    font-size: 22px;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a90e2, stop:1 #00c6fb);
                    border-radius: 8px;
                }
            """)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.setValue(0)
            QApplication.processEvents()
            # 下载
            tmpdir = tempfile.gettempdir()
            zip_path = os.path.join(tmpdir, "stock_monitor_upgrade.zip")
            extract_dir = os.path.join(tmpdir, "stock_monitor_upgrade")
            try:
                progress.setLabelText("正在下载新版本...")
                QApplication.processEvents()
                # 使用新的网络管理器下载文件
                response = network_manager.get(asset_url, stream=True)
                if not response:
                    raise Exception("下载失败")
                    
                total = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                percent = int(downloaded * 100 / total)
                                progress.setValue(min(percent, 99))
                                QApplication.processEvents()
                progress.setValue(100)
                progress.setLabelText("下载完成，正在解压...")
                QApplication.processEvents()
            except Exception as e:
                app_logger.error(f"下载新版本失败: {e}")
                progress.close()
                QMessageBox.warning(self, "升级失败", f"下载新版本失败：{e}")
                return
            # 解压
            try:
                import shutil
                progress.setLabelText("正在解压新版本...")
                QApplication.processEvents()
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                progress.setLabelText("解压完成，正在升级...")
                QApplication.processEvents()
            except Exception as e:
                app_logger.error(f"解压新版本失败: {e}")
                progress.close()
                QMessageBox.warning(self, "升级失败", f"解压新版本失败：{e}")
                return
            # 写升级批处理
            try:
                progress.setLabelText("正在写入升级脚本...")
                QApplication.processEvents()
                bat_path = os.path.join(tmpdir, "stock_monitor_upgrade.bat")
                exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                
                # 修复问题1：升级时保护用户配置目录
                with open(bat_path, 'w', encoding='gbk') as f:
                    f.write(f"""@echo off
timeout /t 1 >nul
echo 正在升级应用程序...
REM 升级前备份配置目录
if exist "{CONFIG_DIR}" (
    echo 备份用户配置...
    xcopy /y /e /q "{CONFIG_DIR}" "{extract_dir}\\config_backup\\"
)

REM 执行升级
xcopy /y /e /q "{extract_dir}\\*" "{exe_dir}\\"

REM 恢复配置目录
if exist "{extract_dir}\\config_backup\\" (
    echo 恢复用户配置...
    xcopy /y /e /q "{extract_dir}\\config_backup\\" "{CONFIG_DIR}"
    rd /s /q "{extract_dir}\\config_backup"
)

REM 清理临时文件
rd /s /q "{extract_dir}"
del "{zip_path}"
echo 升级完成，正在启动新版本...
start "" "{exe_dir}\\stock_monitor.exe"
""")
                progress.setLabelText("升级完成，正在重启...")
                progress.setValue(100)
                QApplication.processEvents()
            except Exception as e:
                app_logger.error(f"写入升级脚本失败: {e}")
                progress.close()
                QMessageBox.warning(self, "升级失败", f"写入升级脚本失败：{e}")
                return
            progress.close()
            app_logger.info("升级完成，即将重启")
            QMessageBox.information(self, "升级提示", "即将自动升级并重启，请稍候。")
            subprocess.Popen(['cmd', '/c', bat_path])
            QApplication.quit()
        except requests.exceptions.RequestException as e:
            app_logger.error(f"网络异常，无法连接到GitHub: {e}")
            QMessageBox.warning(self, "检查更新", f"网络异常，无法连接到GitHub：{e}")
        except Exception as e:
            app_logger.error(f"检查更新时发生错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "检查更新", f"检查更新时发生错误：{e}")

    def get_settings(self):
        """获取当前设置"""
        return {
            'refresh_interval': self.refresh_interval,
            'startup_enabled': self.startup_enabled
        }