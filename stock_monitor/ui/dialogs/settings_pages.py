"""
设置对话框子页面模块
将原 NewSettingsDialog 拆分为独立的配置页类
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class QListWidgetWithAddButton(QListWidget):
    """带添加按钮的列表控件（占位实现，后续完善）"""

    pass


from stock_monitor.version import __version__


class SettingsPageBase(QWidget):
    """设置页面基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """设置 UI - 由子类实现"""
        raise NotImplementedError

    def connect_signals(self):
        """连接信号 - 由子类实现"""
        pass

    def load_config(self, config: dict):
        """加载配置 - 由子类实现"""
        pass

    def save_config(self) -> dict:
        """保存配置 - 由子类实现"""
        return {}


class WatchListSettingsPage(SettingsPageBase):
    """自选股设置页面"""

    stock_added = pyqtSignal(str)  # 股票代码
    stock_removed = pyqtSignal(str)  # 股票代码

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup_ui(self):
        """设置自选股 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 搜索输入
        search_label = QLabel("搜索股票")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入股票名称或拼音...")

        # 搜索结果列表
        self.search_results = QListWidgetWithAddButton()

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.add_button = QPushButton("添加 >>")
        self.add_button.setEnabled(False)
        btn_layout.addWidget(self.add_button)
        btn_layout.addStretch()

        layout.addWidget(search_label)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_results)
        layout.addLayout(btn_layout)

    def connect_signals(self):
        """连接信号"""
        self.add_button.clicked.connect(self._on_add_clicked)

    def _on_add_clicked(self):
        """处理添加按钮点击"""
        selected_items = self.search_results.selectedItems()
        for item in selected_items:
            code = item.data(Qt.ItemDataRole.UserRole)
            if code:
                self.stock_added.emit(code)

    def load_config(self, config: dict):
        """加载配置"""
        # 子类可根据需要实现
        pass

    def save_config(self) -> dict:
        """保存配置"""
        return {}


class DisplaySettingsPage(SettingsPageBase):
    """显示设置页面"""

    font_changed = pyqtSignal(str, int)  # (font_family, font_size)
    transparency_changed = pyqtSignal(int)  # 0-100

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup_ui(self):
        """设置显示相关 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 字体设置组
        font_group = QGroupBox("字体设置")
        font_layout = QVBoxLayout()

        # 字体系列
        font_family_layout = QHBoxLayout()
        font_family_layout.addWidget(QLabel("字体系列:"))
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(
            [
                "Microsoft YaHei",
                "SimSun",
                "SimHei",
                "Arial",
            ]
        )
        font_family_layout.addWidget(self.font_family_combo)
        font_layout.addLayout(font_family_layout)

        # 字体大小
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("字体大小:"))
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setMinimum(8)
        self.font_size_slider.setMaximum(24)
        self.font_size_label = QLabel("12")
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_label)
        font_layout.addLayout(font_size_layout)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # 透明度设置
        transparency_group = QGroupBox("透明度设置")
        transparency_layout = QHBoxLayout()
        transparency_layout.addWidget(QLabel("窗口透明度:"))
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setMinimum(50)
        self.transparency_slider.setMaximum(100)
        self.transparency_label = QLabel("100%")
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_label)
        transparency_group.setLayout(transparency_layout)
        layout.addWidget(transparency_group)

        layout.addStretch()

    def connect_signals(self):
        """连接信号"""
        self.font_family_combo.currentTextChanged.connect(
            lambda: self.font_changed.emit(
                self.font_family_combo.currentText(), self.font_size_slider.value()
            )
        )
        self.font_size_slider.valueChanged.connect(
            lambda value: (
                self.font_size_label.setText(str(value)),
                self.font_changed.emit(self.font_family_combo.currentText(), value),
            )
        )
        self.transparency_slider.valueChanged.connect(
            lambda value: (
                self.transparency_label.setText(f"{value}%"),
                self.transparency_changed.emit(value),
            )
        )

    def load_config(self, config: dict):
        """加载配置"""
        if "font_family" in config:
            index = self.font_family_combo.findText(config["font_family"])
            if index >= 0:
                self.font_family_combo.setCurrentIndex(index)

        if "font_size" in config:
            self.font_size_slider.setValue(config["font_size"])

        if "window_transparency" in config:
            self.transparency_slider.setValue(config["window_transparency"])

    def save_config(self) -> dict:
        """保存配置"""
        return {
            "font_family": self.font_family_combo.currentText(),
            "font_size": self.font_size_slider.value(),
            "window_transparency": self.transparency_slider.value(),
        }


class QuantSettingsPage(SettingsPageBase):
    """量化设置页面"""

    quant_enabled_changed = pyqtSignal(bool)
    scan_interval_changed = pyqtSignal(int)
    thresholds_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup_ui(self):
        """设置量化相关 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 量化开关
        self.quant_enabled_check = QCheckBox("启用量化监控")
        layout.addWidget(self.quant_enabled_check)

        # 扫描间隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("扫描间隔 (秒):"))
        self.scan_interval_spinbox = QSpinBox()
        self.scan_interval_spinbox.setRange(10, 300)
        self.scan_interval_spinbox.setSingleStep(10)
        interval_layout.addWidget(self.scan_interval_spinbox)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)

        # 阈值设置
        threshold_group = QGroupBox("信号阈值")
        threshold_layout = QVBoxLayout()

        # MACD 阈值
        macd_layout = QHBoxLayout()
        macd_layout.addWidget(QLabel("MACD 强度阈值:"))
        self.macd_threshold_spinbox = QDoubleSpinBox()
        self.macd_threshold_spinbox.setRange(0.0, 1.0)
        self.macd_threshold_spinbox.setSingleStep(0.05)
        macd_layout.addWidget(self.macd_threshold_spinbox)
        threshold_layout.addLayout(macd_layout)

        # RSRS 阈值
        rsrs_layout = QHBoxLayout()
        rsrs_layout.addWidget(QLabel("RSRS Z-Score 阈值:"))
        self.rsrs_threshold_spinbox = QDoubleSpinBox()
        self.rsrs_threshold_spinbox.setRange(-2.0, 2.0)
        self.rsrs_threshold_spinbox.setSingleStep(0.1)
        rsrs_layout.addWidget(self.rsrs_threshold_spinbox)
        threshold_layout.addLayout(rsrs_layout)

        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)

        layout.addStretch()

    def connect_signals(self):
        """连接信号"""
        self.quant_enabled_check.stateChanged.connect(
            lambda state: self.quant_enabled_changed.emit(
                state == Qt.CheckState.Checked
            )
        )
        self.scan_interval_spinbox.valueChanged.connect(self.scan_interval_changed.emit)

    def load_config(self, config: dict):
        """加载配置"""
        if "quant_enabled" in config:
            self.quant_enabled_check.setChecked(config["quant_enabled"])

        if "quant_scan_interval" in config:
            self.scan_interval_spinbox.setValue(config["quant_scan_interval"])

        if "macd_threshold" in config:
            self.macd_threshold_spinbox.setValue(config["macd_threshold"])

        if "rsrs_threshold" in config:
            self.rsrs_threshold_spinbox.setValue(config["rsrs_threshold"])

    def save_config(self) -> dict:
        """保存配置"""
        return {
            "quant_enabled": self.quant_enabled_check.isChecked(),
            "quant_scan_interval": self.scan_interval_spinbox.value(),
            "macd_threshold": self.macd_threshold_spinbox.value(),
            "rsrs_threshold": self.rsrs_threshold_spinbox.value(),
        }


class SystemSettingsPage(SettingsPageBase):
    """系统设置页面"""

    update_check_requested = pyqtSignal()
    test_push_requested = pyqtSignal()
    test_app_push_requested = pyqtSignal()
    manual_report_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def setup_ui(self):
        """设置系统相关 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 版本信息
        version_group = QGroupBox("版本信息")
        version_layout = QVBoxLayout()
        self.version_label = QLabel(f"版本：Stock Monitor v{__version__}")
        version_layout.addWidget(self.version_label)

        self.check_update_button = QPushButton("检查更新")
        version_layout.addWidget(self.check_update_button)
        version_group.setLayout(version_layout)
        layout.addWidget(version_group)

        # 消息推送设置
        push_group = QGroupBox("消息推送")
        push_layout = QVBoxLayout()

        # Webhook 配置
        webhook_layout = QHBoxLayout()
        webhook_layout.addWidget(QLabel("企业微信 Webhook:"))
        self.wecom_webhook_input = QLineEdit()
        self.wecom_webhook_input.setPlaceholderText(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )
        webhook_layout.addWidget(self.wecom_webhook_input)
        push_layout.addLayout(webhook_layout)

        # 推送模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("推送模式:"))
        self.push_mode_combo = QComboBox()
        self.push_mode_combo.addItems(["Webhook", "企业应用"])
        mode_layout.addWidget(self.push_mode_combo)
        mode_layout.addStretch()
        push_layout.addLayout(mode_layout)

        # 测试按钮
        test_btn_layout = QHBoxLayout()
        self.test_push_button = QPushButton("测试 Webhook 推送")
        self.test_app_button = QPushButton("测试企业应用推送")
        test_btn_layout.addWidget(self.test_push_button)
        test_btn_layout.addWidget(self.test_app_button)
        push_layout.addLayout(test_btn_layout)

        push_group.setLayout(push_layout)
        layout.addWidget(push_group)

        # 手动报告
        report_group = QGroupBox("复盘报告")
        report_layout = QHBoxLayout()
        self.btn_manual_report = QPushButton("生成早盘复盘")
        report_layout.addWidget(self.btn_manual_report)
        report_layout.addStretch()
        report_group.setLayout(report_layout)
        layout.addWidget(report_group)

        layout.addStretch()

    def connect_signals(self):
        """连接信号"""
        self.check_update_button.clicked.connect(
            lambda: self.update_check_requested.emit()
        )
        self.test_push_button.clicked.connect(lambda: self.test_push_requested.emit())
        self.test_app_button.clicked.connect(
            lambda: self.test_app_push_requested.emit()
        )
        self.btn_manual_report.clicked.connect(
            lambda: self.manual_report_requested.emit()
        )

    def load_config(self, config: dict):
        """加载配置"""
        if "wecom_webhook" in config:
            self.wecom_webhook_input.setText(config["wecom_webhook"])

        if "push_mode" in config:
            index = self.push_mode_combo.findText(config["push_mode"])
            if index >= 0:
                self.push_mode_combo.setCurrentIndex(index)

    def save_config(self) -> dict:
        """保存配置"""
        return {
            "wecom_webhook": self.wecom_webhook_input.text(),
            "push_mode": self.push_mode_combo.currentText(),
        }
