"""
股票搜索组件模块
提供股票搜索和选择功能
"""

import sys
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from ..utils.logger import app_logger
from ..utils.helpers import get_stock_emoji, resource_path
from ..data.stocks import load_stock_data, enrich_pinyin
from ..data.quotation import get_name_by_code as get_stock_name_by_code


class StockSearchWidget(QtWidgets.QWidget):
    """股票搜索组件"""
    
    def __init__(self, parent=None, stock_data=None, stock_list=None, sync_callback=None):
        """
        初始化股票搜索组件
        
        Args:
            parent: 父级控件
            stock_data: 股票数据
            stock_list: 股票列表控件
            sync_callback: 同步回调函数
        """
        super(StockSearchWidget, self).__init__(parent)
        self.stock_data = stock_data or []
        self.stock_list = stock_list
        self.sync_callback = sync_callback
        self.selected_stocks = []
        # 添加搜索节流定时器
        self.search_timer = QtCore.QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)  # type: ignore
        self.pending_search_text = ""
        self.init_ui()
        
    def init_ui(self):
        """初始化搜索界面"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("输入股票代码/名称/拼音")
        self.search_edit.textChanged.connect(self.on_search)  # type: ignore
        self.search_edit.returnPressed.connect(self.add_first_search_result)  # type: ignore
        self.search_edit.setFixedHeight(44)
        layout.addWidget(self.search_edit)
        
        self.search_results = QtWidgets.QListWidget()
        self.search_results.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.search_results.itemDoubleClicked.connect(self.add_selected_stock)  # type: ignore
        self.search_results.setFixedSize(340, 480)
        layout.addWidget(self.search_results)
        
    def load_stock_data(self):
        """加载股票数据"""
        try:
            # 使用缓存机制加载股票数据
            from ..utils.stock_cache import global_stock_cache
            return global_stock_cache.get_stock_data()
        except Exception as e:
            app_logger.warning(f"无法加载本地股票数据: {e}")
            # 使用统一的数据加载函数
            return load_stock_data()
            
    def enrich_pinyin(self, stock_list):
        """
        丰富股票的拼音信息
        
        Args:
            stock_list (list): 股票列表
            
        Returns:
            list: 添加了拼音信息的股票列表
        """
        # 使用统一的拼音处理函数
        return enrich_pinyin(stock_list)
        
    def on_search(self, text):
        """
        搜索股票
        
        Args:
            text (str): 搜索文本
        """
        # 使用节流机制优化搜索性能
        self.pending_search_text = text.strip()
        self.search_timer.start(100)  # 100ms节流延迟
        
    def _perform_search(self):
        """执行实际的搜索操作"""
        text = self.pending_search_text.lower()
        self.search_results.clear()
        if not text:
            return
            
        def is_index(stock):
            return stock['code'].startswith(('sh000', 'sz399', 'sz159', 'sh510')) or '指数' in stock['name'] or '板块' in stock['name']
            
        # 支持拼音、首字母、代码、名称模糊匹配，ST股票去前缀
        results = []
        # 优化搜索算法：先进行简单的过滤，再进行复杂的匹配
        for s in self.stock_data:
            # 先进行简单的包含检查
            if (text in s['code'].lower() or 
                text in s['name'].lower() or 
                text in s.get('pinyin', '') or 
                text in s.get('abbr', '')):
                results.append(s)
            else:
                # 对于ST类，去掉*ST/ST前缀后再匹配
                base = s['name'].replace('*', '').replace('ST', '').replace(' ', '').lower()
                if text in base:
                    results.append(s)
        
        # 实现智能排序，将匹配度高的结果排在前面
        def match_score(stock):
            score = 0
            code_lower = stock['code'].lower()
            name_lower = stock['name'].lower()
            pinyin = stock.get('pinyin', '')
            abbr = stock.get('abbr', '')
            base = stock['name'].replace('*', '').replace('ST', '').replace(' ', '').lower()
            
            # 精确匹配得分最高
            if text == code_lower:
                score += 1000
            elif text == name_lower:
                score += 900
            elif text == pinyin:
                score += 800
            elif text == abbr:
                score += 700
            elif text == base:
                score += 600
            # 前缀匹配得分较高
            elif code_lower.startswith(text):
                score += 500
            elif name_lower.startswith(text):
                score += 400
            elif pinyin.startswith(text):
                score += 300
            elif abbr.startswith(text):
                score += 200
            elif base.startswith(text):
                score += 100
            # 包含匹配得分一般
            elif text in code_lower:
                score += 50
            elif text in name_lower:
                score += 40
            elif text in pinyin:
                score += 30
            elif text in abbr:
                score += 20
            elif text in base:
                score += 10
                
            # 优先显示非指数类股票
            if not is_index(stock):
                score += 50
                
            return score
            
        # 根据匹配度排序
        results.sort(key=lambda s: (-match_score(s), s['code']))
            
        # 限制显示结果数量
        for s in results[:50]:
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
                base = s['name'].replace('*', '').replace('ST', '').replace(' ', '').lower()
                parts_to_search = [s['code'].lower(), s['name'].lower(), s.get('pinyin', ''), s.get('abbr', ''), base]
                for part in parts_to_search:
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
        """
        添加选中的股票
        
        Args:
            item: 选中的列表项
        """
        # item.text()格式为"名称 代码"
        code = item.text().split()[-1]
        name = " ".join(item.text().split()[:-1])
        self.add_stock_to_list(code)
        
    def add_first_search_result(self):
        """添加第一个搜索结果"""
        if self.search_results.count() > 0:
            item = self.search_results.item(0)
            self.add_selected_stock(item)
            
    def add_stock_to_list(self, code):
        """
        添加股票到列表
        
        Args:
            code (str): 股票代码
        """
        if not self.stock_list:
            return
            
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
        if self.sync_callback:
            # 使用 QTimer.singleShot 延迟执行同步回调，避免阻塞UI
            QtCore.QTimer.singleShot(100, self.sync_callback)
            
    def get_name_by_code(self, code):
        """
        根据代码获取股票名称
        
        Args:
            code (str): 股票代码
            
        Returns:
            str: 股票名称
        """
        # 使用统一的获取股票名称函数
        return get_stock_name_by_code(code)