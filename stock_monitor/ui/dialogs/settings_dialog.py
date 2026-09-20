"""
设置对话框模块
"""

import os

from PyQt6 import QtGui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from stock_monitor.ui.dialogs.settings_pages import (
    DisplaySettingsPage,
    GeneralSettingsPage,
    QuantSettingsPage,
    SettingsContext,
    WatchlistPage,
)
from stock_monitor.ui.view_models.settings_view_model import SettingsViewModel
from stock_monitor.ui.workers.settings_workers import (
    DarkTradeExportThread,
    DarkTradeStatsExcelExportThread,
    DarkTradeStatsPushThread,
    ExcelExportThread,
    TestAppThread,
    UpdateCheckThread,
)
from stock_monitor.utils.helpers import (
    resource_path,
)

# C4 结构治理：以下名字仅作 re-export，保持既有导入路径（含测试）兼容
from .settings_widgets import DraggableListWidget, WatchListManager

__all__ = [
    "NewSettingsDialog",
    "DraggableListWidget",
    "WatchListManager",
    "UpdateCheckThread",
    "ExcelExportThread",
    "TestAppThread",
    "DarkTradeExportThread",
    "DarkTradeStatsPushThread",
    "DarkTradeStatsExcelExportThread",
]


class NewSettingsDialog(QDialog):
    """设置对话框类

    C4 结构治理后，本类只负责跨页编排与窗口生命周期；各标签页 / 底部栏的
    UI 构建、读写与页内信号已下沉到 ``settings_pages`` 中的页类：

    - ``GeneralSettingsPage``：P0 底部系统设置行（开机启动 / 刷新频率 / 检查更新）
    - ``WatchlistPage``：P1 自选股管理
    - ``DisplaySettingsPage``：P2 显示设置 + 任务栏行情条
    - ``QuantSettingsPage``：P3 量化预警
    """

    # 定义设置更改信号
    settings_changed = pyqtSignal()
    # 定义配置更改信号，参数为股票列表和刷新间隔
    config_changed = pyqtSignal(list, int)
    # 增加手动复盘信号
    manual_report_requested = pyqtSignal()

    def __init__(self, main_window=None) -> None:
        """初始化设置对话框并绑定 ViewModel。

        Args:
            main_window: 主窗口引用（可选），用于回传配置变更等。
        """
        # 不传递父窗口给 QDialog，避免继承主窗口的置顶属性
        super().__init__(None)
        self.main_window = main_window

        # Initialize ViewModel
        self.viewModel = SettingsViewModel()

        # 各设置页共享上下文（主窗口 / ViewModel / 信号代理 / 冷却状态）
        self.ctx = SettingsContext(
            main_window=main_window,
            view_model=self.viewModel,
            config_changed=self.config_changed,
            manual_report_requested=self.manual_report_requested,
        )

        # 设置窗口标题和图标
        self.setWindowTitle("A 股行情监控设置")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # 同时设置任务栏图标
            self._setup_windows_taskbar_icon()

        # 设置窗口标志：移除帮助按钮，确保不置顶
        flags = Qt.WindowType.Window  # 使用普通窗口标志
        flags |= Qt.WindowType.WindowCloseButtonHint  # 添加关闭按钮
        flags |= Qt.WindowType.WindowMinimizeButtonHint  # 添加最小化按钮
        self.setWindowFlags(flags)

        # 设置窗口大小
        self.resize(900, 700)  # 进一步调大窗口尺寸

        # 设置窗口样式以匹配暗色主题
        self.setObjectName("NewSettingsDialog")

        # 在 Windows 上设置标题栏颜色
        self._setup_windows_caption_color()

        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)

        # 创建各设置页实例（P0 底部栏 / P1 自选股 / P2 显示 / P3 量化）
        self._general_page = GeneralSettingsPage(self.ctx)
        self._watchlist_page = WatchlistPage(self.ctx)
        self._display_page = DisplaySettingsPage(self.ctx)
        self._quant_page = QuantSettingsPage(self.ctx)
        self.pages = [
            self._general_page,
            self._watchlist_page,
            self._display_page,
            self._quant_page,
        ]

        # 跨页只读入口：P3 量化页需要 P1 自选股代码列表（避免页间直接引用）
        self.ctx.stocks_provider = lambda: self._watchlist_page.get_stocks_from_list(
            self._watchlist_page.watch_list
        )

        # === [UI OPTIMIZATION] 创建标签页结构 ===
        self._setup_tabs(main_layout)

        # === 底部：系统设置（P0 页）+ 确定 / 取消（shell）===
        # 保持原一行内的控件顺序 / stretch / 间距：系统设置子布局(stretch=1) 在前，
        # 确定取消按钮布局在后。OK/Cancel 由 shell 创建，accept/reject 语义留在 shell。
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        self._general_page.build_into(bottom_layout)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        button_layout.setSpacing(10)
        button_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )  # 右对齐并垂直居中

        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelButton")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        bottom_layout.addLayout(button_layout)
        main_layout.addLayout(bottom_layout)

        # 连接跨切面信号
        self._connect_signals()

        # 加载配置
        self._load_config_from_vm()

        # 保存原始自选股列表，用于取消操作时恢复
        self._watchlist_page._update_original_watch_list()

    def _setup_windows_taskbar_icon(self) -> None:
        """设置 Windows 任务栏图标（仅 Windows 平台）"""
        import sys

        if sys.platform != "win32":
            return

        try:
            import ctypes

            myappid = "stock.monitor.settings"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    def _setup_windows_caption_color(self) -> None:
        """设置 Windows 10/11 标题栏颜色（仅 Windows 平台）"""
        import sys

        if sys.platform != "win32":
            return

        try:
            import ctypes

            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                35,  # DWMWA_CAPTION_COLOR
                ctypes.byref(ctypes.c_int(0x1E1E1E)),
                ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass

    def _connect_signals(self) -> None:
        """连接「跨页 / 页 ↔ shell」信号（页内信号已在各页 ``build`` 中连接）。"""
        # ViewModel 信号（shell 级）
        self.viewModel.save_completed.connect(self.accept)
        self.viewModel.error_occurred.connect(self._on_vm_error)

        # 确定 / 取消（shell 拥有的按钮）
        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _setup_tabs(self, main_layout) -> None:
        """构建各页 UI 并创建标签页结构 [UI OPTIMIZATION]"""
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")

        # 构建各标签页（P0 底部栏不在此，挂到 main_layout 底部）
        self._watchlist_page.build(self._watchlist_page)
        self._display_page.build(self._display_page)
        self._quant_page.build(self._quant_page)

        # 添加到标签页（顺序 / emoji / 文案保持原样）
        self.tabs.addTab(self._watchlist_page, "📋 自选股管理")
        self.tabs.addTab(self._display_page, "🎨 显示设置")
        self.tabs.addTab(self._quant_page, "📊 量化预警")

        main_layout.addWidget(self.tabs)

    def _on_vm_error(self, message: str) -> None:
        """处理来自 ViewModel 的错误信号"""
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(self, "预警测试", message)

    def _load_config_from_vm(self) -> None:
        """Load config via ViewModel"""
        try:
            settings = self.viewModel.load_settings()

            # 按既有顺序装载各页：P1 → P0 → P2 → P3
            # （顺序保持与原内联实现一致，避免副作用差异）
            self._watchlist_page.load(settings)
            self._general_page.load(settings)
            self._display_page.load(settings)
            self._quant_page.load(settings)
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"Failed to load config from VM: {e}")

    def _save_config_via_vm(self) -> bool:
        """Save config via VM"""
        try:
            # 各页先各自收集自己负责的配置键
            page_settings: dict = {}
            self._watchlist_page.collect(page_settings)
            self._general_page.collect(page_settings)
            self._display_page.collect(page_settings)
            self._quant_page.collect(page_settings)

            # 保持与既有实现逐字一致的键顺序（config_center.set 按序写入）
            settings = {
                "user_stocks": page_settings["user_stocks"],
                "auto_start": page_settings["auto_start"],
                "refresh_interval": page_settings["refresh_interval"],
                "font_size": page_settings["font_size"],
                "font_family": page_settings["font_family"],
                "transparency": page_settings["transparency"],
                "quant_enabled": page_settings["quant_enabled"],
                "auto_export_excel": page_settings["auto_export_excel"],
                "auto_close_export": page_settings["auto_close_export"],
                "wecom_webhook": page_settings["wecom_webhook"],
                "taskbar_quote_enabled": page_settings["taskbar_quote_enabled"],
                "taskbar_per_page": page_settings["taskbar_per_page"],
                "taskbar_carousel_interval": page_settings["taskbar_carousel_interval"],
                "taskbar_show_price": page_settings["taskbar_show_price"],
                "taskbar_show_change": page_settings["taskbar_show_change"],
                "taskbar_show_dark_flow": page_settings["taskbar_show_dark_flow"],
            }

            # 新增企微应用配置保存
            settings["push_mode"] = page_settings["push_mode"]
            settings["wecom_corpid"] = page_settings["wecom_corpid"]
            settings["wecom_corpsecret"] = page_settings["wecom_corpsecret"]
            settings["wecom_agentid"] = page_settings["wecom_agentid"]

            # 斐波那契配置保存
            settings["fib_target_coefficients"] = page_settings[
                "fib_target_coefficients"
            ]

            from stock_monitor.utils.logger import app_logger

            # 保存前验证已在 viewModel.save_settings 中执行，此处不再重复
            self.viewModel.save_settings(settings)
            return True
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"Failed to save config via VM: {e}")
            return False

    def _on_ok_clicked(self) -> None:
        """点击确定按钮的处理函数"""
        # 1. 保存配置
        if self._save_config_via_vm():
            self._display_page._sync_original_display_settings_from_controls()
            self._display_page._clear_preview_state()
            if self.main_window:
                self.main_window.update_font_size()
                self.main_window.update()
            # 2. 保存成功，执行接受操作
            self.accept()

    def accept(self) -> None:
        """点击确定按钮时保存设置"""
        # [P1 FIX] 拆分为多个小方法，遵循单一职责原则
        self._general_page.apply_auto_start()
        self._cleanup_preview_state()
        self._emit_config_changed_signal()
        self._watchlist_page._update_original_watch_list()
        self.hide()

    def _cleanup_preview_state(self) -> None:
        """清理预览状态并恢复主窗口默认状态"""
        if self.main_window:
            self._display_page._clear_preview_state()
            self.main_window.update()

    def _emit_config_changed_signal(self) -> None:
        """发送配置更改信号"""
        if self.main_window:
            stocks = self._watchlist_page.get_stocks_from_list(
                self._watchlist_page.watch_list
            )
            refresh_interval = self._general_page.get_refresh_interval()
            from stock_monitor.utils.logger import app_logger

            app_logger.info(
                f"发送配置更改信号：股票列表={stocks}, 刷新间隔={refresh_interval}"
            )
            self.config_changed.emit(stocks, refresh_interval)

    def reject(self) -> None:
        """点击取消按钮时恢复原始设置"""
        # 恢复原始自选股列表（原始快照由 WatchlistPage 持有）
        self._watchlist_page.restore()

        # 恢复主窗口的原始字体设置（显示状态由 DisplaySettingsPage 持有）
        if self.main_window:
            self._display_page.restore()
            self._display_page._clear_preview_state()
            self.main_window.update_font_size()
            self.main_window.update()

        # 隐藏窗口而不是关闭
        self.hide()

    def showEvent(self, a0) -> None:  # type: ignore
        """重写showEvent以设置初始位置"""
        super().showEvent(a0)

        # 居中显示窗口
        self.center_on_screen()

    def center_on_screen(self) -> None:
        """将窗口居中显示在屏幕中央"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(max(screen_geo.left(), x), max(screen_geo.top(), y))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """设置对话框关闭事件 - 清理资源、断开信号连接"""
        try:
            # 1. 各页清理（定时器 / 页内信号），跨页统一遍历
            for page in self.pages:
                page.cleanup()

            # 2. 断开 ViewModel 信号（只断开由本实例连接的）
            if hasattr(self, "viewModel"):
                try:
                    self.viewModel.save_completed.disconnect(self.accept)
                    self.viewModel.error_occurred.disconnect(self._on_vm_error)
                except Exception:
                    pass  # 忽略信号未连接的错误

            # 3. 断开 shell 拥有的 UI 信号
            try:
                self.ok_button.clicked.disconnect(self._on_ok_clicked)
                self.cancel_button.clicked.disconnect(self.reject)
            except Exception:
                pass  # 忽略信号未连接的错误

            from stock_monitor.utils.logger import app_logger

            app_logger.info("设置对话框资源清理完成")
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"设置对话框 closeEvent 清理失败：{e}")
        finally:
            # 隐藏窗口而不是真正关闭
            self.hide()
            if event:
                event.ignore()  # 阻止窗口真正关闭

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """设置对话框隐藏事件 - 清理预览状态"""
        try:
            # 清除主窗口的预览透明度
            if self.main_window:
                self._display_page._clear_preview_state()
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"设置对话框 hideEvent 处理失败：{e}")
        finally:
            super().hideEvent(event)
