"""
行情数据处理模块
用于获取和处理股票行情数据

该模块包含获取行情数据、处理行情数据等功能。
"""


def get_quotation_engine(market_type='sina'):
    """获取行情引擎实例"""
    try:
        engine = easyquotation.use(market_type)
        app_logger.debug(f"行情引擎初始化成功: {market_type}")
        return engine
    except Exception as e:
        error_msg = f"初始化行情引擎失败: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return None

def is_market_open() -> bool:
    """检查A股是否开市"""
    # 复用config/manager.py中的实现
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
            (datetime.time(13,0) <= t <= datetime.time(15,0)))
import easyquotation
import json
import datetime
from typing import Dict, Any, List, Tuple, Optional
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.helpers import resource_path, is_equal


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
                # 对于港股，只保留中文部分
                if code.startswith('hk'):
                    # 去除"-"及之后的部分，只保留中文名称
                    if '-' in name:
                        name = name.split('-')[0].strip()
            stocks.append((name, "--", "--", "#e6eaf3", "", ""))
            app_logger.warning(f"未获取到股票 {code} 的数据")
    app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
    return stocks

def get_name_by_code(code: str) -> str:
    """根据股票代码获取股票名称"""
    # 读取本地股票数据
    try:
        with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
            stock_data = json.load(f)
        for s in stock_data:
            if s['code'] == code:
                name = s['name']
                # 对于港股，只保留中文部分
                if code.startswith('hk'):
                    # 去除"-"及之后的部分，只保留中文名称
                    if '-' in name:
                        name = name.split('-')[0].strip()
                return name
    except FileNotFoundError as e:
        app_logger.error(f"股票基础数据文件未找到: {e}")
    except json.JSONDecodeError as e:
        app_logger.error(f"股票基础数据文件格式错误: {e}")
    except Exception as e:
        app_logger.error(f"根据代码获取股票名称时发生错误: {e}")
    return ""


def get_stock_info_by_code(code: str) -> Optional[Dict[str, str]]:
    """根据股票代码获取股票完整信息"""
    # 读取本地股票数据
    try:
        with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
            stock_data = json.load(f)
        for s in stock_data:
            if s['code'] == code:
                # 对于港股，只保留中文部分
                if code.startswith('hk') and '-' in s['name']:
                    s['name'] = s['name'].split('-')[0].strip()
                return s
    except FileNotFoundError as e:
        app_logger.error(f"股票基础数据文件未找到: {e}")
    except json.JSONDecodeError as e:
        app_logger.error(f"股票基础数据文件格式错误: {e}")
    except Exception as e:
        app_logger.error(f"根据代码获取股票信息时发生错误: {e}")
    return None
