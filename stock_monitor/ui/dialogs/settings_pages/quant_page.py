"""量化预警设置页（P3）。

C4-2 结构治理：把原内联在 ``NewSettingsDialog`` 中的「📊 量化预警」标签页
（量化开关 / 斐波那契参数 / 推送渠道与企微配置 / 手动复盘与暗盘相关按钮）
及其全部处理函数抽到本页。

跨页取值：本页需要读取 P1 自选股列表，但**不直接引用** ``WatchlistPage``
（避免循环依赖）。改为通过 ``ctx.stocks_provider``（由 shell 在装配完成后注入
的无参可调用对象）获取股票代码列表。

线程实例属性名（``_export_thread`` / ``_dark_export_thread`` / ``_dark_stats_thread``
/ ``_dark_stats_excel_thread`` / ``_test_app_thread``）保持与原实现一致。
"""

from __future__ import annotations

import re
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stock_monitor.ui.workers.settings_workers import (
    DarkTradeExportThread,
    DarkTradeStatsExcelExportThread,
    DarkTradeStatsPushThread,
    ExcelExportThread,
    TestAppThread,
)

from .base import SettingsPage
from .context import SettingsContext


class QuantSettingsPage(SettingsPage):
    """量化预警页：扫描开关 / 斐波那契 / 推送渠道 / 手动导出。"""

    SETTINGS_KEYS = (
        "quant_enabled",
        "auto_export_excel",
        "auto_close_export",
        "wecom_webhook",
        "push_mode",
        "wecom_corpid",
        "wecom_corpsecret",
        "wecom_agentid",
        "fib_target_coefficients",
    )

    def __init__(self, ctx: SettingsContext, parent=None) -> None:
        """初始化量化预警页。"""
        super().__init__(ctx, parent)
        self._export_thread = None
        self._dark_export_thread = None
        self._dark_stats_thread = None
        self._dark_stats_excel_thread = None
        self._test_app_thread = None

    def _watchlist_codes(self) -> list:
        """通过上下文注入的 provider 读取 P1 自选股代码（避免跨页直接引用）。"""
        provider = getattr(self.ctx, "stocks_provider", None)
        if provider is None:
            return []
        return provider()

    def build(self, parent_widget) -> None:
        """设置量化分析与预警 UI [UI OPTIMIZATION - 标签页适配]"""
        # [UI OPTIMIZATION] 简化标题，移除冗余文字
        quant_group = QGroupBox("📊 量化分析预警")
        quant_layout = QVBoxLayout()
        quant_layout.setContentsMargins(15, 15, 15, 15)
        quant_layout.setSpacing(12)
        quant_group.setLayout(quant_layout)

        # 启动开关
        # [UI OPTIMIZATION] 精简复选框标签，移除技术细节
        self.quant_enabled_checkbox = QCheckBox("开启智能扫描")
        self.quant_enabled_checkbox.setToolTip(
            "开启后将在后台静默拉取 15m/30m/60m/日线 等数据并执行底层复杂算力运算。\n"
            "包括：MACD 底背离 / BBands 收口变盘 / 主力碎步吸筹等信号检测"
        )
        quant_layout.addWidget(self.quant_enabled_checkbox)

        # 自动导出 Excel 开关
        self.auto_export_excel_checkbox = QCheckBox("收盘后自动导出自选股指标到 Excel")
        self.auto_export_excel_checkbox.setToolTip(
            "启用后，在收盘复盘时将自动计算并导出所有自选股的技术指标（K线、BOLL、MACD、RSI等）到 Excel 文件。"
        )
        quant_layout.addWidget(self.auto_export_excel_checkbox)

        # 收盘时自动抓取全网数据开关
        self.auto_close_export_checkbox = QCheckBox("收盘时自动抓取全网数据并保存")
        self.auto_close_export_checkbox.setToolTip(
            "启用后，每天15:05将自动执行以下操作：\n"
            "1. 抓取全市场暗盘资金数据并导出Excel\n"
            "2. 抓取自选股详细技术指标并导出Excel\n"
            "3. 保存全A股行情快照"
        )
        quant_layout.addWidget(self.auto_close_export_checkbox)

        # --- 斐波那契设置区域 ---
        fib_group = QGroupBox("📐 斐波那契分析设置")
        fib_layout = QVBoxLayout()
        fib_layout.setContentsMargins(10, 10, 10, 10)
        fib_layout.setSpacing(8)
        fib_group.setLayout(fib_layout)

        # 浪5目标系数
        wave5_layout = QHBoxLayout()
        wave5_layout.addWidget(QLabel("浪5目标系数:"))
        self.fib_wave5_spin = QDoubleSpinBox()
        self.fib_wave5_spin.setRange(0.1, 2.0)
        self.fib_wave5_spin.setSingleStep(0.05)
        self.fib_wave5_spin.setDecimals(3)
        self.fib_wave5_spin.setValue(0.618)
        self.fib_wave5_spin.setToolTip("浪5目标 = 浪1幅度 × 此系数 + 浪4低点")
        wave5_layout.addWidget(self.fib_wave5_spin)
        wave5_layout.addStretch()
        fib_layout.addLayout(wave5_layout)

        # 浪4回调系数
        wave4_layout = QHBoxLayout()
        wave4_layout.addWidget(QLabel("浪4回调系数:"))
        self.fib_wave4_spin = QDoubleSpinBox()
        self.fib_wave4_spin.setRange(0.1, 1.0)
        self.fib_wave4_spin.setSingleStep(0.05)
        self.fib_wave4_spin.setDecimals(3)
        self.fib_wave4_spin.setValue(0.382)
        self.fib_wave4_spin.setToolTip("浪4回调目标 = 浪3幅度 × 此系数")
        wave4_layout.addWidget(self.fib_wave4_spin)
        wave4_layout.addStretch()
        fib_layout.addLayout(wave4_layout)

        # B浪反弹系数
        waveb_layout = QHBoxLayout()
        waveb_layout.addWidget(QLabel("B浪反弹系数:"))
        self.fib_waveb_spin = QDoubleSpinBox()
        self.fib_waveb_spin.setRange(0.1, 1.0)
        self.fib_waveb_spin.setSingleStep(0.05)
        self.fib_waveb_spin.setDecimals(3)
        self.fib_waveb_spin.setValue(0.5)
        self.fib_waveb_spin.setToolTip("B浪反弹目标 = 浪A幅度 × 此系数")
        waveb_layout.addWidget(self.fib_waveb_spin)
        waveb_layout.addStretch()
        fib_layout.addLayout(waveb_layout)

        # 重置按钮
        reset_fib_button = QPushButton("恢复默认值")
        reset_fib_button.setFixedWidth(100)
        reset_fib_button.clicked.connect(self._reset_fib_settings)
        fib_layout.addWidget(reset_fib_button, alignment=Qt.AlignmentFlag.AlignRight)

        quant_layout.addWidget(fib_group)

        # --- 推送通道选择 ---
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("通知渠道:"))
        self.push_mode_combo = QComboBox()
        self.push_mode_combo.addItem("群机器人 (Webhook)", "webhook")
        self.push_mode_combo.addItem("企业自建应用 (Agent)", "app")
        self.push_mode_combo.setFixedWidth(150)
        channel_layout.addWidget(self.push_mode_combo)
        channel_layout.addStretch()
        quant_layout.addLayout(channel_layout)

        # --- Webhook 配置区域 ---
        self.webhook_container = QWidget()
        webhook_sub_layout = QVBoxLayout(self.webhook_container)
        webhook_sub_layout.setContentsMargins(0, 5, 0, 5)
        webhook_sub_layout.setSpacing(8)

        h_layout = QHBoxLayout()
        label = QLabel("Webhook 地址:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度
        h_layout.addWidget(label)
        self.wecom_webhook_input = QLineEdit()
        self.wecom_webhook_input.setPlaceholderText(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
        )
        h_layout.addWidget(self.wecom_webhook_input)

        self.test_push_button = QPushButton("🧪 测试推送")
        self.test_push_button.setObjectName("PrimaryButton")
        self.test_push_button.setFixedWidth(100)
        h_layout.addWidget(self.test_push_button)
        webhook_sub_layout.addLayout(h_layout)
        quant_layout.addWidget(self.webhook_container)

        # --- 企业应用配置区域 ---
        self.app_container = QWidget()
        app_sub_layout = QVBoxLayout(self.app_container)
        app_sub_layout.setContentsMargins(0, 5, 0, 5)
        app_sub_layout.setSpacing(8)

        # CorpID
        corp_layout = QHBoxLayout()
        label = QLabel("企业 ID:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度，简化文字
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        corp_layout.addWidget(label)
        self.wecom_corpid_input = QLineEdit()
        self.wecom_corpid_input.setPlaceholderText("请输入企业 ID")
        corp_layout.addWidget(self.wecom_corpid_input)

        # Secret
        secret_layout = QHBoxLayout()
        label = QLabel("应用密钥:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        secret_layout.addWidget(label)
        self.wecom_corpsecret_input = QLineEdit()
        self.wecom_corpsecret_input.setPlaceholderText("请输入应用密钥")
        self.wecom_corpsecret_input.setEchoMode(QLineEdit.EchoMode.Password)
        secret_layout.addWidget(self.wecom_corpsecret_input)

        # AgentID
        agent_layout = QHBoxLayout()
        label = QLabel("应用 ID:")
        label.setFixedWidth(80)  # [UI OPTIMIZATION] 统一标签宽度
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        agent_layout.addWidget(label)
        self.wecom_agentid_input = QLineEdit()
        self.wecom_agentid_input.setPlaceholderText("请输入应用 ID")
        agent_layout.addWidget(self.wecom_agentid_input)

        self.test_app_button = QPushButton("🧪 测试应用")
        self.test_app_button.setObjectName("PrimaryButton")
        self.test_app_button.setFixedWidth(100)
        agent_layout.addWidget(self.test_app_button)

        app_sub_layout.addLayout(corp_layout)
        app_sub_layout.addLayout(secret_layout)
        app_sub_layout.addLayout(agent_layout)
        quant_layout.addWidget(self.app_container)

        # 按钮行水平布局
        btn_row_layout = QHBoxLayout()
        btn_row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row_layout.setSpacing(15)

        # 全量复盘按钮
        self.btn_manual_report = QPushButton("🧩 立即执行全量复盘")
        self.btn_manual_report.setObjectName("PrimaryButton")
        self.btn_manual_report.setFixedWidth(180)
        self.btn_manual_report.setToolTip(
            "立即对所有自选股执行技术面分析并推送到企业微信"
        )
        btn_row_layout.addWidget(self.btn_manual_report)

        # 手动导出 Excel 按钮
        self.btn_manual_export_excel = QPushButton("📊 导出指标数据到 Excel")
        self.btn_manual_export_excel.setObjectName("PrimaryButton")
        self.btn_manual_export_excel.setFixedWidth(180)
        self.btn_manual_export_excel.setToolTip(
            "立即导出当前所有自选股的技术指标（K线、BOLL、MACD、RSI、成交量等）到 Excel 文件"
        )
        btn_row_layout.addWidget(self.btn_manual_export_excel)

        # 手动抓取暗盘数据按钮
        self.btn_manual_fetch_dark_trade = QPushButton("🌙 刷新暗盘资金数据")
        self.btn_manual_fetch_dark_trade.setObjectName("PrimaryButton")
        self.btn_manual_fetch_dark_trade.setFixedWidth(180)
        self.btn_manual_fetch_dark_trade.setToolTip(
            "立即从东方财富网抓取全市场暗盘资金数据并更新缓存\n"
            "包括主力净流入、超大单/大单/中单/小单资金流向"
        )
        btn_row_layout.addWidget(self.btn_manual_fetch_dark_trade)

        # 测试暗盘统计推送按钮
        self.btn_test_dark_trade_stats = QPushButton("📊 测试暗盘统计推送")
        self.btn_test_dark_trade_stats.setObjectName("PrimaryButton")
        self.btn_test_dark_trade_stats.setFixedWidth(180)
        self.btn_test_dark_trade_stats.setToolTip(
            "立即计算暗盘资金统计并推送到企业微信\n用于测试暗盘统计推送功能是否正常"
        )
        btn_row_layout.addWidget(self.btn_test_dark_trade_stats)

        # 导出暗盘统计Excel按钮
        self.btn_export_dark_trade_excel = QPushButton("📈 导出暗盘Excel")
        self.btn_export_dark_trade_excel.setObjectName("SecondaryButton")
        self.btn_export_dark_trade_excel.setFixedWidth(140)
        self.btn_export_dark_trade_excel.setToolTip(
            "导出暗盘统计到Excel\n筛选条件：3日净流入>0 且 5日流入天数>3"
        )
        btn_row_layout.addWidget(self.btn_export_dark_trade_excel)

        quant_layout.addLayout(btn_row_layout)

        # [FIXED] 添加到父 widget 的 layout
        container_layout = QVBoxLayout()
        container_layout.addWidget(quant_group)
        parent_widget.setLayout(container_layout)

        # 页内信号（跨切面之外的连接收敛进本页）
        self.test_push_button.clicked.connect(self._on_test_push_clicked)
        self.test_app_button.clicked.connect(self._on_test_app_clicked)
        self.push_mode_combo.currentIndexChanged.connect(self._on_push_mode_changed)
        self.btn_manual_report.clicked.connect(self.ctx.manual_report_requested.emit)
        self.btn_manual_export_excel.clicked.connect(
            self._on_manual_export_excel_clicked
        )
        self.btn_manual_fetch_dark_trade.clicked.connect(
            self._on_manual_fetch_dark_trade_clicked
        )
        self.btn_test_dark_trade_stats.clicked.connect(
            self._on_test_dark_trade_stats_clicked
        )
        self.btn_export_dark_trade_excel.clicked.connect(
            self._on_export_dark_trade_excel_clicked
        )

    def load(self, settings: dict) -> None:
        """把量化 / 推送 / 斐波那契配置灌入本页控件。"""
        self.quant_enabled_checkbox.setChecked(settings.get("quant_enabled", False))
        self.auto_export_excel_checkbox.setChecked(
            settings.get("auto_export_excel", False)
        )
        self.auto_close_export_checkbox.setChecked(
            settings.get("auto_close_export", False)
        )
        self.wecom_webhook_input.setText(settings.get("wecom_webhook", ""))

        push_mode = settings.get("push_mode", "webhook")
        index = self.push_mode_combo.findData(push_mode)
        if index >= 0:
            self.push_mode_combo.setCurrentIndex(index)

        self.wecom_corpid_input.setText(settings.get("wecom_corpid", ""))
        self.wecom_corpsecret_input.setText(settings.get("wecom_corpsecret", ""))
        self.wecom_agentid_input.setText(settings.get("wecom_agentid", ""))

        # 斐波那契设置
        fib_coefficients = settings.get("fib_target_coefficients", {})
        self.fib_wave5_spin.setValue(fib_coefficients.get("wave_5_target", 0.618))
        self.fib_wave4_spin.setValue(fib_coefficients.get("wave_4_retrace", 0.382))
        self.fib_waveb_spin.setValue(fib_coefficients.get("wave_b_retrace", 0.5))

        # 收尾：按当前推送模式切换可见性
        self._on_push_mode_changed()

    def collect(self, settings: dict) -> None:
        """把量化 / 推送 / 斐波那契控件值写回配置字典。"""
        settings["quant_enabled"] = self.quant_enabled_checkbox.isChecked()
        settings["auto_export_excel"] = self.auto_export_excel_checkbox.isChecked()
        settings["auto_close_export"] = self.auto_close_export_checkbox.isChecked()
        settings["wecom_webhook"] = self.wecom_webhook_input.text().strip()
        settings["push_mode"] = self.push_mode_combo.currentData()
        settings["wecom_corpid"] = self.wecom_corpid_input.text().strip()
        settings["wecom_corpsecret"] = self.wecom_corpsecret_input.text().strip()
        settings["wecom_agentid"] = self.wecom_agentid_input.text().strip()
        settings["fib_target_coefficients"] = {
            "wave_5_target": self.fib_wave5_spin.value(),
            "wave_4_retrace": self.fib_wave4_spin.value(),
            "wave_b_retrace": self.fib_waveb_spin.value(),
        }

    def _on_test_push_clicked(self) -> None:
        """测试 Webhook 推送"""

        # [P1 FIX] 检查冷却时间
        current_time = time.time()
        if (
            current_time - self.ctx._last_webhook_test_time
            < self.ctx._webhook_test_cooldown
        ):
            remaining = int(
                self.ctx._webhook_test_cooldown
                - (current_time - self.ctx._last_webhook_test_time)
            )
            QMessageBox.warning(self, "请求过于频繁", f"请在 {remaining} 秒后再试")
            return

        webhook = self.wecom_webhook_input.text().strip()
        if not webhook:
            QMessageBox.warning(self, "提示", "请先输入 Webhook 地址")
            return

        from stock_monitor.services.notifier import NotifierService

        success = NotifierService.send_wecom_webhook_text(
            webhook, "这是一条来自股票监控系统的 Webhook 测试消息 🚀"
        )

        if success:
            self.ctx._last_webhook_test_time = current_time
            QMessageBox.information(self, "成功", "测试消息已发出，请检查企业微信通知")
        else:
            QMessageBox.critical(self, "失败", "发送失败，请检查 Webhook 地址是否正确")

    def _on_test_app_clicked(self) -> None:
        """测试企业应用推送并提供 IP 白名单诊断"""
        config = {
            "wecom_corpid": self.wecom_corpid_input.text().strip(),
            "wecom_corpsecret": self.wecom_corpsecret_input.text().strip(),
            "wecom_agentid": self.wecom_agentid_input.text().strip(),
        }

        if not all(config.values()):
            QMessageBox.warning(self, "提示", "请完整填写企业 ID、Secret 和 AgentID")
            return

        corp_id = config["wecom_corpid"]
        secret = config["wecom_corpsecret"]
        agent_id = config["wecom_agentid"]

        # 使用后台线程执行 HTTP 请求，避免阻塞 UI
        self._test_app_thread = TestAppThread(corp_id, secret, agent_id, self)
        self._test_app_thread.test_finished.connect(self._on_test_app_finished)
        self._test_app_thread.start()

    def _on_test_app_finished(self, result: dict) -> None:
        """处理测试应用推送结果"""
        if result["success"]:
            QMessageBox.information(
                self, "成功", "测试应用消息已发出，请检查手机企业微信"
            )
            return

        error = result.get("error")
        resp = result.get("response")

        if resp:
            errcode = resp.get("errcode")
            if errcode == 60020:
                errmsg = resp.get("errmsg", "")
                ip_match = re.search(r"from ip:\s*([0-9.]+)", errmsg)
                ip_str = ip_match.group(1) if ip_match else "您的公网IP"

                QMessageBox.critical(
                    self,
                    "发送失败 (IP白名单限制)",
                    f"❌ 企微自建应用推送失败：公网IP不在白名单内 (错误码 60020)\n\n"
                    f"您的当前公网IP: {ip_str}\n\n"
                    f"【解决方法】:\n"
                    f"1. 登录企业微信管理后台 (work.weixin.qq.com)。\n"
                    f"2. 进入 [应用管理] -> 点击您所填写的 [自建应用]。\n"
                    f"3. 找到 [企业可信IP] 属性，点击配置，将上述IP {ip_str} 添加到白名单中。\n"
                    f'4. 保存配置后，重新点击此处的"测试应用"。\n\n'
                    f"💡 友情提示：本系统已配备自动 Webhook 兜底。即使不配置白名单，在运行期间若应用通道发送失败，也会自动回退到 Webhook 群机器人渠道为您推送消息。",
                )
            else:
                QMessageBox.critical(
                    self,
                    "失败",
                    f"发送失败，请检查配置参数及网络状态。\n\n企微错误码: {errcode}\n错误详情: {resp.get('errmsg')}",
                )
        elif error:
            if "Token 失败" in error:
                QMessageBox.critical(
                    self,
                    "失败",
                    f"获取企业微信 Access Token 失败，请检查企业 ID 和应用密钥是否正确。\n\n{error}",
                )
            else:
                QMessageBox.critical(self, "错误", f"测试推送过程中发生异常:\n{error}")
        else:
            QMessageBox.critical(self, "失败", "测试推送失败，未知错误")

    def _on_push_mode_changed(self) -> None:
        """根据推送模式切换 UI 显示"""
        mode = self.push_mode_combo.currentData()
        self.webhook_container.setVisible(mode == "webhook")
        self.app_container.setVisible(mode == "app")

    def _reset_fib_settings(self) -> None:
        """重置斐波那契设置为默认值"""
        self.fib_wave5_spin.setValue(0.618)
        self.fib_wave4_spin.setValue(0.382)
        self.fib_waveb_spin.setValue(0.5)

    def _on_manual_export_excel_clicked(self) -> None:
        """手动执行自选股指标导出到 Excel"""

        self.btn_manual_export_excel.setEnabled(False)
        self.btn_manual_export_excel.setText("正在导出...")

        # 使用后台线程执行导出，避免阻塞 UI
        watchlist_codes = self._watchlist_codes()
        self._export_thread = ExcelExportThread(watchlist_codes, self)
        self._export_thread.export_finished.connect(self._on_export_finished)
        self._export_thread.start()

    def _on_export_finished(self, success: bool, result: str) -> None:
        """处理导出完成结果"""
        self.btn_manual_export_excel.setEnabled(True)
        self.btn_manual_export_excel.setText("导出自选股指标")

        if success:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "导出成功",
                f"自选股技术指标数据已成功导出至：\n{result}",
            )
        else:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "导出失败", f"导出过程中发生异常：\n{result}")

    def _on_manual_fetch_dark_trade_clicked(self) -> None:
        """手动抓取并导出暗盘资金数据到 Excel"""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox

        user_stocks = self._watchlist_codes()

        # 禁用按钮，显示进度
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.btn_manual_fetch_dark_trade.setEnabled(False)
        self.btn_manual_fetch_dark_trade.setText("⏳ 导出中...")
        QApplication.processEvents()

        def _restore_button() -> None:
            """恢复"刷新暗盘资金数据"按钮的可用状态与文案。"""
            self.btn_manual_fetch_dark_trade.setEnabled(True)
            self.btn_manual_fetch_dark_trade.setText("🌙 刷新暗盘资金数据")

        def _on_export_finished(success: bool, message: str) -> None:
            """导出完成回调（在主线程中执行）"""
            QApplication.restoreOverrideCursor()
            if success:
                QMessageBox.information(self, "导出成功", message)
            else:
                QMessageBox.critical(self, "导出失败", message)
            # 同时刷新内存缓存，使主界面暗盘列更新
            main_window = self.ctx.main_window
            if main_window and hasattr(main_window, "viewModel"):
                try:
                    main_window.viewModel.trigger_manual_dark_trade_fetch()
                except Exception:
                    pass

        # 在后台线程执行导出（避免阻塞UI）
        self._dark_export_thread = DarkTradeExportThread(user_stocks)
        self._dark_export_thread.export_finished.connect(_on_export_finished)
        self._dark_export_thread.finished.connect(self._dark_export_thread.deleteLater)
        self._dark_export_thread.start()

        # 延迟恢复按钮（避免瞬间恢复）
        QTimer.singleShot(3000, _restore_button)

    def _on_test_dark_trade_stats_clicked(self) -> None:
        """测试暗盘统计推送"""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox

        user_stocks = self._watchlist_codes()

        # 禁用按钮，显示进度
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.btn_test_dark_trade_stats.setEnabled(False)
        self.btn_test_dark_trade_stats.setText("⏳ 推送中...")
        QApplication.processEvents()

        def _restore_button() -> None:
            """恢复"测试暗盘统计推送"按钮的可用状态与文案。"""
            self.btn_test_dark_trade_stats.setEnabled(True)
            self.btn_test_dark_trade_stats.setText("📊 测试暗盘统计推送")

        def _on_push_finished(success: bool, message: str) -> None:
            """推送完成回调（在主线程中执行）"""
            QApplication.restoreOverrideCursor()
            if success:
                QMessageBox.information(self, "推送成功", message)
            else:
                QMessageBox.critical(self, "推送失败", message)

        # 在后台线程执行推送（避免阻塞UI）
        self._dark_stats_thread = DarkTradeStatsPushThread(user_stocks)
        self._dark_stats_thread.push_finished.connect(_on_push_finished)
        self._dark_stats_thread.finished.connect(self._dark_stats_thread.deleteLater)
        self._dark_stats_thread.start()

        # 延迟恢复按钮（避免瞬间恢复）
        QTimer.singleShot(3000, _restore_button)

    def _on_export_dark_trade_excel_clicked(self) -> None:
        """导出暗盘统计Excel（后台 QThread 执行，完成回调回到主线程）"""
        from PyQt6.QtWidgets import QApplication, QMessageBox

        user_stocks = self._watchlist_codes()

        # 禁用按钮，显示进度；WaitCursor 在完成回调中恢复（异常路径同样会回调）
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.btn_export_dark_trade_excel.setEnabled(False)
        self.btn_export_dark_trade_excel.setText("⏳ 导出中...")

        def _restore_button() -> None:
            """恢复"导出暗盘Excel"按钮的可用状态与文案。"""
            self.btn_export_dark_trade_excel.setEnabled(True)
            self.btn_export_dark_trade_excel.setText("📈 导出暗盘Excel")

        def _on_export_finished(success: bool, payload: str) -> None:
            """导出完成回调（由 QThread 信号排队回主线程执行）"""
            QApplication.restoreOverrideCursor()
            _restore_button()
            if success:
                QMessageBox.information(
                    self,
                    "导出成功",
                    f"暗盘统计Excel已导出到：\n{payload}",
                )
            else:
                msg = payload or "无符合条件的数据（3日净流入>0且5日流入天数>3）"
                QMessageBox.warning(self, "导出失败", f"导出失败：\n{msg}")

        # 在后台 QThread 中执行导出（信号自动回到主线程）
        self._dark_stats_excel_thread = DarkTradeStatsExcelExportThread(
            user_stocks, self
        )
        self._dark_stats_excel_thread.export_finished.connect(_on_export_finished)
        self._dark_stats_excel_thread.finished.connect(
            self._dark_stats_excel_thread.deleteLater
        )
        self._dark_stats_excel_thread.start()
