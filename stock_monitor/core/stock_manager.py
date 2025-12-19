"""股票管理模块
负责处理股票相关的业务逻辑
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from ..utils.logger import app_logger
from ..core.stock_service import stock_data_service
from ..utils.stock_utils import StockCodeProcessor
from ..core.data_change_detector import DataChangeDetector
from ..utils.helpers import is_equal

# LRU缓存大小常量
LRU_CACHE_SIZE = 128


class StockManager:
    """股票管理器"""
    
    def __init__(self):
        """初始化股票管理器"""
        self._processor = StockCodeProcessor()
        self._data_change_detector = DataChangeDetector()
    
    def has_stock_data_changed(self, stocks: List[tuple]) -> bool:
        """
        检查股票数据是否发生变化
        
        Args:
            stocks (List[tuple]): 当前股票数据列表
            
        Returns:
            bool: 数据是否发生变化
        """
        return self._data_change_detector.has_stock_data_changed(stocks)
    
    def update_last_stock_data(self, stocks: List[tuple]) -> None:
        """
        更新最后股票数据缓存
        
        Args:
            stocks (List[tuple]): 当前股票数据列表
        """
        self._data_change_detector.update_last_stock_data(stocks)
        
    def get_stock_list_data(self, stock_codes: List[str]) -> List[tuple]:
        """
        获取股票列表数据
        
        Args:
            stock_codes (List[str]): 股票代码列表
            
        Returns:
            List[tuple]: 格式化后的股票数据列表
        """
        # 使用批量获取方式获取所有股票数据
        data_dict = stock_data_service.get_multiple_stocks_data(stock_codes)
        
        # 处理股票数据
        stocks = []
        for code in stock_codes:
            info = data_dict.get(code)
            
            if info:
                # 使用带缓存的方法处理单只股票数据
                stock_item = self._process_single_stock_data_cached(code, json.dumps(info, sort_keys=True))
                stocks.append(stock_item)
            else:
                # 如果没有获取到数据，显示默认值
                name = code
                stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                app_logger.warning(f"未获取到股票 {code} 的数据")
                
        app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
        return stocks
    
    @lru_cache(maxsize=LRU_CACHE_SIZE)
    def _process_single_stock_data_cached(self, code: str, info_json: str) -> tuple:
        """
        带LRU缓存的单只股票数据处理方法
        
        Args:
            code (str): 股票代码
            info_json (str): 股票数据的JSON序列化字符串
            
        Returns:
            tuple: 格式化后的股票数据元组
        """
        # 将JSON字符串转换回字典
        try:
            info = json.loads(info_json)
        except:
            info = {}
        
        return self._process_single_stock_data_impl(code, info)
    
    def _process_single_stock_data_impl(self, code: str, info: Dict[str, Any]) -> tuple:
        """
        处理单只股票的数据的实际实现
        
        Args:
            code (str): 股票代码
            info (Dict[str, Any]): 股票原始数据
            
        Returns:
            tuple: 格式化后的股票数据元组
        """
        name = self._extract_stock_name(code, info)
        price_data = self._extract_price_data(code, info)
        
        if price_data is None:
            # 数据不完整或无效
            return (name, "--", "--", "#e6eaf3", "", "")
        
        price, change_str, color = price_data
        seal_vol, seal_type = self._calculate_seal_info(**self._extract_seal_calculation_params(info))
            
        stock_item = (name, price, change_str, color, seal_vol, seal_type)
        app_logger.debug(f"股票 {code} 数据处理完成")
        return stock_item
    
    def _process_single_stock_data(self, code: str, info: Dict[str, Any]) -> tuple:
        """
        处理单只股票的数据
        
        Args:
            code (str): 股票代码
            info (Dict[str, Any]): 股票原始数据
            
        Returns:
            tuple: 格式化后的股票数据元组
        """
        return self._process_single_stock_data_impl(code, info)
    
    def _calculate_seal_info(self, now: Any, high: Any, low: Any, bid1: Any, ask1: Any, 
                             bid1_vol: Any, ask1_vol: Any) -> Tuple[str, str]:
        """
        计算股票的封单信息（涨停/跌停封单量）
        
        Args:
            now: 当前价格
            high: 最高价
            low: 最低价
            bid1: 买一价
            ask1: 卖一价
            bid1_vol: 买一量
            ask1_vol: 卖一量
            
        Returns:
            Tuple[str, str]: 封单量和封单类型
        """
        seal_vol = ''
        seal_type = ''
        try:
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
            app_logger.debug(f"封单计算错误: {e}")
            pass  # 忽略封单计算中的错误
            
        return seal_vol, seal_type
    
    def _extract_stock_name(self, code: str, info: Dict[str, Any]) -> str:
        """
        提取并格式化股票名称
        
        Args:
            code (str): 股票代码
            info (Dict[str, Any]): 股票原始数据
            
        Returns:
            str: 格式化后的股票名称
        """
        name = info.get('name', code)
        # 对于港股，只保留中文部分
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
    
    def _extract_seal_calculation_params(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取封单计算所需参数
        
        Args:
            info (Dict[str, Any]): 股票原始数据
            
        Returns:
            Dict[str, Any]: 封单计算参数
        """
        return {
            'now': info.get('now') or info.get('price'),
            'high': info.get('high', 0),
            'low': info.get('low', 0),
            'bid1': info.get('bid1', 0),
            'ask1': info.get('ask1', 0),
            'bid1_vol': info.get('bid1_volume', 0) or info.get('volume_2', 0),
            'ask1_vol': info.get('ask1_volume', 0) or info.get('volume_3', 0)
        }

# 创建全局股票管理器实例
stock_manager = StockManager()