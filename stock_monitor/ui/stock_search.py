import sys
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from pypinyin import lazy_pinyin, Style
from ..utils.logger import app_logger
from ..utils.helpers import get_stock_emoji, resource_path


class StockSearchWidget(QtWidgets.QWidget):
    """股票搜索组件"""
    
    def __init__(self, parent=None, stock_data=None, stock_list=None, sync_callback=None):
        super(StockSearchWidget, self).__init__(parent)
        self.stock_data = stock_data or []
        self.stock_list = stock_list
        self.sync_callback = sync_callback
        self.selected_stocks = []
        self.init_ui()
        
    def init_ui(self):
        """初始化搜索界面"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("输入股票代码/名称/拼音")
        self.search_edit.textChanged.connect(self.on_search)
        self.search_edit.returnPressed.connect(self.add_first_search_result)
        self.search_edit.setFixedHeight(44)
        layout.addWidget(self.search_edit)
        
        self.search_results = QtWidgets.QListWidget()
        self.search_results.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.search_results.itemDoubleClicked.connect(self.add_selected_stock)
        self.search_results.setFixedSize(340, 480)
        layout.addWidget(self.search_results)
        
    def load_stock_data(self):
        """加载股票数据"""
        try:
            with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            app_logger.warning(f"无法加载本地股票数据: {e}")
            return []
            
    def enrich_pinyin(self, stock_list):
        """丰富股票的拼音信息"""
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
        
    def on_search(self, text):
        """搜索股票"""
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
            pinyin_match = text in s.get('pinyin', '')
            abbr_match = text in s.get('abbr', '')
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
        """添加选中的股票"""
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
        """添加股票到列表"""
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
            self.sync_callback()
            
    def get_name_by_code(self, code):
        """根据代码获取股票名称"""
        for s in self.stock_data:
            if s['code'] == code:
                return s['name']
        return ""