

APP_VERSION = 'v1.1.2'

import sys
import os
import json
import threading
import easyquotation
from PyQt5 import QtWidgets, QtGui, QtCore
import time
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
import datetime
from win32com.client import Dispatch
# 在文件开头导入pypinyin
from pypinyin import lazy_pinyin, Style

def resource_path(relative_path):
    """获取资源文件路径，兼容PyInstaller打包和源码运行"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

CONFIG_FILE = 'config.json'
ICON_FILE = resource_path('icon.png')
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def is_market_open():
    """检查A股是否开市"""
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
            (datetime.time(13,0) <= t <= datetime.time(15,0)))

def get_stock_emoji(code, name):
    """根据股票代码和名称返回对应的emoji"""
    if code.startswith(('sh000', 'sz399', 'sz159', 'sh510')) or (name and ('指数' in name or '板块' in name)):
        return '📈'
    elif name and '银行' in name:
        return '🏦'
    elif name and '保险' in name:
        return '🛡️'
    elif name and '板块' in name:
        return '📊'
    elif name and ('能源' in name or '石油' in name or '煤' in name):
        return '⛽️'
    elif name and ('汽车' in name or '车' in name):
        return '🚗'
    elif name and ('科技' in name or '半导体' in name or '芯片' in name):
        return '💻'
    else:
        return '⭐️'

def is_equal(a, b, tol=0.01):
    try:
        return abs(float(a) - float(b)) < tol
    except Exception:
        return False

class SettingsDialog(QtWidgets.QDialog):
    config_changed = pyqtSignal(list, int)  # stocks, refresh_interval
    
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.setWindowTitle("自选股设置")
        self.setWindowIcon(QtGui.QIcon(resource_path('icon.ico')))
        # 去掉右上角问号
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
        import json
        try:
            with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
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
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("输入股票代码/名称/拼音")
        self.search_edit.textChanged.connect(self.on_search)
        self.search_edit.returnPressed.connect(self.add_first_search_result)
        self.search_edit.setFixedHeight(44)
        left_box.addWidget(self.search_edit)
        self.search_results = QtWidgets.QListWidget()
        self.search_results.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.search_results.itemDoubleClicked.connect(self.add_selected_stock)
        self.search_results.setFixedSize(340, 480)
        left_box.addWidget(self.search_results)
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
        stock_list_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(stock_list_title)
        right_layout.addSpacing(10)
        # 列表（极简样式）
        self.stock_list = StockListWidget(sync_callback=self.sync_to_main)
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
        self.stock_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.stock_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.stock_list.setMinimumHeight(370)
        self.stock_list.setMaximumHeight(370)
        def center_items():
            for i in range(self.stock_list.count()):
                item = self.stock_list.item(i)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
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
        bottom_area.addWidget(freq_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
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
        bottom_area.addWidget(self.freq_combo, alignment=Qt.AlignmentFlag.AlignVCenter)
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
        bottom_area.addWidget(self.startup_checkbox, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # 版本号
        self.version_label = QtWidgets.QLabel(f"版本号：{APP_VERSION}")
        self.version_label.setStyleSheet("color: #666666; font-size: 16px;")
        bottom_area.addWidget(self.version_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
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
        bottom_area.addWidget(self.update_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
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
        
        bottom_area.addWidget(btn_ok, alignment=Qt.AlignmentFlag.AlignVCenter)
        bottom_area.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignVCenter)
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

    def on_search(self, text):
        text = text.strip().lower()
        self.search_results.clear()
        if not text:
            return
        def is_index(stock):
            return stock['code'].startswith(('sh000', 'sz399', 'sz159', 'sh510')) or '指数' in stock['name'] or '板块' in stock['name']
        # 支持拼音、首字母、代码、名称模糊匹配，ST股票去前缀
        results = []
        for s in self.stock_data:
            code_match = text in s['code'].lower()
            name_match = text in s['name'].lower()
            pinyin_match = text in s.get('pinyin','')
            abbr_match = text in s.get('abbr','')
            # 对于ST类，去掉*ST/ST前缀后再匹配
            base = s['name'].replace('*', '').replace('ST', '').replace(' ', '').lower()
            base_match = text in base
            if code_match or name_match or pinyin_match or abbr_match or base_match:
                results.append(s)
        results.sort(key=lambda s: (not is_index(s), s['code']))
        for s in results[:30]:
            display = f"{s['name']} {s['code']}"
            item = QtWidgets.QListWidgetItem(display)
            # emoji区分类型
            if is_index(s):
                emoji = '📈'
            elif '板块' in s['name']:
                emoji = '📊'
            else:
                emoji = '⭐️'
            item.setText(f"{emoji}  {display}")
            # 匹配内容高亮（背景+加粗）
            if text:
                for part in [s['code'].lower(), s['name'].lower(), s.get('pinyin',''), s.get('abbr',''), base]:
                    idx = part.find(text)
                    if idx != -1:
                        item.setBackground(QtGui.QColor('#eaf3fc'))
                        item.setForeground(QtGui.QColor('#357abd'))
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        break
            self.search_results.addItem(item)

    def add_selected_stock(self, item):
        # item.text()格式为“名称 代码”
        code = item.text().split()[-1]
        name = " ".join(item.text().split()[:-1])
        self.add_stock_to_list(code)

    def add_first_search_result(self):
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            self.add_selected_stock(item)

    def add_stock_to_list(self, code):
        name = self.get_name_by_code(code)
        display = f"{name} {code}" if name else code
        # emoji区分类型
        emoji = get_stock_emoji(code, name)
        display = f"{emoji}  {display}"
        for i in range(self.stock_list.count()):
            item = self.stock_list.item(i)
            if item is not None and item.text() == display:
                return
        self.stock_list.addItem(display)
        self.selected_stocks.append(code)
        self.sync_to_main()

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
        super().accept()

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

    def closeEvent(self, event):
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
        super().closeEvent(event)

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
        import requests, re, os, sys, zipfile, tempfile, subprocess
        from packaging import version
        from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
        from PyQt5 import QtGui
        GITHUB_API = "https://api.github.com/repos/leo8912/stock_monitor/releases/latest"
        try:
            # 读取GitHub Token
            cfg = load_config()
            github_token = cfg.get('github_token', '')
            headers = {}
            if github_token:
                headers['Authorization'] = f'token {github_token}'
            
            resp = requests.get(GITHUB_API, headers=headers, timeout=8)
            if resp.status_code != 200:
                if resp.status_code == 403 and 'rate limit' in resp.text.lower():
                    # 提示用户添加GitHub Token
                    QMessageBox.warning(self, "检查更新", "达到GitHub API速率限制，建议添加GitHub Token以提高请求频率。")
                    return
                else:
                    raise Exception(f"Unexpected status code: {resp.status_code}")
            
            data = resp.json()
            tag = data.get('tag_name', '')
            m = re.search(r'v(\d+\.\d+\.\d+)', tag)
            latest_ver = m.group(0) if m else None
            asset_url = None
            for asset in data.get('assets', []):
                if asset['name'] == 'stock_monitor.zip':
                    asset_url = asset['browser_download_url']
                    break
            from main import APP_VERSION
            if not latest_ver or not asset_url:
                QMessageBox.warning(self, "检查更新", "未检测到新版本信息。")
                return
            if version.parse(latest_ver) <= version.parse(APP_VERSION):
                QMessageBox.information(self, "检查更新", f"当前已是最新版本：{APP_VERSION}")
                return
            reply = QMessageBox.question(
                self, "发现新版本",
                f"检测到新版本 {latest_ver}，是否自动下载并升级？",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
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
                with requests.get(asset_url, stream=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    with open(zip_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
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
                progress.close()
                QMessageBox.warning(self, "升级失败", f"写入升级脚本失败：{e}")
                return
            progress.close()
            QMessageBox.information(self, "升级提示", "即将自动升级并重启，请稍候。")
            subprocess.Popen(['cmd', '/c', bat_path])
            QApplication.quit()
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "检查更新", f"网络异常，无法连接到GitHub：{e}")
        except Exception as e:
            QMessageBox.warning(self, "检查更新", f"检查更新时发生错误：{e}")

# 主界面同步显示“名称 代码”
class StockTable(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)  # 增加一列：封单手
        h_header = self.horizontalHeader()
        v_header = self.verticalHeader()
        if h_header is not None:
            h_header.setVisible(False)
            h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        if v_header is not None:
            v_header.setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)  # type: ignore
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # type: ignore
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # type: ignore
        self.setStyleSheet('''
            QTableWidget {
                background: transparent;
                border: none;
                outline: none;
                gridline-color: transparent;
                selection-background-color: transparent;
                selection-color: #fff;
                font-family: "微软雅黑";
                font-size: 20px;
                font-weight: bold;
                color: #fff;
            }
            QTableWidget::item {
                border: none;
                padding: 0px;
                background: transparent;
            }
            QTableWidget::item:selected {
                background: transparent;
                color: #fff;
            }
            QHeaderView::section {
                background: transparent;
                border: none;
                color: transparent;
            }
            QScrollBar {
                background: transparent;
                width: 0px;
                height: 0px;
            }
            QScrollBar::handle {
                background: transparent;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: transparent;
                border: none;
            }
        ''')

    @pyqtSlot(list)
    def update_data(self, stocks):
        self.setRowCount(len(stocks))
        for row, stock in enumerate(stocks):
            name, price, change, color, seal_vol, seal_type = stock
            # ======= 表格渲染 =======
            item_name = QtWidgets.QTableWidgetItem(name)
            item_price = QtWidgets.QTableWidgetItem(price)
            if not change.endswith('%'):
                change = change + '%'
            item_change = QtWidgets.QTableWidgetItem(change)
            item_seal = QtWidgets.QTableWidgetItem(seal_vol)
            # 涨停/跌停高亮
            if seal_type == 'up':
                for item in [item_name, item_price, item_change, item_seal]:
                    item.setBackground(QtGui.QColor('#ffecec'))
                    item.setForeground(QtGui.QColor('#e74c3f'))
            elif seal_type == 'down':
                for item in [item_name, item_price, item_change, item_seal]:
                    item.setBackground(QtGui.QColor('#e8f5e9'))
                    item.setForeground(QtGui.QColor('#27ae60'))
            else:
                item_name.setForeground(QtGui.QColor(color))
                item_price.setForeground(QtGui.QColor(color))
                item_change.setForeground(QtGui.QColor(color))
                item_seal.setForeground(QtGui.QColor('#888'))
            item_name.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
            item_price.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
            item_change.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
            item_seal.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # type: ignore
            self.setItem(row, 0, item_name)
            self.setItem(row, 1, item_price)
            self.setItem(row, 2, item_change)
            self.setItem(row, 3, item_seal)
        h_header = self.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.updateGeometry()
        QtWidgets.QApplication.processEvents()  # 强制刷新事件队列

    def get_name_by_code(self, code):
        # 读取本地股票数据
        try:
            import json
            with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
                stock_data = json.load(f)
            for s in stock_data:
                if s['code'] == code:
                    return s['name']
        except Exception:
            pass
        return ""

class MainWindow(QtWidgets.QWidget):
    update_table_signal = pyqtSignal(list)
    def __init__(self):
        super().__init__()
        self.setWindowTitle('A股行情监控')
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |  # type: ignore
            QtCore.Qt.FramelessWindowHint |  # type: ignore
            QtCore.Qt.Tool |  # type: ignore
            QtCore.Qt.WindowMaximizeButtonHint  # type: ignore
        )  # type: ignore
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)  # type: ignore
        self.resize(320, 160)
        self.drag_position = None
        
        # 初始化UI
        self.table = StockTable(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(self.table)
        self.setLayout(layout)
        
        # 设置样式
        self.setMinimumHeight(80)
        self.setMinimumWidth(280)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        font = QtGui.QFont('微软雅黑', 20)
        self.setFont(font)
        self.setStyleSheet('QWidget { font-family: "微软雅黑"; font-size: 20px; color: #fff; background: transparent; border: none; }')
        
        # 初始化菜单
        self.menu = QtWidgets.QMenu(self)
        self.action_settings = self.menu.addAction('设置')
        self.action_quit = self.menu.addAction('退出')
        self.action_settings.triggered.connect(self.open_settings)  # type: ignore
        self.action_quit.triggered.connect(QtWidgets.QApplication.quit)  # type: ignore
        
        # 初始化数据
        self.settings_dialog = None
        self.quotation = easyquotation.use('sina')
        cfg = load_config()
        self.refresh_interval = cfg.get('refresh_interval', 5)
        self.current_user_stocks = self.load_user_stocks()
        
        # 启动刷新线程和信号连接
        self._start_refresh_thread()
        self.update_table_signal.connect(self.table.update_data)
        
        # 显示窗口并加载位置
        self.load_position()
        self.show()
        self.raise_()
        self.activateWindow()
        self.install_event_filters(self)
        
        # 立即刷新一次
        self.refresh_now(self.current_user_stocks)

    def install_event_filters(self, widget):
        if isinstance(widget, QtWidgets.QWidget):
            widget.installEventFilter(self)
            for child in widget.findChildren(QtWidgets.QWidget):
                self.install_event_filters(child)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:  # type: ignore
            if event.button() == QtCore.Qt.LeftButton:  # type: ignore
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                self.setCursor(QtCore.Qt.SizeAllCursor)  # type: ignore
                event.accept()
                return True
            elif event.button() == QtCore.Qt.RightButton:  # type: ignore
                menu = QtWidgets.QMenu(self)
                menu.setStyleSheet('''
                    QMenu {
                        background: #23272e;
                        color: #fff;
                        border-radius: 8px;
                        font-size: 20px;
                        font-weight: bold;
                        padding: 6px 0;
                        min-width: 100px;
                    }
                    QMenu::item {
                        height: 36px;
                        padding: 0 24px;
                        border-radius: 8px;
                        margin: 2px 6px;
                        font-size: 20px;
                        font-weight: bold;
                    }
                    QMenu::item:selected {
                        background: #4a90e2;
                        color: #fff;
                        border-radius: 8px;
                    }
                    QMenu::separator {
                        height: 1px;
                        background: #444;
                        margin: 4px 0;
                    }
                ''')
                action_settings = menu.addAction('设置')
                menu.addSeparator()
                action_quit = menu.addAction('退出')
                action = menu.exec_(event.globalPos())
                if action == action_settings:
                    if not hasattr(self, 'settings_dialog') or self.settings_dialog is None:
                        self.settings_dialog = SettingsDialog(self, main_window=self)
                        # 连接信号
                        self.settings_dialog.config_changed.connect(self.on_user_stocks_changed)
                    self.settings_dialog.show()
                    self.settings_dialog.raise_()
                    self.settings_dialog.activateWindow()
                elif action == action_quit:
                    QtWidgets.QApplication.instance().quit()  # type: ignore
                event.accept()
                return True
        elif event.type() == QtCore.QEvent.MouseMove:  # type: ignore
            if event.buttons() == QtCore.Qt.LeftButton and self.drag_position is not None:  # type: ignore
                self.move(event.globalPos() - self.drag_position)
                event.accept()
                return True
        elif event.type() == QtCore.QEvent.MouseButtonRelease:  # type: ignore
            self.drag_position = None
            self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
            self.save_position()  # 拖动结束时自动保存位置
            event.accept()
            return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:  # type: ignore
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(QtCore.Qt.SizeAllCursor)  # type: ignore
            event.accept()
        elif event.button() == QtCore.Qt.RightButton:  # type: ignore
            self.menu.popup(event.globalPos())

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self.drag_position is not None:  # type: ignore
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
        self.save_position()  # 拖动结束时自动保存位置

    def closeEvent(self, event):
        self.save_position()
        super().closeEvent(event)

    def save_position(self):
        cfg = load_config()
        pos = self.pos()
        cfg['window_pos'] = [pos.x(), pos.y()]
        save_config(cfg)

    def load_position(self):
        cfg = load_config()
        pos = cfg.get('window_pos')
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(pos[0], pos[1])
        else:
            self.move_to_bottom_right()

    def move_to_bottom_right(self):
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()  # type: ignore
        self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 40)

    def open_settings(self):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self, main_window=self)
        else:
            try:
                self.settings_dialog.config_changed.disconnect(self.on_user_stocks_changed)
            except Exception:
                pass
        self.settings_dialog.config_changed.connect(self.on_user_stocks_changed)
        
        # 设置弹窗位置
        cfg = load_config()
        pos = cfg.get('settings_dialog_pos')
        if pos and isinstance(pos, list) and len(pos) == 2:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen is not None:
                available_geo = screen.availableGeometry()
                x = max(0, min(pos[0], available_geo.width() - self.settings_dialog.width()))
                y = max(0, min(pos[1], available_geo.height() - self.settings_dialog.height()))
                self.settings_dialog.move(x, y)
            else:
                self.settings_dialog.move(pos[0], pos[1])
        else:
            main_geo = self.geometry()
            x = main_geo.x() + main_geo.width() + 20
            y = main_geo.y()
            self.settings_dialog.move(x, y)
        
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def on_user_stocks_changed(self, user_stocks, refresh_interval):
        self.current_user_stocks = user_stocks
        self.refresh_interval = refresh_interval  # 关键：更新刷新间隔
        self.refresh_now(user_stocks)

    def process_stock_data(self, data, stocks_list):
        """处理股票数据，返回格式化的股票列表"""
        stocks = []
        for code in stocks_list:
            code_key = code[-6:] if len(code) >= 6 else code
            info = None
            # 兼容sh/sz前缀和无前缀
            if isinstance(data, dict):
                info = data.get(code_key) or data.get(code)
            if info:
                name = info.get('name', code)
                price = f"{info.get('now', 0):.2f}"
                close = info.get('close', 0)
                now = info.get('now', 0)
                high = info.get('high', 0)
                low = info.get('low', 0)
                bid1 = info.get('bid1', 0)
                bid1_vol = info.get('bid1_volume', 0)
                ask1 = info.get('ask1', 0)
                ask1_vol = info.get('ask1_volume', 0)
                percent = ((now - close) / close * 100) if close else 0
                color = '#e74c3f' if percent > 0 else '#27ae60' if percent < 0 else '#e6eaf3'
                change_str = f"{percent:+.2f}%"
                # 检测涨停/跌停封单
                seal_vol = ''
                seal_type = ''
                if is_equal(now, high) and is_equal(now, bid1) and bid1_vol > 0 and is_equal(ask1, 0):
                    seal_vol = f"{int(bid1_vol/100):,}"
                    seal_type = 'up'
                elif is_equal(now, low) and is_equal(now, ask1) and ask1_vol > 0 and is_equal(bid1, 0):
                    seal_vol = f"{int(ask1_vol/100):,}"
                    seal_type = 'down'
                stocks.append((name, price, change_str, color, seal_vol, seal_type))
            else:
                stocks.append((code, '--', '--', '#e6eaf3', '', ''))
        return stocks

    def refresh_now(self, stocks_list=None):
        if stocks_list is None:
            stocks_list = self.current_user_stocks
        if hasattr(self, 'quotation') and hasattr(self.quotation, 'real') and callable(self.quotation.real):
            try:
                # 逐个请求，避免混淆
                data_dict = {}
                for code in stocks_list:
                    single = self.quotation.real([code])
                    # single返回如 {'000001': {...}}，需用完整code做映射
                    if isinstance(single, dict):
                        # 取第一个value
                        for v in single.values():
                            data_dict[code] = v
                            break
                stocks = self.process_stock_data(data_dict, stocks_list)
                self.table.setRowCount(0)
                self.table.clearContents()
                self.table.update_data(stocks)
                self.table.viewport().update()
                self.table.repaint()
                QtWidgets.QApplication.processEvents()
                self.adjust_window_height()  # 每次刷新后自适应高度
            except Exception as e:
                print('行情刷新异常:', e)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        bg_color = QtGui.QColor(30, 30, 30, 220)  # 降低透明度，更不透明
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.NoPen)  # type: ignore
        painter.drawRect(rect)

    def _start_refresh_thread(self):
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()

    def _refresh_loop(self):
        while True:
            if hasattr(self, 'quotation') and hasattr(self.quotation, 'real') and callable(self.quotation.real):
                try:
                    data_dict = {}
                    for code in self.current_user_stocks:
                        single = self.quotation.real([code])
                        if isinstance(single, dict):
                            for v in single.values():
                                data_dict[code] = v
                                break
                    stocks = self.process_stock_data(data_dict, self.current_user_stocks)
                    self.update_table_signal.emit(stocks)
                except Exception as e:
                    print('行情刷新异常:', e)
            
            # 根据开市状态决定刷新间隔
            sleep_time = self.refresh_interval if is_market_open() else 30
            time.sleep(sleep_time)

    def load_user_stocks(self):
        cfg = load_config()
        stocks = cfg.get('user_stocks', ['sh600460', 'sh603986', 'sh600030', 'sh000001'])
        # 只保留股票代码部分，顺序不变
        processed_stocks = []
        for stock in stocks:
            if isinstance(stock, str) and ' ' in stock:
                parts = stock.split()
                if len(parts) >= 2:
                    code = parts[-1]
                    processed_stocks.append(code)
                else:
                    processed_stocks.append(stock)
            else:
                processed_stocks.append(stock)
        return processed_stocks

    def load_theme_config(self):
        import json
        try:
            with open(resource_path("theme_config.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def adjust_window_height(self):
        # 用真实行高自适应主窗口高度，最小3行
        QtWidgets.QApplication.processEvents()
        vh = self.table.verticalHeader()
        if self.table.rowCount() > 0:
            row_height = vh.sectionSize(0)
        else:
            row_height = 36  # 默认
        min_rows = 3
        layout_margin = 24  # QVBoxLayout上下边距
        table_height = max(self.table.rowCount(), min_rows) * row_height
        # 增加表头高度（4列时略增）
        new_height = table_height + layout_margin
        self.setFixedHeight(new_height)
        # ====== 新增：宽度自适应封单手显示 ======
        has_seal = False
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 3)
            if item and item.text().strip():
                has_seal = True
                break
        if has_seal:
            self.setFixedWidth(400)
        else:
            self.setFixedWidth(320)

class StockListWidget(QtWidgets.QListWidget):
    def __init__(self, parent=None, sync_callback=None):
        super().__init__(parent)
        self.sync_callback = sync_callback
        # 设置拖拽相关属性
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        super().dropEvent(event)
        if self.sync_callback:
            self.sync_callback()

class SystemTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, main_window):
        icon = QtGui.QIcon(ICON_FILE) if os.path.exists(ICON_FILE) else QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)  # type: ignore
        super().__init__(icon)
        self.main_window = main_window
        self.menu = QtWidgets.QMenu()
        self.action_settings = self.menu.addAction('设置')
        self.action_quit = self.menu.addAction('退出')
        self.setContextMenu(self.menu)
        self.action_settings.triggered.connect(self.open_settings)  # type: ignore
        self.action_quit.triggered.connect(QtWidgets.QApplication.quit)  # type: ignore
        self.activated.connect(self.on_activated)
        # self.settings_dialog = None  # 删除托盘自己的 settings_dialog

    def open_settings(self):
        # 直接调用主界面的 open_settings，确保唯一实例和信号链路
        self.main_window.open_settings()

    def on_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:  # type: ignore
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        elif reason == QtWidgets.QSystemTrayIcon.Context:  # type: ignore
            self.contextMenu().popup(QtGui.QCursor.pos())  # type: ignore

def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    tray = SystemTray(main_window)
    tray.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 