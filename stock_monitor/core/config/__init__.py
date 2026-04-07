"""
配置管理层 (Core Config Layer)

职责:
- 服务配置与注册
- 依赖注入容器管理
- 应用启动流程协调

模块包含:
- service_config.py: 核心服务注册(StockDataFetcher/Processor/Validator/Service)
- container.py: DIContainer和全局容器实例
- startup.py: 应用启动初始化流程
"""

from .container import DIContainer, container
from .service_config import configure_services
from .startup import apply_pending_updates, check_update_status, setup_auto_start

__all__ = [
    "configure_services",
    "DIContainer",
    "container",
    "apply_pending_updates",
    "check_update_status",
    "setup_auto_start",
]
