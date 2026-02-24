"""
依赖注入容器模块
用于管理核心组件的依赖关系
"""

import inspect
from typing import Any, Callable, Optional, Union

from ..config.manager import ConfigManager
from ..core.stock_manager import StockManager
from ..core.stock_service import StockDataService
from ..data.stock.stock_db import StockDatabase
from ..utils.logger import app_logger


class DIContainer:
    """依赖注入容器 - 支持类型和字符串键"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._factories: dict[Union[type, str], Callable] = {}
        self._singletons: dict[Union[type, str], Any] = {}
        app_logger.debug("DI容器初始化完成")

    def register_singleton(self, key: Union[type, str], instance: Any) -> None:
        """
        注册单例服务

        Args:
            key: 服务类型或字符串键
            instance: 服务实例
        """
        self._singletons[key] = instance
        app_logger.debug(f"注册单例服务: {key}")

    def register_factory(self, key: Union[type, str], factory: Callable) -> None:
        """
        注册工厂函数

        Args:
            key: 服务类型或字符串键
            factory: 工厂函数
        """
        self._factories[key] = factory
        app_logger.debug(f"注册工厂: {key}")

    def register(self, key: Union[type, str], instance: Any) -> None:
        """
        注册服务实例(向后兼容)

        Args:
            key: 服务类型或字符串键
            instance: 服务实例
        """
        self.register_singleton(key, instance)

    def get(self, key: Union[type, str]) -> Any:
        """
        获取服务实例

        Args:
            key: 服务类型或字符串键

        Returns:
            服务实例
        """
        # 优先返回已注册的单例
        if key in self._singletons:
            return self._singletons[key]

        # 使用工厂创建
        if key in self._factories:
            instance = self._factories[key]()
            # 工厂创建的也缓存为单例
            self._singletons[key] = instance
            app_logger.debug(f"通过工厂创建服务: {key}")
            return instance

        # 向后兼容:自动创建常见服务
        if isinstance(key, type):
            instance = self._auto_create(key)
            if instance is not None:
                self._singletons[key] = instance
                return instance

        raise KeyError(f"服务未注册: {key}")

    def _auto_create(self, service_type: type) -> Optional[Any]:
        """
        自动创建服务实例(向后兼容)

        Args:
            service_type: 服务类型

        Returns:
            服务实例或None
        """
        if service_type == ConfigManager:
            app_logger.debug("自动创建ConfigManager")
            return ConfigManager()
        elif service_type == StockDataService:
            app_logger.debug("自动创建StockDataService")
            return StockDataService()
        elif service_type == StockManager:
            app_logger.debug("自动创建StockManager")
            stock_data_service = self.get(StockDataService)
            return StockManager(stock_data_service=stock_data_service)
        elif service_type == StockDatabase:
            app_logger.debug("自动创建StockDatabase")
            return StockDatabase()

        return None

    def resolve(self, cls: type) -> Any:
        """
        自动解析类的依赖并创建实例

        Args:
            cls: 要创建的类

        Returns:
            类实例
        """
        try:
            # 获取构造函数签名
            sig = inspect.signature(cls.__init__)
            params = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # 尝试从容器获取依赖
                try:
                    # 先尝试用参数名作为字符串键
                    params[param_name] = self.get(param_name)
                except KeyError:
                    # 如果有类型注解,尝试用类型获取
                    if param.annotation != inspect.Parameter.empty:
                        try:
                            params[param_name] = self.get(param.annotation)
                        except KeyError:
                            # 区分有默认值和无默认值的参数
                            if param.default == inspect.Parameter.empty:
                                app_logger.error(
                                    f"无法解析必需依赖: {cls.__name__}.{param_name} "
                                    f"(类型: {param.annotation})"
                                )
                                raise KeyError(
                                    f"无法解析必需依赖: {cls.__name__}.{param_name}"
                                ) from None
                            else:
                                app_logger.debug(
                                    f"可选依赖未找到，使用默认值: {cls.__name__}.{param_name}"
                                )
                    elif param.default == inspect.Parameter.empty:
                        app_logger.warning(
                            f"无法解析依赖且无类型注解: {cls.__name__}.{param_name}"
                        )

            instance = cls(**params)
            app_logger.debug(f"自动解析并创建: {cls.__name__}")
            return instance

        except Exception as e:
            app_logger.error(f"解析依赖失败: {cls.__name__}, 错误: {e}")
            raise

    def has(self, key: Union[type, str]) -> bool:
        """
        检查服务是否已注册

        Args:
            key: 服务类型或字符串键

        Returns:
            是否已注册
        """
        return key in self._singletons or key in self._factories

    def clear(self) -> None:
        """清空所有注册的服务(主要用于测试)"""
        self._factories.clear()
        self._singletons.clear()
        app_logger.debug("DI容器已清空")


# 创建全局容器实例
container = DIContainer()
