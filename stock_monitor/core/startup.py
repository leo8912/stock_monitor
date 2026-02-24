"""
启动辅助模块
包含应用程序启动所需的辅助逻辑
"""

import os
import sys

from stock_monitor.utils.logger import app_logger


def apply_pending_updates():
    """在应用启动时应用待处理的更新"""
    # BAT更新方案不再需要启动检查，更新是即时的
    pass


def check_update_status():
    """
    检查更新状态标记文件

    Returns:
        tuple: (status, info)
               status: "success" | "failed" | None
               info: 更新时间或错误信息
    """
    try:
        from stock_monitor.config.manager import get_config_dir

        config_dir = get_config_dir()
        success_marker = os.path.join(config_dir, "update_complete.txt")
        failed_marker = os.path.join(config_dir, "update_failed.txt")

        # 检查更新成功标记
        if os.path.exists(success_marker):
            try:
                with open(success_marker, encoding="gbk") as f:
                    update_time = f.read().strip()
                os.remove(success_marker)
                app_logger.info(f"检测到更新成功标记，更新时间: {update_time}")
                return ("success", update_time)
            except Exception as e:
                app_logger.warning(f"读取更新成功标记失败: {e}")
                try:
                    os.remove(success_marker)
                except OSError:
                    pass

        # 检查更新失败标记
        if os.path.exists(failed_marker):
            try:
                with open(failed_marker, encoding="gbk") as f:
                    error_info = f.read().strip()
                os.remove(failed_marker)
                app_logger.error(f"检测到更新失败标记: {error_info}")
                return ("failed", error_info)
            except Exception as e:
                app_logger.warning(f"读取更新失败标记失败: {e}")
                try:
                    os.remove(failed_marker)
                except OSError:
                    pass

        return (None, None)
    except Exception as e:
        app_logger.error(f"检查更新状态时出错: {e}")
        return (None, None)


def setup_auto_start():
    """
    设置开机自启动功能
    通过在用户启动文件夹中创建/删除快捷方式实现
    """
    try:
        from stock_monitor.config.manager import ConfigManager
        from stock_monitor.core.container import container

        # 通过 DI 容器获取 ConfigManager，保持架构一致性
        config_manager = container.get(ConfigManager)
        auto_start = config_manager.get("auto_start", False)

        # 获取启动文件夹路径
        startup_folder = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "Startup",
        )

        # 检查启动文件夹是否存在
        if not os.path.exists(startup_folder):
            app_logger.warning(f"启动文件夹不存在: {startup_folder}")
            return

        shortcut_path = os.path.join(startup_folder, "StockMonitor.lnk")

        # 如果启用开机启动
        if auto_start:
            # 获取应用程序路径
            if hasattr(sys, "_MEIPASS"):
                # PyInstaller打包环境
                app_path = sys.executable
            else:
                # 开发环境
                app_path = os.path.abspath(sys.argv[0])

            # 创建快捷方式
            _create_shortcut(app_path, shortcut_path)
            app_logger.info(f"已创建开机启动快捷方式: {shortcut_path}")
        else:
            # 如果禁用开机启动且快捷方式存在，则删除
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                app_logger.info(f"已删除开机启动快捷方式: {shortcut_path}")
    except Exception as e:
        app_logger.error(f"设置开机启动失败: {e}")


def _create_shortcut(target_path, shortcut_path):
    """
    创建快捷方式

    Args:
        target_path (str): 目标文件路径
        shortcut_path (str): 快捷方式保存路径
    """
    try:
        # 尝试使用win32com创建快捷方式
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.IconLocation = target_path
        shortcut.save()
    except ImportError:
        # win32com不可用时的备选方案
        try:
            # 尝试只使用内置模块
            if target_path.endswith(".py"):
                # 如果是Python脚本，创建批处理文件
                batch_content = f'@echo off\npython "{target_path}"\n'
                batch_path = shortcut_path.replace(".lnk", ".bat")
                with open(batch_path, "w") as f:
                    f.write(batch_content)
            else:
                # 如果是exe文件，创建批处理文件启动 (比复制EXE安全得多)
                # 使用 copy2 复制 EXE 会导致自启版本无法更新
                batch_content = f'@echo off\nstart "" "{target_path}"\n'
                batch_path = shortcut_path.replace(".lnk", ".bat")
                with open(batch_path, "w") as f:
                    f.write(batch_content)
                app_logger.info(f"由于win32com不可用，已创建BAT启动脚本: {batch_path}")
        except Exception as e:
            app_logger.error(f"创建快捷方式失败: {e}")
    except Exception as e:
        # 捕获 ImportError 以外的其他异常
        app_logger.error(f"创建快捷方式时发生未知错误: {e}")
