import os
import tempfile
from typing import Any, Optional

import requests

from stock_monitor.utils.logger import app_logger

# 镜像源配置：国内环境优先使用镜像加速下载
GITHUB_MIRROR_PREFIX = "https://ghfast.top/"

# 网络超时配置（秒）
CONNECT_TIMEOUT = 15  # 建立连接超时
READ_TIMEOUT = 30  # 数据读取超时（每个 chunk 的最大等待时间）

# 断点续传配置
CHUNK_SIZE = 8192  # 每次读取的块大小
MAX_RETRIES = 3  # 最大重试次数


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

        except Exception as e:
            app_logger.error(f"下载更新时发生错误: {e}")
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

    def _cleanup_download(self, download_path: str):
        """清理下载的临时文件"""
        try:
            if os.path.exists(download_path):
                os.remove(download_path)
            temp_dir = os.path.dirname(download_path)
            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except OSError as e:
            app_logger.warning(f"清理临时文件失败: {e}")

    def _verify_hash(
        self,
        download_path: str,
        assets: list,
        latest_release_info: dict,
        security_warning_callback=None,
        error_callback=None,
    ) -> bool:
        """
        校验下载文件的哈希值

        Returns:
            bool: 校验通过返回 True，失败返回 False
        """
        try:
            # 1. 尝试从 assets 获取哈希文件
            hash_asset = next(
                (a for a in assets if a.get("name") == "sha256.txt"), None
            )
            expected_hash = ""

            if hash_asset and hash_asset.get("browser_download_url"):
                try:
                    app_logger.info("正在下载哈希校验文件...")
                    hash_url = hash_asset["browser_download_url"]
                    # 哈希文件也优先使用镜像
                    mirror_hash_url = f"{GITHUB_MIRROR_PREFIX}{hash_url}"
                    try:
                        hash_resp = requests.get(
                            mirror_hash_url,
                            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                        )
                        if hash_resp.status_code == 200:
                            expected_hash = hash_resp.text.strip()
                    except requests.exceptions.RequestException:
                        # 镜像失败，回退原始地址
                        hash_resp = requests.get(
                            hash_url,
                            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                        )
                        if hash_resp.status_code == 200:
                            expected_hash = hash_resp.text.strip()
                except Exception as e:
                    app_logger.warning(f"下载哈希校验文件失败: {e}")

            # 2. 从 release body 中解析哈希
            if not expected_hash and latest_release_info.get("body"):
                import re

                body = latest_release_info["body"]
                match = re.search(r"SHA256: `?([a-fA-F0-9]{64})`?", body)
                if match:
                    expected_hash = match.group(1)

            if expected_hash:
                app_logger.info(
                    f"正在校验文件完整性... 期望哈希: {expected_hash[:8]}..."
                )
                import hashlib

                sha256_hash = hashlib.sha256()
                with open(download_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                calculated_hash = sha256_hash.hexdigest().upper()
                expected_hash = expected_hash.upper()

                if calculated_hash != expected_hash:
                    err_msg = (
                        f"安全检查失败：文件哈希不匹配。\n"
                        f"下载的文件哈希: {calculated_hash}\n"
                        f"期望的哈希: {expected_hash}\n"
                        f"文件可能已损坏或被篡改。"
                    )
                    app_logger.error(err_msg)
                    os.remove(download_path)
                    if error_callback:
                        error_callback(err_msg)
                    return False
                app_logger.info("哈希校验通过")
            else:
                warn_msg = (
                    "此更新包没有提供哈希校验值，无法验证文件完整性。\n"
                    "是否仍要继续安装？"
                )
                app_logger.warning(
                    "未找到哈希校验值，跳过安全检查。建议人工确认更新包来源。"
                )
                if security_warning_callback:
                    if not security_warning_callback(warn_msg):
                        os.remove(download_path)
                        return False

        except Exception as e:
            app_logger.error(f"哈希校验过程异常: {e}")
            # 校验逻辑异常不阻止更新，但记录日志

        return True
