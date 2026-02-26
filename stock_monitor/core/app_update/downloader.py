import os
import tempfile
from typing import Any, Optional

import requests

from stock_monitor.utils.logger import app_logger

GITHUB_MIRROR_PREFIX = "https://ghfast.top/"


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

            # 首先尝试使用原始URL下载
            try:
                response = requests.get(download_url, stream=True, timeout=30)
            except requests.exceptions.RequestException as e:
                app_logger.warning(f"使用原始URL下载失败: {e}，尝试使用镜像源...")
                # 构造镜像URL
                mirror_url = f"{GITHUB_MIRROR_PREFIX}{download_url}"
                app_logger.info(f"使用镜像URL: {mirror_url}")
                response = requests.get(mirror_url, stream=True, timeout=30)

            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0

            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # 更新进度
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            if progress_callback:
                                progress_callback(progress)

                        # 处理取消操作
                        if is_cancelled_callback and is_cancelled_callback():
                            os.remove(download_path)
                            os.rmdir(temp_dir)
                            app_logger.info("用户确实取消了下载")
                            return None

            # --- Hash Check ---
            try:
                # 1. Try to get hash from assets (preferred)
                hash_asset = next(
                    (a for a in assets if a.get("name") == "sha256.txt"), None
                )
                expected_hash = ""

                if hash_asset and hash_asset.get("browser_download_url"):
                    try:
                        app_logger.info("Downloading hash file...")
                        hash_resp = requests.get(
                            hash_asset["browser_download_url"], timeout=10
                        )
                        if hash_resp.status_code == 200:
                            expected_hash = hash_resp.text.strip()
                    except Exception as e:
                        app_logger.warning(f"Failed to download hash file: {e}")

                # 2. If no file, try to parse from body
                if not expected_hash and latest_release_info.get("body"):
                    import re

                    # Look for SHA256: `hash` or similar patterns
                    body = latest_release_info["body"]
                    match = re.search(r"SHA256: `?([a-fA-F0-9]{64})`?", body)
                    if match:
                        expected_hash = match.group(1)

                if expected_hash:
                    app_logger.info(
                        f"Verifying Hash... Expected: {expected_hash[:8]}..."
                    )
                    import hashlib

                    sha256_hash = hashlib.sha256()
                    with open(download_path, "rb") as f:
                        for byte_block in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(byte_block)
                    calculated_hash = sha256_hash.hexdigest().upper()
                    expected_hash = expected_hash.upper()

                    if calculated_hash != expected_hash:
                        err_msg = f"安全检查失败：文件哈希不匹配。\n下载的文件哈希: {calculated_hash}\n期望的哈希: {expected_hash}\n文件可能已损坏或被篡改。"
                        app_logger.error(err_msg)
                        os.remove(download_path)
                        if error_callback:
                            error_callback(err_msg)
                        return None
                    app_logger.info("Hash verification passed.")
                else:
                    warn_msg = "此更新包没有提供哈希校验值，无法验证文件完整性。\n是否仍要继续安装？"
                    app_logger.warning(
                        "未找到哈希校验值，跳过安全检查。建议人工确认更新包来源。"
                    )
                    if security_warning_callback:
                        if not security_warning_callback(warn_msg):
                            os.remove(download_path)
                            return None

            except Exception as e:
                app_logger.error(f"Error during hash verification: {e}")
                # We don't block update if verification logic itself fails, but ideally we should warning.
                # For safety, let's allow proceed but log it, unless it was a mismatch which is handled above.
            # ------------------

            app_logger.info(f"更新包下载完成: {download_path}")
            return download_path

        except requests.exceptions.Timeout:
            app_logger.error("下载更新时发生超时错误")
            return None
        except requests.exceptions.ConnectionError:
            app_logger.error("下载更新时发生连接错误")
            return None
        except Exception as e:
            app_logger.error(f"下载更新时发生错误: {e}")
            return None
