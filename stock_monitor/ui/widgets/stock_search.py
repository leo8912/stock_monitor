""" 
股票搜索组件 
提供股票搜索和选择功能 

该模块包含StockSearchWidget类，用于搜索和添加自选股。 
""" 

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal

from stock_monitor.utils.logger import app_logger 
from stock_monitor.data.stock.stocks import enrich_pinyin 
from stock_monitor.utils.helpers import get_stock_emoji 


class StockSearchWidget(QtWidgets.QWidget): 
    """ 
    股票搜索控件 
    提供股票搜索、选择和添加功能 
    """ 
    # 定义信号，当用户添加股票时发出 
    stock_added = pyqtSignal(str, str)  # code, name 
    
    def __init__(self, stock_data=None, stock_list=None, sync_callback=None, parent=None): 
        """ 
        初始化股票搜索控件 
        
        Args: 
            stock_data: 股票数据列表 
            stock_list: 股票列表控件引用 
            sync_callback: 同步回调函数 
            parent: 父级控件 
        """ 
        super(StockSearchWidget, self).__init__(parent) 
        self.stock_data = stock_data or [] 
        self.stock_list = stock_list 
        self.sync_callback = sync_callback 
        self.filtered_stocks = [] 
        # 添加搜索节流定时器 
        self._search_throttle_timer = QtCore.QTimer(self) 
        self._search_throttle_timer.setSingleShot(True) 
        self._search_throttle_timer.timeout.connect(self._perform_search)  # type: ignore 
        self._pending_search_text = "" 
        self.init_ui() 
        
        # 如果提供了股票数据，则丰富拼音信息 
        if self.stock_data: 
            self.stock_data = self._enrich_pinyin(self.stock_data)

    def _enrich_pinyin(self, stock_list):
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
        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
                border-radius: 8px;
                font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self) 
        # 调整间距和边距
        layout.setSpacing(16) 
        layout.setContentsMargins(16, 16, 16, 16) 
        
        # 标题 
        title = QtWidgets.QLabel("🔍 添加自选股") 
        # 增大字体大小并居中显示
        title.setStyleSheet("""
            QLabel {
                color: #000000;
                font-size: 30px;
                font-weight: bold;
                background: transparent;
                padding: 0;
                text-align: center;
            }
        """)
        title.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
        layout.addWidget(title) 
        
        # 搜索框 
        self.search_input = QtWidgets.QLineEdit() 
        # 增大字体大小
        self.search_input.setPlaceholderText("📝 输入股票代码、名称或拼音...") 
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                color: #000000;
                font-size: 20px;
                border-radius: 8px;
                border: 2px solid #cccccc;
                padding: 14px 18px;
                min-height: 32px;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
                background: #ffffff;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)  # type: ignore 
        layout.addWidget(self.search_input) 
        
        # 搜索结果列表 (创建空列表，避免初始化时加载数据)
        self.result_list = QtWidgets.QListWidget() 
        self.result_list.itemClicked.connect(self.on_item_clicked)  # type: ignore 
        # 增大字体大小并居中显示
        self.result_list.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                color: #000000;
                font-size: 20px;
                border-radius: 8px;
                border: 2px solid #cccccc;
                outline: none;
                padding: 10px;
                min-height: 320px;
            }
            QListWidget::item {
                height: 50px;
                border-radius: 6px;
                padding: 0 18px;
                margin: 6px 10px;
                text-align: center;
            }
            QListWidget::item:selected {
                background: #0078d4;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background: #e0e0e0;
            }
            /* 滚动条样式 */
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        # 设置最小高度但不填充数据
        self.result_list.setMinimumHeight(320)
        layout.addWidget(self.result_list) 
        
        # 添加按钮 
        self.add_btn = QtWidgets.QPushButton("➕ 添加选中") 
        self.add_btn.clicked.connect(self.add_selected_stock)  # type: ignore 
        self.add_btn.setEnabled(False) 
        # 增大字体大小和按钮尺寸
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: #ffffff;
                font-size: 20px;
                border-radius: 8px;
                padding: 14px 22px;
                border: none;
                font-weight: bold;
                min-width: 140px;
                min-height: 50px;
                max-height: 50px;
            }
            QPushButton:hover {
                background: #006cbe;
            }
            QPushButton:pressed {
                background: #005ba1;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
        """)
        # 增大按钮尺寸
        self.add_btn.setFixedWidth(140)
        self.add_btn.setFixedHeight(50)
        layout.addWidget(self.add_btn) 
        # 调整间距
        layout.addSpacing(10)
        layout.setAlignment(self.add_btn, QtCore.Qt.AlignmentFlag.AlignHCenter)
        
    def _on_search_text_changed(self, text): 
        """ 
        搜索框文本改变时的处理函数（节流版本） 
        
        Args: 
            text: 输入的文本 
        """ 
        self._pending_search_text = text.strip() 
        # 节流处理，延迟150ms执行搜索 
        if self._search_throttle_timer.isActive(): 
            self._search_throttle_timer.stop() 
        self._search_throttle_timer.start(150) 
        
    def _perform_search(self): 
        """执行实际的搜索操作""" 
        self.on_text_changed(self._pending_search_text) 
        
    def on_text_changed(self, text):
        """
        搜索框文本改变时的处理函数
        
        Args:
            text: 输入的文本
        """
        text = text.strip().lower()
        self.filtered_stocks = []
        self.result_list.clear()
        
        if text:
            # 根据输入文本过滤股票，并计算匹配度和优先级
            matched_stocks = []
            for stock in self.stock_data:
                code = stock['code']
                name = stock['name']
                pinyin = stock.get('pinyin', '')
                abbr = stock.get('abbr', '')
                
                # 计算匹配分数
                score = 0
                if text == code:  # 完全匹配代码
                    score = 100
                elif text in code:  # 部分匹配代码
                    score = 80
                elif text.lower() == name.lower():  # 完全匹配名称
                    score = 90
                elif text.lower() in name.lower():  # 部分匹配名称
                    score = 70
                elif text.lower() == pinyin:  # 完全匹配全拼
                    score = 85
                elif text.lower() in pinyin:  # 部分匹配全拼
                    score = 60
                elif text.lower() == abbr:  # 完全匹配首字母
                    score = 80
                elif text.lower() in abbr:  # 部分匹配首字母
                    score = 50
                
                # 计算优先级，A股优先
                priority = 0
                if code.startswith(('sh', 'sz')) and not code.startswith(('sh000', 'sz399')):
                    priority = 10  # A股最高优先级
                elif code.startswith(('sh000', 'sz399')):
                    priority = 5   # 指数次优先级
                elif code.startswith('hk'):
                    priority = 1   # 港股较低优先级
                
                # 如果有匹配分数，则添加到结果中
                if score > 0:
                    matched_stocks.append((stock, score, priority))
            
            # 按优先级和匹配分数排序，优先级高的在前，匹配度高的在前
            matched_stocks.sort(key=lambda x: (-x[2], -x[1]))
            self.filtered_stocks = [stock for stock, score, priority in matched_stocks]
            
            # 显示前30个匹配结果（增加显示数量）
            for stock in self.filtered_stocks[:30]:
                code = stock['code']
                name = stock['name']
                emoji = get_stock_emoji(code, name)
                display_text = f"{emoji} {name} ({code})"
                item = QtWidgets.QListWidgetItem(display_text)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, stock)  # type: ignore
                self.result_list.addItem(item)
                
        self.add_btn.setEnabled(False)

    def on_item_clicked(self, item): 
        """ 
        列表项被点击时的处理函数 
        
        Args: 
            item: 被点击的列表项 
        """ 
        self.add_btn.setEnabled(True) 

    def add_selected_stock(self): 
        """添加选中的股票到自选股列表""" 
        current_item = self.result_list.currentItem() 
        if not current_item: 
            return 
            
        stock = current_item.data(QtCore.Qt.ItemDataRole.UserRole)  # type: ignore 
        if not stock: 
            return 
            
        code = stock['code'] 
        name = stock['name'] 
        
        # 检查股票是否已存在 
        existing_items = [] 
        if self.stock_list: 
            for i in range(self.stock_list.count()): 
                item = self.stock_list.item(i) 
                if item and code in item.text(): 
                    existing_items.append(item) 
        
        if existing_items: 
            # 如果股票已存在，给出提示 
            QtWidgets.QMessageBox.information(self, "提示", f"股票 {name} 已在自选股列表中") 
            return 
            
        # 添加到股票列表 
        if self.stock_list: 
            from stock_monitor.utils.helpers import get_stock_emoji 
            emoji = get_stock_emoji(code, name) 
            # 对于港股，只显示中文名称部分 
            if code.startswith('hk') and name: 
                # 去除"-"及之后的部分，只保留中文名称 
                if '-' in name: 
                    name = name.split('-')[0].strip() 
                display = f"{emoji} {name} ({code})" 
            elif name: 
                display = f"{emoji} {name} ({code})" 
            else: 
                display = f"{emoji} {code}" 
            self.stock_list.addItem(display) 
            
        # 发出信号 
        self.stock_added.emit(code, name) 
        
        # 调用同步回调 
        if self.sync_callback: 
            self.sync_callback() 
            
        # 清空搜索框和结果列表 
        self.search_input.clear() 
        self.result_list.clear() 
        self.add_btn.setEnabled(False) 
        
        app_logger.info(f"添加自选股: {code} {name}")