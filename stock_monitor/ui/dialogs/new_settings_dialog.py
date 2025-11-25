"""
新的设置对话框模块
根据settings_ui_requirements.md要求重新设计实现
"""

import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal

# 尝试导入win32com用于创建开机启动快捷方式
try:
    from win32com.client import Dispatch
    WIN32_AVAILABLE = True
except ImportError:
    Dispatch = None
    WIN32_AVAILABLE = False

# 导入项目相关模块
from stock_monitor.utils.logger import app_logger
from stock_monitor.ui.widgets.stock_search import StockSearchWidget
from stock_monitor.utils.helpers import get_stock_emoji, resource_path
from stock_monitor.config.manager import load_config, save_config
from stock_monitor.version import __version__
from stock_monitor.data.stock.stocks import enrich_pinyin
from stock_monitor.data.market.quotation import get_name_by_code as get_stock_name_by_code


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
        # 设置拖拽相关属性，允许内部移动
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        # 设置选择模式为扩展选择（可多选）
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        # 启用拖拽功能
        self.setDragEnabled(True)
        # 启用放置功能
        self.setAcceptDrops(True)
        # 显示拖拽放置指示器
        self.setDropIndicatorShown(True)
        
        # 初始化界面样式
        self.init_ui()
        
        # 创建节流定时器，用于优化频繁的拖拽事件
        self._throttle_timer = QtCore.QTimer(self)
        self._throttle_timer.setSingleShot(True)
        # 连接定时器超时信号到实际处理函数
        self._throttle_timer.timeout.connect(self._on_items_reordered)  # type: ignore
        # 连接项目重新排序信号到节流处理函数
        self.items_reordered.connect(self._throttle_reorder)  # type: ignore

    def init_ui(self):
        """初始化UI样式"""
        self.setStyleSheet("""
            QListWidget {
                background: #ffffff;           /* 背景色为白色 */
                color: #212529;                /* 文字颜色为深灰色 */
                font-size: 18px;               /* 字体大小 */
                border-radius: 8px;            /* 圆角半径 */
                border: 1px solid #ced4da;     /* 边框颜色 */
                outline: none;                 /* 无轮廓 */
                padding: 6px;                  /* 内边距 */
            }
            QListWidget::item {
                height: 45px;                  /* 项目高度 */
                border-radius: 4px;            /* 项目圆角半径 */
                padding: 0 12px;               /* 项目内边距 */
                margin: 2px 0;                 /* 项目外边距 */
            }
            QListWidget::item:selected {
                background: #e3f2fd;           /* 选中项背景色 */
                color: #212529;                /* 选中项文字颜色 */
            }
            QListWidget::item:hover {
                background: #f8f9fa;           /* 悬停项背景色 */
            }
            /* 滚动条样式 */
            QScrollBar:vertical {
                border: none;                  /* 无边框 */
                background: transparent;       /* 背景透明 */
                width: 10px;                   /* 宽度10px */
                margin: 0px 0px 0px 0px;       /* 外边距 */
            }
            QScrollBar::handle:vertical {
                background: #cccccc;           /* 滚动条颜色 */
                border-radius: 5px;            /* 滚动条圆角 */
                min-height: 20px;              /* 最小高度 */
            }
            QScrollBar::handle:vertical:hover {
                background: #777777;           /* 滚动条悬停颜色 */
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;                   /* 隐藏滚动条箭头 */
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;              /* 页面滚动区域无背景 */
            }
        """)

    def dropEvent(self, event):
        """
        拖拽放置事件处理
        
        Args:
            event: 拖拽事件对象
        """
        # 调用父类的拖拽放置事件处理
        super(StockListWidget, self).dropEvent(event)
        # 发出重新排序信号而不是直接调用回调
        self.items_reordered.emit()

    def _throttle_reorder(self):
        """节流处理重新排序事件"""
        # 如果定时器正在运行，则停止它
        if self._throttle_timer.isActive():
            self._throttle_timer.stop()
        # 启动定时器，延迟100ms执行
        self._throttle_timer.start(100)  # 100ms节流延迟

    def _on_items_reordered(self):
        """实际处理重新排序的回调"""
        # 如果设置了同步回调函数，则调用它
        if self.sync_callback:
            self.sync_callback()


class StockDataLoader(QtCore.QObject):
    """
    股票数据加载器
    在后台线程中加载股票数据，避免阻塞UI
    """
    # 定义信号
    data_loaded = pyqtSignal(list)  # 股票数据加载完成信号
    loading_error = pyqtSignal(str)  # 加载错误信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def load_stock_data(self):
        """
        在后台线程中加载股票数据
        """
        try:
            # 使用缓存机制加载股票数据
            from stock_monitor.utils.stock_cache import global_stock_cache
            stock_data = global_stock_cache.get_stock_data()
            # 发出数据加载完成信号
            self.data_loaded.emit(stock_data)
        except Exception as e:
            # 如果无法加载本地股票数据，记录警告并使用网络数据
            app_logger.warning(f"无法加载本地股票数据: {e}，将使用网络数据")
            try:
                import easyquotation
                # 使用sina行情源
                quotation = easyquotation.use('sina')
                
                # 获取一些热门股票作为默认数据
                stock_codes = ['sh600460', 'sh603986', 'sh600030', 'sh000001', 'sz000001', 'sz000002', 'sh600036']
                stock_data = []
                
                # 移除前缀以获取数据
                pure_codes = [code[2:] if code.startswith(('sh', 'sz')) else code for code in stock_codes]
                try:
                    # 获取股票数据
                    data = quotation.stocks(pure_codes)  # type: ignore
                except Exception:
                    # 如果stocks方法不可用，尝试使用all方法
                    data = getattr(quotation, 'all', {})
                    if callable(data):
                        data = data()
                
                # 处理获取到的数据
                if isinstance(data, dict) and data:
                    for i, code in enumerate(stock_codes):
                        pure_code = pure_codes[i]
                        # 检查数据是否有效
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
                stock_data = self._enrich_pinyin(stock_data)
                # 发出数据加载完成信号
                self.data_loaded.emit(stock_data)
            except Exception as e2:
                # 如果无法从网络获取股票数据，记录错误并发出错误信号
                error_msg = f"无法从网络获取股票数据: {e2}"
                app_logger.error(error_msg)
                self.loading_error.emit(error_msg)
    
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


class NewSettingsDialog(QtWidgets.QDialog): 
    """ 
    新的设置对话框类 
    提供用户配置界面，包括自选股设置和应用设置 
    """ 
    # 定义配置更改信号，参数为股票列表和刷新间隔 
    config_changed = pyqtSignal(list, int)  # stocks, refresh_interval 
    
    def __init__(self, parent=None, main_window=None): 
        """ 
        初始化设置对话框 
        
        Args: 
            parent: 父级控件 
            main_window: 主窗口引用 
        """ 
        # 调用父类初始化 
        super(NewSettingsDialog, self).__init__(parent) 
        # 设置窗口标题 
        self.setWindowTitle("设置") 
        # 设置窗口图标 
        self.setWindowIcon(QtGui.QIcon(resource_path('icon.ico'))) 
        # 去掉右上角问号按钮 
        if hasattr(QtCore.Qt, 'WindowContextHelpButtonHint'): 
            self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)  # type: ignore 
        # 设置为模态对话框 
        self.setModal(True) 
        # 设置最小尺寸 
        self.setMinimumSize(800, 600) 
        # 设置默认尺寸 
        self.resize(1000, 700) 
        # 保存主窗口引用 
        self.main_window = main_window 
        # 初始化选中股票列表 
        self.selected_stocks = [] 
        # 初始化刷新间隔 
        self.refresh_interval = 5 
        # 初始化待保存配置 
        self._pending_save_config = None 
        # 初始化股票数据为空列表
        self.stock_data = []
        # 初始化用户界面 
        self.init_ui() 
        # 启动后台线程加载股票数据
        self._load_stock_data_async()
        # 加载当前股票列表 
        self.load_current_stocks() 
        # 加载刷新间隔配置 
        self.load_refresh_interval()

    def _load_stock_data_async(self):
        """
        异步加载股票数据
        使用后台线程加载股票数据，避免阻塞UI线程
        """
        # 使用QTimer来确保在事件循环之后才开始加载数据
        # 这样可以确保UI先显示出来
        QtCore.QTimer.singleShot(100, self._start_data_loading_thread)  # type: ignore

    def _start_data_loading_thread(self):
        """启动数据加载线程"""
        # 创建线程和数据加载器
        self._data_loader_thread = QtCore.QThread()
        self._data_loader = StockDataLoader()
        
        # 将数据加载器移动到线程中
        self._data_loader.moveToThread(self._data_loader_thread)
        
        # 连接信号和槽
        self._data_loader_thread.started.connect(self._data_loader.load_stock_data)  # type: ignore
        self._data_loader.data_loaded.connect(self._on_stock_data_loaded)  # type: ignore
        self._data_loader.loading_error.connect(self._on_stock_data_error)  # type: ignore
        self._data_loader.data_loaded.connect(self._data_loader_thread.quit)  # type: ignore
        self._data_loader.loading_error.connect(self._data_loader_thread.quit)  # type: ignore
        self._data_loader_thread.finished.connect(self._data_loader.deleteLater)  # type: ignore
        self._data_loader_thread.finished.connect(self._data_loader_thread.deleteLater)  # type: ignore
        
        # 启动线程
        self._data_loader_thread.start()

    def _on_stock_data_loaded(self, stock_data):
        """
        股票数据加载完成的处理函数
        
        Args:
            stock_data: 加载完成的股票数据
        """
        # 更新股票数据
        self.stock_data = stock_data
        # 更新股票搜索组件的股票数据
        if hasattr(self, 'stock_search') and self.stock_search:
            self.stock_search.stock_data = stock_data
            # 如果股票数据不为空，丰富拼音信息
            if stock_data:
                self.stock_search.stock_data = self.stock_search._enrich_pinyin(stock_data)  # type: ignore

    def _on_stock_data_error(self, error_msg):
        """
        股票数据加载错误的处理函数
        
        Args:
            error_msg: 错误信息
        """
        # 记录错误日志
        app_logger.error(f"加载股票数据时发生错误: {error_msg}")
        # 显示错误提示
        QtWidgets.QMessageBox.warning(self, "加载失败", f"加载股票数据失败: {error_msg}")

    def init_ui(self):
        """初始化用户界面"""
        # 设置整体样式
        self.setStyleSheet("""
            QDialog {
                background: #f8f9fa;           /* 背景色 */
                font-family: "Microsoft YaHei", "微软雅黑";
            }
        """)
        
        # 创建主布局
        layout = QtWidgets.QVBoxLayout(self)
        # 减小控件间距
        layout.setSpacing(15)
        # 减小边距
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建主体区域（左右分栏）
        main_splitter = QtWidgets.QHBoxLayout()
        # 减小控件间距
        main_splitter.setSpacing(20)
        # 减小边距
        main_splitter.setContentsMargins(0, 0, 0, 0)
        
        # 创建左侧添加自选股区域
        left_widget = self._create_add_stock_widget()
        # 设置宽度
        left_widget.setFixedWidth(350)
        
        # 创建右侧自选股列表区域
        right_widget = self._create_stock_list_widget()
        # 设置宽度
        right_widget.setFixedWidth(350)
        
        # 将左右区域添加到主分栏布局中
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        
        # 创建底部区域（设置选项和操作按钮在同一行）
        bottom_widget = self._create_bottom_widget()
        
        # 将所有区域添加到主布局中
        layout.addLayout(main_splitter)
        layout.addWidget(bottom_widget)
        
        # 设置整体布局
        self.setLayout(layout)
        
        # 创建定时器，用于延迟初始化复杂组件
        self._init_components_timer = QtCore.QTimer(self)
        self._init_components_timer.setSingleShot(True)
        self._init_components_timer.timeout.connect(self._init_complex_components)  # type: ignore
        # 启动定时器，1ms后初始化复杂组件
        self._init_components_timer.start(1)

    def _init_complex_components(self):
        """延迟初始化复杂组件"""
        pass

    def _create_bottom_widget(self):
        """创建底部区域，包含设置选项和操作按钮"""
        # 创建区域容器
        widget = QtWidgets.QWidget()
        # 设置样式
        widget.setStyleSheet("QWidget { background: transparent; }")
        
        # 创建水平布局
        layout = QtWidgets.QHBoxLayout(widget)
        # 减小间距
        layout.setSpacing(15)
        # 减小边距
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建设置选项区域
        settings_widget = self._create_settings_widget()
        # 移除设置区域的边距
        settings_layout = settings_widget.layout()
        if settings_layout:
            settings_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建弹性空间
        spacer = QtWidgets.QSpacerItem(20, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)  # type: ignore
        
        # 创建按钮区域
        buttons_widget = QtWidgets.QWidget()
        # 设置样式
        buttons_widget.setStyleSheet("QWidget { background: transparent; }")
        
        # 将控件添加到布局中
        layout.addWidget(settings_widget)
        layout.addSpacerItem(spacer)
        layout.addWidget(buttons_widget)
        
        # 返回创建的区域
        return widget

    def _create_add_stock_widget(self):
        """创建添加自选股区域"""
        # 创建区域容器
        widget = QtWidgets.QWidget()
        # 设置样式
        widget.setStyleSheet("""
            QWidget {
                background: #ffffff;       /* 白色背景 */
                border: 1px solid #dee2e6; /* 边框 */
                border-radius: 10px;       /* 圆角 */
            }
        """)
        
        # 创建垂直布局
        layout = QtWidgets.QVBoxLayout(widget)
        # 调整间距
        layout.setSpacing(15)
        # 调整边距
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建标题标签
        title_label = QtWidgets.QLabel("添加自选股")
        # 增大字体大小并居中显示
        title_label.setStyleSheet("""
            QLabel {
                color: #212529;                /* 文字颜色 */
                font-size: 20px;               /* 字体大小 */
                font-weight: bold;             /* 粗体 */
                text-align: center;            /* 居中对齐 */
            }
        """)
        title_label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
        
        # 创建股票搜索组件
        self.stock_search = StockSearchWidget(
            stock_data=self.stock_data,
            stock_list=None,  # 将在后面设置
            sync_callback=self.sync_to_main
        )
        
        # 将控件添加到布局中
        layout.addWidget(title_label)
        layout.addWidget(self.stock_search)
        
        # 返回创建的区域
        return widget

    def _create_stock_list_widget(self):
        """创建自选股列表区域"""
        # 创建区域容器
        widget = QtWidgets.QWidget()
        # 设置样式
        widget.setStyleSheet("""
            QWidget {
                background: #ffffff;       /* 白色背景 */
                border: 1px solid #dee2e6; /* 边框 */
                border-radius: 10px;       /* 圆角 */
            }
        """)
        
        # 创建垂直布局
        layout = QtWidgets.QVBoxLayout(widget)
        # 调整间距
        layout.setSpacing(15)
        # 调整边距
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建标题标签
        title_label = QtWidgets.QLabel("自选股列表")
        # 增大字体大小并居中显示
        title_label.setStyleSheet("""
            QLabel {
                color: #212529;                /* 文字颜色 */
                font-size: 20px;               /* 字体大小 */
                font-weight: bold;             /* 粗体 */
                text-align: center;            /* 居中对齐 */
            }
        """)
        title_label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
        
        # 创建自选股列表控件
        self.stock_list = StockListWidget(sync_callback=self.sync_to_main)
        # 设置股票搜索组件的股票列表引用
        self.stock_search.stock_list = self.stock_list
        
        # 创建删除按钮布局（居中）
        del_btn_layout = QtWidgets.QHBoxLayout()
        # 调整间距
        del_btn_layout.setSpacing(10)
        # 调整边距
        del_btn_layout.setContentsMargins(0, 0, 0, 0)
        # 添加左侧弹性空间
        del_btn_layout.addStretch(1)
        # 创建删除按钮
        self.btn_del = QtWidgets.QPushButton("🗑️ 删除选中")
        # 连接按钮点击信号到处理函数
        self.btn_del.clicked.connect(self.delete_selected_stocks)  # type: ignore
        # 增大按钮尺寸
        self.btn_del.setFixedWidth(120)
        self.btn_del.setFixedHeight(36)
        # 增大字体大小
        self.btn_del.setStyleSheet("""
            QPushButton {
                background: #dc3545;           /* 背景色 */
                color: #ffffff;                /* 文字颜色 */
                font-size: 16px;               /* 字体大小 */
                border-radius: 6px;            /* 圆角 */
                padding: 8px 16px;             /* 内边距 */
                border: none;                  /* 无边框 */
                font-weight: 600;              /* 字体粗细 */
                min-width: 120px;              /* 最小宽度 */
                min-height: 36px;              /* 最小高度 */
                max-height: 36px;              /* 固定最大高度 */
            }
            QPushButton:hover {
                background: #c82333;           /* 悬停背景色 */
            }
            QPushButton:pressed {
                background: #bd2130;           /* 按下背景色 */
            }
            QPushButton:disabled {
                background: #6c757d;           /* 禁用背景色 */
                color: #ffffff;                /* 禁用文字颜色 */
            }
        """)
        # 将按钮添加到布局中
        del_btn_layout.addWidget(self.btn_del)
        # 添加右侧弹性空间
        del_btn_layout.addStretch(1)
        
        # 将控件添加到布局中
        layout.addWidget(title_label)
        layout.addWidget(self.stock_list)
        layout.addLayout(del_btn_layout)
        
        # 返回创建的区域
        return widget

    def _create_settings_widget(self):
        """创建应用设置区域"""
        # 创建区域容器
        widget = QtWidgets.QWidget()
        # 设置样式
        widget.setStyleSheet("""
            QWidget {
                background: #ffffff;       /* 白色背景 */
                border: 1px solid #dee2e6; /* 边框 */
                border-radius: 8px;        /* 圆角 */
                padding: 12px;
            }
        """)
        
        # 创建水平布局
        layout = QtWidgets.QHBoxLayout(widget)
        # 减小间距
        layout.setSpacing(12)
        # 减小边距
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 创建左侧设置项布局
        left_layout = QtWidgets.QHBoxLayout()
        # 减小间距
        left_layout.setSpacing(12)
        # 减小边距
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建刷新频率设置布局
        freq_layout = QtWidgets.QHBoxLayout()
        # 减小间距
        freq_layout.setSpacing(8)
        # 减小边距
        freq_layout.setContentsMargins(0, 0, 0, 0)
        # 创建刷新频率标签
        freq_label = QtWidgets.QLabel("🔄 刷新频率:")
        # 减小字体大小
        freq_label.setStyleSheet("QLabel { color: #212529; font-size: 16px; font-weight: bold; }")
        # 创建刷新频率下拉框
        self.freq_combo = QtWidgets.QComboBox()
        # 添加下拉框选项
        self.freq_combo.addItems(["2秒", "5秒", "10秒", "30秒", "60秒"])
        # 设置默认选中项（5秒）
        self.freq_combo.setCurrentIndex(1)  # 默认5秒
        # 连接下拉框索引改变信号到处理函数
        self.freq_combo.currentIndexChanged.connect(self.on_settings_changed)  # type: ignore
        # 减小字体大小和控件尺寸
        self.freq_combo.setStyleSheet("""
            QComboBox {
                background: #ffffff;           /* 背景色 */
                color: #212529;                /* 文字颜色 */
                font-size: 14px;               /* 字体大小 */
                border-radius: 6px;            /* 圆角 */
                border: 1px solid #ced4da;     /* 边框 */
                padding: 6px 10px;             /* 内边距 */
                min-width: 70px;               /* 最小宽度 */
                min-height: 32px;              /* 最小高度 */
                max-height: 32px;              /* 固定最大高度 */
            }
            QComboBox:hover {
                border: 1px solid #2196f3;     /* 悬停边框颜色 */
            }
            QComboBox::drop-down {
                border: none;                  /* 下拉按钮无边框 */
                width: 20px;                   /* 下拉按钮宽度 */
            }
            QComboBox::down-arrow {
                image: url(none);              /* 无下拉箭头图片 */
                width: 0;                      /* 宽度为0 */
                height: 0;                     /* 高度为0 */
            }
            QComboBox QAbstractItemView {
                background: #ffffff;           /* 下拉列表背景色 */
                color: #212529;                /* 下拉列表文字颜色 */
                selection-background-color: #e3f2fd;  /* 选中项背景色 */
                selection-color: #212529;      /* 选中项文字颜色 */
                border: 1px solid #ced4da;     /* 下拉列表边框 */
                font-size: 14px;               /* 字体大小 */
            }
        """)
        # 将控件添加到刷新频率布局中
        freq_layout.addWidget(freq_label)
        freq_layout.addWidget(self.freq_combo)
        
        # 创建开机启动设置布局
        startup_layout = QtWidgets.QHBoxLayout()
        # 减小间距
        startup_layout.setSpacing(8)
        # 减小边距
        startup_layout.setContentsMargins(0, 0, 0, 0)
        # 创建开机启动标签
        startup_label = QtWidgets.QLabel("💻 开机启动:")
        # 减小字体大小
        startup_label.setStyleSheet("QLabel { color: #212529; font-size: 16px; font-weight: bold; }")
        # 创建开机启动复选框
        self.startup_checkbox = QtWidgets.QCheckBox()
        # 连接复选框状态改变信号到处理函数
        self.startup_checkbox.stateChanged.connect(self.on_startup_checkbox_changed)  # type: ignore
        # 连接复选框状态改变信号到设置更改处理函数
        self.startup_checkbox.stateChanged.connect(self.on_settings_changed)  # type: ignore
        # 减小字体大小和控件尺寸
        self.startup_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 6px;                  /* 文字与复选框间距 */
                font-size: 16px;               /* 字体大小 */
                font-weight: bold;             /* 字体粗细 */
            }
            QCheckBox::indicator {
                width: 18px;                   /* 复选框宽度 */
                height: 18px;                  /* 复选框高度 */
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ced4da;     /* 未选中边框 */
                background: #ffffff;           /* 未选中背景 */
                border-radius: 4px;            /* 圆角 */
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196f3;     /* 选中边框 */
                background: #2196f3;           /* 选中背景 */
                border-radius: 4px;            /* 圆角 */
            }
            QCheckBox::indicator:checked::after {
                content: "";
                position: absolute;
                left: 5px;
                top: 1px;
                width: 5px;
                height: 8px;
                border: solid white;
                border-width: 0 2px 2px 0;
                transform: rotate(45deg);
            }
        """)
        # 减小复选框固定高度
        self.startup_checkbox.setFixedHeight(32)
        # 将控件添加到开机启动布局中
        startup_layout.addWidget(startup_label)
        startup_layout.addWidget(self.startup_checkbox)
        
        # 将刷新频率和开机启动布局添加到左侧设置布局中
        left_layout.addLayout(freq_layout)
        left_layout.addLayout(startup_layout)
        # 添加左侧弹性空间
        left_layout.addStretch(1)
        
        # 创建右侧版本信息布局
        right_layout = QtWidgets.QHBoxLayout()
        # 减小间距
        right_layout.setSpacing(12)
        # 减小边距
        right_layout.setContentsMargins(0, 0, 0, 0)
        # 创建版本标签
        version_label = QtWidgets.QLabel(f"🔖 版本: {__version__}")
        # 减小字体大小
        version_label.setStyleSheet("QLabel { color: #6c757d; font-size: 16px; font-weight: bold; }")
        # 创建检查更新按钮
        self.update_btn = QtWidgets.QPushButton("🔍 检查更新")
        # 连接按钮点击信号到处理函数
        self.update_btn.clicked.connect(self.check_update)  # type: ignore
        # 减小按钮尺寸
        self.update_btn.setFixedHeight(32)
        # 减小字体大小
        self.update_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;           /* 背景色 */
                color: #ffffff;                /* 文字颜色 */
                font-size: 14px;               /* 字体大小 */
                border-radius: 6px;            /* 圆角 */
                padding: 6px 14px;             /* 内边距 */
                border: none;                  /* 无边框 */
                font-weight: bold;             /* 粗体 */
                min-width: 90px;               /* 最小宽度 */
                min-height: 32px;              /* 最小高度 */
                max-height: 32px;              /* 固定最大高度 */
            }
            QPushButton:hover {
                background: #5a6268;           /* 悬停背景色 */
            }
            QPushButton:pressed {
                background: #545b62;           /* 按下背景色 */
            }
        """)
        # 将控件添加到右侧版本信息布局中
        right_layout.addWidget(version_label)
        right_layout.addWidget(self.update_btn)
        
        # 将左侧设置和右侧版本信息布局添加到主布局中
        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        
        # 返回创建的区域
        return widget

    def _create_buttons_widget(self):
        """创建操作按钮区域"""
        # 创建区域容器
        widget = QtWidgets.QWidget()
        # 设置样式
        widget.setStyleSheet("QWidget { background: transparent; }")
        
        # 创建水平布局
        btn_layout = QtWidgets.QHBoxLayout(widget)
        # 减小间距
        btn_layout.setSpacing(15)
        # 减小边距
        btn_layout.setContentsMargins(0, 0, 0, 0)
        # 添加左侧弹性空间
        btn_layout.addStretch(1)
        
        # 创建确定按钮
        self.btn_ok = QtWidgets.QPushButton("✅ 确定")
        # 连接按钮点击信号到处理函数
        self.btn_ok.clicked.connect(self.accept)  # type: ignore
        # 减小按钮尺寸
        self.btn_ok.setFixedWidth(90)
        self.btn_ok.setFixedHeight(36)
        # 减小字体大小
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background: #28a745;           /* 背景色 */
                color: #ffffff;                /* 文字颜色 */
                font-size: 16px;               /* 字体大小 */
                border-radius: 6px;            /* 圆角 */
                padding: 8px 16px;            /* 内边距 */
                border: none;                  /* 无边框 */
                font-weight: bold;             /* 粗体 */
                min-width: 90px;              /* 最小宽度 */
                min-height: 36px;              /* 最小高度 */
                max-height: 36px;              /* 固定最大高度 */
            }
            QPushButton:hover {
                background: #218838;           /* 悬停背景色 */
            }
            QPushButton:pressed {
                background: #1e7e34;           /* 按下背景色 */
            }
        """)
        
        # 创建取消按钮
        self.btn_cancel = QtWidgets.QPushButton("❌ 取消")
        # 连接按钮点击信号到处理函数
        self.btn_cancel.clicked.connect(self.reject)  # type: ignore
        # 减小按钮尺寸
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.setFixedHeight(36)
        # 减小字体大小
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #6c757d;           /* 背景色 */
                color: #ffffff;                /* 文字颜色 */
                font-size: 16px;               /* 字体大小 */
                border-radius: 6px;            /* 圆角 */
                padding: 8px 16px;            /* 内边距 */
                border: none;                  /* 无边框 */
                font-weight: bold;             /* 粗体 */
                min-width: 90px;              /* 最小宽度 */
                min-height: 36px;              /* 最小高度 */
                max-height: 36px;              /* 固定最大高度 */
            }
            QPushButton:hover {
                background: #5a6268;           /* 悬停背景色 */
            }
            QPushButton:pressed {
                background: #545b62;           /* 按下背景色 */
            }
        """)
        
        # 将按钮添加到布局中
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        # 返回创建的区域
        return widget

    def load_current_stocks(self):
        """加载当前用户股票列表"""
        # 加载配置
        cfg = load_config()
        # 获取用户股票列表
        stocks = cfg.get('user_stocks', ['sh600460', 'sh603986', 'sh600030', 'sh000001'])
        # 清空股票列表
        self.stock_list.clear()
        # 遍历股票列表
        for stock in stocks:
            # 获取股票名称
            name = self.get_name_by_code(stock)
            # 获取股票emoji
            emoji = get_stock_emoji(stock, name)
            # 对于港股，只显示中文名称部分
            if stock.startswith('hk') and name:
                # 去除"-"及之后的部分，只保留中文名称
                if '-' in name:
                    name = name.split('-')[0].strip()
                display = f"{emoji} {name} {stock}"
            elif name:
                display = f"{emoji} {name} {stock}"
            else:
                display = f"{emoji} {stock}"
            # 添加到股票列表中
            self.stock_list.addItem(display)
        # 保存选中股票列表
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
        from stock_monitor.data.market.quotation import get_stock_info_by_code
        stock_info = get_stock_info_by_code(code)
        if stock_info:
            return stock_info['name']
        return code

    def load_refresh_interval(self):
        """加载刷新间隔配置"""
        # 加载配置
        cfg = load_config()
        # 获取刷新间隔
        interval = cfg.get('refresh_interval', 5)
        # 保存刷新间隔
        self.refresh_interval = interval
        # 更新设置面板的刷新频率
        idx = {2:0, 5:1, 10:2, 30:3, 60:4}.get(interval, 1)
        self.freq_combo.setCurrentIndex(idx)

    def delete_selected_stocks(self):
        """删除选中的股票"""
        # 遍历选中的项目
        for item in self.stock_list.selectedItems():
            if item is not None:
                # 从列表中移除项目
                self.stock_list.takeItem(self.stock_list.row(item))
        # 更新选中股票列表
        self.selected_stocks = self.get_stocks_from_list()
        # 同步到主界面
        self.sync_to_main()

    def on_settings_changed(self):
        """
        设置改变时的处理函数
        """
        # 获取刷新间隔（秒）
        intervals = [2, 5, 10, 30, 60]
        refresh_interval = intervals[self.freq_combo.currentIndex()]
        
        # 获取开机启动状态
        startup_enabled = self.startup_checkbox.isChecked()
        
        # 保存刷新间隔
        self.refresh_interval = refresh_interval
        # 同步到主界面
        self.sync_to_main()

    def on_startup_checkbox_changed(self, state):
        """
        开机启动复选框状态改变处理
        
        Args:
            state: 复选框状态
        """
        # 如果win32com不可用，记录警告并返回
        if not WIN32_AVAILABLE:
            app_logger.warning("win32com不可用，无法设置开机启动")
            return
            
        import os
        # 获取开机启动目录
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        # 获取可执行文件路径
        exe_path = sys.executable
        # 构造快捷方式路径
        shortcut_path = os.path.join(startup_dir, "StockMonitor.lnk")
        
        # 根据状态创建或删除快捷方式
        if state == QtCore.Qt.CheckState.Checked:
            # 添加快捷方式
            if WIN32_AVAILABLE and Dispatch is not None:
                try:
                    # 创建快捷方式
                    shell = Dispatch('WScript.Shell')
                    shortcut = shell.CreateShortCut(shortcut_path)
                    shortcut.Targetpath = exe_path
                    shortcut.WorkingDirectory = os.path.dirname(exe_path)
                    shortcut.IconLocation = exe_path
                    shortcut.save()
                except Exception as e:
                    # 记录创建快捷方式失败的错误
                    app_logger.error(f"创建开机启动快捷方式失败: {e}")
        else:
            # 删除快捷方式
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                except Exception:
                    pass

    def accept(self):
        """确定按钮点击事件处理"""
        # 保存配置
        self._save_user_config()
        # 调用父类的accept方法
        super(NewSettingsDialog, self).accept()

    def sync_to_main(self):
        """同步配置到主界面"""
        # 获取股票列表
        stocks = self.get_stocks_from_list()
        # 发出配置更改信号
        self.config_changed.emit(stocks, self.refresh_interval)

    def _save_user_config(self):
        """保存用户配置到文件"""
        # 获取股票列表
        stocks = self.get_stocks_from_list()
        # 加载配置
        cfg = load_config()
        # 更新用户股票列表
        cfg['user_stocks'] = stocks
        # 更新刷新间隔
        cfg['refresh_interval'] = self.refresh_interval
        # 保存配置
        save_config(cfg)

    def closeEvent(self, a0):
        """
        关闭事件处理
        
        Args:
            a0: 关闭事件对象
        """
        # 加载配置
        cfg = load_config()
        # 获取窗口位置
        pos = self.pos()
        # 保存窗口位置
        cfg['settings_dialog_pos'] = [int(pos.x()), int(pos.y())]
        # 保存配置
        save_config(cfg)
        # 关键：关闭时让主界面指针置空，防止多实例
        p = self.parent()
        if p is not None and hasattr(p, 'settings_dialog'):
            setattr(p, 'settings_dialog', None)
        # 调用父类的关闭事件处理
        super(NewSettingsDialog, self).closeEvent(a0)

    def check_update(self):
        """检查更新"""
        import requests, re
        from packaging import version
        from PyQt5.QtWidgets import QMessageBox
        # GitHub API地址
        GITHUB_API = "https://api.github.com/repos/leo8912/stock_monitor/releases/latest"
        try:
            # 发送请求获取最新版本信息
            response = requests.get(GITHUB_API, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 解析标签名
            tag = data.get('tag_name', '')
            m = re.search(r'v(\d+\.\d+\.\d+)', tag)
            latest_ver = m.group(1) if m else None
            
            # 如果未检测到新版本信息
            if not latest_ver:
                app_logger.warning("未检测到新版本信息")
                # 创建自定义对话框
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("检查更新")
                dialog.setFixedSize(400, 200)
                layout = QtWidgets.QVBoxLayout(dialog)
                
                label = QtWidgets.QLabel("未检测到新版本信息。")
                label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
                layout.addWidget(label)
                
                button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                button_box.accepted.connect(dialog.accept)
                layout.addWidget(button_box)
                
                dialog.exec_()
                return
                
            # 如果当前已是最新版本
            if version.parse(latest_ver) <= version.parse(__version__):
                app_logger.info("当前已是最新版本")
                # 准备更新信息
                published_date = data.get('published_at', '未知')[:10] if data.get('published_at') else '未知'
                body = data.get('body', '无更新说明')
                if body and len(body) > 200:
                    body = body[:200] + '...'
                elif not body:
                    body = '无更新说明'
                
                # 创建自定义对话框
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("检查更新")
                dialog.setFixedSize(500, 300)
                layout = QtWidgets.QVBoxLayout(dialog)
                
                title_label = QtWidgets.QLabel("当前已是最新版本")
                title_label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
                title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
                layout.addWidget(title_label)
                
                info_text = f"""
版本号: {__version__}
发布日期: {published_date}

更新内容:
{body}
                """
                info_label = QtWidgets.QLabel(info_text)
                info_label.setStyleSheet("font-size: 14px; margin: 10px;")
                info_label.setWordWrap(True)
                layout.addWidget(info_label)
                
                button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                button_box.accepted.connect(dialog.accept)
                layout.addWidget(button_box)
                
                dialog.exec_()
                return
                
            # 询问用户是否前往下载
            # 准备更新信息
            published_date = data.get('published_at', '未知')[:10] if data.get('published_at') else '未知'
            body = data.get('body', '无更新说明')
            if body and len(body) > 200:
                body = body[:200] + '...'
            elif not body:
                body = '无更新说明'
                
            # 创建自定义对话框
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("发现新版本")
            dialog.setFixedSize(500, 350)
            layout = QtWidgets.QVBoxLayout(dialog)
            
            title_label = QtWidgets.QLabel("发现新版本")
            title_label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)
            
            info_text = f"""
检测到新版本: {latest_ver}
当前版本: {__version__}
发布日期: {published_date}

更新内容:
{body}
            """
            info_label = QtWidgets.QLabel(info_text)
            info_label.setStyleSheet("font-size: 14px; margin: 10px;")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Yes | QtWidgets.QDialogButtonBox.No)
            yes_button = button_box.button(QtWidgets.QDialogButtonBox.Yes)
            no_button = button_box.button(QtWidgets.QDialogButtonBox.No)
            if yes_button:
                yes_button.setText("前往下载")
            if no_button:
                no_button.setText("取消")
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            result = dialog.exec_()
            if result == QtWidgets.QDialog.Accepted:
                import webbrowser
                # 打开下载页面
                webbrowser.open("https://github.com/leo8912/stock_monitor/releases/latest")
                
        except requests.exceptions.RequestException as e:
            # 网络异常处理
            app_logger.error(f"网络异常，无法连接到GitHub: {e}")
            # 创建自定义对话框
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("检查更新")
            dialog.setFixedSize(400, 200)
            layout = QtWidgets.QVBoxLayout(dialog)
            
            label = QtWidgets.QLabel(f"网络异常，无法连接到GitHub：{e}")
            label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
            label.setWordWrap(True)
            layout.addWidget(label)
            
            button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)
            
            dialog.exec_()
        except Exception as e:
            # 其他异常处理
            app_logger.error(f"检查更新时发生错误: {e}")
            # 创建自定义对话框
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("检查更新")
            dialog.setFixedSize(400, 200)
            layout = QtWidgets.QVBoxLayout(dialog)
            
            label = QtWidgets.QLabel(f"检查更新时发生错误：{e}")
            label.setAlignment(QtCore.Qt.AlignCenter)  # type: ignore
            label.setWordWrap(True)
            layout.addWidget(label)
            
            button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)
            
            dialog.exec_()
            
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