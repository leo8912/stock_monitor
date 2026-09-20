"""设置页基类。

``SettingsPage`` 定义所有设置页的统一契约：在给定父布局/父控件上构建 UI
（``build``）、把配置字典灌入控件（``load``）、把控件值写回配置字典
（``collect``）、可选校验（``validate``）与资源清理（``cleanup``）。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from .context import SettingsContext


class SettingsPage(QWidget):
    """设置页基类，约定 build/load/collect/validate/cleanup 契约。"""

    #: 该页在 ``collect``/``load`` 中读写的配置键（供编排层参考）
    SETTINGS_KEYS: tuple = ()

    def __init__(self, ctx: SettingsContext, parent=None) -> None:
        """初始化设置页。

        Args:
            ctx: 共享上下文。
            parent: 可选父控件。
        """
        super().__init__(parent)
        self.ctx = ctx

    def build(self, parent_widget) -> None:
        """在 ``parent_widget`` 上构建本页 UI。

        Args:
            parent_widget: 承载本页控件的父控件（通常为本页自身或标签页容器）。
        """
        raise NotImplementedError

    def load(self, settings: dict) -> None:
        """把配置字典中的值灌入本页控件。

        Args:
            settings: 由 ViewModel 提供的配置字典。
        """
        raise NotImplementedError

    def collect(self, settings: dict) -> None:
        """把本页控件当前值写回配置字典。

        Args:
            settings: 待保存的配置字典（原地更新）。
        """
        raise NotImplementedError

    def validate(self) -> bool:
        """校验本页输入是否有效，默认通过。"""
        return True

    def cleanup(self) -> None:
        """释放本页资源（定时器/信号等），默认无操作。"""
