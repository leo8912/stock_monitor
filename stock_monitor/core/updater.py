import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from packaging import version
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from stock_monitor.network.manager import NetworkManager
from stock_monitor.utils.logger import app_logger
from stock_monitor.version import __version__


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
        self.latest_release_info: Optional[Dict[Any, Any]] = None

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

            app_logger.info(f"当前版本: {self.current_version}, 最新版本: {latest_version}")

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

    def download_update(self, parent=None) -> Optional[str]:
        """
        下载更新包

        Args:
            parent: 父窗口，用于显示进度对话框

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

            # 创建临时目录用于下载
            temp_dir = tempfile.mkdtemp()
            download_path = os.path.join(temp_dir, file_name)

            # 显示进度对话框
            progress_dialog = QProgressDialog("正在下载更新...", "取消", 0, 100, parent)
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setWindowTitle("下载更新")
            progress_dialog.setAutoClose(True)
            progress_dialog.setAutoReset(True)
            progress_dialog.show()

            # 首先尝试使用原始URL下载
            try:
                response = requests.get(download_url, stream=True, timeout=30)
            except requests.exceptions.RequestException as e:
                app_logger.warning(f"使用原始URL下载失败: {e}，尝试使用镜像源...")
                # 构造镜像URL
                mirror_url = f"https://ghfast.top/{download_url}"
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
                            progress_dialog.setValue(progress)

                        # 处理取消操作
                        QApplication.processEvents()
                        if progress_dialog.wasCanceled():
                            os.remove(download_path)
                            os.rmdir(temp_dir)
                            app_logger.info("用户取消了下载")
                            return None

            progress_dialog.close()

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
                        app_logger.error(
                            f"Hash mismatch! Downloaded: {calculated_hash}, Expected: {expected_hash}"
                        )
                        os.remove(download_path)
                        QMessageBox.critical(
                            parent,
                            "Verify Failed",
                            "Security check failed: File hash mismatch.\nThe file may be corrupted or tampered with.",
                            QMessageBox.StandardButton.Ok,
                        )
                        return None
                    app_logger.info("Hash verification passed.")
                else:
                    app_logger.warning(
                        "No hash found for verification, skipping security check."
                    )

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
            if getattr(sys, 'frozen', False):
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
            with zipfile.ZipFile(update_zip, 'r') as zip_ref:
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

            app_logger.info("正在生成更新脚本 update.bat...")

            # 3. 生成 BAT 脚本
            bat_path = app_dir / "update.bat"
            main_exe_name = "stock_monitor.exe"
            current_pid = os.getpid()
            
            # BAT 脚本内容 (使用 GBK 兼容中文 CMD)
            bat_content = f"""@echo off
title Stock Monitor Updater
color 0A
mode con cols=80 lines=30
cls

echo ======================================================================
echo.
echo                   STOCK MONITOR UPDATE SYSTEM
echo.
echo ======================================================================
echo.
echo    [INFO] 正在更新 Stock Monitor 至最新版本...
echo    [INFO] Updating Stock Monitor to latest version...
echo.
echo    --------------------------------------------------------
echo    [DEBUG] Source: "{source_dir.absolute()}"
echo    [DEBUG] Target: "{app_dir.absolute()}"
echo    --------------------------------------------------------
echo.
echo    [STEP 1/3] 等待主程序退出 / Waiting for exit...
:loop
tasklist | find "{current_pid}" >nul
if %errorlevel%==0 (
    timeout /t 1 /nobreak >nul
    goto loop
)
echo    [OK] 主程序已退出

echo    --------------------------------------------------------
echo    [STEP 2/3] 正在替换文件 / Replacing files...
echo.
xcopy /Y /E /H /R "{source_dir.absolute()}\\*" "{app_dir.absolute()}"
if %errorlevel% NEQ 0 goto error
echo    [OK] 文件替换成功
goto cleanup

:error
color 0C
echo.
echo    ========================================================
echo    [ERROR] 文件替换失败! (File Replacement Failed)
echo    Error Level: %errorlevel%
echo    请尝试手动解压更新包 / Please unzip manually.
echo    Temp Path: "{temp_dir.absolute()}"
echo    ========================================================
echo.
pause
exit /b 1

:cleanup

echo.
echo    --------------------------------------------------------
echo    [STEP 3/3] 清理临时文件 / Cleaning up...
echo    Target: "{temp_dir.absolute()}"
rmdir /S /Q "{temp_dir.absolute()}"
if exist "{temp_dir.absolute()}" (
    echo    [WARNING] 临时目录清理失败 (Cleanup Failed)
    echo    请稍后手动删除: "{temp_dir.absolute()}"
) else (
    echo    [OK] 临时文件已清理 (Cleanup Done)
)

echo.
echo    ======================================================================
echo    [SUCCESS] 更新完成，正在启动软件...
echo    Restarting application...
echo    ======================================================================
timeout /t 2 /nobreak >nul
start "" "{app_dir.absolute()}\\{main_exe_name}"
del "%0"
"""
            # 写入 BAT 文件
            try:
                # 使用 GBK 写入，确保在中文 Windows 环境下 CMD 能正确执行
                with open(bat_path, "w", encoding="gbk") as f:
                    f.write(bat_content)
            except Exception as e:
                app_logger.error(f"写入BAT失败: {e}")
                return False

            app_logger.info("启动 update.bat，主程序即将退出")
            
            # 4. 运行脚本并退出
            try:
                # 使用 os.startfile 直接打开 BAT 文件，这在 Windows 上最可靠
                # 等同于用户双击文件
                os.startfile(str(bat_path))
            except Exception as e:
                app_logger.error(f"os.startfile调用失败: {e}, 尝试回退到subprocess...")
                # 回退方案
                subprocess.Popen(
                    f'"{str(bat_path)}"', 
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=str(app_dir)
                )
            
            # 强制退出
            import time
            time.sleep(1.0) 
            os._exit(0)
            
            return True

        except Exception as e:
            app_logger.error(f"启动更新程序时发生错误: {e}", exc_info=True)
            return False

    def show_update_dialog(self, parent=None) -> bool:
        """
        显示更新对话框

        Args:
            parent: 父窗口

        Returns:
            bool: 用户是否同意更新
        """
        if not self.latest_release_info:
            return False

        latest_version = (
            self.latest_release_info.get("tag_name", "")
            .replace("stock_monitor_", "")
            .replace("v", "")
        )
        release_body = self.latest_release_info.get("body", "暂无更新说明")

        message = f"发现新版本!\n\n当前版本: {self.current_version}\n最新版本: {latest_version}\n\n更新说明:\n{release_body}\n\n是否现在更新?"

        reply = QMessageBox.question(
            parent,
            "发现新版本",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        return reply == QMessageBox.StandardButton.Yes

    def perform_update(self, parent=None) -> bool:
        """
        执行完整的更新流程

        Args:
            parent: 父窗口

        Returns:
            bool: 更新是否成功
        """
        try:
            # 显示更新对话框
            if self.show_update_dialog(parent):
                # 下载更新
                update_file = self.download_update(parent)
                if update_file:
                    # 应用更新(启动updater.exe并退出)
                    return self.apply_update(update_file)
                else:
                    QMessageBox.warning(
                        parent,
                        "下载失败",
                        "更新包下载失败,请检查网络连接后重试。",
                        QMessageBox.StandardButton.Ok,
                    )
            return False
        except Exception as e:
            app_logger.error(f"执行更新时发生错误: {e}")
            QMessageBox.critical(
                parent,
                "更新失败",
                f"更新过程中发生错误: {str(e)}",
                QMessageBox.StandardButton.Ok,
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
            from stock_monitor.data.stock.stock_db import stock_db

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
