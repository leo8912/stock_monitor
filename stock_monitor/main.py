from stock_monitor.version import APP_VERSION

import sys
import os
import json
import threading
import easyquotation
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import time
import datetime
import requests
from win32com.client import Dispatch
# 在文件开头导入pypinyin
from pypinyin import lazy_pinyin, Style

from stock_monitor.utils.logger import app_logger
from stock_monitor.data.updater import update_stock_database
from stock_monitor.ui.market_status import MarketStatusBar

from stock_monitor.config.manager import is_market_open, load_config, save_config

from stock_monitor.utils.helpers import resource_path, get_stock_emoji, is_equal

ICON_FILE = resource_path('icon.ico')  # 统一使用ICO格式图标


from stock_monitor.ui.settings_dialog import SettingsDialog
from stock_monitor.ui.components import StockTable

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
        
        # 初始化股市状态条
        self.market_status_bar = MarketStatusBar(self)
        
        # 初始化UI
        self.table = StockTable(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)  # 进一步减小边距: 左6, 上2, 右6, 下2
        layout.setSpacing(0)
        layout.addWidget(self.market_status_bar)  # 添加状态条
        layout.addWidget(self.table)
        self.setLayout(layout)
        
        # 设置样式
        self.setMinimumHeight(80)
        self.setMinimumWidth(280)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)  # type: ignore
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
        self.update_table_signal.connect(self.table.update_data)  # type: ignore
        
        # 立即刷新一次，确保在窗口显示前加载数据
        self.refresh_now(self.current_user_stocks)
        self._start_refresh_thread()
        self._start_database_update_thread()
        
        # 启动时立即更新一次数据库
        self._update_database_on_startup()
        
        # 显示窗口并加载位置
        self.show()
        self.load_position()
        self.raise_()
        self.activateWindow()
        self.install_event_filters(self)
        
        # 立即更新市场状态条，提高优先级
        self._update_market_status_immediately()
        
    def _update_market_status_immediately(self):
        """立即更新市场状态条，提高优先级"""
        # 在新线程中立即更新市场状态，避免阻塞UI
        update_thread = threading.Thread(target=self._immediate_market_status_update, daemon=True)
        update_thread.start()
        
    def _immediate_market_status_update(self):
        """立即更新市场状态的实现"""
        try:
            # 直接调用市场状态条的更新方法
            self.market_status_bar.update_market_status()
        except Exception as e:
            app_logger.error(f"立即更新市场状态失败: {e}")

    def install_event_filters(self, widget):
        if isinstance(widget, QtWidgets.QWidget):
            widget.installEventFilter(self)
            for child in widget.findChildren(QtWidgets.QWidget):
                self.install_event_filters(child)

    def eventFilter(self, a0, a1):
        event = a1
        if event.type() == QtCore.QEvent.MouseButtonPress:  # type: ignore
            if event.button() == QtCore.Qt.LeftButton:  # type: ignore
                cursor_pos = QtGui.QCursor.pos()
                frame_top_left = self.frameGeometry().topLeft()
                self.drag_position = QtCore.QPoint(cursor_pos.x() - frame_top_left.x(), 
                                                  cursor_pos.y() - frame_top_left.y())
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
                action = menu.exec_(QtGui.QCursor.pos())
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
                cursor_pos = QtGui.QCursor.pos()
                self.move(cursor_pos.x() - self.drag_position.x(), 
                         cursor_pos.y() - self.drag_position.y())
                event.accept()
                return True
        elif event.type() == QtCore.QEvent.MouseButtonRelease:  # type: ignore
            self.drag_position = None
            self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
            self.save_position()  # 拖动结束时自动保存位置
            event.accept()
            return True
        return super().eventFilter(a0, a1)

    def mousePressEvent(self, event):  # type: ignore
        if event.button() == QtCore.Qt.LeftButton:  # type: ignore
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(QtCore.Qt.SizeAllCursor)  # type: ignore
            event.accept()
        elif event.button() == QtCore.Qt.RightButton:  # type: ignore
            self.menu.popup(QtGui.QCursor.pos())

    def mouseMoveEvent(self, event):  # type: ignore
        if event.buttons() == QtCore.Qt.LeftButton and self.drag_position is not None:  # type: ignore
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):  # type: ignore
        self.drag_position = None
        self.setCursor(QtCore.Qt.ArrowCursor)  # type: ignore
        self.save_position()  # 拖动结束时自动保存位置

    def closeEvent(self, a0):  # type: ignore
        self.save_position()
        super().closeEvent(a0)

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
        # 使用QueuedConnection避免阻塞UI
        from PyQt5.QtCore import Qt
        self.settings_dialog.config_changed.connect(self.on_user_stocks_changed, type=Qt.ConnectionType.QueuedConnection)
        
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
        from stock_monitor.data.quotation import process_stock_data as quotation_process_stock_data
        return quotation_process_stock_data(data, stocks_list)

    def refresh_now(self, stocks_list=None):
        """立即刷新数据"""
        if stocks_list is None:
            stocks_list = self.current_user_stocks
        # 使用 hasattr 检查 quotation 对象是否有 real 方法
        if hasattr(self, 'quotation'):
            try:
                # 逐个请求，避免混淆，并确保键值精确匹配
                data_dict = {}
                failed_stocks = []
                for code in stocks_list:
                    try:
                        # 直接调用 real 方法，添加类型注释忽略检查
                        single = self.quotation.real([code])  # type: ignore
                        
                        if isinstance(single, dict):
                            # 精确使用原始 code 作为 key 获取数据，避免映射错误
                            data_dict[code] = single.get(code) or next(iter(single.values()), None)
                        else:
                            failed_stocks.append(code)
                    except Exception as e:
                        app_logger.error(f'获取股票 {code} 数据失败: {e}')
                        print(f'获取股票 {code} 数据失败: {e}')
                        failed_stocks.append(code)
                
                stocks = self.process_stock_data(data_dict, stocks_list)
                
                # 如果所有股票都失败了，显示错误信息
                if len(failed_stocks) == len(stocks_list) and len(stocks_list) > 0:
                    app_logger.error("所有股票数据获取失败")
                    error_stocks = [("数据加载失败", "--", "--", "#e6eaf3", "", "")] * len(stocks_list)
                    self.table.setRowCount(0)
                    self.table.clearContents()
                    self.table.update_data(error_stocks)  # type: ignore
                else:
                    self.table.setRowCount(0)
                    self.table.clearContents()
                    self.table.update_data(stocks)  # type: ignore
                
                self.table.viewport().update()
                self.table.repaint()
                QtWidgets.QApplication.processEvents()
                self.adjust_window_height()  # 每次刷新后自适应高度
                app_logger.debug(f"数据刷新完成，失败{len(failed_stocks)}只股票")
            except Exception as e:
                app_logger.error(f'行情刷新异常: {e}')
                print('行情刷新异常:', e)
                # 显示错误信息
                error_stocks = [("数据加载异常", "--", "--", "#e6eaf3", "", "")] * max(3, len(stocks_list) if stocks_list else 3)
                self.table.setRowCount(0)
                self.table.clearContents()
                self.table.update_data(error_stocks)  # type: ignore
                self.table.viewport().update()
                self.table.repaint()
                QtWidgets.QApplication.processEvents()
                self.adjust_window_height()

    def paintEvent(self, a0):  # type: ignore
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)  # type: ignore
        rect = self.rect()
        bg_color = QtGui.QColor(30, 30, 30, 220)  # 降低透明度，更不透明
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.NoPen)  # type: ignore
        painter.drawRect(rect)

    def _start_refresh_thread(self):
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()

    def _refresh_loop(self):
        """刷新循环"""
        consecutive_failures = 0
        max_consecutive_failures = 3  # 最大连续失败次数
        
        # 导入缓存管理器
        from stock_monitor.utils.cache import global_cache
        
        while True:
            if hasattr(self, 'quotation') and hasattr(self.quotation, 'real') and callable(self.quotation.real):
                try:
                    data_dict = {}
                    failed_count = 0
                    
                    # 检查是否有需要更新的数据
                    current_stocks = self.current_user_stocks
                    if not current_stocks:
                        # 如果没有股票，等待下次刷新
                        sleep_time = self.refresh_interval if is_market_open() else 30
                        app_logger.debug(f"无自选股数据，下次刷新间隔: {sleep_time}秒")
                        time.sleep(sleep_time)
                        continue
                    
                    # 检查缓存中是否有所有股票的数据
                    need_fetch = []
                    for code in current_stocks:
                        cached_data = global_cache.get(f"stock_{code}")
                        if cached_data is not None:
                            data_dict[code] = cached_data
                        else:
                            need_fetch.append(code)
                    
                    # 只获取缓存中没有的股票数据
                    if need_fetch:
                        app_logger.debug(f"需要获取 {len(need_fetch)} 只股票数据")
                        for code in need_fetch:
                            try:
                                single = self.quotation.real([code])
                                # 精确使用完整代码作为键，避免数据混淆
                                if isinstance(single, dict):
                                    stock_data = single.get(code) or next(iter(single.values()), None)
                                    if stock_data:
                                        data_dict[code] = stock_data
                                        # 缓存数据，根据市场开市状态设置不同的TTL
                                        ttl = self.refresh_interval if is_market_open() else 60
                                        global_cache.set(f"stock_{code}", stock_data, ttl)
                                else:
                                    failed_count += 1
                            except Exception as e:
                                app_logger.error(f'获取股票 {code} 数据失败: {e}')
                                print(f'获取股票 {code} 数据失败: {e}')
                                failed_count += 1
                    
                    stocks = self.process_stock_data(data_dict, self.current_user_stocks)
                    
                    # 如果所有股票都失败了，且股票列表不为空，显示错误信息
                    if failed_count == len(self.current_user_stocks) and len(self.current_user_stocks) > 0:
                        app_logger.error("所有股票数据获取失败")
                        error_stocks = [("数据加载失败", "--", "--", "#e6eaf3", "", "")] * len(self.current_user_stocks)
                        self.update_table_signal.emit(error_stocks)
                    else:
                        self.update_table_signal.emit(stocks)
                        
                    consecutive_failures = 0  # 重置失败计数
                    app_logger.debug(f"后台刷新完成，失败{failed_count}只股票，缓存命中{len(current_stocks) - failed_count - len(need_fetch)}只股票")
                except Exception as e:
                    app_logger.error(f'行情刷新异常: {e}')
                    print('行情刷新异常:', e)
                    consecutive_failures += 1
                    
                    # 如果连续失败多次，发送错误信息到UI
                    if consecutive_failures >= max_consecutive_failures:
                        app_logger.error(f"连续{max_consecutive_failures}次刷新失败")
                        error_stocks = [("网络连接异常", "--", "--", "#e6eaf3", "", "")] * max(3, len(self.current_user_stocks))
                        self.update_table_signal.emit(error_stocks)
                        consecutive_failures = 0  # 重置失败计数
            
            # 根据开市状态决定刷新间隔
            sleep_time = self.refresh_interval if is_market_open() else 30
            app_logger.debug(f"下次刷新间隔: {sleep_time}秒")
            time.sleep(sleep_time)

    def _update_database_on_startup(self):
        """在启动时更新数据库"""
        def update_database():
            try:
                app_logger.info("应用启动时更新股票数据库...")
                success = update_stock_database()
                if success:
                    app_logger.info("启动时股票数据库更新完成")
                else:
                    app_logger.warning("启动时股票数据库更新失败")
            except Exception as e:
                app_logger.error(f"启动时数据库更新出错: {e}")
        
        # 在后台线程中执行数据库更新，避免阻塞UI
        update_thread = threading.Thread(target=update_database, daemon=True)
        update_thread.start()

    def _start_database_update_thread(self):
        """启动数据库更新线程"""
        self._database_update_thread = threading.Thread(target=self._database_update_loop, daemon=True)
        self._database_update_thread.start()

    def _database_update_loop(self):
        """数据库更新循环 - 每天更新一次股票数据库"""
        # 等待应用启动完成
        time.sleep(10)
        
        # 启动后立即更新一次市场状态
        self.market_status_bar.update_market_status()
        
        while True:
            try:
                # 检查是否是凌晨时段（2:00-4:00之间）
                now = datetime.datetime.now()
                if now.hour >= 2 and now.hour < 4:
                    app_logger.info("开始更新股票数据库...")
                    success = update_stock_database()
                    if success:
                        app_logger.info("股票数据库更新完成")
                        # 数据库更新完成后，更新市场状态
                        self.market_status_bar.update_market_status()
                    else:
                        app_logger.warning("股票数据库更新失败")
                    
                    # 等待到明天同一时间
                    tomorrow = now + datetime.timedelta(days=1)
                    tomorrow_update = tomorrow.replace(hour=3, minute=0, second=0, microsecond=0)
                    sleep_seconds = (tomorrow_update - now).total_seconds()
                    time.sleep(sleep_seconds)
                else:
                    # 每30秒更新一次市场状态
                    time.sleep(30)
                    self.market_status_bar.update_market_status()
            except Exception as e:
                app_logger.error(f"数据库更新循环出错: {e}")
                time.sleep(3600)  # 出错后等待1小时再重试

    def load_user_stocks(self):
        """加载用户自选股列表，包含完整的错误处理和格式规范化"""
        try:
            cfg = load_config()
            stocks = cfg.get('user_stocks', None)
            
            # 确保stocks是一个非空列表
            if not isinstance(stocks, list) or len(stocks) == 0:
                print("配置文件中未找到有效的用户股票列表，使用默认值")
                stocks = ['sh600460', 'sh603986', 'sh600030', 'sh000001']
            
            processed_stocks = []
            default_stocks = ['sh600460', 'sh603986', 'sh600030', 'sh000001']
            
            for stock in stocks:
                try:
                    # 处理字符串类型的股票标识
                    if isinstance(stock, str):
                        # 如果包含空格，提取最后一个部分作为代码
                        if ' ' in stock:
                            parts = [p.strip() for p in stock.split() if p.strip()]
                            if len(parts) >= 2:
                                code = parts[-1]
                            else:
                                code = parts[0] if parts else ''
                        else:
                            code = stock.strip()
                        
                        # 格式化股票代码
                        from stock_monitor.utils.helpers import format_stock_code
                        formatted_code = format_stock_code(code)
                        if formatted_code:
                            processed_stocks.append(formatted_code)
                    
                    # 非字符串类型直接跳过
                except Exception as e:
                    print(f"处理股票 {stock} 时发生错误: {e}")
                    continue
            
            # 去除重复项，保持原有顺序
            seen = set()
            unique_stocks = []
            for stock in processed_stocks:
                if stock not in seen:
                    seen.add(stock)
                    unique_stocks.append(stock)
            processed_stocks = unique_stocks
            
            # 确保至少有3个股票
            if len(processed_stocks) < 3:
                print(f"用户股票数量不足3个，添加默认股票")
                for default_stock in default_stocks:
                    if default_stock not in processed_stocks:
                        processed_stocks.append(default_stock)
                    if len(processed_stocks) >= 3:
                        break
            
            return processed_stocks
            
        except Exception as e:
            print(f"加载用户股票列表时发生严重错误: {e}")
            # 返回安全的默认值
            return ['sh600460', 'sh603986', 'sh600030', 'sh000001']



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
        layout_margin = 4  # 固定边距总和
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
        
        # 根据内容自适应宽度
        base_width = 280  # 基础宽度
        seal_width_addition = 80  # 有封单时的额外宽度
        margin_adjustment = 12  # 边距调整
        
        if has_seal:
            self.setFixedWidth(base_width + seal_width_addition - margin_adjustment)
        else:
            self.setFixedWidth(base_width - margin_adjustment)

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


    def open_settings(self):

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