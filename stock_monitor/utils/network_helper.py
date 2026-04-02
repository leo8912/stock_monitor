"""
网络请求错误处理工具模块
提供统一的 HTTP 请求封装和错误处理机制
"""

from typing import Any, Optional

import requests
from requests.exceptions import HTTPError, RequestException, Timeout


class NetworkRequestError(Exception):
    """网络请求异常基类"""

    pass


class HTTPStatusError(NetworkRequestError):
    """HTTP 状态码错误"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class APIResponseError(NetworkRequestError):
    """API 响应错误"""

    def __init__(self, error_code: int, message: str):
        self.error_code = error_code
        super().__init__(f"API Error {error_code}: {message}")


class SafeRequest:
    """安全的 HTTP 请求封装类"""

    @staticmethod
    def get(
        url: str,
        timeout: int = 10,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        **kwargs,
    ) -> Optional[requests.Response]:
        """
        安全的 GET 请求

        Args:
            url: 请求 URL（必须使用 HTTPS）
            timeout: 超时时间 (秒)
            headers: 请求头
            params: URL 参数
            **kwargs: 其他传递给 requests 的参数

        Returns:
            Response 对象或 None（失败时）

        Raises:
            HTTPStatusError: HTTP 状态码错误
            NetworkRequestError: 网络错误
        """
        # 强制使用 HTTPS
        if not url.startswith("https://"):
            from ..utils.logger import app_logger

            app_logger.warning(f"非 HTTPS URL，已强制转换：{url}")
            url = url.replace("http://", "https://")

        try:
            resp = requests.get(
                url, timeout=timeout, headers=headers, params=params, **kwargs
            )
            resp.raise_for_status()  # 检查 HTTP 状态码
            return resp

        except HTTPError as e:
            from ..utils.logger import app_logger

            app_logger.error(f"HTTP 错误 [{e.response.status_code}]: {e}")
            raise HTTPStatusError(e.response.status_code, str(e)) from e

        except Timeout as e:
            from ..utils.logger import app_logger

            app_logger.error(f"请求超时 ({timeout}s): {url}")
            raise NetworkRequestError(f"请求超时：{e}") from e

        except RequestException as e:
            from ..utils.logger import app_logger

            app_logger.error(f"网络异常：{e}")
            raise NetworkRequestError(f"网络错误：{e}") from e

    @staticmethod
    def post(
        url: str,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: int = 10,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Optional[requests.Response]:
        """
        安全的 POST 请求

        Args:
            url: 请求 URL（必须使用 HTTPS）
            json: JSON 数据
            data: 表单数据
            timeout: 超时时间 (秒)
            headers: 请求头
            **kwargs: 其他传递给 requests 的参数

        Returns:
            Response 对象或 None（失败时）

        Raises:
            HTTPStatusError: HTTP 状态码错误
            NetworkRequestError: 网络错误
        """
        # 强制使用 HTTPS
        if not url.startswith("https://"):
            from ..utils.logger import app_logger

            app_logger.warning(f"非 HTTPS URL，已强制转换：{url}")
            url = url.replace("http://", "https://")

        try:
            resp = requests.post(
                url, json=json, data=data, timeout=timeout, headers=headers, **kwargs
            )
            resp.raise_for_status()  # 检查 HTTP 状态码
            return resp

        except HTTPError as e:
            from ..utils.logger import app_logger

            app_logger.error(f"HTTP 错误 [{e.response.status_code}]: {e}")
            raise HTTPStatusError(e.response.status_code, str(e)) from e

        except Timeout as e:
            from ..utils.logger import app_logger

            app_logger.error(f"POST 请求超时 ({timeout}s): {url}")
            raise NetworkRequestError(f"请求超时：{e}") from e

        except RequestException as e:
            from ..utils.logger import app_logger

            app_logger.error(f"POST 网络异常：{e}")
            raise NetworkRequestError(f"网络错误：{e}") from e


def safe_request_get(
    url: str, timeout: int = 10, expect_json: bool = True, **kwargs
) -> Optional[Any]:
    """
    便捷函数：安全的 GET 请求并返回解析后的数据

    Args:
        url: 请求 URL
        timeout: 超时时间
        expect_json: 是否期望 JSON 响应
        **kwargs: 其他参数

    Returns:
        解析后的数据（JSON 或文本）或 None
    """
    try:
        resp = SafeRequest.get(url, timeout=timeout, **kwargs)
        if resp is None:
            return None

        if expect_json:
            return resp.json()
        else:
            return resp.text

    except Exception as e:
        from ..utils.logger import app_logger

        app_logger.error(f"GET 请求失败：{e}")
        return None


def safe_request_post(
    url: str,
    json_data: Optional[dict] = None,
    timeout: int = 10,
    expect_json: bool = True,
    **kwargs,
) -> Optional[Any]:
    """
    便捷函数：安全的 POST 请求并返回解析后的数据

    Args:
        url: 请求 URL
        json_data: JSON 数据
        timeout: 超时时间
        expect_json: 是否期望 JSON 响应
        **kwargs: 其他参数

    Returns:
        解析后的数据或 None
    """
    try:
        resp = SafeRequest.post(url, json=json_data, timeout=timeout, **kwargs)
        if resp is None:
            return None

        if expect_json:
            return resp.json()
        else:
            return resp.text

    except Exception as e:
        from ..utils.logger import app_logger

        app_logger.error(f"POST 请求失败：{e}")
        return None


# 预定义的超时配置
class TimeoutConfig:
    """超时配置常量"""

    SHORT = 5  # 短超时（简单请求）
    DEFAULT = 10  # 默认超时
    LONG = 30  # 长超时（大数据量）
    VERY_LONG = 60  # 超长超时（文件上传等）
