"""
股票数据服务模块
提供统一的股票数据获取接口
"""

from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import app_logger
from .stock_data_fetcher import StockDataFetcher
from .stock_data_processor import StockDataProcessor
from .stock_data_validator import StockDataValidator


class StockDataService:
    """股票数据服务类 - 协调各个数据模块"""

    def __init__(
        self,
        fetcher: Optional[StockDataFetcher] = None,
        validator: Optional[StockDataValidator] = None,
        processor: Optional[StockDataProcessor] = None,
    ):
        """
        初始化股票数据服务

        Args:
            fetcher: 数据获取器(可选,用于依赖注入)
            validator: 数据验证器(可选,用于依赖注入)
            processor: 数据处理器(可选,用于依赖注入)
        """
        # 支持依赖注入,同时保持向后兼容
        self.fetcher = fetcher or StockDataFetcher()
        self.validator = validator or StockDataValidator()
        self.processor = processor or StockDataProcessor()
        app_logger.info("股票数据服务初始化完成")

    def get_stock_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票数据,带重试机制

        Args:
            code (str): 股票代码

        Returns:
            Optional[Dict[str, Any]]: 股票数据,获取失败则返回None
        """
        return self.fetcher.fetch_single(code)

    def get_multiple_stocks_data(
        self, codes: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        批量获取多只股票数据,按市场类型分组处理

        Args:
            codes (List[str]): 股票代码列表

        Returns:
            Dict[str, Optional[Dict[str, Any]]]: 股票数据字典,键为股票代码,值为股票数据或None
        """
        return self.fetcher.fetch_multiple(codes)

    def is_stock_data_valid(self, stock_data: Dict[str, Any]) -> bool:
        """
        检查股票数据是否完整有效

        Args:
            stock_data: 股票数据字典

        Returns:
            bool: 数据是否有效
        """
        return self.validator.is_valid(stock_data)

    def process_stock_data(
        self, data: Dict[str, Any], stocks_list: List[str]
    ) -> List[Tuple]:
        """
        处理股票数据,返回格式化的股票列表

        Args:
            data: 股票数据字典
            stocks_list: 股票代码列表

        Returns:
            List[Tuple]: 格式化后的股票数据列表
        """
        from ..data.market.quotation import get_name_by_code

        stocks = []

        for code in stocks_list:
            info = self.validator.get_stock_info(data, code)

            if info:
                # 使用 StockDataProcessor 处理单只股票数据
                result = self.processor.process_raw_data(code, info)
                stocks.append(result)
                app_logger.debug(f"股票 {code} 数据处理完成")
            else:
                # 如果没有获取到数据,显示默认值
                name = code
                # 尝试从本地数据获取股票名称
                local_name = get_name_by_code(code)
                if local_name:
                    name = local_name
                    # 对于港股,只保留中文部分
                    if code.startswith("hk") and "-" in name:
                        name = name.split("-")[0].strip()
                stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                app_logger.warning(f"未获取到股票 {code} 的数据")

        app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
        app_logger.info(f"股票数据处理完成: 总计 {len(stocks)} 只股票")
        return stocks

    def get_all_market_data(self) -> Optional[Dict[str, Any]]:
        """
        获取全市场股票数据

        Returns:
            Optional[Dict[str, Any]]: 全市场股票数据字典,失败返回None
        """
        import easyquotation

        from ..utils.error_handler import safe_call

        def init_sina_if_needed():
            if self.fetcher.sina_quotation is None:
                self.fetcher.sina_quotation = easyquotation.use("sina")
            return self.fetcher.sina_quotation

        quotation_engine = safe_call(
            init_sina_if_needed,
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(
                f"初始化新浪行情引擎失败: {e}"
            )
            or None,
        )

        if quotation_engine:

            def fetch_market_snapshot():
                return quotation_engine.market_snapshot(prefix=True)

            market_data = safe_call(
                fetch_market_snapshot,
                default_return=None,
                exception_handler=lambda e, error_type: app_logger.error(
                    f"获取全市场数据失败: {e}"
                )
                or None,
            )
            return market_data
        return None


# 创建全局实例
stock_data_service = StockDataService()
