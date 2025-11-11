"""
股票管理模块
负责处理股票相关的业务逻辑
"""

from typing import List, Dict, Any, Optional
from ..utils.logger import app_logger
from ..core.stock_service import stock_data_service


class StockManager:
    """股票管理器"""
    
    def __init__(self):
        """初始化股票管理器"""
        self._last_stock_data: Dict[str, str] = {}
    
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
        
    def get_stock_list_data(self, stock_codes: List[str]) -> List[tuple]:
        """
        获取股票列表数据
        
        Args:
            stock_codes (List[str]): 股票代码列表
            
        Returns:
            List[tuple]: 格式化后的股票数据列表
        """
        # 获取所有股票数据
        data_dict = stock_data_service.get_multiple_stocks_data(stock_codes)
        
        # 处理股票数据
        stocks = []
        for code in stock_codes:
            info = data_dict.get(code)
            
            if info:
                name = info.get('name', code)
                # 对于港股，只保留中文部分
                if code.startswith('hk'):
                    # 去除"-"及之后的部分，只保留中文名称
                    if '-' in name:
                        name = name.split('-')[0].strip()
                
                try:
                    # 不同行情源的字段可能不同
                    now = info.get('now') or info.get('price')
                    close = info.get('close') or info.get('lastPrice') or now
                    high = info.get('high', 0)
                    low = info.get('low', 0)
                    bid1 = info.get('bid1', 0)
                    bid1_vol = info.get('bid1_volume', 0) or info.get('volume_2', 0)
                    ask1 = info.get('ask1', 0)
                    ask1_vol = info.get('bid1_volume', 0) or info.get('volume_3', 0)
                    
                    # 添加更严格的None值检查
                    if now is None or close is None:
                        app_logger.warning(f"股票 {code} 数据不完整: now={now}, close={close}")
                        stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                        continue
                        
                    # 检查数据是否有效（防止获取到空字符串等无效数据）
                    try:
                        float(now)
                        float(close)
                    except (ValueError, TypeError):
                        app_logger.warning(f"股票 {code} 数据无效: now={now}, close={close}")
                        stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                        continue
                        
                    price = f"{float(now):.2f}" if now is not None else "--"
                    
                    percent = ((float(now) - float(close)) / float(close) * 100) if close and float(close) != 0 else 0
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
                except (ValueError, TypeError, ZeroDivisionError) as e:
                    app_logger.warning(f"股票 {code} 数据计算错误: {e}")
                    color = '#e6eaf3'
                    change_str = "--"
                    price = "--"
                    # 为后续处理设置默认值
                    now = 0
                    high = 0
                    low = 0
                    bid1 = 0
                    ask1 = 0
                    bid1_vol = 0
                    ask1_vol = 0
                
                # 检测涨停/跌停封单
                seal_vol = ''
                seal_type = ''
                try:
                    # 确保所有值都不是None
                    if (now is not None and high is not None and bid1 is not None and 
                        bid1_vol is not None and ask1 is not None and
                        str(now) == str(high) and str(now) == str(bid1) and 
                        bid1_vol > 0 and str(ask1) == "0.0"):
                        # 将封单数转换为以"k"为单位，封单数/100000来算（万手转k）
                        seal_vol = f"{int(bid1_vol/100000)}k" if bid1_vol >= 100000 else f"{int(bid1_vol)}"
                        seal_type = 'up'
                    elif (now is not None and low is not None and ask1 is not None and 
                          ask1_vol is not None and bid1 is not None and
                          str(now) == str(low) and str(now) == str(ask1) and 
                          ask1_vol > 0 and str(bid1) == "0.0"):
                        # 将封单数转换为以"k"为单位，封单数/100000来算（万手转k）
                        seal_vol = f"{int(ask1_vol/100000)}k" if ask1_vol >= 100000 else f"{int(ask1_vol)}"
                        seal_type = 'down'
                except (ValueError, TypeError) as e:
                    app_logger.debug(f"股票 {code} 封单计算错误: {e}")
                    pass  # 忽略封单计算中的错误
                    
                stocks.append((name, price, change_str, color, seal_vol, seal_type))
                app_logger.debug(f"股票 {code} 数据处理完成")
            else:
                # 如果没有获取到数据，显示默认值
                name = code
                stocks.append((name, "--", "--", "#e6eaf3", "", ""))
                app_logger.warning(f"未获取到股票 {code} 的数据")
                
        app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
        return stocks


# 创建全局股票管理器实例
stock_manager = StockManager()