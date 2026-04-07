"""兼容旧路径的服务配置导出（重定向到 core.config.service_config）。"""

from stock_monitor.core.config.service_config import configure_services

__all__ = ["configure_services"]
