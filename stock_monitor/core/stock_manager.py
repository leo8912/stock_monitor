"""股票管理模块
负责处理股票相关的业务逻辑
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from ..utils.logger import app_logger
from ..core.stock_service import stock_data_service
from ..utils.stock_utils import StockCodeProcessor
from ..utils.helpers import is_equal

# LRU缓存大小常量
LRU_CACHE_SIZE = 128

# 添加动态调整LRU缓存大小的函数
def get_dynamic_lru_cache_size():
    """
    根据系统资源和使用情况动态调整LRU缓存大小
    在资源受限环境中减小缓存大小以节省内存
    """
    try:
        import psutil
        # 获取可用内存（GB）
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        
        # 根据可用内存动态调整缓存大小
        if available_memory_gb < 1:  # 可用内存小于1GB
            return 64
        elif available_memory_gb < 2:  # 可用内存小于2GB
            return 128
        elif available_memory_gb < 4:  # 可用内存小于4GB
            return 256
        else:  # 可用内存大于等于4GB
            return 512
    except ImportError:
        # 如果无法导入psutil，则使用默认值
        return LRU_CACHE_SIZE


class StockManager:
    """股票管理器"""
    
    def __init__(self, stock_data_service=None):
        """初始化股票管理器"""
        self._processor = StockCodeProcessor()
        # 缓存上一帧的股票数据，用于差异比较
        self._last_stock_data: Dict[str, str] = {}
        # 使用依赖注入，如果没有提供则使用全局实例
        from ..core.stock_service import stock_data_service as global_stock_data_service
        self._stock_data_service = stock_data_service or global_stock_data_service
        # 初始化动态LRU缓存
        self._init_dynamic_lru_cache()
    
    def _init_dynamic_lru_cache(self):
        """初始化动态LRU缓存"""
        # 获取动态缓存大小
        dynamic_cache_size = get_dynamic_lru_cache_size()
        
        # 定义处理股票数据的核心函数
        def process_single_stock_data_core(code: str, info_json: str) -> tuple:
            # 将JSON字符串转换回字典
            try:
                info = json.loads(info_json)
            except:
                info = {}
            return self._process_single_stock_data_impl(code, info)
        
        # 应用LRU缓存装饰器
        self._process_single_stock_data_cached = lru_cache(maxsize=dynamic_cache_size)(
            process_single_stock_data_core
        )

    def has_stock_data_changed(self, stocks: List[tuple]) -> bool:
        """
        检查股票数据是否发生变化
        
        Args:
            stocks (List[tuple]): 当前股票数据列表
            
        Returns:
            bool: 数据是否发生变化
        """
        # 如果没有缓存数据，认为发生了变化
        if not self._last_stock_data:
            return True
            
        # 比较每只股票的数据
        for stock in stocks:
            name, price, change, color, seal_vol, seal_type = stock
            key = f"{name}_{price}_{change}_{color}_{seal_vol}_{seal_type}"
            
            # 如果这只股票之前没有数据，认为发生了变化
            if name not in self._last_stock_data:
                return True
                
            # 如果数据不匹配，认为发生了变化
            if self._last_stock_data[name] != key:
                return True
                
        # 检查是否有股票被移除
        current_names = [stock[0] for stock in stocks]
        for name in self._last_stock_data.keys():
            if name not in current_names:
                return True
                
        # 数据没有变化
        return False
    
    def update_last_stock_data(self, stocks: List[tuple]) -> None:
        """
        更新最后股票数据缓存
        
        Args:
            stocks (List[tuple]): 当前股票数据列表
        """
        self._last_stock_data.clear()
        for stock in stocks:
            name, price, change, color, seal_vol, seal_type = stock
            key = f"{name}_{price}_{change}_{color}_{seal_vol}_{seal_type}"
            self._last_stock_data[name] = key
            
        app_logger.debug(f"更新股票数据缓存，共{len(self._last_stock_data)}只股票")
        
    def fetch_and_process_stocks(self, stock_codes: List[str]) -> Tuple[List[tuple], int]:
        """
        获取并处理股票数据
        
        Args:
            stock_codes (List[str]): 股票代码列表
            
        Returns:
            Tuple[List[tuple], int]: (格式化后的股票数据列表, 失败数量)
        """
        # 使用依赖注入的服务获取所有股票数据
        data_dict = self._stock_data_service.get_multiple_stocks_data(stock_codes)
        
        # 计算失败数量 (值为None的)
        failed_count = sum(1 for data in data_dict.values() if data is None)
        
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
        return stocks, failed_count
    
    def get_stock_list_data(self, stock_codes: List[str]) -> List[tuple]:
        """
        获取股票列表数据
        
        Args:
            stock_codes (List[str]): 股票代码列表
            
        Returns:
            List[tuple]: 格式化后的股票数据列表
        """
        stocks, _ = self.fetch_and_process_stocks(stock_codes)
        return stocks
    
    
    def get_all_market_data(self) -> Dict[str, Any]:
        """
        获取全市场数据
        
        Returns:
            Dict[str, Any]: 全市场数据字典
        """
        return self._stock_data_service.get_all_market_data()

    def _process_single_stock_data_impl(self, code: str, info: Dict[str, Any]) -> tuple:
        """
        处理单只股票的数据的实际实现
        
        Args:
            code (str): 股票代码
            info (Dict[str, Any]): 股票原始数据
            
        Returns:
            tuple: 格式化后的股票数据元组
        """
        from ..core.processor import stock_processor
        result = stock_processor.process_raw_data(code, info)
        app_logger.debug(f"股票 {code} 数据处理完成")
        return result
    
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

# 创建全局股票管理器实例
stock_manager = StockManager()