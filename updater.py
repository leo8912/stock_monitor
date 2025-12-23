"""
独立更新程序
负责在主程序退出后替换文件并重启
"""

import argparse
import logging
import shutil
import subprocess
import sys
import time
import zipfile
from enum import IntEnum
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QVBoxLayout

    HAS_GUI = True
except ImportError:
    HAS_GUI = False


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("updater.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class UpdaterError(IntEnum):
    """更新错误码"""

    SUCCESS = 0
    PROCESS_TIMEOUT = 1001  # 等待进程超时
    EXTRACT_FAILED = 1002  # 解压失败
    BACKUP_FAILED = 1003  # 备份失败
    REPLACE_FAILED = 1004  # 文件替换失败
    START_FAILED = 1005  # 启动新版本失败
    UNKNOWN_ERROR = 1999  # 未知错误


class UpdaterGUI(QDialog):
    """更新程序的GUI界面"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stock Monitor - 正在更新")
        self.setFixedSize(480, 180)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        # 设置现代化样式
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #fff;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #45a049);
                border-radius: 3px;
            }
        """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # 状态标签
        self.status_label = QLabel("正在准备更新...")
        self.status_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumHeight(25)
        layout.addWidget(self.progress_bar)

        # 详细信息标签
        self.detail_label = QLabel("")
        self.detail_label.setFont(QFont("Microsoft YaHei", 9))
        self.detail_label.setStyleSheet("color: #666; padding: 5px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.setLayout(layout)

    def update_status(self, status: str, progress: int, detail: str = ""):
        """更新状态"""
        self.status_label.setText(status)
        self.progress_bar.setValue(progress)
        if detail:
            self.detail_label.setText(detail)
        QApplication.processEvents()


class Updater:
    """更新程序核心逻辑"""

    def __init__(
        self,
        update_package: str,
        target_dir: str,
        main_exe: str,
        pid: Optional[int] = None,
    ):
        self.update_package = Path(update_package)
        self.target_dir = Path(target_dir)
        self.main_exe = main_exe
        self.pid = pid
        self.gui: Optional[UpdaterGUI] = None

    def set_gui(self, gui: UpdaterGUI):
        """设置GUI界面"""
        self.gui = gui

    def log(
        self, message: str, progress: int = 0, detail: str = "", level: str = "INFO"
    ):
        """记录日志并更新GUI"""
        # 记录到日志文件
        log_func = getattr(logger, level.lower(), logger.info)
        log_msg = f"{message} | Progress: {progress}%"
        if detail:
            log_msg += f" | Detail: {detail}"
        log_func(log_msg)

        # 更新GUI
        if self.gui:
            self.gui.update_status(message, progress, detail)

    def wait_for_process_exit(self, timeout: int = 30) -> bool:
        """等待主程序退出"""
        if not self.pid:
            return True

        if not psutil:
            # 如果没有psutil,简单等待5秒
            self.log("等待主程序退出...", 10, "等待5秒")
            time.sleep(5)
            return True

        self.log("等待主程序退出...", 10, f"进程ID: {self.pid}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            if not psutil.pid_exists(self.pid):
                self.log("主程序已退出", 20)
                return True
            time.sleep(0.5)

        self.log("等待超时,继续更新", 20, "主程序可能未完全退出")
        return False

    def extract_update_package(self, extract_dir: Path) -> bool:
        """解压更新包"""
        try:
            self.log("正在解压更新包...", 30, f"源: {self.update_package.name}")
            logger.info(f"开始解压: {self.update_package} -> {extract_dir}")

            with zipfile.ZipFile(self.update_package, "r") as zip_ref:
                file_list = zip_ref.namelist()
                logger.info(f"更新包包含 {len(file_list)} 个文件")
                zip_ref.extractall(extract_dir)

            self.log("更新包解压完成", 50, f"文件数: {len(file_list)}")
            logger.info(f"解压完成: {len(file_list)} 个文件")
            return True
        except zipfile.BadZipFile as e:
            self.log("解压失败: 更新包损坏", 50, f"错误码: {UpdaterError.EXTRACT_FAILED}", "ERROR")
            logger.error(f"更新包损坏: {e}")
            return False
        except PermissionError as e:
            self.log("解压失败: 权限不足", 50, f"错误码: {UpdaterError.EXTRACT_FAILED}", "ERROR")
            logger.error(f"权限不足: {e}")
            return False
        except Exception as e:
            self.log(f"解压失败: {e}", 50, f"错误码: {UpdaterError.EXTRACT_FAILED}", "ERROR")
            logger.error(f"解压失败: {e}", exc_info=True)
            return False

    def backup_current_version(self, backup_dir: Path) -> bool:
        """备份当前版本"""
        try:
            self.log("正在备份当前版本...", 55, str(backup_dir))

            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            # 只备份主要文件,不备份配置和数据
            backup_dir.mkdir(parents=True, exist_ok=True)

            for item in self.target_dir.iterdir():
                if item.name.startswith(".") or item.name in [
                    "logs",
                    "cache",
                    ".stock_monitor",
                ]:
                    continue

                dest = backup_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            self.log("备份完成", 60)
            return True
        except Exception as e:
            self.log(f"备份失败: {e}", 60, "继续更新")
            return False

    def replace_files(self, source_dir: Path) -> bool:
        """替换文件"""
        try:
            self.log("正在替换文件...", 70, "请稍候")
            logger.info(f"开始替换文件: {source_dir} -> {self.target_dir}")

            # 查找解压后的实际目录
            actual_source = source_dir
            if not (source_dir / self.main_exe).exists():
                # 可能在子目录中
                subdirs = [d for d in source_dir.iterdir() if d.is_dir()]
                if subdirs:
                    actual_source = subdirs[0]
                    logger.info(f"使用子目录: {actual_source}")

            # 替换文件
            replaced_count = 0
            for item in actual_source.iterdir():
                dest = self.target_dir / item.name

                # 跳过配置和数据目录
                if item.name.startswith(".") or item.name in [
                    "logs",
                    "cache",
                    ".stock_monitor",
                ]:
                    logger.debug(f"跳过: {item.name}")
                    continue

                try:
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()

                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

                    replaced_count += 1
                    logger.debug(f"替换: {item.name}")
                except Exception as e:
                    logger.warning(f"替换 {item.name} 失败: {e}")

            self.log("文件替换完成", 90, f"已替换 {replaced_count} 个文件/目录")
            logger.info(f"替换完成: {replaced_count} 个项目")
            return True
        except Exception as e:
            self.log(f"替换文件失败: {e}", 90, f"错误码: {UpdaterError.REPLACE_FAILED}", "ERROR")
            logger.error(f"替换文件失败: {e}", exc_info=True)
            return False

    def start_main_program(self) -> bool:
        """启动新版本主程序"""
        try:
            self.log("正在启动新版本...", 95, self.main_exe)

            main_exe_path = self.target_dir / self.main_exe
            if not main_exe_path.exists():
                self.log(f"找不到主程序: {main_exe_path}", 95, "启动失败")
                return False

            # 使用Popen分离进程
            subprocess.Popen(
                [str(main_exe_path)],
                cwd=str(self.target_dir),
                creationflags=subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP,
            )

            self.log("新版本已启动", 100)
            return True
        except Exception as e:
            self.log(f"启动失败: {e}", 100, "请手动启动程序")
            return False

    def self_delete(self):
        """延迟自删除"""
        try:
            # 创建批处理脚本来删除自己
            updater_path = Path(
                sys.executable if getattr(sys, "frozen", False) else __file__
            )
            bat_path = updater_path.parent / "cleanup_updater.bat"

            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
del /f /q "{updater_path}"
del /f /q "%~f0"
"""

            with open(bat_path, "w") as f:
                f.write(bat_content)

            # 启动批处理脚本
            subprocess.Popen(
                [str(bat_path)],
                creationflags=subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP,
                shell=True,
            )
        except Exception as e:
            print(f"自删除失败: {e}")

    def run(self) -> bool:
        """执行更新流程"""
        try:
            # 1. 等待主程序退出
            if not self.wait_for_process_exit():
                return False

            # 2. 创建临时目录
            temp_dir = self.target_dir.parent / "update_temp"
            backup_dir = self.target_dir.parent / "backup_old"

            # 3. 解压更新包
            if not self.extract_update_package(temp_dir):
                return False

            # 4. 备份当前版本
            self.backup_current_version(backup_dir)

            # 5. 替换文件
            if not self.replace_files(temp_dir):
                self.log("更新失败,正在回滚...", 80)
                # 回滚
                if backup_dir.exists():
                    self.replace_files(backup_dir)
                return False

            # 6. 清理临时文件
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                if self.update_package.exists():
                    self.update_package.unlink()
            except:
                pass

            # 7. 启动新版本
            if not self.start_main_program():
                return False

            # 8. 延迟自删除
            self.self_delete()

            return True
        except Exception as e:
            self.log(f"更新失败: {e}", 0, "发生错误")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Stock Monitor Updater")
    parser.add_argument("--update-package", required=True, help="更新包路径")
    parser.add_argument("--target-dir", required=True, help="目标目录")
    parser.add_argument("--main-exe", required=True, help="主程序文件名")
    parser.add_argument("--pid", type=int, help="主程序进程ID")
    parser.add_argument("--no-gui", action="store_true", help="不显示GUI")

    args = parser.parse_args()

    # 创建更新器
    updater = Updater(
        update_package=args.update_package,
        target_dir=args.target_dir,
        main_exe=args.main_exe,
        pid=args.pid,
    )

    # 如果有GUI支持且未禁用,显示GUI
    if HAS_GUI and not args.no_gui:
        app = QApplication(sys.argv)
        gui = UpdaterGUI()
        updater.set_gui(gui)
        gui.show()

        # 使用QTimer延迟执行更新,避免阻塞GUI
        def run_update():
            success = updater.run()
            if success:
                QTimer.singleShot(2000, app.quit)
            else:
                QTimer.singleShot(5000, app.quit)

        QTimer.singleShot(500, run_update)
        sys.exit(app.exec())
    else:
        # 命令行模式
        success = updater.run()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
