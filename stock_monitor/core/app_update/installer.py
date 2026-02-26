import os
import shutil
import sys
import zipfile
from pathlib import Path

from stock_monitor.utils.logger import app_logger


class UpdateInstaller:
    """负责将下载好的应用包进行安装"""

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
