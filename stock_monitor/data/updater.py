"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 stock_basic.json 文件
"""

import json
import os
from typing import List, Dict
from ..utils.logger import app_logger


def resource_path(relative_path):
    """获取资源文件路径，兼容PyInstaller打包和源码运行"""
    import sys
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # 基于当前文件的目录定位resources文件夹
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resources_dir = os.path.join(current_dir, 'resources')
    return os.path.join(resources_dir, relative_path)


def fetch_all_stocks() -> List[Dict[str, str]]:
    """
    从网络获取所有A股股票数据
    
    Returns:
        List[Dict[str, str]]: 股票列表，每个元素包含code和name字段
    """
    try:
        import easyquotation
        
        # 使用easyquotation获取股票列表
        quotation = easyquotation.use('sina')
        
        # 获取所有股票代码列表
        stock_codes_str = quotation.stock_list
        # 解析股票代码字符串
        all_stock_codes = []
        for item in stock_codes_str:
            codes = item.split(',')
            all_stock_codes.extend(codes)
        
        # 分批获取股票数据，避免一次性请求过多
        batch_size = 50
        stocks_data = []
        
        for i in range(0, len(all_stock_codes), batch_size):
            batch_codes = all_stock_codes[i:i+batch_size]
            # 移除前缀获取纯代码用于查询
            pure_codes = [code[2:] if code.startswith(('sh', 'sz')) else code for code in batch_codes]
            
            try:
                # 获取股票详细数据
                data = quotation.stocks(pure_codes)
                if data:
                    for j, code in enumerate(batch_codes):
                        pure_code = pure_codes[j]
                        if pure_code in data and data[pure_code] and 'name' in data[pure_code]:
                            stocks_data.append({
                                'code': code,
                                'name': data[pure_code]['name']
                            })
            except Exception as e:
                app_logger.warning(f"获取批次股票数据失败: {e}")
                continue
        
        app_logger.info(f"成功获取 {len(stocks_data)} 只股票数据")
        return stocks_data
        
    except Exception as e:
        app_logger.error(f"获取股票数据失败: {e}")
        return []


def update_stock_database() -> bool:
    """
    更新本地股票数据库文件
    
    Returns:
        bool: 更新是否成功
    """
    try:
        # 获取最新的股票数据
        stocks_data = fetch_all_stocks()
        
        if not stocks_data:
            app_logger.warning("未获取到股票数据，取消更新")
            return False
        
        # 按代码排序
        stocks_data.sort(key=lambda x: x['code'])
        
        # 写入文件
        stock_file_path = resource_path("stock_basic.json")
        with open(stock_file_path, 'w', encoding='utf-8') as f:
            json.dump(stocks_data, f, ensure_ascii=False, indent=2)
        
        app_logger.info(f"股票数据库更新完成，共 {len(stocks_data)} 只股票")
        return True
        
    except Exception as e:
        app_logger.error(f"更新股票数据库失败: {e}")
        return False


def get_stock_list() -> List[Dict[str, str]]:
    """
    获取股票列表，优先从本地文件读取，如果失败则从网络获取
    
    Returns:
        List[Dict[str, str]]: 股票列表
    """
    try:
        stock_file_path = resource_path("stock_basic.json")
        with open(stock_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        app_logger.warning(f"无法从本地文件加载股票数据: {e}，尝试从网络获取")
        return fetch_all_stocks()


if __name__ == "__main__":
    # 测试更新功能
    success = update_stock_database()
    if success:
        print("股票数据库更新成功")
    else:
        print("股票数据库更新失败")