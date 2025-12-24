"""
股票数据源抽象接口
定义统一的数据访问接口，将数据库、缓存、文件等数据源的访问方式抽象化
"""

from abc import ABC, abstractmethod
from typing import Optional


class StockDataSource(ABC):
    """股票数据源抽象接口"""

    @abstractmethod
    def get_stock_by_code(self, code: str) -> Optional[dict[str, str]]:
        """
        根据股票代码获取股票信息

        Args:
            code: 股票代码

        Returns:
            Optional[Dict[str, str]]: 股票信息，未找到返回None
        """
        pass

    @abstractmethod
    def search_stocks(self, keyword: str, limit: int = 30) -> list[dict[str, str]]:
        """
        搜索股票

        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            List[Dict[str, str]]: 匹配的股票列表
        """
        pass

    @abstractmethod
    def get_all_stocks(self) -> list[dict[str, str]]:
        """
        获取所有股票数据

        Returns:
            List[Dict[str, str]]: 所有股票数据
        """
        pass

    @abstractmethod
    def get_stocks_by_market_type(self, market_type: str) -> list[dict[str, str]]:
        """
        根据市场类型获取股票列表

        Args:
            market_type: 市场类型 ('A', 'INDEX', 'HK')

        Returns:
            List[Dict[str, str]]: 股票列表
        """
        pass
