"""通用设置页（P0 底部公共栏）。

C4-2 结构治理：把原内联在 ``NewSettingsDialog`` 中的底部「系统设置」行
（开机启动 / 刷新频率 / 版本与检查更新）及其处理逻辑抽到本页。

注意：P0 不是标签页，而是挂在 ``main_layout`` 底部的公共行，且同一行里混有
shell 级的「确定 / 取消」按钮。为保持一行内的控件顺序、stretch 与间距完全一致，
本页只负责构建系统设置子布局（``build_into``），确定/取消仍由 shell 构建，
``accept`` / ``reject`` 语义留在 shell。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from stock_monitor.ui.workers.settings_workers import UpdateCheckThread
from stock_monitor.version import __version__

from .base import SettingsPage
from .context import SettingsContext


class GeneralSettingsPage(SettingsPage):
    """通用设置页：开机启动 / 刷新频率 / 检查更新。"""

    SETTINGS_KEYS = ("auto_start", "refresh_interval")

    def __init__(self, ctx: SettingsContext, parent=None) -> None:
        """初始化通用设置页。"""
        super().__init__(ctx, parent)
        self._update_thread = None

    def build_into(self, bottom_layout) -> None:
        """在底部布局中构建系统设置子布局（不含确定/取消）。

        Args:
            bottom_layout: shell 的底部水平布局，本页把系统设置子布局以
                ``stretch=1`` 追加进去（与既有实现一致）。
        """
        # 系统设置行（移出分组框）
        system_layout = QHBoxLayout()
        system_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        system_layout.setSpacing(6)  # 调整为 6px 间距
        system_layout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
        )  # 垂直居中对齐，确保与按钮视觉齐平

        # 开机启动
        self.auto_start_checkbox = QCheckBox()
        self.auto_start_checkbox.setToolTip("开机自动启动")
        # 添加鼠标悬停反馈
        # 注意：大部分样式已在全局样式表中定义，这里只需要补充悬停效果

        # 刷新频率：1-60 秒自由输入（不再限定 1/2/5/10/30 预设）
        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(1, 60)
        self.refresh_spin.setValue(5)
        self.refresh_spin.setSuffix(" 秒")
        self.refresh_spin.setMinimumWidth(80)
        self.refresh_spin.setToolTip("行情自动刷新间隔（1-60 秒，可直接输入任意值）")

        # 检查更新
        update_layout = QHBoxLayout()
        update_layout.setSpacing(4)
        self.version_label = QLabel(f"v{__version__}")
        self.check_update_button = QPushButton("检查更新")
        self.check_update_button.setObjectName("checkUpdateButton")
        update_layout.addWidget(self.version_label)
        update_layout.addWidget(self.check_update_button)

        # 添加开机启动标签和复选框
        self.auto_start_label = QLabel("开机启动:")
        system_layout.addWidget(self.auto_start_label)
        system_layout.addWidget(self.auto_start_checkbox)
        system_layout.addSpacing(6)  # 调整为 6px 间距
        system_layout.addWidget(QLabel("刷新频率:"))
        system_layout.addWidget(self.refresh_spin)
        system_layout.addSpacing(6)  # 调整为 6px 间距

        # 添加版本号标签
        version_label_text = QLabel("版本号:")
        system_layout.addWidget(version_label_text)
        # 从配置文件读取版本号
        self.version_label.setText(f"v{__version__}")
        system_layout.addLayout(update_layout)
        system_layout.addStretch()

        bottom_layout.addLayout(system_layout, 1)

        # 页内信号：检查更新按钮（跨切面之外，收敛进本页）
        self.check_update_button.clicked.connect(self.check_for_updates)

    def build(self, parent_widget) -> None:
        """基类契约适配：把系统设置行构建进 ``parent_widget``（P0 非标签页）。"""
        layout = QVBoxLayout()
        self.build_into(layout)
        parent_widget.setLayout(layout)

    def load(self, settings: dict) -> None:
        """把开机启动与刷新频率灌入控件。"""
        self.auto_start_checkbox.setChecked(settings.get("auto_start", False))

        # Refresh interval：仅接受 1-60 整数，越界/非法值回落默认 5
        ri = settings.get("refresh_interval", 5)
        if isinstance(ri, bool) or not isinstance(ri, int) or not (1 <= ri <= 60):
            ri = 5
        self.refresh_spin.setValue(ri)

    def collect(self, settings: dict) -> None:
        """把开机启动与刷新频率写回配置字典。"""
        settings["auto_start"] = self.auto_start_checkbox.isChecked()
        settings["refresh_interval"] = self.refresh_spin.value()

    def apply_auto_start(self) -> None:
        """应用开机启动设置（``accept`` 时调用）。"""
        auto_start_enabled = self.auto_start_checkbox.isChecked()
        self._set_auto_start(auto_start_enabled)

    def get_refresh_interval(self) -> int:
        """返回当前刷新频率数值（供 shell 发信号时使用）。"""
        return self.refresh_spin.value()

    def check_for_updates(self) -> None:
        """检查更新"""
        try:
            self.check_update_button.setEnabled(False)
            self.check_update_button.setText("检查中...")

            # [P2 FIX] 使用提取的线程类，避免内联定义
            self._update_thread = UpdateCheckThread()
            self._update_thread.finished_check.connect(self._on_update_check_result)
            self._update_thread.error_occurred.connect(
                lambda e: self._on_update_check_result(None, error_msg=e)
            )
            self._update_thread.finished.connect(self._update_thread.deleteLater)
            self._update_thread.start()

        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"启动自动更新检查失败：{e}")
            self._on_update_check_result(None, error_msg=str(e))

    def _on_update_check_result(self, result, error_msg=None) -> None:
        """处理更新检查结果"""
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("检查更新")

        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QMessageBox, QProgressDialog

        from stock_monitor.core.updater import app_updater

        if error_msg:
            QMessageBox.critical(
                self,
                "检查更新失败",
                f"检查更新失败：{error_msg}",
                QMessageBox.StandardButton.Ok,
            )
            return

        try:
            if result is True:
                # 有新版本，显示提示框
                latest_version = (
                    app_updater.latest_release_info.get("tag_name", "")
                    .replace("stock_monitor_", "")
                    .replace("v", "")
                )
                release_body = app_updater.latest_release_info.get(
                    "body", "暂无更新说明"
                )

                message = f"发现新版本!\n\n当前版本: {app_updater.current_version}\n最新版本: {latest_version}\n\n更新说明:\n{release_body}\n\n是否现在更新?"

                reply = QMessageBox.question(
                    self,
                    "发现新版本",
                    message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    progress_dialog = QProgressDialog(
                        "正在下载更新...", "取消", 0, 100, self
                    )
                    progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                    progress_dialog.setWindowTitle("下载更新")
                    progress_dialog.setAutoClose(True)
                    progress_dialog.setAutoReset(True)
                    progress_dialog.show()

                    def progress_cb(percent) -> None:
                        """下载进度回调：更新进度对话框数值。

                        不再手动调用 QApplication.processEvents()，
                        Qt 事件循环会在合适的时机处理重绘。
                        """
                        progress_dialog.setValue(percent)

                    def is_cancelled_cb() -> bool:
                        """取消检查回调：返回用户是否已取消下载。"""
                        return progress_dialog.wasCanceled()

                    def security_warn_cb(warn_msg) -> bool:
                        """安全提示回调：弹出确认框，返回用户是否选择继续。"""
                        reply_warn = QMessageBox.warning(
                            self,
                            "安全提示",
                            warn_msg,
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.Yes,
                        )
                        return reply_warn == QMessageBox.StandardButton.Yes

                    def error_cb(err_msg) -> None:
                        """下载错误回调：弹出错误提示框。"""
                        QMessageBox.critical(
                            self, "更新错误", err_msg, QMessageBox.StandardButton.Ok
                        )

                    # 下载更新
                    update_file = app_updater.download_update(
                        progress_callback=progress_cb,
                        is_cancelled_callback=is_cancelled_cb,
                        security_warning_callback=security_warn_cb,
                        error_callback=error_cb,
                    )

                    progress_dialog.close()

                    if update_file:
                        # 应用更新
                        if not app_updater.apply_update(update_file):
                            QMessageBox.critical(
                                self,
                                "更新失败",
                                "应用更新包时发生错误",
                                QMessageBox.StandardButton.Ok,
                            )
                    else:
                        if not progress_dialog.wasCanceled():
                            QMessageBox.warning(
                                self,
                                "下载失败",
                                "更新包下载失败,请检查网络连接后重试。",
                                QMessageBox.StandardButton.Ok,
                            )
            elif result is False:
                QMessageBox.information(
                    self,
                    "无更新",
                    "当前已是最新版本，无需更新",
                    QMessageBox.StandardButton.Ok,
                )
            else:
                QMessageBox.critical(
                    self,
                    "检查更新失败",
                    "检查更新失败：网络连接异常，请稍后重试",
                    QMessageBox.StandardButton.Ok,
                )
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"处理更新结果失败: {e}")

    def _set_auto_start(self, enabled) -> None:
        """
        设置开机启动

        Args:
            enabled (bool): 是否启用开机启动
        """
        try:
            import os
            import sys

            from stock_monitor.utils.logger import app_logger

            if not hasattr(sys, "_MEIPASS"):
                app_logger.info("[开发环境] 跳过设置页开机启动变更，避免影响已安装版本")
                return

            # 获取启动文件夹路径
            startup_folder = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "Startup",
            )

            # 检查启动文件夹是否存在
            if not os.path.exists(startup_folder):
                app_logger.warning(f"启动文件夹不存在: {startup_folder}")
                return

            shortcut_path = os.path.join(startup_folder, "StockMonitor.lnk")

            if enabled:
                # 获取应用程序路径
                if hasattr(sys, "_MEIPASS"):
                    # PyInstaller打包环境
                    app_path = sys.executable
                else:
                    # 开发环境
                    app_path = os.path.abspath(sys.argv[0])

                # 创建快捷方式
                self._create_shortcut(app_path, shortcut_path)
                app_logger.info(f"已创建开机启动快捷方式: {shortcut_path}")
            else:
                # 删除快捷方式（如果存在）
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                    app_logger.info(f"已删除开机启动快捷方式: {shortcut_path}")
        except Exception as e:
            from stock_monitor.utils.logger import app_logger

            app_logger.error(f"设置开机启动失败: {e}")

    def _create_shortcut(self, target_path, shortcut_path):
        """
        创建快捷方式

        Args:
            target_path (str): 目标文件路径
            shortcut_path (str): 快捷方式保存路径
        """
        try:
            # 尝试使用win32com创建快捷方式
            import os

            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target_path
            shortcut.WorkingDirectory = os.path.dirname(target_path)
            shortcut.save()
        except ImportError:
            # win32com 不可用时的备选方案
            from stock_monitor.utils.logger import app_logger

            app_logger.warning(
                "pywin32 未安装，无法创建开机启动快捷方式。"
                "建议运行：pip install pywin32"
            )
            # 不再创建批处理文件作为备选，因为安全性和用户体验较差
            return False
