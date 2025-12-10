import os
import sys
import json
import tempfile
import shutil
import subprocess
from typing import Optional, Dict, Any
import requests
from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
from PyQt5.QtCore import Qt
from packaging import version

from stock_monitor.version import __version__
from stock_monitor.network.manager import NetworkManager
from stock_monitor.utils.logger import app_logger


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
        
    def check_for_updates(self) -> bool:
        """
        检查是否有新版本可用
        
        Returns:
            bool: 如果有新版本返回True，否则返回False
        """
        try:
            app_logger.info("开始检查更新...")
            
            # 获取最新的release信息
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            release_info = self.network_manager.github_api_request(api_url)
            
            if not release_info:
                app_logger.warning("无法获取最新的release信息")
                return False
                
            self.latest_release_info = release_info
            latest_version = release_info.get('tag_name', '').replace('stock_monitor_', '').replace('v', '')
            
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
            return False
    
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
            assets = self.latest_release_info.get('assets', [])
            zip_asset = None
            for asset in assets:
                if asset.get('name', '').endswith('.zip'):
                    zip_asset = asset
                    break
                    
            if not zip_asset:
                app_logger.error("未找到zip格式的更新包")
                return None
                
            download_url = zip_asset.get('browser_download_url')
            file_name = zip_asset.get('name', 'update.zip')
            
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
            
            # 下载文件
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(download_path, 'wb') as f:
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
            app_logger.info(f"更新包下载完成: {download_path}")
            return download_path
            
        except Exception as e:
            app_logger.error(f"下载更新时发生错误: {e}")
            return None
    
    def apply_update(self, update_file_path: str) -> bool:
        """
        应用更新
        
        Args:
            update_file_path: 更新包文件路径
            
        Returns:
            bool: 更新是否成功
        """
        backup_dir = None
        try:
            app_logger.info("开始应用更新...")
            
            # 获取当前程序目录
            if hasattr(sys, '_MEIPASS'):
                # 打包环境
                current_dir = os.path.dirname(sys.executable)
            else:
                # 开发环境
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
            app_logger.info(f"当前程序目录: {current_dir}")
            
            # 解压更新包到临时目录
            import zipfile
            temp_extract_dir = tempfile.mkdtemp()
            
            with zipfile.ZipFile(update_file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
                
            app_logger.info(f"更新包解压到: {temp_extract_dir}")
            
            # 创建备份目录
            backup_dir = tempfile.mkdtemp()
            app_logger.info(f"创建备份目录: {backup_dir}")
            
            # 替换文件
            # 获取解压后的目录
            extracted_dirs = os.listdir(temp_extract_dir)
            if not extracted_dirs:
                raise Exception("更新包为空")
                
            # 确保我们获取的是正确的解压目录
            extracted_dir = temp_extract_dir
            if len(extracted_dirs) == 1:
                single_path = os.path.join(temp_extract_dir, extracted_dirs[0])
                # 如果是目录，则使用这个目录作为源
                if os.path.isdir(single_path):
                    extracted_dir = single_path
                    
            app_logger.info(f"更新文件目录: {extracted_dir}")
            
            # 检查是否有正在运行的文件需要更新
            locked_files = []
            for root, dirs, files in os.walk(extracted_dir):
                # 修正相对路径计算
                relative_path = os.path.relpath(root, extracted_dir)
                # 确保相对路径正确处理根目录情况
                if relative_path == ".":
                    target_path = current_dir
                else:
                    target_path = os.path.join(current_dir, relative_path)
                
                # 检查文件是否需要更新并且正在被占用
                for file in files:
                    dst_file = os.path.join(target_path, file)
                    if os.path.exists(dst_file):
                        # 检查是否是正在运行的exe文件
                        if dst_file.lower() == os.path.join(current_dir, 'stock_monitor.exe').lower():
                            locked_files.append(dst_file)
                        # 检查其他可能被占用的文件（DLL、PYD等）
                        elif dst_file.lower().endswith(('.dll', '.pyd')):
                            locked_files.append(dst_file)
            
            # 如果有文件被占用，需要先重启应用
            if locked_files:
                app_logger.info(f"检测到 {len(locked_files)} 个被占用的文件，需要先重启应用")
                # 创建更新标记文件
                update_marker = os.path.join(current_dir, 'update_pending')
                with open(update_marker, 'w') as f:
                    f.write(update_file_path)
                app_logger.info("已创建更新标记文件，准备重启应用")
                return True  # 返回True表示需要重启
            
            # 替换文件
            for root, dirs, files in os.walk(extracted_dir):
                # 修正相对路径计算
                relative_path = os.path.relpath(root, extracted_dir)
                # 确保相对路径正确处理根目录情况
                if relative_path == ".":
                    target_path = current_dir
                else:
                    target_path = os.path.join(current_dir, relative_path)
                
                # 创建目标目录
                if not os.path.exists(target_path):
                    os.makedirs(target_path)
                
                # 复制文件
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(target_path, file)
                    
                    # 如果目标文件存在，先备份再替换
                    if os.path.exists(dst_file):
                        # 特殊处理正在运行的可执行文件和动态链接库文件
                        if dst_file.lower() == os.path.join(current_dir, 'stock_monitor.exe').lower() or \
                           dst_file.lower().endswith(('.dll', '.pyd')):
                            # 对于正在运行的exe文件和动态链接库，先重命名为临时名称
                            temp_dst_file = dst_file + '.tmp'
                            try:
                                os.rename(dst_file, temp_dst_file)
                                app_logger.info(f"已将正在运行的文件重命名为: {temp_dst_file}")
                            except OSError:
                                # 如果重命名失败，跳过这个文件
                                app_logger.warning(f"无法重命名正在运行的文件: {dst_file}")
                                continue
                        else:
                            # 对于其他文件，先备份再删除
                            try:
                                backup_file = os.path.join(backup_dir, os.path.relpath(dst_file, current_dir))
                                backup_dirname = os.path.dirname(backup_file)
                                if not os.path.exists(backup_dirname):
                                    os.makedirs(backup_dirname)
                                shutil.copy2(dst_file, backup_file)
                                os.remove(dst_file)
                            except OSError as e:
                                app_logger.warning(f"无法备份或删除文件 {dst_file}: {e}")
                                continue
                    
                    shutil.copy2(src_file, dst_file)
                    
            # 清理临时文件
            shutil.rmtree(temp_extract_dir)
            os.remove(update_file_path)
            shutil.rmtree(backup_dir)
            
            # 清理可能遗留的.tmp文件
            self._cleanup_tmp_files(current_dir)
            
            app_logger.info("更新应用完成")
            return True
            
        except Exception as e:
            app_logger.error(f"应用更新时发生错误: {e}")
            # 如果有备份目录，尝试清理
            if backup_dir is not None:
                try:
                    shutil.rmtree(backup_dir)
                except:
                    pass
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
            
        latest_version = self.latest_release_info.get('tag_name', '').replace('stock_monitor_', '').replace('v', '')
        release_body = self.latest_release_info.get('body', '暂无更新说明')
        
        message = f"发现新版本!\n\n当前版本: {self.current_version}\n最新版本: {latest_version}\n\n更新说明:\n{release_body}\n\n是否现在更新?"
        
        reply = QMessageBox.question(
            parent, 
            '发现新版本', 
            message,
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        
        return reply == QMessageBox.Yes

    def restart_application(self) -> None:
        """
        重启应用程序
        """
        try:
            app_logger.info("正在重启应用程序...")
            
            # 获取当前可执行文件路径
            if hasattr(sys, '_MEIPASS'):
                # 打包环境
                executable = sys.executable
                # 检查是否有待处理的更新
                update_marker = os.path.join(os.path.dirname(executable), 'update_pending')
                if os.path.exists(update_marker):
                    app_logger.info("检测到待处理的更新，先处理更新")
                    # 读取更新文件路径
                    with open(update_marker, 'r') as f:
                        update_file_path = f.read().strip()
                    # 删除标记文件
                    os.remove(update_marker)
                    # 应用更新
                    if self.apply_update(update_file_path):
                        app_logger.info("更新应用完成，继续重启应用")
                    else:
                        app_logger.error("更新应用失败")
                
                # 首先尝试使用 execv 直接替换进程
                try:
                    os.execv(executable, [executable] + sys.argv[1:])
                except Exception as e:
                    app_logger.warning(f"os.execv 重启失败: {e}，回退到 subprocess 方式")
                    # 回退到 subprocess 方式
                    subprocess.Popen([executable] + sys.argv[1:])
                    QApplication.quit()
            else:
                # 开发环境
                executable = sys.executable
                # 在开发环境中需要指定主模块
                if os.path.basename(executable).lower().startswith('python'):
                    # 如果是通过python运行的，则需要指定主模块
                    main_module = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')
                    if os.path.exists(main_module):
                        # 首先尝试使用 execv 直接替换进程
                        try:
                            os.execv(executable, [executable, main_module] + sys.argv[1:])
                        except Exception as e:
                            app_logger.warning(f"os.execv 重启失败: {e}，回退到 subprocess 方式")
                            # 回退到 subprocess 方式
                            subprocess.Popen([executable, main_module] + sys.argv[1:])
                            QApplication.quit()
        except Exception as e:
            app_logger.error(f"重启应用程序时发生错误: {e}")

    def _cleanup_tmp_files(self, directory: str) -> None:
        """
        清理目录中遗留的.tmp文件
        
        Args:
            directory: 要清理的目录路径
        """
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.tmp'):
                        tmp_file = os.path.join(root, file)
                        try:
                            os.remove(tmp_file)
                            app_logger.info(f"已清理临时文件: {tmp_file}")
                        except Exception as e:
                            app_logger.warning(f"无法删除临时文件 {tmp_file}: {e}")
        except Exception as e:
            app_logger.error(f"清理临时文件时发生错误: {e}")

# 创建全局更新器实例
app_updater = AppUpdater()