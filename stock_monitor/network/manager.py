import threading
from typing import Any

import requests

from ..utils.logger import app_logger
from ..utils.network_helper import create_session
from ..utils.retry import DEFAULT_MAX_ATTEMPTS, network_retry

# 默认重试等待（秒）——共享 utils.retry 策略，客户端内联使用
_RETRY_MIN_WAIT = 0.5
_RETRY_MAX_WAIT = 5.0


class NetworkManager:
    """统一 HTTP 客户端（canonical client）。

    - 显式 timeout（构造默认值 + 单次调用可覆盖）
    - 共享 ``utils.retry.network_retry`` 重试策略（可用 ``enable_retry=False`` 关闭）
    - ``threading.local`` 会话：并发调用下每线程独立 Session（Session 非线程安全）
    """

    def __init__(
        self,
        timeout: int | float | tuple = 15,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        enable_retry: bool = True,
    ):
        """
        初始化网络管理器

        Args:
            timeout: 默认请求超时时间（秒，或 (connect, read) 元组），
                单次调用可通过 kwargs["timeout"] 覆盖
            max_attempts: 共享重试策略的最大尝试次数
            enable_retry: 是否默认启用共享网络重试（单次调用可覆盖）
        """
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.enable_retry = enable_retry
        self._headers = {
            # 版本号应与 stock_monitor 版本保持同步
            "User-Agent": "StockMonitor/4.9 (Windows; Python)",
            "Accept": "application/vnd.github.v3+json",
        }
        self._local = threading.local()
        self._sessions_lock = threading.Lock()
        self._all_sessions: list[requests.Session] = []

    def _session(self) -> requests.Session:
        """返回当前线程绑定的 Session（惰性创建，记入关闭清单）。"""
        session = getattr(self._local, "session", None)
        if session is None:
            session = create_session(self._headers)
            self._local.session = session
            with self._sessions_lock:
                self._all_sessions.append(session)
        return session

    def close(self):
        """关闭本实例创建的所有会话，释放连接资源"""
        with self._sessions_lock:
            sessions, self._all_sessions = self._all_sessions, []
        for session in sessions:
            try:
                session.close()
            except Exception:
                app_logger.debug("关闭 Session 失败", exc_info=True)
        if hasattr(self._local, "session"):
            self._local.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def get(self, url: str, **kwargs) -> requests.Response | None:
        """
        发送GET请求

        Args:
            url: 请求URL
            **kwargs: 其他请求参数；支持 ``timeout``、``enable_retry``

        Returns:
            Response对象或None（如果失败）
        """
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response | None:
        """
        发送POST请求

        Args:
            url: 请求URL
            **kwargs: 其他请求参数；支持 ``timeout``、``enable_retry``

        Returns:
            Response对象或None（如果失败）
        """
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response | None:
        """带共享重试与显式超时的底层请求。失败返回 None（不向上抛）。"""
        enable_retry = kwargs.pop("enable_retry", self.enable_retry)
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        session = self._session()
        method_u = method.upper()

        def _once() -> requests.Response:
            response = session.request(method_u, url, **kwargs)
            response.raise_for_status()
            return response

        try:
            if enable_retry:
                response = network_retry(
                    max_attempts=self.max_attempts,
                    min_wait=_RETRY_MIN_WAIT,
                    max_wait=_RETRY_MAX_WAIT,
                )(_once)()
            else:
                response = _once()
            app_logger.debug(f"{method_u}请求成功: {url}")
            return response
        except (
            requests.exceptions.RequestException,
            ConnectionError,
            TimeoutError,
            OSError,
        ) as e:
            app_logger.error(f"{method_u}请求失败: {url}, 错误: {e}")
            return None
        except Exception as e:
            # 重试耗尽后 reraise 的底层异常也可能不是 RequestException
            app_logger.error(f"{method_u}请求失败: {url}, 错误: {e}")
            return None

    def github_api_request(
        self, url: str, use_mirror: bool = False
    ) -> dict[Any, Any] | None:
        """
        发送GitHub API请求

        Args:
            url: GitHub API URL
            use_mirror: 已废弃，保留接口兼容

        Returns:
            JSON响应数据或None（如果失败）
        """
        # GitHub API 请求使用更长超时 + 可选 Token
        # 注意：不修改 self.timeout 和会话 headers，避免多线程竞态
        headers = {}
        try:
            from stock_monitor.core.config_center import config_center

            token = config_center.get_str("github_token", "")
            if token:
                headers["Authorization"] = f"token {token}"
        except Exception:
            pass

        response = self.get(url, timeout=30, headers=headers)
        if response is None:
            return None

        try:
            return response.json()
        except ValueError as e:
            app_logger.error(f"解析GitHub API响应失败: {e}")
            return None
