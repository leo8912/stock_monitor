import sys
import os
import json
import easyquotation
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from win32com.client import Dispatch
# 在文件开头导入pypinyin
from pypinyin import lazy_pinyin, Style

from ..utils.logger import app_logger
from ..data.updater import update_stock_database
from ..ui.market_status import MarketStatusBar
from ..ui.components import StockTable
from ..ui.stock_search import StockSearchWidget
from ..utils.helpers import get_stock_emoji, is_equal, resource_path
from ..config.manager import load_config, save_config, is_market_open
from ..network.manager import NetworkManager
from ..version import APP_VERSION


class StockListWidget(QtWidgets.QListWidget):
    def __init__(self, parent=None, sync_callback=None):
        super(StockListWidget, self).__init__(parent)
        self.sync_callback = sync_callback
        # 设置拖拽相关属性
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        super(StockListWidget, self).dropEvent(event)
        if self.sync_callback:
            self.sync_callback()


class SettingsDialog(QtWidgets.QDialog):
    config_changed = pyqtSignal(list, int)  # stocks, refresh_interval
    
    def __init__(self, parent=None, main_window=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("自选股设置")
        self.setWindowIcon(QtGui.QIcon(resource_path('icon.ico')))
        # 去掉右上角问号
        if hasattr(QtCore.Qt, 'WindowContextHelpButtonHint'):
            self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)
        self.main_window = main_window
        self.stock_data = self.enrich_pinyin(self.load_stock_data())
        self.selected_stocks = []
        self.refresh_interval = 5
        self.init_ui()
        self.load_current_stocks()
        self.load_refresh_interval()

    def load_stock_data(self):
        try:
            with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            # 如果无法加载本地股票数据，则从网络获取部分股票数据
            app_logger.warning(f"无法加载本地股票数据: {e}，将使用网络数据")
            try:
                import easyquotation
                quotation = easyquotation.use('sina')
                
                # 获取一些热门股票作为默认数据
                stock_codes = ['sh600460', 'sh603986', 'sh600030', 'sh000001', 'sz000001', 'sz000002', 'sh600036']
                stock_data = []
                
                # 移除前缀以获取数据
                pure_codes = [code[2:] if code.startswith(('sh', 'sz')) else code for code in stock_codes]
                try:
                    data = quotation.stocks(pure_codes)
                except Exception:
                    # fallback to all if stocks method is not available
                    data = getattr(quotation, 'all', {})
                    if callable(data):
                        data = data()
                
                if isinstance(data, dict) and data:
                    for i, code in enumerate(stock_codes):
                        pure_code = pure_codes[i]
                        if pure_code in data and isinstance(data[pure_code], dict) and 'name' in data[pure_code] and data[pure_code]['name']:
                            stock_data.append({
                                'code': code,
                                'name': data[pure_code]['name']
                            })
                        else:
                            # 如果获取不到名称，就使用代码作为名称
                            stock_data.append({
                                'code': code,
                                'name': code
                            })
                
                return stock_data
            except Exception as e2:
                app_logger.error(f"无法从网络获取股票数据: {e2}")
                # 返回空列表作为最后的备选方案
                return []

    def enrich_pinyin(self, stock_list):
        for s in stock_list:
            name = s['name']
            # 去除*ST、ST等前缀
            base = name.replace('*', '').replace('ST', '').replace(' ', '')
            # 全拼
            full_pinyin = ''.join(lazy_pinyin(base))
            # 首字母
            abbr = ''.join(lazy_pinyin(base, style=Style.FIRST_LETTER))
            s['pinyin'] = full_pinyin.lower()
            s['abbr'] = abbr.lower()
        return stock_list

    def init_ui(self):
        self.setStyleSheet('''
            QDialog { 
                background: #fafafa; 
            }
            QLabel { 
                color: #333333; 
                font-size: 20px; 
                font-weight: normal; 
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QLineEdit, QListWidget, QComboBox {
                background: #ffffff; 
                color: #333333; 
                font-size: 18px; 
                border-radius: 6px;
                border: 1px solid #e0e0e0; 
                padding: 8px 12px;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QLineEdit:focus, QListWidget:focus, QComboBox:focus {
                border: 1px solid #2196f3;
                background: #ffffff;
            }
            QListWidget { 
                font-size: 20px; 
                border: none;
                outline: none;
                background: transparent;
            }
            QListWidget::item { 
                height: 44px; 
                border-radius: 4px;
                margin: 1px 2px;
                padding: 4px 8px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #1976d2;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
            QPushButton {
                background: #2196f3;
                color: #ffffff; 
                font-size: 18px; 
                border-radius: 6px;
                padding: 8px 24px;
                border: none;
                font-weight: normal;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QPushButton:hover { 
                background: #1976d2;
            }
            QPushButton:pressed { 
                background: #0d47a1;
            }
            QCheckBox { 
                font-size: 18px; 
                color: #333333; 
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
        ''')
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(32, 32, 32, 32)

        # 主体区域（左右对称）
        main_area = QtWidgets.QHBoxLayout()
        main_area.setSpacing(32)
        main_area.setContentsMargins(0, 0, 0, 0)
        # 左侧
        left_box = QtWidgets.QVBoxLayout()
        left_box.setSpacing(18)
        left_box.setContentsMargins(0, 0, 0, 0)
        
        # 使用股票搜索组件
        self.stock_search = StockSearchWidget(
            stock_data=self.stock_data, 
            stock_list=None,  # 将在后面设置
            sync_callback=self.sync_to_main
        )
        left_box.addWidget(self.stock_search)
        left_box.addStretch(1)
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_box)
        left_widget.setFixedSize(360, 540)

        # 右侧自选股区（极简风格）
        right_frame = QtWidgets.QFrame()
        right_frame.setFixedSize(400, 540)
        right_frame.setStyleSheet(
            "QFrame { "
            "background: #ffffff; "
            "border-radius: 8px; "
            "border: 1px solid #e0e0e0; "
            "}"
        )
        right_layout = QtWidgets.QVBoxLayout(right_frame)
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(24, 24, 24, 24)
        # 标题
        stock_list_title = QtWidgets.QLabel("自选股列表：")
        stock_list_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(stock_list_title)
        right_layout.addSpacing(10)
        # 列表（极简样式）
        self.stock_list = StockListWidget(sync_callback=self.sync_to_main)
        # 设置股票搜索组件的股票列表引用
        self.stock_search.stock_list = self.stock_list
        
        self.stock_list.setStyleSheet("""
            QListWidget {
                font-size: 18px;
                border: none;
                outline: none;
                background: transparent;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QListWidget::item {
                height: 40px;
                border-radius: 4px;
                margin: 1px 2px;
                padding: 4px 8px;
                background: transparent;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #1976d2;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.stock_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.stock_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.stock_list.setMinimumHeight(370)
        self.stock_list.setMaximumHeight(370)
        def center_items():
            for i in range(self.stock_list.count()):
                item = self.stock_list.item(i)
                if item:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.stock_list.itemChanged.connect(lambda _: center_items())
        model = self.stock_list.model()
        if model:
            model.rowsInserted.connect(lambda *_: center_items())
            model.rowsRemoved.connect(lambda *_: center_items())
        QtCore.QTimer.singleShot(0, center_items)
        right_layout.addWidget(self.stock_list)
        right_layout.addSpacing(16)
        # 删除按钮居中（在自选股列表下方）
        del_btn_layout = QtWidgets.QHBoxLayout()
        del_btn_layout.addStretch(1)
        btn_del = QtWidgets.QPushButton("删除选中")
        btn_del.clicked.connect(self.delete_selected_stocks)
        btn_del.setFixedWidth(120)
        btn_del.setFixedHeight(36)
        btn_del.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: #ffffff;
                font-size: 16px;
                font-weight: normal;
                padding: 6px 16px;
                border-radius: 4px;
                border: none;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QPushButton:hover {
                background: #d32f2f;
            }
            QPushButton:pressed {
                background: #b71c1c;
            }
        """)
        del_btn_layout.addWidget(btn_del)
        del_btn_layout.addStretch(1)
        right_layout.addLayout(del_btn_layout)
        
        # 新增GitHub Token输入框
        github_token_layout = QtWidgets.QHBoxLayout()
        github_token_layout.addStretch(1)
        github_token_label = QtWidgets.QLabel("GitHub Token:")
        github_token_label.setStyleSheet("font-size: 16px; color: #333333;")
        github_token_layout.addWidget(github_token_label)
        self.github_token_edit = QtWidgets.QLineEdit()
        self.github_token_edit.setPlaceholderText("请输入GitHub Token（可选）")
        self.github_token_edit.textChanged.connect(self.on_github_token_changed)
        github_token_layout.addWidget(self.github_token_edit)
        github_token_layout.addStretch(1)
        right_layout.addLayout(github_token_layout)
        
        right_layout.addStretch(1)

        main_area.addWidget(left_widget)
        main_area.addWidget(right_frame)
        layout.addLayout(main_area)
        layout.addStretch(1)

        # 底部功能区（极简样式）
        bottom_area = QtWidgets.QHBoxLayout()
        bottom_area.setSpacing(16)
        bottom_area.setContentsMargins(0, 24, 0, 0)
        
        # 刷新频率
        freq_label = QtWidgets.QLabel("刷新频率：")
        freq_label.setStyleSheet("font-size: 18px; color: #333333;")
        bottom_area.addWidget(freq_label, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
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
        self.freq_combo.currentIndexChanged.connect(self.on_freq_changed)
        bottom_area.addWidget(self.freq_combo, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        # 开机启动
        self.startup_checkbox = QtWidgets.QCheckBox("开机自动启动")
        self.startup_checkbox.setChecked(self.is_startup_enabled())
        self.startup_checkbox.stateChanged.connect(self.on_startup_checkbox_changed)
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
        bottom_area.addWidget(self.startup_checkbox, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
        # 版本号
        self.version_label = QtWidgets.QLabel(f"版本号：{APP_VERSION}")
        self.version_label.setStyleSheet("color: #666666; font-size: 16px;")
        bottom_area.addWidget(self.version_label, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        
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
        self.update_btn.clicked.connect(self.check_update)
        bottom_area.addWidget(self.update_btn, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        bottom_area.addStretch(1)
        # 右侧按钮区
        btn_ok = QtWidgets.QPushButton("确定")
        btn_ok.setStyleSheet("""
            QPushButton {
                background: #2196f3;
                color: #ffffff;
                font-size: 18px;
                font-weight: normal;
                padding: 8px 24px;
                border-radius: 4px;
                border: none;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QPushButton:hover {
                background: #1976d2;
            }
            QPushButton:pressed {
                background: #0d47a1;
            }
        """)
        btn_ok.setFixedHeight(36)
        btn_ok.clicked.connect(self.accept)
        
        btn_cancel = QtWidgets.QPushButton("取消")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #757575;
                color: #ffffff;
                font-size: 18px;
                font-weight: normal;
                padding: 8px 24px;
                border-radius: 4px;
                border: none;
                font-family: "Microsoft YaHei", "微软雅黑";
            }
            QPushButton:hover {
                background: #616161;
            }
            QPushButton:pressed {
                background: #424242;
            }
        """)
        btn_cancel.setFixedHeight(36)
        btn_cancel.clicked.connect(self.reject)
        
        bottom_area.addWidget(btn_ok, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        bottom_area.addWidget(btn_cancel, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(bottom_area)

    def load_current_stocks(self):
        cfg = load_config()
        stocks = cfg.get('user_stocks', ['sh600460', 'sh603986', 'sh600030', 'sh000001'])
        self.stock_list.clear()
        for stock in stocks:
            name = self.get_name_by_code(stock)
            # emoji区分类型
            emoji = get_stock_emoji(stock, name)
            display = f"{emoji}  {name} {stock}" if name else stock
            self.stock_list.addItem(display)
        self.selected_stocks = stocks[:]

    def get_name_by_code(self, code):
        for s in self.stock_data:
            if s['code'] == code:
                return s['name']
        return ""

    def load_refresh_interval(self):
        cfg = load_config()
        interval = cfg.get('refresh_interval', 5)
        self.refresh_interval = interval
        idx = {2:0, 5:1, 10:2, 30:3, 60:4}.get(interval, 1)
        self.freq_combo.setCurrentIndex(idx)

    def delete_selected_stocks(self):
        for item in self.stock_list.selectedItems():
            if item is not None:
                self.stock_list.takeItem(self.stock_list.row(item))
        self.selected_stocks = self.get_stocks_from_list()
        self.sync_to_main()

    def on_freq_changed(self, idx):
        interval = [2, 5, 10, 30, 60][idx]
        self.refresh_interval = interval
        self.sync_to_main()

    def accept(self):
        # 保存配置
        stocks = self.get_stocks_from_list()
        cfg = load_config()
        cfg['user_stocks'] = stocks
        cfg['refresh_interval'] = self.refresh_interval
        save_config(cfg)
        self.config_changed.emit(stocks, self.refresh_interval)
        super(SettingsDialog, self).accept()

    def sync_to_main(self):
        # 实时同步到主界面
        stocks = self.get_stocks_from_list()
        cfg = load_config()
        cfg['user_stocks'] = stocks
        cfg['refresh_interval'] = self.refresh_interval
        save_config(cfg)
        self.config_changed.emit(stocks, self.refresh_interval)

    # 新增方法：实时保存GitHub Token
    def on_github_token_changed(self, text):
        # 实时保存GitHub Token（可选）
        cfg = load_config()
        cfg['github_token'] = text.strip()
        save_config(cfg)

    def closeEvent(self, a0):
        cfg = load_config()
        pos = self.pos()
        cfg['settings_dialog_pos'] = [int(pos.x()), int(pos.y())]
        
        # 保存GitHub Token
        cfg['github_token'] = self.github_token_edit.text().strip()
        
        save_config(cfg)
        # 关键：关闭时让主界面指针置空，防止多实例
        p = self.parent()
        if p is not None and hasattr(p, 'settings_dialog'):
            setattr(p, 'settings_dialog', None)
        super(SettingsDialog, self).closeEvent(a0)

    def is_startup_enabled(self):
        import os
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_dir, "StockMonitor.lnk")
        return os.path.exists(shortcut_path)

    def on_startup_checkbox_changed(self, state):
        import os
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        exe_path = sys.executable
        shortcut_path = os.path.join(startup_dir, "StockMonitor.lnk")
        if state == QtCore.Qt.CheckState.Checked:
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
        import requests, re, os, sys, zipfile, tempfile, subprocess
        from packaging import version
        from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
        from PyQt5 import QtGui
        GITHUB_API = "https://api.github.com/repos/leo8912/stock_monitor/releases/latest"
        try:
            # 读取GitHub Token
            cfg = load_config()
            github_token = cfg.get('github_token', '')
            
            # 使用新的网络管理器
            network_manager = NetworkManager()
            data = network_manager.github_api_request(GITHUB_API, github_token)
            
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
            if version.parse(latest_ver) <= version.parse(APP_VERSION):
                app_logger.info("当前已是最新版本")
                QMessageBox.information(self, "检查更新", f"当前已是最新版本：{APP_VERSION}")
                return
            reply = QMessageBox.question(
                self, "发现新版本",
                f"检测到新版本 {latest_ver}，是否自动下载并升级？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            # 美化进度对话框
            progress = QProgressDialog("正在下载新版本...", None, 0, 100, self)
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
                with open(bat_path, 'w', encoding='gbk') as f:
                    f.write(f"""@echo off
timeout /t 1 >nul
xcopy /y /e /q "{extract_dir}\\*" "{exe_dir}\\"
rd /s /q "{extract_dir}"
del "{zip_path}"
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
            QMessageBox.warning(self, "检查更新", f"检查更新时发生错误：{e}")

    def get_stocks_from_list(self):
        """从股票列表中提取股票代码"""
        stocks = []
        for i in range(self.stock_list.count()):
            item = self.stock_list.item(i)
            if item is not None and hasattr(item, 'text'):
                text = item.text()
                # 提取最后的股票代码部分
                parts = text.split()
                if len(parts) >= 2:
                    stocks.append(parts[-1])
        return stocks