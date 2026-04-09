import re

from PyQt6 import QtCore
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.config.container import container
from stock_monitor.data.stock.stocks import load_stock_data
from stock_monitor.utils.helpers import get_stock_emoji
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.stock_utils import StockCodeProcessor


class TestScanThread(QtCore.QThread):
    """
    独立测试扫描线程，避免在函数内匿名实例化导致生命周期异常被回收崩溃。
    """

    finished_sig = pyqtSignal()
    error_sig = pyqtSignal(str)

    def __init__(self, worker_instance, parent=None):
        super().__init__(parent)
        self.worker = worker_instance

    def run(self):
        try:
            self.worker.perform_scan()
        except Exception as e:
            self.error_sig.emit(str(e))
        finally:
            self.finished_sig.emit()


class SettingsViewModel(QObject):
    """
    ViewModel for SettingsDialog
    Handles configuration loading/saving and stock search logic.
    """

    settings_loaded = pyqtSignal(dict)
    save_completed = pyqtSignal()
    search_results_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    validation_failed = pyqtSignal(str, str)  # (field_name, error_message)

    def __init__(self):
        super().__init__()
        self._container = container
        self._config_manager = self._container.get(ConfigManager)
        self._processor = StockCodeProcessor()

        # 搜索防抖定时器
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._perform_search)
        self._last_query = ""

    def validate_settings(self, settings: dict) -> bool:
        """验证配置有效性（保存前执行）

        Returns:
            bool: 验证是否通过
        """
        # 1. 验证 Webhook URL 格式
        webhook = settings.get("wecom_webhook", "")
        if webhook and not self._is_valid_webhook_url(webhook):
            self.validation_failed.emit(
                "wecom_webhook",
                "Webhook URL 格式无效，应为 https://qyapi.weixin.qq.com/cgi/webhook/send?key=xxx",
            )
            return False

        # 2. 验证企业微信配置完整性
        push_mode = settings.get("push_mode", "")
        if push_mode == "app":
            corpid = settings.get("wecom_corpid", "")
            corpsecret = settings.get("wecom_corpsecret", "")
            agentid = settings.get("wecom_agentid", "")

            if not corpid:
                self.validation_failed.emit("wecom_corpid", "企业 ID 不能为空")
                return False
            if not corpsecret:
                self.validation_failed.emit("wecom_corpsecret", "企业应用密钥不能为空")
                return False
            if not agentid:
                self.validation_failed.emit("wecom_agentid", "应用 AgentId 不能为空")
                return False

        # 3. 验证刷新间隔范围
        refresh_interval = settings.get("refresh_interval", 5)
        if not isinstance(refresh_interval, int) or refresh_interval < 1:
            self.validation_failed.emit(
                "refresh_interval", "刷新间隔必须为大于 0 的整数"
            )
            return False
        if refresh_interval > 3600:
            self.validation_failed.emit("refresh_interval", "刷新间隔不能超过 3600 秒")
            return False

        # 4. 验证字体大小范围
        font_size = settings.get("font_size", 13)
        if not isinstance(font_size, int) or font_size < 8:
            self.validation_failed.emit("font_size", "字体大小不能小于 8")
            return False
        if font_size > 72:
            self.validation_failed.emit("font_size", "字体大小不能超过 72")
            return False

        # 5. 验证透明度范围
        transparency = settings.get("transparency", 80)
        if not isinstance(transparency, (int, float)) or transparency < 0:
            self.validation_failed.emit("transparency", "透明度必须为 0-100 之间的数值")
            return False
        if transparency > 100:
            self.validation_failed.emit("transparency", "透明度不能超过 100")
            return False

        return True

    def _is_valid_webhook_url(self, url: str) -> bool:
        """验证 Webhook URL 格式"""
        # 企业微信 Webhook URL 正则表达式
        # 支持两种格式：/cgi-bin/webhook/send 和 /cgi/webhook/send
        pattern = r"^https://qyapi\.weixin\.qq\.com/cgi(?:-bin)?/webhook/send\?key=[A-Za-z0-9-]+$"
        return bool(re.match(pattern, url))

    def load_settings(self):
        """Load all settings"""
        settings = {
            "user_stocks": self._config_manager.get("user_stocks", []),
            "auto_start": self._config_manager.get("auto_start", False),
            "refresh_interval": self._config_manager.get("refresh_interval", 5),
            "font_size": self._config_manager.get("font_size", 13),
            "font_family": self._config_manager.get("font_family", "微软雅黑"),
            "transparency": self._config_manager.get("transparency", 80),
            "drag_sensitivity": self._config_manager.get("drag_sensitivity", 5),
            # Add missing quant settings for persistence
            "quant_enabled": self._config_manager.get("quant_enabled", False),
            "wecom_webhook": self._config_manager.get("wecom_webhook", ""),
            "push_mode": self._config_manager.get("push_mode", "webhook"),
            "wecom_corpid": self._config_manager.get("wecom_corpid", ""),
            "wecom_corpsecret": self._config_manager.get("wecom_corpsecret", ""),
            "wecom_agentid": self._config_manager.get("wecom_agentid", ""),
        }
        self.settings_loaded.emit(settings)
        return settings

    def save_settings(self, settings: dict):
        """Save settings"""
        try:
            # [UX] 保存前执行验证
            if not self.validate_settings(settings):
                # 验证失败时 validation_failed 信号已触发，直接返回
                return False

            for key, value in settings.items():
                self._config_manager.set(key, value)

            self.save_completed.emit()
            return True
        except Exception as e:
            app_logger.error(f"Failed to save settings: {e}")
            return False

    def search_stocks(self, query: str):
        """搜索入口（含防抖）"""
        self._last_query = query.strip()
        self._search_timer.start(300)  # 300ms 防抖

    def _perform_search(self):
        """执行实际搜索逻辑"""
        query = self._last_query
        if not query:
            self.search_results_updated.emit([])
            return

        try:
            # Load stock data
            all_stocks_list = load_stock_data()
            all_stocks = {stock["code"]: stock for stock in all_stocks_list}

            if not all_stocks:
                return

            # Filter and prioritize
            matched_stocks = []
            lower_query = query.lower()

            for code, stock in all_stocks.items():
                name = stock.get("name", "")
                if lower_query in code.lower() or lower_query in name.lower():
                    # Priority logic
                    priority = 0
                    if code.startswith(("sh", "sz")) and not code.startswith(
                        ("sh000", "sz399")
                    ):
                        priority = 10  # A shares
                    elif code.startswith(("sh000", "sz399")):
                        priority = 5  # Indices
                    elif code.startswith("hk"):
                        priority = 1  # HK shares
                    matched_stocks.append((priority, code, stock))

            # Sort by priority desc, then code asc
            matched_stocks.sort(key=lambda x: (-x[0], x[1]))

            # Format top 20 results
            results = []
            for _, code, stock in matched_stocks[:20]:
                emoji = get_stock_emoji(code, stock.get("name", ""))
                display_text = f"{emoji} {stock.get('name', '')} ({code})"
                # Return object or dict ideally, but keeping string for simple UI binding first?
                # UI takes strings. Let's return dict with display text and code
                results.append(
                    {
                        "display": display_text,
                        "code": code,
                        "name": stock.get("name", ""),
                    }
                )

            self.search_results_updated.emit(results)

        except Exception as e:
            app_logger.error(f"Search failed: {e}")
            self.search_results_updated.emit([])

    def get_stock_display_info(self, stock_code: str) -> str:
        """Get display text for a stock code (emoji + name + code)"""
        # Logic to reconstitute display string from saved code
        clean_code = self._processor.clean_code(stock_code)

        # We need current stock data to get name
        # Optimization: cache this or load on demand? load_stock_data is cached in module usually?
        all_stocks_list = load_stock_data()
        all_stocks_dict = {stock["code"]: stock for stock in all_stocks_list}

        stock_info = all_stocks_dict.get(clean_code)
        if stock_info:
            emoji = get_stock_emoji(clean_code, stock_info.get("name", ""))
            name = stock_info.get("name", "")
            if name:
                return f"{emoji} {name} ({clean_code})"
            else:
                return f"{emoji} {clean_code}"
        else:
            emoji = get_stock_emoji(clean_code, "")
            return f"{emoji} {clean_code}"

    def test_quant_push(self, webhook: str):
        """测试量化推送 (异步执行，避免阻塞 UI)"""
        if not webhook:
            self.error_occurred.emit("请先输入 Webhook 地址")
            return

        try:
            from stock_monitor.core.workers.quant_worker import QuantWorker

            worker = self._container.get(QuantWorker)
            if worker:
                # 记录原始配置用于恢复
                self._old_webhook = worker.wecom_webhook
                worker.wecom_webhook = webhook
                worker._alert_cache.clear()

                # 防止旧线程还在跑被回收
                if hasattr(self, "_test_thread") and self._test_thread.isRunning():
                    self.error_occurred.emit("测试正在进行中，请稍后")
                    return

                self._test_thread = TestScanThread(worker, parent=self)
                self._test_thread.finished_sig.connect(
                    lambda: setattr(worker, "wecom_webhook", self._old_webhook)
                )
                self._test_thread.error_sig.connect(
                    lambda e: self.error_occurred.emit(f"测试推送扫描失败: {e}")
                )
                self._test_thread.start()
            else:
                self.error_occurred.emit("量化引擎未就绪")
        except Exception as e:
            app_logger.error(f"测试推送启动失败: {e}")
            self.error_occurred.emit(f"测试推送启动失败: {e}")
