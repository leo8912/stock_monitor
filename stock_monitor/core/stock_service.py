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
        stocks = []
        
        for code in stocks_list:
            info = self._get_stock_info(data, code)
            
            if info:
                name = info.get('name', code)
                # 对于港股，只保留中文部分
                name = self._format_hk_stock_name(name, code)
                
                # 处理股票价格和涨跌幅信息
                price_info = self._process_price_info(info, code)
                if not price_info:
                    stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                    continue
                    
                price, change_str, color = price_info
                
                # 检测涨停/跌停封单
                seal_vol, seal_type = self._detect_limit_info(info, code, price)
                    
                stocks.append((name, price, change_str, color, seal_vol, seal_type))
                app_logger.debug(f"股票 {code} 数据处理完成")
            else:
                # 如果没有获取到数据，显示默认值
                name = code
                # 尝试从本地数据获取股票名称
                local_name = get_name_by_code(code)
                if local_name:
                    name = local_name
                    # 对于港股，只保留中文部分
                    name = self._format_hk_stock_name(name, code)
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

    def _fetch_stock_data_with_retry(self, quotation_engine, code: str) -> Optional[Dict[str, Any]]:
        """
        带重试机制获取股票数据
        
        Args:
            quotation_engine: 行情引擎
            code (str): 股票代码
            
        Returns:
            Optional[Dict[str, Any]]: 股票数据或None
        """
        # 统一使用带前缀的代码查询，避免代码混淆
        # 特别是对于sh000001和sz000001这样的同数字代码
        query_code = code[2:] if code.startswith(('sh', 'sz', 'hk')) else code
        
        if code.startswith(('sh', 'sz')):
            # 对于A股带前缀的代码，直接使用prefix=True参数查询
            single = quotation_engine.stocks(code, prefix=True)
            # 直接使用完整代码作为键获取数据
            stock_data = single if isinstance(single, dict) and code in single else None
        elif code.startswith('hk'):
            # 对于港股代码，移除前缀进行查询
            single = quotation_engine.stocks(query_code)
            # 检查返回数据是否有效
            if isinstance(single, dict):
                # 确保返回的数据不是None且是完整的
                stock_data = single
            else:
                stock_data = None
        else:
            # 对于不带前缀的代码，使用纯代码查询
            single = quotation_engine.stocks(query_code)
            # 检查返回数据是否有效
            if isinstance(single, dict):
                # 确保返回的数据不是None且是完整的
                stock_data = single
            else:
                stock_data = None
        
        if stock_data is not None:
            return stock_data
        
        # 添加重试机制
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if code.startswith(('sh', 'sz')):
                    # 对于A股带前缀的代码，直接使用prefix=True参数查询
                    single = quotation_engine.stocks(code, prefix=True)
                    stock_data = single if isinstance(single, dict) and code in single else None
                elif code.startswith('hk'):
                    # 对于港股代码，移除前缀进行查询
                    single = quotation_engine.stocks(query_code)
                    if isinstance(single, dict):
                        stock_data = single
                    else:
                        stock_data = None
                else:
                    single = quotation_engine.stocks(query_code)
                    if isinstance(single, dict):
                        stock_data = single
                    else:
                        stock_data = None
                
                if stock_data is not None:
                    return stock_data
                retry_count += 1
                app_logger.debug(f"获取 {code} 数据失败或不完整，第 {retry_count} 次重试")
                if retry_count < max_retries:
                    time.sleep(2)
            except Exception as e:
                retry_count += 1
                app_logger.debug(f"获取 {code} 数据异常: {e}，第 {retry_count} 次重试")
                if retry_count < max_retries:
                    time.sleep(2)
                    
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
            info = self._handle_special_stock_cases(info, pure_code, code, copy_required=True)
            
        return info

    def _handle_special_stock_cases(self, info: Dict[str, Any], pure_code: str, code: str, copy_required: bool = False) -> Optional[Dict[str, Any]]:
        """
        处理特殊情况下的股票数据（如上证指数和平安银行）
        
        Args:
            info (Dict[str, Any]): 股票信息
            pure_code (str): 纯股票代码
            code (str): 完整股票代码
            copy_required (bool): 是否需要复制数据
            
        Returns:
            Optional[Dict[str, Any]]: 处理后的股票信息
        """
        if pure_code == '000001':
            # 检查是否应该显示为上证指数
            if code == 'sh000001':
                # 强制修正名称为上证指数
                info = info.copy() if copy_required else info  # 创建副本避免修改原始数据
                info['name'] = '上证指数'
            elif code == 'sz000001':
                # 强制修正名称为平安银行
                info = info.copy() if copy_required else info  # 创建副本避免修改原始数据
                info['name'] = '平安银行'
        return info

    def _format_hk_stock_name(self, name: str, code: str) -> str:
        """
        格式化港股名称显示
        
        Args:
            name (str): 原始名称
            code (str): 股票代码
            
        Returns:
            str: 格式化后的名称
        """
        if code.startswith('hk'):
            # 去除"-"及之后的部分，只保留中文名称
            if '-' in name:
                name = name.split('-')[0].strip()
        return name
    
    def _validate_price_data(self, code: str, now: Any, close: Any) -> bool:
        """
        验证价格数据的有效性
        
        Args:
            code (str): 股票代码
            now: 当前价格
            close: 收盘价格
            
        Returns:
            bool: 数据是否有效
        """
        # 添加更严格的None值检查
        if now is None or close is None:
            app_logger.warning(f"股票 {code} 数据不完整: now={now}, close={close}")
            return False
            
        # 检查数据是否有效（防止获取到空字符串等无效数据）
        try:
            float(now)
            float(close)
            return True
        except (ValueError, TypeError):
            app_logger.warning(f"股票 {code} 数据无效: now={now}, close={close}")
            return False
    
    def _calculate_price_change(self, now: float, close: float) -> Tuple[str, str, str]:
        """
        计算价格变化和颜色
        
        Args:
            now (float): 当前价格
            close (float): 收盘价格
            
        Returns:
            Tuple[str, str, str]: 价格、变化百分比和颜色
        """
        price = f"{now:.2f}"
        percent = ((now - close) / close * 100) if close != 0 else 0
        
        # 修改颜色逻辑：超过5%的涨幅使用亮红色
        if percent >= 5:
            color = '#FF4500'  # 亮红色（更亮的红色）
        elif percent > 0:
            color = '#e74c3f'  # 红色
        elif percent < 0:
            color = '#27ae60'  # 绿色
        else:
            color = '#e6eaf3'  # 平盘
            
        change_str = f"{percent:+.2f}%"
        return price, change_str, color
    
    def _extract_price_data(self, code: str, info: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
        """
        提取并处理价格数据
        
        Args:
            code (str): 股票代码
            info (Dict[str, Any]): 股票原始数据
            
        Returns:
            Optional[Tuple[str, str, str]]: 价格、变化百分比和颜色，如果数据无效则返回None
        """
        try:
            # 不同行情源的字段可能不同
            now = info.get('now') or info.get('price')
            close = info.get('close') or info.get('lastPrice') or now
            
            # 验证价格数据
            if not self._validate_price_data(code, now, close):
                return None
                
            return self._calculate_price_change(float(now), float(close))
        except (ValueError, TypeError, ZeroDivisionError) as e:
            app_logger.warning(f"股票 {code} 数据计算错误: {e}")
            return None
    
    def _process_price_info(self, info: Dict[str, Any], code: str) -> Optional[Tuple[str, str, str]]:
        """
        处理股票价格和涨跌幅信息
        
        Args:
            info (Dict[str, Any]): 股票信息
            code (str): 股票代码
            
        Returns:
            Optional[Tuple[str, str, str]]: 价格、涨跌幅和颜色的元组，处理失败时返回None
        """
        price_data = self._extract_price_data(code, info)
        
        if price_data is None:
            return "--", "--", "#e6eaf3"
            
        return price_data
    
    def _detect_limit_info(self, info: Dict[str, Any], code: str, price: str) -> Tuple[str, str]:
        """
        检测涨停/跌停封单信息
        
        Args:
            info (Dict[str, Any]): 股票信息
            code (str): 股票代码
            price (str): 当前价格
            
        Returns:
            Tuple[str, str]: 封单量和封单类型
        """
        seal_vol = ''
        seal_type = ''
        
        try:
            # 获取相关信息
            now = info.get('now') or info.get('price')
            high = info.get('high', 0)
            low = info.get('low', 0)
            bid1 = info.get('bid1', 0)
            bid1_vol = info.get('bid1_volume', 0) or info.get('volume_2', 0)
            ask1 = info.get('ask1', 0)
            ask1_vol = info.get('ask1_volume', 0) or info.get('volume_3', 0)
            
            # 确保所有值都不是None
            if (now is not None and high is not None and bid1 is not None and 
                bid1_vol is not None and ask1 is not None and
                is_equal(str(now), str(high)) and is_equal(str(now), str(bid1)) and 
                bid1_vol > 0 and is_equal(str(ask1), "0.0")):
                # 将封单数转换为以"k"为单位，封单数/100000来算（万手转k）
                seal_vol = f"{int(bid1_vol/100000)}k" if bid1_vol >= 100000 else f"{int(bid1_vol)}"
                seal_type = 'up'
            elif (now is not None and low is not None and ask1 is not None and 
                  ask1_vol is not None and bid1 is not None and
                  is_equal(str(now), str(low)) and is_equal(str(now), str(ask1)) and 
                  ask1_vol > 0 and is_equal(str(bid1), "0.0")):
                # 将封单数转换为以"k"为单位，封单数/100000来算（万手转k）
                seal_vol = f"{int(ask1_vol/100000)}k" if ask1_vol >= 100000 else f"{int(ask1_vol)}"
                seal_type = 'down'
        except (ValueError, TypeError) as e:
            app_logger.debug(f"股票 {code} 封单计算错误: {e}")
            # 忽略封单计算中的错误
            
        return seal_vol, seal_type

# 创建全局股票数据服务实例
stock_data_service = StockDataService()