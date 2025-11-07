"""
股票管理核心模块
负责处理股票相关的业务逻辑

该模块包含StockManager类，用于获取和处理股票数据。
"""

from typing import List, Dict, Any, Tuple
import easyquotation
from stock_monitor.utils.logger import app_logger
from stock_monitor.config.manager import is_market_open


class StockManager:
    """
    股票管理器，负责处理股票数据获取和处理的核心业务逻辑
    """
    
    def __init__(self):
        self.quotation = easyquotation.use('sina')
        self.hk_quotation = easyquotation.use('hkquote')
    
    def fetch_stock_data(self, stocks_list: List[str]) -> Tuple[List[Tuple], List[str]]:
        """
        获取股票数据
        
        Args:
            stocks_list: 股票代码列表
            
        Returns:
            tuple: (处理后的股票数据列表, 失败的股票列表)
        """
        from stock_monitor.data.market.quotation import process_stock_data as quotation_process_stock_data
        
        data_dict = {}
        failed_stocks = []
        app_logger.info(f"开始刷新 {len(stocks_list)} 只股票数据: {stocks_list}")
        
        for code in stocks_list:
            try:
                # 根据股票代码类型选择不同的行情引擎
                if code.startswith('hk'):
                    quotation_engine = self.hk_quotation
                    app_logger.debug(f"使用 hkquote 引擎获取港股 {code} 数据")
                else:
                    quotation_engine = self.quotation
                    app_logger.debug(f"使用 sina 引擎获取股票 {code} 数据")
                    
                # 对于港股，使用纯数字代码查询
                query_code = code[2:] if code.startswith('hk') else code
                app_logger.debug(f"请求代码: {query_code}")
                single = quotation_engine.stocks([query_code])  # type: ignore
                
                if isinstance(single, dict):
                    # 精确使用原始 code 作为 key 获取数据，避免映射错误
                    stock_data = single.get(query_code) or next(iter(single.values()), None)
                    data_dict[code] = stock_data
                    app_logger.debug(f"成功获取 {code} 数据: {stock_data}")
                else:
                    failed_stocks.append(code)
                    app_logger.warning(f"获取 {code} 数据失败，返回数据类型: {type(single)}")
            except Exception as e:
                app_logger.error(f'获取股票 {code} 数据失败: {e}')
                failed_stocks.append(code)
        
        stocks = quotation_process_stock_data(data_dict, stocks_list)
        return stocks, failed_stocks
    
    def is_stock_data_valid(self, stock_data: Dict) -> bool:
        """
        检查股票数据是否完整有效
        
        Args:
            stock_data: 股票数据字典
            
        Returns:
            bool: 数据是否有效
        """
        if not isinstance(stock_data, dict):
            return False
            
        # 检查关键字段是否存在且不为None
        now = stock_data.get('now') or stock_data.get('price')
        close = stock_data.get('close') or stock_data.get('lastPrice') or now
        
        # 如果now和close都为None，则数据不完整
        if now is None and close is None:
            return False
            
        return True