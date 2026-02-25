import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import requests
from packaging import version

from stock_monitor.network.manager import NetworkManager
from stock_monitor.utils.logger import app_logger
from stock_monitor.version import __version__

# 镜像源前缀，便于统一管理和切换
GITHUB_MIRROR_PREFIX = "https://ghfast.top/"


class AppUpdater:
    """应用程序更新器"""

    def __init__(self, github_repo: str = "leo8912/stock_monitor"):
        """
        初始化更新器

        Args:
            github_repo: GitHub仓库路径，格式为"user/repo"
        """
        self.github_repo = github_repo
        self.network_manager = NetworkManager()
        self.current_version = __version__
        self.latest_release_info: Optional[dict[Any, Any]] = None

    def check_for_updates(self) -> Optional[bool]:
        """
        检查是否有新版本可用

        Returns:
            bool: 如果有新版本返回True，如果没有新版本返回False，如果网络错误返回None
        """
        try:
            app_logger.info("开始检查更新...")

            # 首先尝试使用原始GitHub地址
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            release_info = self.network_manager.github_api_request(api_url)

            # 如果失败，尝试使用镜像源
            if not release_info:
                app_logger.warning("使用GitHub原始地址检查更新失败，尝试使用镜像源...")
                release_info = self.network_manager.github_api_request(
                    api_url, use_mirror=True
                )

            if not release_info:
                app_logger.warning("无法获取最新的release信息")
                # 区分是网络问题还是其他问题
                return None  # 网络问题，无法确定是否有新版本

            self.latest_release_info = release_info
            latest_version = (
                release_info.get("tag_name", "")
                .replace("stock_monitor_", "")
                .replace("v", "")
            )

            app_logger.info(
                f"当前版本: {self.current_version}, 最新版本: {latest_version}"
            )

            # 比较版本号
            if version.parse(latest_version) > version.parse(self.current_version):
                app_logger.info("发现新版本")
                return True
            else:
                app_logger.info("当前已是最新版本")
                return False

        except Exception as e:
            app_logger.error(f"检查更新时发生错误: {e}")
            return None  # 网络错误或其他异常

    def download_update(
        self,
        progress_callback=None,
        is_cancelled_callback=None,
        security_warning_callback=None,
        error_callback=None,
    ) -> Optional[str]:
        """
        下载更新包

        Args:
            progress_callback: 进度回调函数，接收(int)百分比参数
            is_cancelled_callback: 是否取消回调函数，返回bool
            security_warning_callback: 安全警告回调，接收(str)提示，返回bool(True继续)
            error_callback: 错误提示回调，接收(str)错误信息

        Returns:
            str: 下载文件的路径，如果失败返回None
        """
        if not self.latest_release_info:
            app_logger.error("没有可用的更新信息")
            return None

        try:
            # 查找zip文件资产
            assets = self.latest_release_info.get("assets", [])
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
                if not expected_hash and self.latest_release_info.get("body"):
                    import re

                    # Look for SHA256: `hash` or similar patterns
                    body = self.latest_release_info["body"]
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

    def apply_update(self, update_file_path: str) -> bool:
        """
        应用更新 (BAT脚本方案)

        1. 解压更新包到临时目录
        2. 生成 update.bat 脚本
        3. 运行脚本并退出主程序
        """
        try:
            app_logger.info("准备应用更新(BAT方案)...")

            # 1. 准备路径
            if getattr(sys, "frozen", False):
                app_dir = Path(sys.executable).parent
            else:
                app_dir = Path(os.getcwd())

            temp_dir = app_dir / "temp_update"
            update_zip = Path(update_file_path)

            # 清理旧的临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(exist_ok=True)

            app_logger.info(f"正在解压更新包到: {temp_dir}")

            # 2. 解压文件
            with zipfile.ZipFile(update_zip, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # 智能寻找源目录: 查找包含 stock_monitor.exe 的目录
            source_dir = temp_dir
            for root, dirs, files in os.walk(temp_dir):
                if "stock_monitor.exe" in files:
                    source_dir = Path(root)
                    break

            app_logger.info(f"更新源目录: {source_dir}")
            if source_dir == temp_dir:
                app_logger.info("注意: 未在子目录找到exe，将使用解压根目录作为源")

            app_logger.info("正在生成静默更新脚本...")

            # 3. 生成 BAT 脚本 (静默模式)
            bat_path = app_dir / "update.bat"
            main_exe_name = "stock_monitor.exe"
            current_pid = os.getpid()
            config_dir = app_dir / ".stock_monitor"

            # 确保配置目录存在
            config_dir.mkdir(exist_ok=True)

            # BAT 脚本内容 (静默模式 - 无输出，只写日志文件)
            bat_content = f"""@echo off
cd /d "%~dp0"

:: 等待主程序退出
:loop
tasklist | find "{current_pid}" >nul 2>&1
if %errorlevel%==0 (
    timeout /t 1 /nobreak >nul 2>&1
    goto loop
)

:: 替换文件
xcopy /Y /E /H /R "{source_dir.absolute()}\\*" "{app_dir.absolute()}" >nul 2>&1
if %errorlevel% NEQ 0 goto error

:: 清理临时文件
rmdir /S /Q "{temp_dir.absolute()}" >nul 2>&1

:: 写入更新成功标记
echo %date% %time% > "{config_dir.absolute()}\\update_complete.txt"

:: 启动程序
start "" "{app_dir.absolute()}\\{main_exe_name}"
del "%~f0" >nul 2>&1
exit /b 0

:error
:: 写入更新失败标记
echo UPDATE_FAILED %date% %time% > "{config_dir.absolute()}\\update_failed.txt"
echo Error: xcopy failed with errorlevel %errorlevel% >> "{config_dir.absolute()}\\update_failed.txt"
echo Source: {source_dir.absolute()} >> "{config_dir.absolute()}\\update_failed.txt"
echo Target: {app_dir.absolute()} >> "{config_dir.absolute()}\\update_failed.txt"
del "%~f0" >nul 2>&1
exit /b 1
"""
            # 写入 BAT 文件
            try:
                with open(bat_path, "w", encoding="gbk") as f:
                    f.write(bat_content)
            except Exception as e:
                app_logger.error(f"写入BAT失败: {e}")
                return False

            # 4. 生成 VBS 脚本用于隐藏运行 BAT
            vbs_path = app_dir / "update_silent.vbs"
            vbs_content = (
                f'CreateObject("Wscript.Shell").Run """{bat_path}""", 0, False'
            )
            try:
                with open(vbs_path, "w", encoding="gbk") as f:
                    f.write(vbs_content)
            except Exception as e:
                app_logger.error(f"写入VBS失败: {e}")
                return False

            app_logger.info("启动静默更新脚本，主程序即将退出")

            # 5. 使用 VBS 静默运行 BAT
            try:
                os.startfile(str(vbs_path))
            except Exception as e:
                app_logger.error(f"VBS启动失败: {e}, 尝试回退到可见模式...")
                # 回退到可见模式
                try:
                    os.startfile(str(bat_path))
                except Exception as e2:
                    app_logger.error(f"BAT启动也失败: {e2}")
                    return False

            # 强制退出
            import time

            time.sleep(1.0)
            os._exit(0)
            # 注意: os._exit(0) 后程序已终止，此处不会执行

        except Exception as e:
            app_logger.error(f"启动更新程序时发生错误: {e}", exc_info=True)
            return False

    def perform_update(self, parent=None) -> bool:
        # 这个方法已经被弃用，它的UI逻辑应该在外层实现。
        # 为了兼容性暂时保留，但直接返回False。应该使用外层的重构代码。
        app_logger.warning(
            "AppUpdater.perform_update is deprecated. Please handle UI externally."
        )
        return False

    def _run_post_update_hooks(self):
        """
        运行更新后钩子

        执行更新完成后需要的操作，如数据库迁移、配置升级等
        """
        try:
            app_logger.info("执行更新后钩子...")

            # 检查并初始化数据库
            from stock_monitor.core.container import container
            from stock_monitor.data.stock.stock_db import StockDatabase

            stock_db = container.get(StockDatabase)

            if stock_db.is_empty():
                app_logger.info("检测到空数据库，正在初始化...")
                stock_db._populate_base_data()
            else:
                stock_count = stock_db.get_stock_count()
                app_logger.info(f"数据库检查完成，当前有 {stock_count} 只股票")

            # 未来可以在这里添加更多钩子
            # - 配置文件升级
            # - 缓存清理
            # - 日志轮转

            app_logger.info("更新后钩子执行完成")
        except Exception as e:
            app_logger.error(f"执行更新后钩子失败: {e}")


# 创建全局更新器实例
app_updater = AppUpdater()
