import os
import time
from typing import Optional

from .logger import app_logger


def clean_old_logs(log_dir: Optional[str] = None, days_to_keep: int = 7) -> int:
    """
    清理指定目录下超过指定天数的日志文件

    Args:
        log_dir: 日志目录路径，默认为项目根目录下的logs目录
        days_to_keep: 保留天数，默认为7天

    Returns:
        int: 删除的日志文件数量
    """
    if log_dir is None:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(project_root, "logs")

    # 检查日志目录是否存在
    if not os.path.exists(log_dir):
        app_logger.info(f"日志目录不存在: {log_dir}")
        return 0

    # 计算删除时间阈值
    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    deleted_count = 0

    try:
        # 遍历日志目录中的所有文件
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)

            # 只处理文件，跳过目录
            if os.path.isfile(file_path):
                # 获取文件的修改时间
                file_mtime = os.path.getmtime(file_path)

                # 如果文件修改时间早于阈值，则删除文件
                if file_mtime < cutoff_time:
                    try:
                        os.remove(file_path)
                        app_logger.info(f"已删除过期日志文件: {file_path}")
                        deleted_count += 1
                    except OSError as e:
                        app_logger.warning(f"删除日志文件失败: {file_path}, 错误: {e}")

        app_logger.info(f"日志清理完成，删除了 {deleted_count} 个过期日志文件")
        return deleted_count

    except Exception as e:
        app_logger.error(f"清理日志文件时发生错误: {e}")
        return 0


def schedule_log_cleanup(days_to_keep: int = 7, interval_hours: int = 24) -> None:
    """
    定期清理日志文件

    Args:
        days_to_keep: 保留天数，默认为7天
        interval_hours: 清理间隔小时数，默认为24小时
    """
    from PyQt6.QtCore import QTimer

    from stock_monitor.utils.logger import app_logger

    app_logger.info(
        f"准备启动日志定期清理任务，保留 {days_to_keep} 天日志，清理间隔 {interval_hours} 小时"
    )

    # 首次启动立即执行一次清理
    try:
        clean_old_logs(days_to_keep=days_to_keep)
    except Exception as e:
        app_logger.error(f"首次日志清理失败: {e}")

    # 将 timer 绑定到函数本身以防止被垃圾回收
    if getattr(schedule_log_cleanup, "_timer", None) is not None:
        schedule_log_cleanup._timer.stop()

    schedule_log_cleanup._timer = QTimer()

    def on_timeout():
        try:
            clean_old_logs(days_to_keep=days_to_keep)
        except Exception as e:
            app_logger.error(f"定期日志清理失败: {e}")

    schedule_log_cleanup._timer.timeout.connect(on_timeout)
    # interval_hours * 小时 -> 毫秒
    schedule_log_cleanup._timer.start(interval_hours * 3600 * 1000)
    app_logger.debug("日志清理 QTimer 已启动")
