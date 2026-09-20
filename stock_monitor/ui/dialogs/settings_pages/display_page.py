"""显示设置页（P2）。

从 ``NewSettingsDialog`` 抽出的「🎨 显示设置」标签页：字体、透明度、任务栏
行情条设置与实时预览（防抖）。本页只依赖本页控件 + ``ctx.main_window`` +
字体预览 QTimer，不含 ``view_model``、无跨页写。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from .base import SettingsPage
from .context import SettingsContext


class DisplaySettingsPage(SettingsPage):
    """显示设置页：字体 / 透明度 / 任务栏行情条。"""

    SETTINGS_KEYS = (
        "font_size",
        "font_family",
        "transparency",
        "taskbar_quote_enabled",
        "taskbar_per_page",
        "taskbar_carousel_interval",
        "taskbar_show_price",
        "taskbar_show_change",
        "taskbar_show_dark_flow",
    )

    def __init__(self, ctx: SettingsContext, parent=None) -> None:
        """初始化显示页并创建字体预览防抖定时器与显示状态。"""
        super().__init__(ctx, parent)

        # 添加字体预览防抖定时器
        self._font_preview_timer = QTimer()
        self._font_preview_timer.setSingleShot(True)
        self._font_preview_timer.timeout.connect(self._apply_font_preview)
        self._pending_font_family = None
        self._pending_font_size = None
        self._original_display_settings = {
            "font_family": "微软雅黑",
            "font_size": 13,
            "transparency": 80,
        }

    def build(self, parent_widget) -> None:
        """在 ``parent_widget`` 上构建显示设置 UI [UI OPTIMIZATION - 标签页适配]。"""
        # [UI OPTIMIZATION] 添加图标，优化间距
        display_group = QGroupBox("🎨 显示设置")
        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(15, 15, 15, 15)
        display_layout.setSpacing(12)
        display_group.setLayout(display_layout)

        # === 显示设置行 ===
        display_row_layout = QHBoxLayout()
        display_row_layout.setContentsMargins(0, 0, 0, 0)
        display_row_layout.setSpacing(15)  # [OPTIMIZATION] 增加间距

        # 字体大小设置
        font_layout = QHBoxLayout()
        font_layout.setSpacing(8)  # [OPTIMIZATION] 增加元素间距
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(10, 40)
        self.font_size_slider.setValue(13)  # 默认 13px
        self.font_size_slider.setMinimumWidth(120)  # [OPTIMIZATION] 统一滑块长度
        self.font_size_slider.setObjectName("FontSizeSlider")

        self.font_size_value_label = QLabel("13px")
        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_value_label.setText(f"{v}px")
        )

        font_layout.addWidget(QLabel("字体大小:"))
        font_layout.addWidget(self.font_size_slider)
        font_layout.addWidget(self.font_size_value_label)

        # 字体设置
        font_family_layout = QHBoxLayout()
        font_family_layout.setSpacing(8)  # [OPTIMIZATION] 增加元素间距
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["微软雅黑", "宋体", "黑体", "楷体", "仿宋"])
        self.font_family_combo.setMinimumWidth(120)
        font_family_layout.addWidget(QLabel("字    体:"))
        font_family_layout.addWidget(self.font_family_combo)

        # 透明度设置
        transparency_layout = QHBoxLayout()
        transparency_layout.setSpacing(8)  # [OPTIMIZATION] 增加元素间距
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(80)
        self.transparency_slider.setMinimumWidth(120)  # [OPTIMIZATION] 统一滑块长度

        # 极简滑块样式
        self.transparency_slider.setObjectName("TransparencySlider")

        self.transparency_value_label = QLabel("80%")
        self.transparency_slider.valueChanged.connect(
            lambda v: self.transparency_value_label.setText(f"{v}%")
        )
        transparency_layout.addWidget(QLabel("透明度:"))
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_value_label)

        display_row_layout.addLayout(font_layout)
        display_row_layout.addSpacing(20)  # [OPTIMIZATION] 增加分组间距
        display_row_layout.addLayout(font_family_layout)
        display_row_layout.addSpacing(20)  # [OPTIMIZATION] 增加分组间距
        display_row_layout.addLayout(transparency_layout)
        display_row_layout.addSpacing(20)  # [OPTIMIZATION] 增加分组间距

        # 添加恢复默认值按钮
        self.reset_display_button = QPushButton("↺ 恢复默认")
        self.reset_display_button.setMinimumWidth(100)  # [OPTIMIZATION] 增加按钮宽度
        self.reset_display_button.setObjectName("reset_display_button")
        self.reset_display_button.clicked.connect(self.reset_display_settings)
        display_row_layout.addWidget(self.reset_display_button)

        display_row_layout.addStretch()

        display_layout.addLayout(display_row_layout)

        # === 任务栏行情条设置 ===
        taskbar_group = QGroupBox("📌 任务栏行情条")
        taskbar_layout = QVBoxLayout()
        taskbar_layout.setContentsMargins(10, 10, 10, 10)
        taskbar_layout.setSpacing(8)
        taskbar_group.setLayout(taskbar_layout)

        self.taskbar_quote_enabled_checkbox = QCheckBox(
            "在任务栏显示滚动行情（重启后生效）"
        )
        self.taskbar_quote_enabled_checkbox.setToolTip(
            "启用后将行情条嵌入 Windows 任务栏通知区左侧，滚动显示自选股。\n"
            "若嵌入失败（如系统限制），将自动降级到托盘图标轮播。"
        )
        taskbar_layout.addWidget(self.taskbar_quote_enabled_checkbox)

        taskbar_row = QHBoxLayout()
        taskbar_row.setSpacing(15)

        # 每页股票数
        per_page_layout = QHBoxLayout()
        per_page_layout.setSpacing(8)
        per_page_layout.addWidget(QLabel("每页显示:"))
        self.taskbar_per_page_spin = QDoubleSpinBox()
        self.taskbar_per_page_spin.setRange(1, 10)
        self.taskbar_per_page_spin.setDecimals(0)
        self.taskbar_per_page_spin.setSingleStep(1)
        self.taskbar_per_page_spin.setValue(3)
        per_page_layout.addWidget(self.taskbar_per_page_spin)
        per_page_layout.addWidget(QLabel("只"))
        taskbar_row.addLayout(per_page_layout)

        # 轮播间隔
        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(8)
        interval_layout.addWidget(QLabel("轮播间隔:"))
        self.taskbar_interval_spin = QDoubleSpinBox()
        self.taskbar_interval_spin.setRange(1, 60)
        self.taskbar_interval_spin.setDecimals(0)
        self.taskbar_interval_spin.setSingleStep(1)
        self.taskbar_interval_spin.setValue(5)
        interval_layout.addWidget(self.taskbar_interval_spin)
        interval_layout.addWidget(QLabel("秒"))
        taskbar_row.addLayout(interval_layout)

        taskbar_row.addStretch()
        taskbar_layout.addLayout(taskbar_row)

        # 显示字段
        fields_row = QHBoxLayout()
        fields_row.setSpacing(15)
        self.taskbar_show_price_checkbox = QCheckBox("显示价格")
        self.taskbar_show_price_checkbox.setChecked(True)
        self.taskbar_show_change_checkbox = QCheckBox("显示涨跌幅")
        self.taskbar_show_change_checkbox.setChecked(True)
        self.taskbar_show_dark_flow_checkbox = QCheckBox("显示暗盘")
        self.taskbar_show_dark_flow_checkbox.setChecked(False)
        fields_row.addWidget(self.taskbar_show_price_checkbox)
        fields_row.addWidget(self.taskbar_show_change_checkbox)
        fields_row.addWidget(self.taskbar_show_dark_flow_checkbox)
        fields_row.addStretch()
        taskbar_layout.addLayout(fields_row)

        # [FIXED] 添加到父 widget 的 layout
        container_layout = QVBoxLayout()
        container_layout.addWidget(display_group)
        container_layout.addWidget(taskbar_group)
        parent_widget.setLayout(container_layout)

        # 页内信号（字体 / 透明度实时预览）收敛进本页
        self.font_size_slider.valueChanged.connect(self.on_font_setting_changed)
        self.font_family_combo.currentTextChanged.connect(self.on_font_setting_changed)
        self.transparency_slider.valueChanged.connect(self.on_transparency_changed)

    def load(self, settings: dict) -> None:
        """把配置中的显示设置与任务栏设置灌入控件。"""
        # Font size
        fs = settings.get("font_size", 13)
        self.font_size_slider.setValue(int(fs))

        # Font family
        ff = settings.get("font_family", "微软雅黑")
        index = self.font_family_combo.findText(ff)
        if index >= 0:
            self.font_family_combo.setCurrentIndex(index)

        # Transparency
        tp = settings.get("transparency", 80)
        self.transparency_slider.setValue(int(tp))
        self._original_display_settings = {
            "font_family": ff,
            "font_size": int(fs),
            "transparency": int(tp),
        }

        # 任务栏行情条设置
        self.taskbar_quote_enabled_checkbox.setChecked(
            settings.get("taskbar_quote_enabled", False)
        )
        self.taskbar_per_page_spin.setValue(settings.get("taskbar_per_page", 3))
        self.taskbar_interval_spin.setValue(
            settings.get("taskbar_carousel_interval", 5)
        )
        self.taskbar_show_price_checkbox.setChecked(
            settings.get("taskbar_show_price", True)
        )
        self.taskbar_show_change_checkbox.setChecked(
            settings.get("taskbar_show_change", True)
        )
        self.taskbar_show_dark_flow_checkbox.setChecked(
            settings.get("taskbar_show_dark_flow", False)
        )

    def collect(self, settings: dict) -> None:
        """把显示设置与任务栏设置控件值写回配置字典。"""
        settings["font_size"] = self.font_size_slider.value()
        settings["font_family"] = self.font_family_combo.currentText()
        settings["transparency"] = self.transparency_slider.value()

        settings["taskbar_quote_enabled"] = (
            self.taskbar_quote_enabled_checkbox.isChecked()
        )
        settings["taskbar_per_page"] = int(self.taskbar_per_page_spin.value())
        settings["taskbar_carousel_interval"] = int(self.taskbar_interval_spin.value())
        settings["taskbar_show_price"] = self.taskbar_show_price_checkbox.isChecked()
        settings["taskbar_show_change"] = self.taskbar_show_change_checkbox.isChecked()
        settings["taskbar_show_dark_flow"] = (
            self.taskbar_show_dark_flow_checkbox.isChecked()
        )

    def on_font_setting_changed(self) -> None:
        """字体设置变化时的处理函数，用于实时预览（带防抖）"""
        main_window = self.ctx.main_window
        if not main_window:
            return

        try:
            # 获取当前字体设置
            font_size = self.font_size_slider.value()
            font_family = self.font_family_combo.currentText()

            # 保存待预览的值
            self._pending_font_family = font_family
            self._pending_font_size = font_size

            # 重启防抖定时器（300ms延迟）
            self._font_preview_timer.stop()
            self._font_preview_timer.start(300)

        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"字体设置变化处理失败: {e}")

    def _apply_font_preview(self) -> None:
        """应用字体预览（防抖后实际执行）"""
        main_window = self.ctx.main_window
        if not main_window or self._pending_font_family is None:
            return

        try:
            font_family = self._pending_font_family
            font_size = self._pending_font_size

            from stock_monitor.utils.logger import app_logger

            if font_size <= 0:
                app_logger.warning(f"检测到非法的字体大小: {font_size}，自动修正为 13")
            app_logger.debug(f"预览字体设置: {font_family}, {font_size}px")

            # 预览只写入主窗口内存态，点击“确定”时再统一持久化
            main_window._preview_font_family = font_family
            main_window._preview_font_size = font_size
            main_window.update_font_size()

        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"应用字体预览失败: {e}")

    def on_transparency_changed(self) -> None:
        """透明度设置变化时的处理函数，用于实时预览"""
        main_window = self.ctx.main_window
        if main_window:
            # 使用窗口级别的属性传递预览透明度值，触发主窗口重绘以预览背景透明度
            # 这样可以确保只改变背景透明度，不影响文字清晰度
            main_window._preview_transparency = self.transparency_slider.value()
            main_window.update()

    def reset_display_settings(self) -> None:
        """恢复显示设置为默认值"""
        try:
            from stock_monitor.utils.logger import app_logger

            app_logger.info("恢复显示设置为默认值")

            # 恢复默认值
            self.font_size_slider.setValue(13)
            self.font_family_combo.setCurrentText("微软雅黑")
            self.transparency_slider.setValue(80)

            # 显示提示（可选）
            QMessageBox.information(
                self,
                "恢复默认",
                "显示设置已恢复为默认值",
                QMessageBox.StandardButton.Ok,
            )
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"恢复默认设置失败: {e}")

    def _sync_original_display_settings_from_controls(self) -> None:
        """记录当前已确认的显示设置，供取消回滚使用。"""
        self._original_display_settings = {
            "font_family": self.font_family_combo.currentText(),
            "font_size": self.font_size_slider.value(),
            "transparency": self.transparency_slider.value(),
        }

    def restore(self) -> None:
        """取消时把控件回滚到已确认的显示设置。"""
        original_display = self._original_display_settings
        self.font_family_combo.setCurrentText(original_display["font_family"])
        self.font_size_slider.setValue(original_display["font_size"])
        self.transparency_slider.setValue(original_display["transparency"])

    def _clear_preview_state(self) -> None:
        """清理主窗口预览态，不触及持久化配置。"""
        main_window = self.ctx.main_window
        if not main_window:
            return

        for attr_name in (
            "_preview_font_family",
            "_preview_font_size",
            "_preview_transparency",
        ):
            if hasattr(main_window, attr_name):
                delattr(main_window, attr_name)

    def cleanup(self) -> None:
        """停止字体预览定时器并断开本页预览信号（best-effort）。"""
        if self._font_preview_timer:
            try:
                self._font_preview_timer.stop()
                # 不立即调用 deleteLater()，避免后续访问已删除对象
                self._font_preview_timer = None
            except Exception:
                pass  # 忽略定时器已删除的错误

        try:
            self.font_size_slider.valueChanged.disconnect(self.on_font_setting_changed)
            self.font_family_combo.currentTextChanged.disconnect(
                self.on_font_setting_changed
            )
            self.transparency_slider.valueChanged.disconnect(
                self.on_transparency_changed
            )
        except Exception:
            pass  # 忽略信号未连接的错误
