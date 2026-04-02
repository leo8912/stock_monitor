from json import JSONDecodeError
from typing import Any, Optional

from packaging import version
from requests.exceptions import HTTPError, RequestException, Timeout

from stock_monitor.network.manager import NetworkManager
from stock_monitor.utils.logger import app_logger


class UpdateChecker:
    """负责检查应用更新"""

    def __init__(self, github_repo: str, current_version: str):
        self.github_repo = github_repo
        self.current_version = current_version
        self.network_manager = NetworkManager()
        self.latest_release_info: Optional[dict[Any, Any]] = None

    def check_for_updates(self) -> Optional[bool]:
        """
        检查是否有新版本可用

        Returns:
            bool: 如果有新版本返回 True，如果没有新版本返回 False，如果网络错误返回 None
        """
        try:
            app_logger.info("开始检查更新...")

            # 首先尝试使用原始 GitHub 地址
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            release_info = self.network_manager.github_api_request(api_url)

            # 如果失败，尝试使用镜像源
            if not release_info:
                app_logger.warning(
                    "使用 GitHub 原始地址检查更新失败，尝试使用镜像源..."
                )
                release_info = self.network_manager.github_api_request(
                    api_url, use_mirror=True
                )

            if not release_info:
                app_logger.warning("无法获取最新的 release 信息")
                return None  # 网络问题，无法确定是否有新版本

            self.latest_release_info = release_info
            latest_version = (
                release_info.get("tag_name", "")
                .replace("stock_monitor_", "")
                .replace("v", "")
            )

            app_logger.info(
                f"当前版本：{self.current_version}, 最新版本：{latest_version}"
            )

            # 比较版本号
            if version.parse(latest_version) > version.parse(self.current_version):
                app_logger.info("发现新版本")
                return True
            else:
                app_logger.info("当前已是最新版本")
                return False

        except HTTPError as e:
            app_logger.error(f"GitHub API HTTP 错误 [{e.response.status_code}]: {e}")
            return None
        except Timeout:
            app_logger.error("GitHub API 请求超时")
            return None
        except RequestException as e:
            app_logger.error(f"GitHub API 网络异常：{e}")
            return None
        except (JSONDecodeError, ValueError) as e:
            app_logger.error(f"GitHub API 响应解析失败：{e}")
            return None
        except Exception as e:
            app_logger.error(f"检查更新时发生未知错误：{e}", exc_info=True)
            return None
