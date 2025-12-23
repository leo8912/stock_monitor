"""
股票数据获取模块
负责从各种数据源获取原始股票数据
"""

import time
from typing import Any, Dict, List, Optional

import easyquotation

from ..utils.error_handler import retry_on_failure, safe_call
from ..utils.logger import app_logger

# 常量定义
MAX_RETRY_ATTEMPTS = 5  # 股票数据获取最大重试次数
RETRY_DELAY_SECONDS = 2  # 重试间隔(秒)


class StockDataFetcher:
    """股票数据获取类"""
    
    def __init__(self):
        """初始化数据获取器"""
        def init_sina_quotation():
            return easyquotation.use('sina')
        
        self.sina_quotation = safe_call(
            init_sina_quotation, 
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(f"初始化新浪行情引擎失败: {e}") or None
        )
    
    def get_quotation_engine(self, code: str):
        """
        根据股票代码获取相应的行情引擎
        
        Args:
            code (str): 股票代码
            
        Returns:
            行情引擎实例或None
        """
        # 根据股票代码类型选择不同的行情引擎
        if code.startswith('hk'):
            def init_hk_quotation():
                return easyquotation.use('hkquote')
                
            quotation_engine = safe_call(
                init_hk_quotation,
                default_return=None,
                exception_handler=lambda e, error_type: app_logger.error(f"初始化港股行情引擎失败: {e}") or None
            )
            if quotation_engine:
                app_logger.debug(f"使用 hkquote 引擎获取港股 {code} 数据")
            return quotation_engine
        else:
            if self.sina_quotation is None:
                def init_sina_quotation():
                    return easyquotation.use('sina')
                    
                self.sina_quotation = safe_call(
                    init_sina_quotation,
                    default_return=None,
                    exception_handler=lambda e, error_type: app_logger.error(f"重新初始化新浪行情引擎失败: {e}") or None
                )
            quotation_engine = self.sina_quotation
            app_logger.debug(f"使用 sina 引擎获取股票 {code} 数据")
        return quotation_engine
    
    def fetch_single_stock(self, quotation_engine, code: str, query_code: str) -> Optional[Dict[str, Any]]:
        """
        从行情引擎获取单只股票数据
        
        Args:
            quotation_engine: 行情引擎
            code: 完整股票代码(带前缀)
            query_code: 查询用代码(可能不带前缀)
            
        Returns:
            股票数据字典或None
        """
        try:
            if code.startswith(('sh', 'sz')):
                # A股:使用prefix=True参数,用完整代码作为键
                single = quotation_engine.stocks(code, prefix=True)
                return single if isinstance(single, dict) and code in single else None
            elif code.startswith('hk'):
                # 港股:移除前缀查询
                single = quotation_engine.stocks(query_code)
                return single if isinstance(single, dict) else None
            else:
                # 其他:使用纯代码查询
                single = quotation_engine.stocks(query_code)
                return single if isinstance(single, dict) else None
        except Exception as e:
            app_logger.debug(f"获取股票 {code} 数据时发生异常: {e}")
            return None

    def fetch_with_retry(self, quotation_engine, code: str) -> Optional[Dict[str, Any]]:
        """
        带重试机制获取股票数据
        
        Args:
            quotation_engine: 行情引擎
            code (str): 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票数据或None
        """
        # 准备查询代码(移除前缀)
        query_code = code[2:] if code.startswith(('sh', 'sz', 'hk')) else code
        
        # 首次尝试
        stock_data = self.fetch_single_stock(quotation_engine, code, query_code)
        if stock_data is not None:
            return stock_data
        
        # 重试机制
        for retry_count in range(1, MAX_RETRY_ATTEMPTS + 1):
            app_logger.debug(f"获取 {code} 数据失败,第 {retry_count} 次重试")
            time.sleep(RETRY_DELAY_SECONDS)
            
            stock_data = self.fetch_single_stock(quotation_engine, code, query_code)
            if stock_data is not None:
                return stock_data
                
        return None
    
    @retry_on_failure(max_attempts=3, delay=1.0)
    def fetch_single(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票数据,带重试机制
        
        Args:
            code (str): 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票数据,获取失败则返回None
        """
        try:
            quotation_engine = self.get_quotation_engine(code)
            if quotation_engine is None:
                return None
            
            stock_data = self.fetch_with_retry(quotation_engine, code)
            return stock_data
        except Exception as e:
            app_logger.error(f'获取股票 {code} 数据失败: {e}')
            return None
    
    def fetch_multiple(self, codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        批量获取多只股票数据,按市场类型分组处理
        
        Args:
            codes (List[str]): 股票代码列表
            
        Returns:
            Dict[str, Optional[Dict[str, Any]]]: 股票数据字典,键为股票代码,值为股票数据或None
        """
        result = {}
        
        # 按市场类型分组
        sina_codes = []      # A股普通股票和指数
        hk_codes = []        # 港股
        
        for code in codes:
            if code.startswith('hk'):
                hk_codes.append(code)
            else:
                sina_codes.append(code)
        
        # 批量获取A股数据(包括指数)
        if sina_codes:
            self._fetch_sina_stocks(result, sina_codes)
        
        # 批量获取港股数据
        if hk_codes:
            self._fetch_hk_stocks(result, hk_codes)
        
        # 处理未能获取的数据
        for code in codes:
            if code not in result:
                result[code] = None
                
        return result
    
    def _fetch_sina_stocks(self, result: dict, sina_codes: List[str]):
        """
        批量获取A股数据
        
        Args:
            result (dict): 结果字典
            sina_codes (List[str]): A股代码列表
        """
        try:
            # 确保sina引擎已初始化
            def init_sina_if_needed():
                if self.sina_quotation is None:
                    self.sina_quotation = easyquotation.use('sina')
                return self.sina_quotation
            
            quotation_engine = safe_call(
                init_sina_if_needed,
                default_return=None,
                exception_handler=lambda e, error_type: app_logger.error(f"初始化新浪行情引擎失败: {e}") or None
            )
            
            if quotation_engine:
                def fetch_sina_stocks():
                    # 使用prefix=True确保返回的键包含前缀
                    return quotation_engine.stocks(sina_codes, prefix=True)
                
                sina_data = safe_call(
                    fetch_sina_stocks,
                    default_return={},
                    exception_handler=lambda e, error_type: app_logger.error(f"批量获取A股数据失败: {e}") or {}
                )
                
                if sina_data:
                    result.update(sina_data)
                    app_logger.debug(f"成功获取 {len(sina_data)} 只A股数据")
        except Exception as e:
            app_logger.error(f"批量获取A股数据时发生错误: {e}")
    
    def _fetch_hk_stocks(self, result: dict, hk_codes: List[str]):
        """
        批量获取港股数据
        
        Args:
            result (dict): 结果字典
            hk_codes (List[str]): 港股代码列表
        """
        try:
            # 初始化港股引擎
            def init_hk_quotation():
                return easyquotation.use('hkquote')
            
            quotation_engine = safe_call(
                init_hk_quotation,
                default_return=None,
                exception_handler=lambda e, error_type: app_logger.error(f"初始化港股行情引擎失败: {e}") or None
            )
            
            if quotation_engine:
                # 港股需要移除前缀
                query_codes = [code[2:] for code in hk_codes]
                
                def fetch_hk_stocks():
                    hk_data_raw = quotation_engine.stocks(query_codes)
                    # 将返回的数据键添加hk前缀
                    if isinstance(hk_data_raw, dict):
                        return {f"hk{k}": v for k, v in hk_data_raw.items()}
                    return {}
                
                hk_data = safe_call(
                    fetch_hk_stocks,
                    default_return={},
                    exception_handler=lambda e, error_type: app_logger.error(f"批量获取港股数据失败: {e}") or {}
                )
                
                if hk_data:
                    result.update(hk_data)
                    app_logger.debug(f"成功获取 {len(hk_data)} 只港股数据")
        except Exception as e:
            app_logger.error(f"批量获取港股数据时发生错误: {e}")


# 创建全局实例
stock_data_fetcher = StockDataFetcher()
