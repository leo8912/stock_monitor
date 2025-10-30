"""
设置对话框模块
用于管理用户设置，包括自选股列表和刷新频率等配置
"""

import sys
import os
import threading
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal
from win32com.client import Dispatch
# 在文件开头导入pypinyin
from pypinyin import lazy_pinyin, Style

from ..utils.logger import app_logger
from ..ui.stock_search import StockSearchWidget
from ..ui.settings_panel import SettingsPanel
from ..utils.helpers import get_stock_emoji, resource_path
from ..config.manager import load_config, save_config, is_market_open
from ..network.manager import NetworkManager
from ..version import APP_VERSION
from ..data.stocks import load_stock_data, enrich_pinyin
from ..data.quotation import get_name_by_code as get_stock_name_by_code


class StockListWidget(QtWidgets.QListWidget):
    """
    股票列表控件
    支持拖拽重新排序功能
    """
    # 定义一个节流信号，用于优化拖拽性能
    items_reordered = pyqtSignal()
    
    def __init__(self, parent=None, sync_callback=None):
        """
        初始化股票列表控件
        
        Args:
            parent: 父级控件
            sync_callback: 同步回调函数
        """
        super(StockListWidget, self).__init__(parent)
        self.sync_callback = sync_callback
        # 设置拖拽相关属性
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        
        # 节流定时器，用于优化频繁的拖拽事件
        self._throttle_timer = QtCore.QTimer(self)
        self._throttle_timer.setSingleShot(True)
        self._throttle_timer.timeout.connect(self._on_items_reordered)  # type: ignore
        self.items_reordered.connect(self._throttle_reorder)  # type: ignore

    def dropEvent(self, event):
        """
        拖拽放置事件处理
        
        Args:
            event: 拖拽事件对象
        """
        super(StockListWidget, self).dropEvent(event)
        # 发出重新排序信号而不是直接调用回调
        self.items_reordered.emit()

    def _throttle_reorder(self):
        """节流处理重新排序事件"""
        if self._throttle_timer.isActive():
            self._throttle_timer.stop()
        self._throttle_timer.start(100)  # 100ms节流延迟

    def _on_items_reordered(self):
        """实际处理重新排序的回调"""
        if self.sync_callback:
            self.sync_callback()


class SettingsDialog(QtWidgets.QDialog):
    """
    设置对话框类
    提供用户配置界面，包括自选股设置和应用设置
    """
    config_changed = pyqtSignal(list, int)  # stocks, refresh_interval
    
    def __init__(self, parent=None, main_window=None):
        """
        初始化设置对话框
        
        Args:
            parent: 父级控件
            main_window: 主窗口引用
        """
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("自选股设置")
        self.setWindowIcon(QtGui.QIcon(resource_path('icon.ico')))
        # 去掉右上角问号
        if hasattr(QtCore.Qt, 'WindowContextHelpButtonHint'):
            self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)  # type: ignore
        self.setModal(True)
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)
        self.main_window = main_window
        self.stock_data = self.enrich_pinyin(self.load_stock_data())
        self.selected_stocks = []
        self.refresh_interval = 5
        # 添加配置保存节流定时器
        self._save_throttle_timer = QtCore.QTimer(self)
        self._save_throttle_timer.setSingleShot(True)
        self._save_throttle_timer.timeout.connect(self._throttled_save_config)  # type: ignore
        self._pending_save_config = None
        self.init_ui()
        self.load_current_stocks()
        self.load_refresh_interval()


    def _load_stock_data(self):
        """加载股票数据"""
        try:
            # 使用缓存机制加载股票数据
            from ..utils.stock_cache import global_stock_cache
            stock_data = global_stock_cache.get_stock_data()
            # 更新股票搜索组件的数据
            if hasattr(self, 'stock_search') and self.stock_search:
                self.stock_search.stock_data = stock_data
        except Exception as e:
            app_logger.error(f"加载股票数据失败: {e}")
    
    def load_stock_data(self):
        """
        加载股票数据
        
        Returns:
            list: 股票数据列表
        """
        try:
            # 使用缓存机制加载股票数据
            from ..utils.stock_cache import global_stock_cache
            return global_stock_cache.get_stock_data()
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
                    # type: ignore 是因为pyright无法正确识别这个方法
                    data = quotation.stocks(pure_codes)  # type: ignore
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
                
                # 使用统一的拼音处理函数
                return enrich_pinyin(stock_data)
            except Exception as e2:
                app_logger.error(f"无法从网络获取股票数据: {e2}")
                # 返回空列表作为最后的备选方案
                return []

    def enrich_pinyin(self, stock_list):
        """
        丰富股票列表的拼音信息
        
        Args:
            stock_list (list): 股票列表
            
        Returns:
            list: 添加了拼音信息的股票列表
        """
        # 使用统一的拼音处理函数
        return enrich_pinyin(stock_list)

    def init_ui(self):
        """初始化用户界面"""
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

        # 主体区域（使用更灵活的布局）
        main_area = QtWidgets.QHBoxLayout()
        main_area.setSpacing(32)
        main_area.setContentsMargins(0, 0, 0, 0)
        # 左侧
        left_box = QtWidgets.QVBoxLayout()
        left_box.setSpacing(18)
        left_box.setContentsMargins(0, 0, 0, 0)
        
        # 使用股票搜索组件，直接使用已加载的股票数据
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
        
        right_layout.addWidget(self.stock_list)
        right_layout.addSpacing(16)
        # 删除按钮居中（在自选股列表下方）
        del_btn_layout = QtWidgets.QHBoxLayout()
        del_btn_layout.addStretch(1)
        btn_del = QtWidgets.QPushButton("删除选中")
        btn_del.clicked.connect(self.delete_selected_stocks)  # type: ignore
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
        

        
        right_layout.addStretch(1)

        main_area.addWidget(left_widget)
        main_area.addWidget(right_frame)
        layout.addLayout(main_area)
        layout.addStretch(1)

        # 底部设置面板
        self.settings_panel = SettingsPanel()
        self.settings_panel.settings_changed.connect(self.on_settings_changed)  # type: ignore
        bottom_area = QtWidgets.QHBoxLayout()
        bottom_area.setSpacing(16)
        bottom_area.setContentsMargins(0, 24, 0, 0)
        bottom_area.addWidget(self.settings_panel)
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
        btn_ok.clicked.connect(self.accept)  # type: ignore
        
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
        btn_cancel.clicked.connect(self.reject)  # type: ignore
        
        bottom_area.addWidget(btn_ok, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        bottom_area.addWidget(btn_cancel, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(bottom_area)

    def load_current_stocks(self):
        """加载当前用户股票列表"""
        cfg = load_config()
        stocks = cfg.get('user_stocks', ['sh600460', 'sh603986', 'sh600030', 'sh000001'])
        self.stock_list.clear()
        for stock in stocks:
            name = self.get_name_by_code(stock)
            # emoji区分类型
            emoji = get_stock_emoji(stock, name)
            # 对于港股，只显示中文名称部分
            if stock.startswith('hk') and name:
                # 去除"-"及之后的部分，只保留中文名称
                if '-' in name:
                    name = name.split('-')[0].strip()
                display = f"{emoji}  {name} {stock}"
            elif name:
                display = f"{emoji}  {name} {stock}"
            else:
                display = f"{emoji}  {stock}"
            self.stock_list.addItem(display)
        self.selected_stocks = stocks[:]

    def get_name_by_code(self, code):
        """
        根据股票代码获取股票名称
        
        Args:
            code (str): 股票代码
            
        Returns:
            str: 股票名称
        """
        # 使用统一的获取股票名称函数
        name = get_stock_name_by_code(code)
        # 对于港股，只保留中文部分
        if code.startswith('hk') and name:
            # 去除"-"及之后的部分，只保留中文名称
            if '-' in name:
                name = name.split('-')[0].strip()
        return name

    def load_refresh_interval(self):
        """加载刷新间隔配置"""
        cfg = load_config()
        interval = cfg.get('refresh_interval', 5)
        self.refresh_interval = interval
        # 更新设置面板的刷新频率
        idx = {2:0, 5:1, 10:2, 30:3, 60:4}.get(interval, 1)
        self.settings_panel.freq_combo.setCurrentIndex(idx)

    def delete_selected_stocks(self):
        """删除选中的股票"""
        for item in self.stock_list.selectedItems():
            if item is not None:
                self.stock_list.takeItem(self.stock_list.row(item))
        self.selected_stocks = self.get_stocks_from_list()
        self.sync_to_main()

    def on_settings_changed(self, refresh_interval, startup_enabled):
        """
        设置改变时的处理函数
        
        Args:
            refresh_interval (int): 刷新间隔
            startup_enabled (bool): 是否开机启动
        """
        self.refresh_interval = refresh_interval
        self.sync_to_main()

    def accept(self):
        """确定按钮点击事件处理"""
        # 保存配置
        self._save_user_config()
        super(SettingsDialog, self).accept()

    def sync_to_main(self):
        """同步配置到主界面"""
        # 实时同步到主界面，不使用节流机制
        self._save_user_config()
        # 使用QueuedConnection避免阻塞UI
        stocks = self.get_stocks_from_list()
        self.config_changed.emit(stocks, self.refresh_interval)

    def _save_user_config(self):
        """保存用户配置到文件"""
        stocks = self.get_stocks_from_list()
        cfg = load_config()
        cfg['user_stocks'] = stocks
        cfg['refresh_interval'] = self.refresh_interval
        # 直接保存配置，不使用节流机制
        self._throttle_save_config_params(cfg, stocks, self.refresh_interval)

    def _throttle_save_config_params(self, cfg=None, stocks=None, refresh_interval=None):
        """保存配置"""
        if cfg is not None and stocks is not None and refresh_interval is not None:
            # 直接调用方式
            self._pending_save_config = (cfg, stocks, refresh_interval)
        else:
            # 从当前状态获取参数
            stocks = self.get_stocks_from_list()
            cfg = load_config()
            cfg['user_stocks'] = stocks
            cfg['refresh_interval'] = self.refresh_interval
            self._pending_save_config = (cfg, stocks, self.refresh_interval)
        
        # 直接保存配置，不使用节流定时器
        if self._save_throttle_timer.isActive():
            self._save_throttle_timer.stop()
        self._throttled_save_config()

    def _throttled_save_config(self):
        """保存配置"""
        if self._pending_save_config:
            cfg, stocks, refresh_interval = self._pending_save_config
            # 直接保存配置，不使用后台线程
            self._save_config_and_emit_signal_wrapper(cfg, stocks, refresh_interval)
            self._pending_save_config = None
            
    def _save_config_and_emit_signal_wrapper(self, cfg, stocks, refresh_interval):
        """包装_save_config_and_emit_signal方法的包装器"""
        # 确保在保存前重新加载配置以避免覆盖其他设置
        try:
            from ..config.manager import load_config, save_config
            current_cfg = load_config()
            current_cfg.update(cfg)
            save_config(current_cfg)
        except Exception as e:
            # 如果重新加载失败，则直接保存传入的配置
            from ..config.manager import save_config
            save_config(cfg)
        
        # 使用QueuedConnection避免阻塞UI
        self.config_changed.emit(stocks, refresh_interval)

    def closeEvent(self, a0):
        """
        关闭事件处理
        
        Args:
            a0: 关闭事件对象
        """
        cfg = load_config()
        pos = self.pos()
        cfg['settings_dialog_pos'] = [int(pos.x()), int(pos.y())]
        

        
        save_config(cfg)
        # 关键：关闭时让主界面指针置空，防止多实例
        p = self.parent()
        if p is not None and hasattr(p, 'settings_dialog'):
            setattr(p, 'settings_dialog', None)
        super(SettingsDialog, self).closeEvent(a0)

    def is_startup_enabled(self):
        """
        检查是否已设置开机启动
        
        Returns:
            bool: 是否已设置开机启动
        """
        import os
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_dir, "StockMonitor.lnk")
        return os.path.exists(shortcut_path)

    def on_startup_checkbox_changed(self, state):
        """
        开机启动复选框状态改变处理
        
        Args:
            state: 复选框状态
        """
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
        # 将检查更新功能移到设置面板中
        self.settings_panel.parent_dialog = self  # type: ignore
        self.settings_panel.check_update()
        
    def _check_update_impl(self):
        """检查更新的实际实现"""
        import requests, re, os, sys, zipfile, tempfile, subprocess
        from packaging import version
        from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
        from PyQt5 import QtGui
        from ..network.manager import NetworkManager
        from ..config.manager import CONFIG_DIR
        GITHUB_API = "https://api.github.com/repos/leo8912/stock_monitor/releases/latest"
        try:
            # 使用新的网络管理器
            network_manager = NetworkManager()
            data = network_manager.github_api_request(GITHUB_API)
            
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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)  # type: ignore
            if reply != QMessageBox.StandardButton.Yes:  # type: ignore
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
            QMessageBox.warning(self, "检查更新", f"检查更新时发生错误：{e}")

    def get_stocks_from_list(self):
        """
        从股票列表中提取股票代码
        
        Returns:
            list: 股票代码列表
        """
        stocks = []
        # 使用count()方法获取项目数量，然后逐个处理
        for i in range(self.stock_list.count()):
            item = self.stock_list.item(i)
            if item is not None:
                text = item.text().strip()
                # 修复港股代码保存问题
                if text.startswith(('🇭🇰', '⭐️', '📈', '📊', '🏦', '🛡️', '⛽️', '🚗', '💻')):
                    text = text[2:].strip()  # 移除emoji
                
                code = None
                # 特殊处理港股，直接提取代码
                if text.startswith('hk'):
                    # 港股代码格式为hkxxxxx
                    parts = text.split()
                    if len(parts) >= 1:
                        code = parts[0]  # 港股代码就是第一部分
                else:
                    # 提取最后的股票代码部分
                    parts = text.split()
                    if len(parts) >= 2:
                        code = parts[-1]
                
                # 确保代码有效后再添加
                if code:
                    # 格式化股票代码
                    from stock_monitor.utils.helpers import format_stock_code
                    formatted_code = format_stock_code(code)
                    if formatted_code:
                        stocks.append(formatted_code)
                    else:
                        # 如果格式化失败，但代码以hk开头，则直接添加
                        if code.startswith('hk') and len(code) == 7 and code[2:].isdigit():
                            stocks.append(code)
        return stocks
