import easyquotation
import time
import requests
import json
import datetime
from typing import Dict, Any, List, Tuple, Optional
from .stocks import is_equal
from ..utils.logger import app_logger

def get_quotation_engine():
    """获取行情引擎实例"""
    try:
        engine = easyquotation.use('sina')
        app_logger.debug("行情引擎初始化成功")
        return engine
    except Exception as e:
        error_msg = f"初始化行情引擎失败: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return None

def is_market_open() -> bool:
    """检查A股是否开市"""
    now = datetime.datetime.now()
    # 检查是否为周末
    if now.weekday() >= 5:  # 周末
        app_logger.debug("当前为周末，市场关闭")
        return False
    
    # 检查是否在交易时间内
    t = now.time()
    is_open = ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
               (datetime.time(13,0) <= t <= datetime.time(15,0)))
    
    if is_open:
        app_logger.debug("市场开市中")
    else:
        app_logger.debug("市场休市中")
        
    return is_open

def process_stock_data(data: Dict[str, Any], stocks_list: List[str]) -> List[Tuple]:
    """处理股票数据，返回格式化的股票列表"""
    stocks = []
    for code in stocks_list:
        info = None
        # 优先使用完整代码作为键进行精确匹配，防止 sh000001 和 000001 混淆
        if isinstance(data, dict):
            info = data.get(code)  # 精确匹配完整代码
        
        if info:
            name = info.get('name', code)
            try:
                price = f"{float(info.get('now', 0)):.2f}"
            except (ValueError, TypeError) as e:
                app_logger.warning(f"股票 {code} 价格数据格式错误: {e}")
                price = "--"
                
            try:
                close = float(info.get('close', 0))
                now = float(info.get('now', 0))
                high = float(info.get('high', 0))
                low = float(info.get('low', 0))
                bid1 = float(info.get('bid1', 0))
                bid1_vol = float(info.get('bid1_volume', 0))
                ask1 = float(info.get('ask1', 0))
                ask1_vol = float(info.get('ask1_volume', 0))
                
                percent = ((now - close) / close * 100) if close else 0
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
                if (is_equal(str(now), str(high)) and is_equal(str(now), str(bid1)) and 
                    bid1_vol > 0 and is_equal(str(ask1), "0.0")):
                    # 将封单数转换为以"k"为单位，封单数/100000来算（万手转k）
                    seal_vol = f"{int(bid1_vol/100000)}k" if bid1_vol >= 100000 else f"{int(bid1_vol)}"
                    seal_type = 'up'
                elif (is_equal(str(now), str(low)) and is_equal(str(now), str(ask1)) and 
                      ask1_vol > 0 and is_equal(str(bid1), "0.0")):
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
            # 尝试从本地数据获取股票名称
            local_name = get_name_by_code(code)
            if local_name:
                name = local_name
            stocks.append((name, "--", "--", "#e6eaf3", "", ""))
            app_logger.warning(f"未获取到股票 {code} 的数据")
    app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
    return stocks

def get_name_by_code(code: str) -> str:
    """根据股票代码获取股票名称"""
    # 读取本地股票数据
    try:
        from ..utils.helpers import resource_path
        with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
            stock_data = json.load(f)
        for s in stock_data:
            if s['code'] == code:
                return s['name']
    except FileNotFoundError as e:
        app_logger.error(f"股票基础数据文件未找到: {e}")
    except json.JSONDecodeError as e:
        app_logger.error(f"股票基础数据文件格式错误: {e}")
    except Exception as e:
        app_logger.error(f"根据代码获取股票名称时发生错误: {e}")
    return ""