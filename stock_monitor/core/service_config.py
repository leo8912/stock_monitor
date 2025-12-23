"""
服务配置模块
统一配置和注册所有服务到DI容器
"""

from ..utils.logger import app_logger
from .container import container
from .stock_data_fetcher import StockDataFetcher
from .stock_data_processor import StockDataProcessor
from .stock_data_validator import StockDataValidator
from .stock_service import StockDataService


def configure_services():
    """配置所有服务到DI容器"""

    # 注册数据获取器
    container.register_singleton("stock_fetcher", StockDataFetcher())
    container.register_singleton(StockDataFetcher, container.get("stock_fetcher"))

    # 注册数据验证器
    container.register_singleton("stock_validator", StockDataValidator())
    container.register_singleton(StockDataValidator, container.get("stock_validator"))

    # 注册数据处理器
    container.register_singleton("stock_processor", StockDataProcessor())
    container.register_singleton(StockDataProcessor, container.get("stock_processor"))

    # 注册股票数据服务(使用工厂模式,支持依赖注入)
    def create_stock_service():
        return StockDataService(
            fetcher=container.get("stock_fetcher"),
            validator=container.get("stock_validator"),
            processor=container.get("stock_processor"),
        )

    container.register_factory("stock_service", create_stock_service)
    container.register_factory(StockDataService, create_stock_service)

    app_logger.info("服务配置完成")


# 可选:在模块导入时自动配置
# configure_services()
