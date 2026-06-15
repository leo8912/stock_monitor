from typing import Any, Optional

import requests

from ..utils.logger import app_logger


class NetworkManager:
    """网络请求管理器"""

    def __init__(self, timeout: int = 15):
        """
        初始化网络管理器

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()
        # 设置默认请求头
        self.session.headers.update(
            {
                "User-Agent": "StockMonitor/4.4 (Windows; Python)",
                "Accept": "application/vnd.github.v3+json",
            }
        )

    def close(self):
        """关闭会话，释放连接资源"""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        发送GET请求

        Args:
            url: 请求URL
            **kwargs: 其他请求参数

        Returns:
            Response对象或None（如果失败）
        """
        try:
            if "timeout" not in kwargs:
                kwargs["timeout"] = self.timeout

            response = self.session.get(url, **kwargs)
            response.raise_for_status()  # 检查HTTP错误
            app_logger.debug(f"GET请求成功: {url}")
            return response
        except requests.exceptions.RequestException as e:
            app_logger.error(f"GET请求失败: {url}, 错误: {e}")
            return None

    def post(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        发送POST请求

        Args:
            url: 请求URL
            **kwargs: 其他请求参数

        Returns:
            Response对象或None（如果失败）
        """
        try:
            if "timeout" not in kwargs:
                kwargs["timeout"] = self.timeout

            response = self.session.post(url, **kwargs)
            response.raise_for_status()  # 检查HTTP错误
            app_logger.debug(f"POST请求成功: {url}")
            return response
        except requests.exceptions.RequestException as e:
            app_logger.error(f"POST请求失败: {url}, 错误: {e}")
            return None

    def github_api_request(
        self, url: str, use_mirror: bool = False
    ) -> Optional[dict[Any, Any]]:
        """
        发送GitHub API请求

        Args:
            url: GitHub API URL
            use_mirror: 已废弃，保留接口兼容

        Returns:
            JSON响应数据或None（如果失败）
        """
        # GitHub API 请求使用更长超时 + 可选 Token
        old_timeout = self.timeout
        self.timeout = 30
        try:
            # 如果配置了 GitHub Token，添加认证（提高限流到 5000次/小时）
            try:
                from stock_monitor.core.config_center import config_center

                token = config_center.get_str("github_token", "")
                if token:
                    self.session.headers["Authorization"] = f"token {token}"
            except Exception:
                pass

            response = self.get(url)
        finally:
            self.timeout = old_timeout
            # 清理认证头
            self.session.headers.pop("Authorization", None)

        if response:
            try:
                return response.json()
            except ValueError as e:
                app_logger.error(f"解析GitHub API响应失败: {e}")
                return None
        return None
