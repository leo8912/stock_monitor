"""兼容旧路径的启动模块导出（重定向到 core.config.startup）。"""

from stock_monitor.core.config.startup import (
    apply_pending_updates,
    check_update_status,
    setup_auto_start,
)

__all__ = [
    "apply_pending_updates",
    "check_update_status",
    "setup_auto_start",
]
