"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 stock_basic.json 文件
"""

import json
import os
import threading
import time
from typing import List, Dict
from ..utils.logger import app_logger
from typing import Any, Union
from ..utils.helpers import resource_path
from ..utils.cache import global_cache


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
                            # 特殊处理：确保上证指数正确映射
                            name = data[pure_code]['name']
                            if pure_code == '000001':
                                # 根据前缀确定正确的名称
                                if code.startswith('sh'):
                                    name = '上证指数'
                                elif code.startswith('sz'):
                                    name = '平安银行'
                                    
                            stocks_data.append({
                                'code': code,
                                'name': name
                            })
            except Exception as e:
                app_logger.warning(f"获取批次股票数据失败: {e}")
                continue
        
        # 添加主要指数数据
        try:
            index_data: Union[Dict[str, Any], None] = quotation.stocks(['sh000001', 'sh000002', 'sh000300', 'sz399001', 'sz399006'], prefix=True)
            if index_data:
                for code, info in index_data.items():
                    if info and 'name' in info:
                        stocks_data.append({
                            'code': code,
                            'name': info['name']
                        })
        except Exception as e:
            app_logger.warning(f"获取指数数据失败: {e}")
        
        # 去重处理，确保每个代码只出现一次
        unique_stocks = {}
        for stock in stocks_data:
            code = stock['code']
            # 对于重复的代码，优先保留指数类的
            if code in unique_stocks:
                # 如果已存在的不是指数而当前是指数，则替换
                existing_name = unique_stocks[code]['name']
                current_name = stock['name']
                # 特殊处理：确保上证指数和Ａ股指数优先
                if (code == 'sh000001' and current_name == '上证指数') or \
                   (code == 'sh000002' and 'Ａ股' in current_name) or \
                   (code == 'sz000002' and current_name == '万科Ａ'):
                    unique_stocks[code] = stock
                elif ('指数' in current_name and '指数' not in existing_name) or \
                     ('Ａ股' in current_name and 'Ａ股' not in existing_name):
                    unique_stocks[code] = stock
            else:
                unique_stocks[code] = stock
        
        stocks_data = list(unique_stocks.values())
        
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
        
        # 直接使用网络数据覆盖本地文件，去除所有手动修改
        stock_file_path = resource_path("stock_basic.json")
        with open(stock_file_path, 'w', encoding='utf-8') as f:
            json.dump(stocks_data, f, ensure_ascii=False, indent=2)
        
        app_logger.info(f"股票数据库更新完成，共 {len(stocks_data)} 只股票，已清除所有本地手动修改")
        return True
        
    except Exception as e:
        app_logger.error(f"更新股票数据库失败: {e}")
        return False


def get_stock_list() -> List[Dict[str, str]]:
    """
    获取股票列表，完全从本地文件读取
    
    Returns:
        List[Dict[str, str]]: 股票列表
    """
    try:
        stock_file_path = resource_path("stock_basic.json")
        with open(stock_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        app_logger.error(f"无法从本地文件加载股票数据: {e}")
        # 返回空列表而不是从网络获取
        return []


def preload_popular_stocks_data() -> None:
    """
    预加载热门股票数据到缓存中
    这个函数会在市场开盘前运行，预热缓存
    """
    try:
        app_logger.info("开始预加载热门股票数据...")
        
        # 热门股票列表（包括主要指数和一些热门个股）
        popular_stocks = [
            'sh000001',  # 上证指数
            'sz399001',  # 深证成指
            'sh000300',  # 沪深300
            'sz399006',  # 创业板指
            'sh600036',  # 招商银行
            'sh600519',  # 贵州茅台
            'sh600030',  # 中信证券
            'sz000001',  # 平安银行
            'sz000002',  # 万科A
            'sz000858',  # 五粮液
            'sh600460',  # 士兰微
            'sh603986',  # 兆易创新
        ]
        
        import easyquotation
        quotation = easyquotation.use('sina')
        
        # 获取热门股票数据并存入缓存
        for stock_code in popular_stocks:
            try:
                # 移除前缀获取纯代码
                pure_code = stock_code[2:] if stock_code.startswith(('sh', 'sz')) else stock_code
                
                # 获取股票数据
                data = quotation.real([pure_code])
                if data:
                    # 存入缓存，设置较长的TTL（1小时）
                    global_cache.set(f"stock_{stock_code}", data, ttl=3600)
                    app_logger.debug(f"预加载股票数据到缓存: {stock_code}")
                    
            except Exception as e:
                app_logger.warning(f"预加载股票 {stock_code} 数据失败: {e}")
                continue
        
        app_logger.info("热门股票数据预加载完成")
        
    except Exception as e:
        app_logger.error(f"预加载热门股票数据时出错: {e}")


def start_preload_scheduler() -> None:
    """
    启动预加载调度器
    在市场开盘前（9:25）自动预加载热门股票数据
    """
    def scheduler():
        while True:
            try:
                import datetime
                
                # 获取当前时间
                now = datetime.datetime.now()
                # 计算下次预加载时间（今天或明天的9:25）
                next_preload = now.replace(hour=9, minute=25, second=0, microsecond=0)
                if now >= next_preload:
                    # 如果当前时间已经超过今天的9:25，则设置为明天的9:25
                    next_preload += datetime.timedelta(days=1)
                
                # 计算睡眠时间
                sleep_seconds = (next_preload - now).total_seconds()
                app_logger.info(f"预加载调度器: 下次预加载将在 {next_preload} 执行，睡眠 {sleep_seconds} 秒")
                
                # 睡眠直到下次预加载时间
                time.sleep(sleep_seconds)
                
                # 执行预加载
                preload_popular_stocks_data()
                
            except Exception as e:
                app_logger.error(f"预加载调度器出错: {e}")
                # 出错时等待1小时再重试
                time.sleep(3600)
    
    # 在独立线程中运行调度器
    scheduler_thread = threading.Thread(target=scheduler, daemon=True)
    scheduler_thread.start()
    app_logger.info("预加载调度器已启动")


if __name__ == "__main__":
    # 测试更新功能
    success = update_stock_database()
    if success:
        print("股票数据库更新成功")
    else:
        print("股票数据库更新失败")