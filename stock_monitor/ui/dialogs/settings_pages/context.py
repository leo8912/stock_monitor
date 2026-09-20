"""设置页共享上下文。

``SettingsContext`` 在设置对话框与其各页之间传递共享依赖（主窗口、ViewModel、
信号代理、Webhook 测试冷却状态与日志器），使各页无需反向持有对话框实例。
仅依赖 PyQt。
"""

from __future__ import annotations

from stock_monitor.utils.logger import app_logger


class SettingsContext:
    """设置页共享上下文对象。

    Attributes:
        main_window: 主窗口引用（可为 None）。
        view_model: ``SettingsViewModel`` 实例。
        config_changed: 对话框 ``config_changed`` 信号代理（可直接 emit）。
        manual_report_requested: 对话框 ``manual_report_requested`` 信号代理。
        logger: 日志器（``app_logger``）。
        stocks_provider: 读取当前自选股代码列表的无参可调用对象，由 shell 在
            装配完成后注入（让 P3 量化页跨页取值而不直接引用 P1 页）。
        _last_webhook_test_time: 上次 Webhook 测试时间戳（冷却用）。
        _webhook_test_cooldown: Webhook 测试冷却秒数。
    """

    def __init__(
        self,
        main_window=None,
        view_model=None,
        config_changed=None,
        manual_report_requested=None,
    ) -> None:
        """初始化共享上下文。

        Args:
            main_window: 主窗口引用（可选）。
            view_model: 设置 ViewModel（可选）。
            config_changed: 对话框 config_changed 信号代理（可选）。
            manual_report_requested: 对话框 manual_report_requested 信号代理（可选）。
        """
        self.main_window = main_window
        self.view_model = view_model
        self.config_changed = config_changed
        self.manual_report_requested = manual_report_requested
        self.logger = app_logger

        # 由 shell 装配后注入：读取自选股代码列表（跨页只读，避免循环引用）
        self.stocks_provider = None

        # [P1 FIX] 速率限制，防止 Webhook 测试被滥用
        self._last_webhook_test_time = 0
        self._webhook_test_cooldown = 60  # 60 秒冷却时间
