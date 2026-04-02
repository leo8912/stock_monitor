"""
股票搜索组件
提供股票搜索和选择功能

该模块包含StockSearchWidget类，用于搜索和添加自选股。
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import pyqtSignal

from stock_monitor.data.stock.stock_data_source import StockDataSource
from stock_monitor.data.stock.stocks import enrich_pinyin
from stock_monitor.utils.helpers import get_stock_emoji
from stock_monitor.utils.logger import app_logger


class StockSearchWidget(QtWidgets.QWidget):
    """
    股票搜索控件
    提供股票搜索、选择和添加功能
    """

    # 定义信号，当用户添加股票时发出
    stock_added = pyqtSignal(str, str)  # code, name

    def __init__(self, stock_data_source: StockDataSource):
        super().__init__()
        self.stock_data_source = stock_data_source
        self._pending_search_text = ""
        self._search_throttle_timer = QtCore.QTimer(self)
        self._search_throttle_timer.setSingleShot(True)
        self._search_throttle_timer.timeout.connect(self._perform_search)
        self.filtered_stocks = []  # 添加这个属性以满足测试要求
        self.setup_ui()
        self._load_stock_data()

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

    def setup_ui(self):
        """初始化用户界面"""
        # 允许接收拖拽事件
        self.setAcceptDrops(True)
        # 移除inline stylesheet, 设置ObjectName以便在QSS中针对此组件特殊样式
        self.setObjectName("StockSearchWidget")

        # 创建主布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 创建搜索框
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 输入股票代码/名称/拼音/首字母")
        self._set_search_input_style()
        # 连接信号
        self.search_input.textChanged.connect(self._on_search_text_changed)  # type: ignore
        self.search_input.returnPressed.connect(self._on_return_pressed)  # type: ignore
        layout.addWidget(self.search_input)

        # 创建结果列表
        self.result_list = QtWidgets.QListWidget()
        self._set_result_list_style()
        self.result_list.clicked.connect(self.on_item_clicked)  # type: ignore
        layout.addWidget(self.result_list)

        # 创建添加按钮
        self.add_btn = QtWidgets.QPushButton("➕ 添加到自选股")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.add_selected_stock)  # type: ignore
        self._set_add_button_style()
        # 调整按钮尺寸
        self.add_btn.setFixedHeight(30)
        layout.addWidget(self.add_btn)
        # 调整间距
        layout.addSpacing(10)
        layout.setAlignment(self.add_btn, QtCore.Qt.AlignmentFlag.AlignHCenter)

    def _set_search_input_style(self):
        """设置搜索输入框样式"""
        pass

    def _set_result_list_style(self):
        """设置结果列表样式"""
        pass

    def _set_add_button_style(self):
        """设置添加按钮样式"""
        # 设置ObjectName以获取主级样式
        self.add_btn.setObjectName("PrimaryButton")

    def _load_stock_data(self):
        """加载股票数据"""
        try:
            # 从数据源加载股票数据
            self.stock_data = self.stock_data_source.get_all_stocks()
            app_logger.debug(f"从数据源加载了 {len(self.stock_data)} 条股票数据")
            # 丰富拼音信息
            if self.stock_data:
                self.stock_data = self._enrich_pinyin(self.stock_data)
        except Exception as e:
            app_logger.error(f"从数据源加载股票数据失败: {e}")
            self.stock_data = []

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

    def _on_return_pressed(self):
        """处理回车键按下事件"""
        # 如果有搜索结果，添加第一个结果
        if self.result_list.count() > 0:
            self.result_list.setCurrentRow(0)  # 选中第一项
            self.add_selected_stock()  # 添加选中的股票
        # 清空搜索框
        self.search_input.clear()
        self.result_list.clear()
        self.add_btn.setEnabled(False)

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
        self.result_list.clear()

        if text:
            # 使用数据源进行搜索
            self.filtered_stocks = self.stock_data_source.search_stocks(text, limit=30)

            # 显示匹配结果
            for stock in self.filtered_stocks:
                code = stock["code"]
                name = stock["name"]
                emoji = get_stock_emoji(code, name)
                display_text = f"{emoji} {name} ({code})"
                item = QtWidgets.QListWidgetItem(display_text)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, stock)  # type: ignore
                self.result_list.addItem(item)

        else:
            # 当文本为空时，清空过滤后的股票列表
            self.filtered_stocks = []

        self.add_btn.setEnabled(False)

    def on_item_clicked(self, item):
        """
        列表项被点击时的处理函数

        Args:
            item: 被点击的列表项
        """
        self.add_btn.setEnabled(True)

    def add_selected_stock(self):
        """添加选中的股票，触发信号"""
        current_item = self.result_list.currentItem()
        if not current_item:
            return

        stock = current_item.data(QtCore.Qt.ItemDataRole.UserRole)  # type: ignore
        if not stock:
            return

        code = stock["code"]
        name = stock["name"]

        # 发出信号，只发送股票代码与名称，后续判重及添加交由父组件
        self.stock_added.emit(code, name)

        # 清空搜索框和结果列表
        self.search_input.clear()
        self.result_list.clear()
        self.add_btn.setEnabled(False)

        app_logger.info(f"触发添加自选股信号: {code} {name}")

    def _format_stock_display_text(self, code: str, name: str, emoji: str) -> str:
        """
        格式化股票显示文本

        Args:
            code (str): 股票代码
            name (str): 股票名称
            emoji (str): 股票emoji

        Returns:
            str: 格式化后的显示文本
        """
        # 对于港股，只显示中文名称部分
        if code.startswith("hk") and name:
            # 去除"-"及之后的部分，只保留中文名称
            if "-" in name:
                name = name.split("-")[0].strip()
            return f"{emoji} {name} ({code})"
        elif name:
            return f"{emoji} {name} ({code})"
        else:
            return f"{emoji} {code}"

    def closeEvent(self, event: QtGui.QCloseEvent):
        """
        窗口关闭事件处理 - 清理定时器、断开信号连接

        Args:
            event: 关闭事件对象
        """
        try:
            # 1. 停止并清理定时器
            if hasattr(self, "_search_throttle_timer") and self._search_throttle_timer:
                self._search_throttle_timer.stop()
                self._search_throttle_timer.deleteLater()

            # 2. 断开数据源相关连接（如果有）
            if hasattr(self, "stock_data_source"):
                # 清空股票数据引用，帮助 GC
                self.stock_data = []
                self.filtered_stocks = []
        finally:
            super().closeEvent(event)
