"""设置对话框页面包（C4 结构治理）。

把 ``NewSettingsDialog`` 中按逻辑页划分的 UI 构建与读写逻辑，逐步抽到
``SettingsPage`` 子类中，使对话框文件专注于跨页编排与窗口生命周期。
"""

from .base import SettingsPage
from .context import SettingsContext
from .display_page import DisplaySettingsPage
from .general_page import GeneralSettingsPage
from .quant_page import QuantSettingsPage
from .watchlist_page import WatchlistPage

__all__ = [
    "SettingsContext",
    "SettingsPage",
    "GeneralSettingsPage",
    "DisplaySettingsPage",
    "WatchlistPage",
    "QuantSettingsPage",
]
