import hashlib
import os
import re
import tempfile
import urllib.parse
from typing import Any, Optional

import requests
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)

from stock_monitor.utils.logger import app_logger

# 镜像源配置：国内环境优先使用镜像加速下载
GITHUB_MIRROR_PREFIX = "https://mirror.ghproxy.com/"

# 官方发布域名白名单（精确匹配 hostname，禁止子串匹配）
OFFICIAL_HOSTS = {
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
}

# 网络超时配置（秒）
CONNECT_TIMEOUT = 15  # 建立连接超时
READ_TIMEOUT = 30  # 数据读取超时（每个 chunk 的最大等待时间）

# 断点续传配置
CHUNK_SIZE = 8192  # 每次读取的块大小
MAX_RETRIES = 3  # 最大重试次数

# 合法 SHA256 十六进制格式
_SHA256_RE = re.compile(r"[a-fA-F0-9]{64}")


def _is_official_url(url: str) -> bool:
    """判断 URL 是否属于官方发布域名（hostname 精确匹配 + 标准端口）。

    Args:
        url: 待检查的 URL。

    Returns:
        bool: 属于官方域名且端口为标准 HTTPS 端口时返回 True，否则 False。
    """
    if not url:
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if hostname.lower() not in OFFICIAL_HOSTS:
        return False
    # 收紧：仅允许未显式指定端口或标准 HTTPS 端口 443，拒绝 github.com:444 之类
    try:
        port = parsed.port
    except ValueError:
        return False
    return port in (None, 443)


def _is_valid_sha256(value: str) -> bool:
    """校验字符串是否为合法的 64 位十六进制 SHA256。"""
    if not value:
        return False
    return _SHA256_RE.fullmatch(value.strip()) is not None


def _calculate_sha256(file_path: str) -> str:
    """计算文件的 SHA256 摘要（大写十六进制）。"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest().upper()


class UpdateDownloader:
    """负责下载应用更新包"""

    def download_update(
        self,
        latest_release_info: dict[Any, Any],
        progress_callback=None,
        is_cancelled_callback=None,
        security_warning_callback=None,
        error_callback=None,
    ) -> Optional[str]:
        """
        下载更新包

        采用优化策略：
        1. 优先使用镜像源下载（国内更快更稳定），失败回退到原始 GitHub
        2. 设置连接+读取双超时，防止下载卡死
        3. 支持断点续传，下载中断后从已下载位置继续

        Args:
            latest_release_info: release信息的字典
            progress_callback: 进度回调函数，接收(int)百分比参数
            is_cancelled_callback: 是否取消回调函数，返回bool
            security_warning_callback: 安全警告回调，接收(str)提示，返回bool(True继续)
            error_callback: 错误提示回调，接收(str)错误信息

        Returns:
            str: 下载文件的路径，如果失败返回None
        """
        if not latest_release_info:
            app_logger.error("没有可用的更新信息")
            return None

        try:
            # 查找zip文件资产
            assets = latest_release_info.get("assets", [])
            zip_asset = None
            for asset in assets:
                if asset.get("name", "").endswith(".zip"):
                    zip_asset = asset
                    break

            if not zip_asset:
                app_logger.error("未找到zip格式的更新包")
                return None

            download_url = zip_asset.get("browser_download_url")
            file_name = zip_asset.get("name", "update.zip")

            if not download_url:
                app_logger.error("未找到下载链接")
                return None

            app_logger.info(f"开始下载更新: {file_name}")

            # 准备下载路径
            temp_dir = tempfile.mkdtemp()
            download_path = os.path.join(temp_dir, file_name)

            # 构造镜像URL
            mirror_url = f"{GITHUB_MIRROR_PREFIX}{download_url}"

            # 优先使用镜像源下载，失败回退到原始 GitHub
            download_urls = [
                ("镜像源", mirror_url),
                ("GitHub原始地址", download_url),
            ]

            result = self._download_with_resume(
                download_urls,
                download_path,
                progress_callback,
                is_cancelled_callback,
            )

            if not result:
                app_logger.error("所有下载源均失败")
                if error_callback:
                    error_callback(
                        "下载更新失败，所有下载源均不可用。请检查网络连接后重试。"
                    )
                return None

            # --- 哈希校验 ---
            verified = self._verify_hash(
                download_path,
                assets,
                latest_release_info,
                security_warning_callback,
                error_callback,
            )
            if not verified:
                return None

            app_logger.info(f"更新包下载完成: {download_path}")
            return download_path

        except HTTPError as e:
            app_logger.error(f"下载 HTTP 错误 [{e.response.status_code}]: {e}")
            if error_callback:
                error_callback(f"下载失败：HTTP {e.response.status_code}")
            return None
        except (Timeout, ConnectionError):
            app_logger.error("下载网络连接错误或超时")
            if error_callback:
                error_callback("下载失败：网络连接错误或超时，请检查网络后重试")
            return None
        except RequestException as e:
            app_logger.error(f"下载网络异常：{e}")
            if error_callback:
                error_callback(f"下载失败：网络异常 - {e}")
            return None
        except Exception as e:
            app_logger.error(f"下载更新时发生未知错误：{e}", exc_info=True)
            if error_callback:
                error_callback(f"下载失败：{e}")
            return None

    def _download_with_resume(
        self,
        url_list: list[tuple[str, str]],
        download_path: str,
        progress_callback=None,
        is_cancelled_callback=None,
    ) -> bool:
        """
        支持断点续传的下载，依次尝试多个下载源

        每个下载源最多重试 MAX_RETRIES 次，每次从已下载的位置继续。
        一个源彻底失败后切换到下一个源（但保留已下载的部分继续续传）。

        Args:
            url_list: [(源名称, URL), ...] 按优先级排序
            download_path: 本地保存路径
            progress_callback: 进度回调
            is_cancelled_callback: 取消检查回调

        Returns:
            bool: 是否下载成功
        """
        total_size = 0  # 文件总大小（从第一次成功响应中获取）

        for source_name, url in url_list:
            app_logger.info(f"尝试使用{source_name}下载: {url}")

            for retry in range(MAX_RETRIES):
                try:
                    # 检查已下载的字节数（用于断点续传）
                    downloaded_size = 0
                    if os.path.exists(download_path):
                        downloaded_size = os.path.getsize(download_path)

                    # 如果已经下载了一些数据且知道总大小，检查是否已完成
                    if total_size > 0 and downloaded_size >= total_size:
                        app_logger.info("文件已完整下载，跳过")
                        return True

                    # 构造请求头
                    headers = {}
                    if downloaded_size > 0:
                        headers["Range"] = f"bytes={downloaded_size}-"
                        app_logger.info(
                            f"断点续传: 从 {downloaded_size} 字节处继续下载"
                            f"（第{retry + 1}/{MAX_RETRIES}次尝试）"
                        )
                    elif retry > 0:
                        app_logger.info(
                            f"重试下载（第{retry + 1}/{MAX_RETRIES}次尝试）"
                        )

                    response = requests.get(
                        url,
                        stream=True,
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                        headers=headers,
                    )
                    response.raise_for_status()

                    # 解析文件总大小
                    if response.status_code == 206:
                        # 服务器支持续传，返回 206 Partial Content
                        content_range = response.headers.get("Content-Range", "")
                        if "/" in content_range:
                            total_size = int(content_range.split("/")[-1])
                        app_logger.info(
                            f"服务器支持断点续传，总大小: {total_size} 字节"
                        )
                    elif response.status_code == 200:
                        # 服务器不支持续传或首次请求，返回完整文件
                        total_size = int(response.headers.get("content-length", 0))
                        # 如果服务器忽略了 Range 请求，需要从头开始
                        if downloaded_size > 0:
                            app_logger.warning("服务器不支持断点续传，重新从头下载")
                            downloaded_size = 0

                    # 写入文件
                    # 续传时追加写入，否则覆盖写入
                    mode = (
                        "ab"
                        if downloaded_size > 0 and response.status_code == 206
                        else "wb"
                    )
                    with open(download_path, mode) as f:
                        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)

                                # 更新进度
                                if total_size > 0 and progress_callback:
                                    progress = int((downloaded_size / total_size) * 100)
                                    progress_callback(progress)

                                # 处理取消操作
                                if is_cancelled_callback and is_cancelled_callback():
                                    app_logger.info("用户取消了下载")
                                    self._cleanup_download(download_path)
                                    return False

                    # 下载完成校验
                    if total_size > 0 and downloaded_size < total_size:
                        app_logger.warning(
                            f"下载不完整: {downloaded_size}/{total_size} 字节，"
                            "将尝试续传"
                        )
                        continue  # 继续重试（会从断点续传）

                    app_logger.info(
                        f"使用{source_name}下载成功，共 {downloaded_size} 字节"
                    )
                    return True

                except requests.exceptions.Timeout:
                    app_logger.warning(
                        f"{source_name}下载超时（第{retry + 1}/{MAX_RETRIES}次）"
                    )
                except requests.exceptions.ConnectionError:
                    app_logger.warning(
                        f"{source_name}连接失败（第{retry + 1}/{MAX_RETRIES}次）"
                    )
                except requests.exceptions.ChunkedEncodingError:
                    app_logger.warning(
                        f"{source_name}下载中断"
                        f"（第{retry + 1}/{MAX_RETRIES}次），"
                        "将尝试断点续传"
                    )
                except requests.exceptions.RequestException as e:
                    app_logger.warning(
                        f"{source_name}请求异常（第{retry + 1}/{MAX_RETRIES}次）: {e}"
                    )

            app_logger.warning(f"{source_name}已达最大重试次数，切换下一个源")

        return False

    def _cleanup_download(self, download_path: str) -> None:
        """清理下载的临时文件"""
        try:
            if os.path.exists(download_path):
                os.remove(download_path)
            temp_dir = os.path.dirname(download_path)
            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except OSError as e:
            app_logger.warning(f"清理临时文件失败: {e}")

    def _reject_update(
        self,
        download_path: str,
        security_warning_callback,
        error_callback,
        reason: str,
    ) -> bool:
        """拒绝当前更新包：记录原因、通知用户并清理已下载文件。

        Args:
            download_path: 已下载文件路径。
            security_warning_callback: 安全提示回调（仅用于提示拒绝原因）。
            error_callback: 错误提示回调。
            reason: 拒绝原因。

        Returns:
            bool: 恒为 False（表示校验未通过）。
        """
        app_logger.error(reason)
        if error_callback:
            error_callback(reason)
        if security_warning_callback:
            try:
                security_warning_callback(reason)
            except Exception:
                app_logger.debug("安全提示回调执行失败", exc_info=True)
        try:
            if os.path.exists(download_path):
                os.remove(download_path)
        except OSError as e:
            app_logger.warning(f"删除被拒绝的更新包失败: {e}")
        return False

    def _verify_hash(
        self,
        download_path: str,
        assets: list,
        latest_release_info: dict,
        security_warning_callback=None,
        error_callback=None,
    ) -> bool:
        """校验下载文件的哈希值（fail-closed 策略）。

        安全策略：任何无法确定可信哈希的情况一律判为失败并拒绝安装，
        包括：取不到哈希、哈希来源非官方域名、哈希格式非法、计算过程异常、
        哈希不匹配。``security_warning_callback`` 仅用于提示拒绝原因，
        不再决定是否放行。

        Args:
            download_path: 已下载文件路径。
            assets: release 资产列表。
            latest_release_info: release 信息（body 可能含 SHA256）。
            security_warning_callback: 安全提示回调（提示拒绝原因）。
            error_callback: 错误提示回调。

        Returns:
            bool: 校验通过返回 True，否则 False。
        """
        try:
            expected_hash = ""

            # 1. 从 assets 获取 sha256.txt 哈希文件（仅允许官方域名）
            hash_asset = next(
                (a for a in assets if a.get("name") == "sha256.txt"), None
            )
            if hash_asset and hash_asset.get("browser_download_url"):
                hash_url = hash_asset["browser_download_url"]
                if not _is_official_url(hash_url):
                    return self._reject_update(
                        download_path,
                        security_warning_callback,
                        error_callback,
                        f"哈希校验文件来源非官方域名，已拒绝更新: {hash_url}",
                    )
                app_logger.info("正在下载哈希校验文件...")
                try:
                    hash_resp = requests.get(
                        hash_url,
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    )
                    if hash_resp.status_code == 200:
                        expected_hash = hash_resp.text.strip()
                except (Timeout, ConnectionError):
                    # 网络问题不立即判失败，允许回退到 release body 解析
                    app_logger.warning("下载哈希校验文件超时或连接失败")
                except RequestException as e:
                    app_logger.warning(f"下载哈希校验文件网络异常：{e}")

            # 2. 回退：从 release body 中解析哈希
            #    兼容 markdown 加粗写法（**SHA256**: `hash`）与纯文本（SHA256: hash）
            if not expected_hash and latest_release_info.get("body"):
                match = re.search(
                    r"SHA256\**\s*:\s*`?([a-fA-F0-9]{64})`?",
                    latest_release_info["body"],
                )
                if match:
                    expected_hash = match.group(1)

            # 3. 哈希格式校验：必须是合法 64 位十六进制，否则视为无哈希
            if not _is_valid_sha256(expected_hash):
                return self._reject_update(
                    download_path,
                    security_warning_callback,
                    error_callback,
                    "无法获取可信的哈希校验值（缺失或格式非法），已拒绝安装该更新包。",
                )

            # 4. 计算并比对哈希
            expected_hash = expected_hash.strip().upper()
            app_logger.info(f"正在校验文件完整性... 期望哈希: {expected_hash[:8]}...")
            calculated_hash = _calculate_sha256(download_path)
            if calculated_hash != expected_hash:
                err_msg = (
                    f"安全检查失败：文件哈希不匹配。\n"
                    f"下载的文件哈希: {calculated_hash}\n"
                    f"期望的哈希: {expected_hash}\n"
                    f"文件可能已损坏或被篡改。"
                )
                return self._reject_update(
                    download_path,
                    security_warning_callback,
                    error_callback,
                    err_msg,
                )

            app_logger.info("哈希校验通过")
            return True

        except Exception as e:
            # fail-closed：任何校验过程异常都拒绝更新
            app_logger.error(f"哈希校验过程异常，已拒绝更新: {e}", exc_info=True)
            if error_callback:
                error_callback(f"哈希校验过程异常，已拒绝安装该更新包：{e}")
            return False
