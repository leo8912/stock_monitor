"""
股票数据服务模块
提供统一的股票数据获取和处理接口
"""

import easyquotation
import time
import threading
from typing import Dict, Any, List, Tuple, Optional
from ..utils.logger import app_logger
from ..utils.cache import global_cache
from ..config.manager import is_market_open


class StockDataService:
    """股票数据服务类"""
    
    def __init__(self):
        """初始化股票数据服务"""
        self.quotation = easyquotation.use('sina')
        self._lock = threading.Lock()
        
    def get_stock_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票数据
        
        Args:
            code (str): 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票数据，获取失败返回None
        """
        # 检查缓存
        cache_key = f"stock_{code}"
        cached_data = global_cache.get_with_market_aware_ttl(cache_key)
        if cached_data is not None:
            return cached_data
            
        try:
            # 根据股票代码类型选择不同的行情引擎
            if code.startswith('hk'):
                quotation_engine = easyquotation.use('hkquote')
                app_logger.debug(f"使用 hkquote 引擎获取港股 {code} 数据")
            else:
                quotation_engine = easyquotation.use('sina')
                app_logger.debug(f"使用 sina 引擎获取股票 {code} 数据")
                
            # 对于港股，使用纯数字代码查询
            query_code = code[2:] if code.startswith('hk') else code
            app_logger.debug(f"请求代码: {query_code}")
            
            # 添加重试机制
            max_retries = 5
            retry_count = 0
            single = None
            
            while retry_count < max_retries:
                try:
                    single = quotation_engine.stocks([query_code])
                    # 检查返回数据是否有效
                    if isinstance(single, dict) and (query_code in single or any(single.values())):
                        # 确保返回的数据不是None且是完整的
                        stock_data = single.get(query_code) or next(iter(single.values()), None)
                        if stock_data is not None:
                            # 缓存数据
                            ttl = 30 if is_market_open() else 300  # 开市期间30秒，闭市期间300秒
                            global_cache.set(cache_key, stock_data, ttl=ttl)
                            return stock_data
                    retry_count += 1
                    app_logger.warning(f"获取 {code} 数据失败或不完整，第 {retry_count} 次重试")
                    if retry_count < max_retries:
                        time.sleep(2)
                except Exception as e:
                    retry_count += 1
                    app_logger.warning(f"获取 {code} 数据异常: {e}，第 {retry_count} 次重试")
                    if retry_count < max_retries:
                        time.sleep(2)
                        
            return None
        except Exception as e:
            app_logger.error(f'获取股票 {code} 数据失败: {e}')
            return None
            
    def get_multiple_stocks_data(self, codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        批量获取多只股票数据
        
        Args:
            codes (List[str]): 股票代码列表
            
        Returns:
            Dict[str, Optional[Dict[str, Any]]]: 股票数据字典，键为股票代码，值为股票数据或None
        """
        result = {}
        for code in codes:
            result[code] = self.get_stock_data(code)
        return result
        
    def is_stock_data_valid(self, stock_data: Dict[str, Any]) -> bool:
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


# 创建全局股票数据服务实例
stock_data_service = StockDataService()