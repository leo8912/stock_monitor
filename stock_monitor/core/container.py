"""
依赖注入容器模块
用于管理核心组件的依赖关系
"""

from typing import Dict, Type, Any, Optional
from ..config.manager import ConfigManager
from ..core.stock_manager import StockManager
from ..core.stock_service import StockDataService


class DIContainer:
    """依赖注入容器"""
    
    _instance = None
    _services: Dict[Type, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DIContainer, cls).__new__(cls)
        return cls._instance
    
    def register(self, service_type: Type, instance: Any) -> None:
        """
        注册服务实例
        
        Args:
            service_type: 服务类型
            instance: 服务实例
        """
        self._services[service_type] = instance
    
    def get(self, service_type: Type) -> Any:
        """
        获取服务实例
        
        Args:
            service_type: 服务类型
            
        Returns:
            服务实例
        """
        if service_type not in self._services:
            # 如果还没有创建实例，则创建单例实例
            if service_type == ConfigManager:
                self._services[service_type] = ConfigManager()
            elif service_type == StockManager:
                self._services[service_type] = StockManager()
            elif service_type == StockDataService:
                self._services[service_type] = StockDataService()
            else:
                raise ValueError(f"Unknown service type: {service_type}")
        
        return self._services[service_type]


# 创建全局容器实例
container = DIContainer()