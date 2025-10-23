import json
from typing import List, Dict, Any, Tuple, Optional
from ..utils.helpers import resource_path
from ..utils.logger import app_logger

def load_stock_data() -> List[Dict[str, Any]]:
    """加载股票基础数据"""
    try:
        with open(resource_path("stock_basic.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            app_logger.debug(f"股票基础数据加载成功，共{len(data)}条记录")
            return data
    except FileNotFoundError as e:
        error_msg = f"股票基础数据文件未找到: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return []
    except json.JSONDecodeError as e:
        error_msg = f"股票基础数据文件格式错误: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return []
    except Exception as e:
        error_msg = f"加载股票基础数据时发生未知错误: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return []

def enrich_pinyin(stock_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """丰富股票的拼音信息"""
    try:
        # 延迟导入pypinyin，减少启动时间
        from pypinyin import lazy_pinyin, Style
        
        for s in stock_list:
            name = s['name']
            # 去除*ST、ST等前缀
            base = name.replace('*', '').replace('ST', '').replace(' ', '')
            # 全拼
            full_pinyin = ''.join(lazy_pinyin(base))
            # 首字母
            abbr = ''.join(lazy_pinyin(base, style=Style.FIRST_LETTER))
            s['pinyin'] = full_pinyin.lower()
            s['abbr'] = abbr.lower()
        app_logger.debug(f"股票拼音信息处理完成，共处理{len(stock_list)}条记录")
        return stock_list
    except ImportError as e:
        error_msg = f"pypinyin库未安装: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return stock_list
    except Exception as e:
        error_msg = f"处理股票拼音信息时发生错误: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return stock_list

def is_equal(a: str, b: str, tol: float = 0.01) -> bool:
    """比较两个字符串数值是否近似相等"""
    try:
        return abs(float(a) - float(b)) < tol
    except Exception as e:
        app_logger.debug(f"数值比较失败 ({a}, {b}): {e}")
        return False

def format_stock_code(code: str) -> Optional[str]:
    """格式化股票代码，确保正确的前缀"""
    if not isinstance(code, str) or not code:
        app_logger.debug(f"无效的股票代码输入: {code}")
        return None
        
    code = code.strip().lower()
    
    # 移除可能存在的额外字符
    code = ''.join(c for c in code if c.isalnum())
    
    if not code:
        app_logger.debug("股票代码处理后为空")
        return None
        
    # 检查是否已经有正确前缀
    if code.startswith('sh') or code.startswith('sz'):
        # 验证代码长度和数字部分
        if len(code) == 8 and code[2:].isdigit():
            return code
        else:
            app_logger.debug(f"股票代码格式不正确: {code}")
            return None
            
    # 6位纯数字代码
    elif len(code) == 6 and code.isdigit():
        if code.startswith('6') or code.startswith('5'):
            return 'sh' + code
        elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
            return 'sz' + code
        else:
            app_logger.debug(f"未知交易所的6位数字代码: {code}")
            return None
    
    # 其他情况返回None
    app_logger.debug(f"无法识别的股票代码格式: {code}")
    return None