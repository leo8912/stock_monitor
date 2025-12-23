"""
股票数据服务模块
提供统一的股票数据获取接口
"""

import time
from typing import List, Dict, Any, Optional, Tuple
import easyquotation
from ..utils.logger import app_logger
from ..utils.error_handler import retry_on_failure, safe_call
from ..utils.helpers import is_equal
from typing import Tuple

# 常量定义
MAX_RETRY_ATTEMPTS = 5  # 股票数据获取最大重试次数
RETRY_DELAY_SECONDS = 2  # 重试间隔(秒)


class StockDataService:
    """股票数据服务类"""
    
    def __init__(self):
        """初始化股票数据服务"""
        def init_sina_quotation():
            return easyquotation.use('sina')
        
        self.sina_quotation = safe_call(
            init_sina_quotation, 
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(f"初始化新浪行情引擎失败: {e}") or None
        )
    
    @retry_on_failure(max_attempts=3, delay=1.0)
    def get_stock_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票数据，带重试机制
        
        Args:
            code (str): 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票数据，获取失败则返回None
        """
        try:
            quotation_engine = self._get_quotation_engine(code)
            if quotation_engine is None:
                return None
            
            stock_data = self._fetch_stock_data_with_retry(quotation_engine, code)
            return stock_data
        except Exception as e:
            app_logger.error(f'获取股票 {code} 数据失败: {e}')
            return None
            
    def get_multiple_stocks_data(self, codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        批量获取多只股票数据，按市场类型分组处理
        
        Args:
            codes (List[str]): 股票代码列表
            
        Returns:
            Dict[str, Optional[Dict[str, Any]]]: 股票数据字典，键为股票代码，值为股票数据或None
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
        
        # 批量获取A股数据（包括指数）
        if sina_codes:
            self._fetch_sina_stocks_data(result, sina_codes)
        
        # 批量获取港股数据
        if hk_codes:
            self._fetch_hk_stocks_data(result, hk_codes)
        
        # 处理未能获取的数据
        for code in codes:
            if code not in result:
                result[code] = None
                
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
        required_fields = ['now', 'close']
        for field in required_fields:
            if field not in stock_data or stock_data[field] is None:
                return False
                
        # 检查关键字段是否为有效数值
        try:
            float(stock_data['now'])
            float(stock_data['close'])
            return True
        except (ValueError, TypeError):
            return False

    def process_stock_data(self, data: Dict[str, Any], stocks_list: List[str]) -> List[Tuple]:
        """
        处理股票数据，返回格式化的股票列表
        
        Args:
            data: 股票数据字典
            stocks_list: 股票代码列表
            
        Returns:
            List[Tuple]: 格式化后的股票数据列表
        """
        from ..data.market.quotation import get_name_by_code
        from ..core.processor import stock_processor
        
        stocks = []
        
        for code in stocks_list:
            info = self._get_stock_info(data, code)
            
            if info:
                # 使用 StockDataProcessor 处理单只股票数据
                result = stock_processor.process_raw_data(code, info)
                stocks.append(result)
                app_logger.debug(f"股票 {code} 数据处理完成")
            else:
                # 如果没有获取到数据，显示默认值
                name = code
                # 尝试从本地数据获取股票名称
                local_name = get_name_by_code(code)
                if local_name:
                    name = local_name
                    # 对于港股，只保留中文部分
                    if code.startswith('hk') and '-' in name:
                        name = name.split('-')[0].strip()
                stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                app_logger.warning(f"未获取到股票 {code} 的数据")
                
        app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
        app_logger.info(f"股票数据处理完成: 总计 {len(stocks)} 只股票")
        return stocks

    def _get_quotation_engine(self, code: str):
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

    def _fetch_single_stock(self, quotation_engine, code: str, query_code: str) -> Optional[Dict[str, Any]]:
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

    def _fetch_stock_data_with_retry(self, quotation_engine, code: str) -> Optional[Dict[str, Any]]:
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
        stock_data = self._fetch_single_stock(quotation_engine, code, query_code)
        if stock_data is not None:
            return stock_data
        
        # 重试机制
        for retry_count in range(1, MAX_RETRY_ATTEMPTS + 1):
            app_logger.debug(f"获取 {code} 数据失败,第 {retry_count} 次重试")
            time.sleep(RETRY_DELAY_SECONDS)
            
            stock_data = self._fetch_single_stock(quotation_engine, code, query_code)
            if stock_data is not None:
                return stock_data
                
        return None

    def _fetch_sina_stocks_data(self, result: dict, sina_codes: List[str]) -> None:
        """
        批量获取A股数据
        
        Args:
            result (dict): 结果字典
            sina_codes (List[str]): A股代码列表
        """
        def init_sina_if_needed():
            if self.sina_quotation is None:
                self.sina_quotation = easyquotation.use('sina')
            
        safe_call(
            init_sina_if_needed,
            exception_handler=lambda e, error_type: app_logger.error(f"初始化新浪行情引擎失败: {e}") or None
        )
        
        def fetch_sina_stocks():
            # 使用prefix=True参数批量获取A股数据，确保sh000001和sz000001等指数正确处理
            return self.sina_quotation.stocks(sina_codes, prefix=True) if self.sina_quotation else None
            
        sina_data = safe_call(
            fetch_sina_stocks,
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(f"批量获取A股数据失败: {e}") or None
        )
        
        if isinstance(sina_data, dict):
            result.update(sina_data)
            app_logger.debug(f"批量获取 {len(sina_codes)} 只A股数据成功")
        else:
            app_logger.warning("A股批量数据获取返回格式异常")
            # 如果批量获取失败，逐个获取
            for code in sina_codes:
                result[code] = self.get_stock_data(code)

    def _fetch_hk_stocks_data(self, result: dict, hk_codes: List[str]) -> None:
        """
        批量获取港股数据
        
        Args:
            result (dict): 结果字典
            hk_codes (List[str]): 港股代码列表
        """
        def init_hk_quotation():
            return easyquotation.use('hkquote')
            
        hk_quotation = safe_call(
            init_hk_quotation,
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(f"初始化港股行情引擎失败: {e}") or None
        )
        
        if not hk_quotation:
            app_logger.warning("港股行情引擎初始化失败，无法获取港股数据")
            # 如果初始化失败，逐个获取
            for code in hk_codes:
                result[code] = self.get_stock_data(code)
            return
            
        def fetch_hk_stocks():
            # 港股代码需要去掉'hk'前缀
            pure_hk_codes = [code[2:] for code in hk_codes]
            return hk_quotation.stocks(pure_hk_codes)
            
        hk_data = safe_call(
            fetch_hk_stocks,
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(f"批量获取港股数据失败: {e}") or None
        )
        
        if isinstance(hk_data, dict):
            # 将数据映射回带'hk'前缀的代码
            for pure_code, data in hk_data.items():
                result[f"hk{pure_code}"] = data
            app_logger.debug(f"批量获取 {len(hk_codes)} 只港股数据成功")
        else:
            app_logger.warning("港股批量数据获取返回格式异常")
            # 如果批量获取失败，逐个获取
            for code in hk_codes:
                result[code] = self.get_stock_data(code)

    def _get_stock_info(self, data: Dict[str, Any], code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票信息
        
        Args:
            data (Dict[str, Any]): 股票数据字典
            code (str): 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票信息或None
        """
        info = None
        # 优先使用完整代码作为键进行精确匹配，防止 sh000001 和 000001 混淆
        if isinstance(data, dict):
            info = data.get(code)  # 精确匹配完整代码
        
        # 如果没有精确匹配，尝试使用纯数字代码匹配
        if not info and isinstance(data, dict):
            # 提取纯数字代码
            pure_code = code[2:] if code.startswith(('sh', 'sz')) else code
            info = data.get(pure_code)
            
            # 特殊处理：确保上证指数和平安银行正确映射
            info = self._handle_special_stock_cases(info, pure_code, code)
        
        # 特殊处理：确保上证指数和平安银行正确映射（即使精确匹配也需处理）
        if info and isinstance(data, dict):
            # 提取纯数字代码
            pure_code = code[2:] if code.startswith(('sh', 'sz')) else code
            info = self._handle_special_stock_cases(info, pure_code, code, should_copy_data=True)
            
        return info

    def _handle_special_stock_cases(self, info: Dict[str, Any], pure_code: str, code: str, should_copy_data: bool = False) -> Optional[Dict[str, Any]]:
        """
        处理特殊情况下的股票数据（如上证指数和平安银行）
        
        Args:
            info (Dict[str, Any]): 股票信息
            pure_code (str): 纯股票代码
            code (str): 完整股票代码
            should_copy_data (bool): 是否需要复制数据以避免修改原始数据
            
        Returns:
            Optional[Dict[str, Any]]: 处理后的股票信息
        """
        if pure_code == '000001':
            # 检查是否应该显示为上证指数
            if code == 'sh000001':
                # 强制修正名称为上证指数
                info = info.copy() if should_copy_data else info  # 创建副本避免修改原始数据
                info['name'] = '上证指数'
            elif code == 'sz000001':
                # 强制修正名称为平安银行
                info = info.copy() if should_copy_data else info  # 创建副本避免修改原始数据
                info['name'] = '平安银行'
        return info

    def get_all_market_data(self) -> Optional[Dict[str, Any]]:
        """
        获取全市场股票数据
        
        Returns:
            Optional[Dict[str, Any]]: 全市场股票数据字典，失败返回None
        """
        def init_sina_if_needed():
            if self.sina_quotation is None:
                self.sina_quotation = easyquotation.use('sina')
        
        safe_call(
            init_sina_if_needed,
            exception_handler=lambda e, error_type: app_logger.error(f"初始化新浪行情引擎失败: {e}") or None
        )
        
        if not self.sina_quotation:
            return None
            
        def fetch_market_snapshot():
            # 使用market_snapshot获取更完整的市场数据（约5500+只股票）
            return self.sina_quotation.market_snapshot(prefix=True)
            
        market_data = safe_call(
            fetch_market_snapshot,
            default_return=None,
            exception_handler=lambda e, error_type: app_logger.error(f"获取全市场数据失败: {e}") or None
        )
        
        if market_data:
            app_logger.info(f"成功获取全市场数据，共 {len(market_data)} 只股票")
        else:
            app_logger.warning("获取全市场数据失败，返回空数据")
            
        return market_data
    

# 创建全局股票数据服务实例
stock_data_service = StockDataService()
