from typing import Any, Optional

from stock_monitor.core.app_update.checker import UpdateChecker
from stock_monitor.core.app_update.downloader import UpdateDownloader
from stock_monitor.core.app_update.installer import UpdateInstaller
from stock_monitor.utils.logger import app_logger
from stock_monitor.version import __version__


class AppUpdater:
    """应用程序更新器 (Facade)"""

    def __init__(self, github_repo: str = "leo8912/stock_monitor"):
        self.current_version = __version__
        self.checker = UpdateChecker(github_repo, self.current_version)
        self.downloader = UpdateDownloader()
        self.installer = UpdateInstaller()

    @property
    def latest_release_info(self) -> Optional[dict[Any, Any]]:
        return self.checker.latest_release_info

    def check_for_updates(self) -> Optional[bool]:
        """检查是否有新版本可用"""
        return self.checker.check_for_updates()

    def download_update(
        self,
        progress_callback=None,
        is_cancelled_callback=None,
        security_warning_callback=None,
        error_callback=None,
    ) -> Optional[str]:
        """下载更新包"""
        if not self.latest_release_info:
            app_logger.error("没有可用的更新信息，调用 download_update 失败")
            return None

        return self.downloader.download_update(
            self.latest_release_info,
            progress_callback,
            is_cancelled_callback,
            security_warning_callback,
            error_callback,
        )

    def apply_update(self, update_file_path: str) -> bool:
        """应用更新 (BAT脚本方案)"""
        return self.installer.apply_update(update_file_path)


# 创建全局更新器实例
app_updater = AppUpdater()
