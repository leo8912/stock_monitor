"""
启动辅助模块
包含应用程序启动所需的辅助逻辑
"""

import os
import sys
import shutil
from stock_monitor.utils.logger import app_logger

def apply_pending_updates():
    """在应用启动时应用待处理的更新"""
    try:
        from stock_monitor.core.updater import app_updater
        
        # 获取当前目录 - 确保始终使用程序所在目录
        if hasattr(sys, '_MEIPASS'):
            # 打包环境 - 使用可执行文件所在目录
            current_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境或普通生产环境 - 使用main.py所在目录的父目录的父目录(项目根目录)
            # 注意：这里的逻辑需要小心，原始main.py是在 stock_monitor/main.py
            # 如果我们假设 main.py 在 stock_monitor 包内，那么 __file__ 指向 stock_monitor/main.py
            # 原始代码: current_dir = os.path.dirname(os.path.abspath(__file__))
            # 但在 startup.py 中 (stock_monitor/core/startup.py)，我们需要根据实际情况调整
            # 为了保持一致性，我们模拟 main.py 的行为
            # 实际上，更新逻辑通常基于 stock_monitor 包所在的目录或者更上层
            
            # 使用项目根目录作为基准可能更安全，或者直接复用原始逻辑
            # 原始逻辑是取 main.py 所在目录
            # 我们这里取 sys.argv[0] 的目录可能更准确，或者硬编码
             current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
             # 上面得到的是 stock_monitor 的父目录 (项目根目录)
             # 但原始代码 main.py 里的 current_dir 是 stock_monitor 包目录
             # 原始 main.py: os.path.dirname(os.path.abspath(__file__)) -> d:\code\stock\stock_monitor
        
        # 修正：直接使用 stock_monitor 包的根目录
        import stock_monitor
        package_dir = os.path.dirname(os.path.abspath(stock_monitor.__file__))
        current_dir = package_dir

        # 检查更新标记文件 (通常在程序根目录下)
        # 如果是打包环境，根目录是 exe 所在目录
        # 如果是开发环境，通常希望是在项目根目录或包目录
        # 保持与原始逻辑一致：update_pending 文件位置
        
        if hasattr(sys, '_MEIPASS'):
             base_dir = os.path.dirname(sys.executable)
        else:
             base_dir = package_dir

        update_marker = os.path.join(base_dir, 'update_pending')
        
        if os.path.exists(update_marker):
            try:
                # 读取更新文件路径
                with open(update_marker, 'r') as f:
                    update_file_path = f.read().strip()
                # 删除标记文件
                os.remove(update_marker)
                app_logger.info("检测到待处理的更新，正在应用...")
                # 应用更新，跳过锁定检查
                if app_updater.apply_update(update_file_path, skip_lock_check=True):
                    app_logger.info("更新应用完成")
                else:
                    app_logger.error("更新应用失败")
            except Exception as e:
                app_logger.error(f"应用待处理更新时出错: {e}")
                
        # 查找并删除所有的 .tmp 文件
        for filename in os.listdir(base_dir):
            if filename.endswith('.tmp'):
                tmp_file = os.path.join(base_dir, filename)
                try:
                    os.remove(tmp_file)
                    app_logger.info(f"已清理临时文件: {tmp_file}")
                except Exception as e:
                    app_logger.warning(f"无法删除临时文件 {tmp_file}: {e}")
    except Exception as e:
        # 此时logger可能尚未初始化完全，使用print
        print(f"应用更新检查失败: {e}")


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
            os.environ.get('APPDATA', ''),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        
        # 检查启动文件夹是否存在
        if not os.path.exists(startup_folder):
            app_logger.warning(f"启动文件夹不存在: {startup_folder}")
            return
            
        shortcut_path = os.path.join(startup_folder, 'StockMonitor.lnk')
        
        # 如果启用开机启动
        if auto_start:
            # 获取应用程序路径
            if hasattr(sys, '_MEIPASS'):
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
            if target_path.endswith('.py'):
                # 如果是Python脚本，创建批处理文件
                batch_content = f'@echo off\npython "{target_path}"\n'
                batch_path = shortcut_path.replace('.lnk', '.bat')
                with open(batch_path, 'w') as f:
                    f.write(batch_content)
            else:
                # 如果是exe文件，直接复制（不太理想，但作为fallback）
                # 注意：直接复制exe不是快捷方式，但能达到启动目的
                shutil.copy2(target_path, shortcut_path.replace('.lnk', '.exe'))
        except Exception as e:
            app_logger.error(f"创建快捷方式失败: {e}")
    except Exception as e:
        # 捕获 ImportError 以外的其他异常
        app_logger.error(f"创建快捷方式时发生未知错误: {e}")
