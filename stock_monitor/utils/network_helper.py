"""
网络请求错误处理工具模块
提供统一的 HTTP 会话与请求封装
"""

import requests
from requests.exceptions import HTTPError, RequestException, Timeout


def create_session(headers: dict[str, str] | None = None) -> requests.Session:
    """创建统一配置的 HTTP 会话。

    会话所有权仍属于调用方：并发代码必须每个线程各自调用本函数，不能跨线程共享。
    """
    session = requests.Session()
    if headers:
        session.headers.update(headers)
    return session


class NetworkRequestError(Exception):
    """网络请求异常基类"""


class HTTPStatusError(NetworkRequestError):
    """HTTP 状态码错误"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class SafeRequest:
    """安全的 HTTP 请求封装类"""

    @staticmethod
    def get(
        url: str,
        timeout: int = 10,
        headers: dict | None = None,
        params: dict | None = None,
        **kwargs,
    ) -> requests.Response | None:
        """安全 GET；失败抛 NetworkRequestError / HTTPStatusError。"""
        if not url.startswith("https://"):
            from ..utils.logger import app_logger

            app_logger.warning(f"非 HTTPS URL，已强制转换：{url}")
            url = url.replace("http://", "https://")

        try:
            resp = requests.get(
                url, timeout=timeout, headers=headers, params=params, **kwargs
            )
            resp.raise_for_status()
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
        json: dict | None = None,
        data: dict | None = None,
        timeout: int = 10,
        headers: dict | None = None,
        **kwargs,
    ) -> requests.Response | None:
        """安全 POST；失败抛 NetworkRequestError / HTTPStatusError。"""
        if not url.startswith("https://"):
            from ..utils.logger import app_logger

            app_logger.warning(f"非 HTTPS URL，已强制转换：{url}")
            url = url.replace("http://", "https://")

        try:
            resp = requests.post(
                url, json=json, data=data, timeout=timeout, headers=headers, **kwargs
            )
            resp.raise_for_status()
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
