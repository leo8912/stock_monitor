"""
启动辅助模块
包含应用程序启动所需的辅助逻辑
"""

import os
import shutil
import sys

from stock_monitor.utils.logger import app_logger


def apply_pending_updates():
    """在应用启动时应用待处理的更新"""
    # BAT更新方案不再需要启动检查，更新是即时的
    pass


def setup_auto_start():
    """
    设置开机自启动功能
    通过在用户启动文件夹中创建/删除快捷方式实现
    """
    try:
        from stock_monitor.config.manager import ConfigManager

        # 获取配置
        # 注意：ConfigManager 应该通过依赖注入获取，或者直接实例化（单例模式）
        # 这里直接实例化，因为 startup 可能在 container 初始化之前或之后
        # 为了安全，这里实例化一个新的，ConfigManager内部处理了单例/配置加载
        config_manager = ConfigManager()
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
                # 如果是exe文件，直接复制（不太理想，但作为fallback）
                # 注意：直接复制exe不是快捷方式，但能达到启动目的
                shutil.copy2(target_path, shortcut_path.replace(".lnk", ".exe"))
        except Exception as e:
            app_logger.error(f"创建快捷方式失败: {e}")
    except Exception as e:
        # 捕获 ImportError 以外的其他异常
        app_logger.error(f"创建快捷方式时发生未知错误: {e}")
