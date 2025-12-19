"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 SQLite 数据库
"""
import json
import threading
import time
import os
from typing import List, Dict
from stock_monitor.utils.logger import app_logger
from typing import Any, Union
from stock_monitor.utils.helpers import resource_path
from stock_monitor.utils.cache import global_cache
import requests
import io
import pandas as pd

# 安全导入zhconv，如果失败则提供一个空的convert函数
try:
    from zhconv import convert
except ImportError:
    app_logger.warning("无法导入zhconv库，将使用原样返回的替代函数")
    def convert(s, locale, update=None):  # type: ignore
        return s
except Exception as e:
    app_logger.warning(f"导入zhconv库时发生异常: {e}，将使用原样返回的替代函数")
    def convert(s, locale, update=None):  # type: ignore
        return s

import easyquotation


def fetch_hk_stocks() -> List[Dict[str, str]]:
    """
    从香港交易所获取港股列表数据
    
    Returns:
        List[Dict[str, str]]: 港股列表，每个元素包含code和name字段
    """
    try:
        app_logger.info("开始获取港股数据...")
        # 首先尝试中文版URL
        hkex_urls = [
            "https://www.hkex.com.hk/chi/services/trading/securities/securitieslists/ListOfSecurities_c.xlsx",
            "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
        ]
        
        content = None
        for url in hkex_urls:
            try:
                # 添加请求头，模拟浏览器访问
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://www.hkex.com.hk/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
                
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                content = response.content
                app_logger.info(f"成功从 {url} 获取港股数据")
                break
            except Exception as e:
                app_logger.warning(f"从 {url} 获取港股数据失败: {e}")
                continue
        
        if content is None:
            app_logger.error("无法从任何URL获取港股数据")
            return []
        
        # 使用pandas读取Excel文件，因为它能更好地处理这种格式
        # 修复zhconv资源文件缺失问题，使用pandas内置的中文处理功能
        excel_file = io.BytesIO(content)
        df = pd.read_excel(excel_file, header=1)  # 从第二行开始读取标题
        
        app_logger.info(f"Excel数据形状: {df.shape}")
        app_logger.info(f"列名: {list(df.columns)}")
        
        hk_stocks = []
        
        # 打印前几行内容以调试
        app_logger.debug(f"前5行数据:\n{df.head()}")
        
        # 根据实际的列结构提取数据
        # 从pandas输出看，前几列应该是代码和名称
        if len(df.columns) >= 2:
            code_col = df.columns[0]  # 第一列是股份代号
            name_col = df.columns[1]  # 第二列是股份名称
            
            # 遍历数据行
            for index, row in df.iterrows():
                code = row[code_col]
                name = row[name_col]
                
                # 检查是否为有效的股票数据
                if (code is not None and str(code) != 'nan') and (name is not None and str(name) != 'nan'):
                    # 格式化港股代码为5位数字，不足5位前面补0
                    if isinstance(code, (int, float)):
                        code = str(int(code)).zfill(5)
                    elif isinstance(code, str) and code.isdigit():
                        code = code.zfill(5)
                    else:
                        continue  # 不是有效的代码格式
                    
                    # 确保名称是字符串
                    if isinstance(name, str):
                        stock_name = name.strip()
                    else:
                        stock_name = str(name).strip()
                    
                    # 繁简转换
                    if stock_name:  # 确保名称不为空
                        try:
                            simplified_name = convert(str(stock_name).strip(), 'zh-hans')
                            # 处理港股名称中的后缀，如 -W 等，只保留中文部分
                            if '-' in simplified_name:
                                simplified_name = simplified_name.split('-')[0].strip()
                        except Exception as e:
                            app_logger.warning(f"繁简转换失败: {e}，使用原始名称")
                            simplified_name = str(stock_name).strip()
                        hk_stocks.append({
                            'code': f'hk{code}',
                            'name': simplified_name
                        })
                        
                        # 用于调试，显示前几条记录
                        if len(hk_stocks) <= 5:
                            app_logger.debug(f"找到港股: 代码={code}, 名称={stock_name}")
        
        app_logger.info(f"成功获取 {len(hk_stocks)} 只港股数据")
        return hk_stocks
        
    except Exception as e:
        app_logger.error(f"获取港股数据失败: {e}")
        import traceback
        app_logger.error(f"详细错误信息: {traceback.format_exc()}")
        # 出错时返回空列表
        app_logger.warning("获取港股数据失败，返回空列表")
        return []

def fetch_all_stocks() -> List[Dict[str, str]]:
    """
    从网络获取所有A股股票数据
    
    Returns:
        List[Dict[str, str]]: 股票列表，每个元素包含code和name字段
    """
    try:
        # 使用easyquotation获取股票列表
        quotation = easyquotation.use('sina')
        
        # 获取所有股票代码列表
        stock_codes_str = quotation.stock_list  # type: ignore
        # 解析股票代码字符串
        all_stock_codes = []
        for item in stock_codes_str:
            codes = item.split(',')
            all_stock_codes.extend(codes)
        
        # 限制股票数量以提高性能
        max_stocks = 10000  # 限制最多处理10000只股票
        if len(all_stock_codes) > max_stocks:
            app_logger.info(f"股票数量过多 ({len(all_stock_codes)})，限制处理前 {max_stocks} 只股票")
            all_stock_codes = all_stock_codes[:max_stocks]
        
        # 分批获取股票数据，避免一次性请求过多
        batch_size = 800
        stocks_data = []
        
        for i in range(0, len(all_stock_codes), batch_size):
            batch_codes = all_stock_codes[i:i+batch_size]
            # 统一使用带前缀的代码查询，避免代码混淆
            pure_codes = [code[2:] if code.startswith(('sh', 'sz')) else code for code in batch_codes]
            # 对于sh000001和sz000001，直接使用完整代码
            query_codes = []
            for code in batch_codes:
                if code in ['sh000001', 'sz000001']:
                    query_codes.append(code)
                else:
                    query_codes.append(code[2:] if code.startswith(('sh', 'sz')) else code)
            
            try:
                # 获取股票详细数据
                # 对于sh000001和sz000001，使用prefix=True参数确保精确匹配
                data = {}
                special_codes = []
                normal_codes = []
                
                # 分离特殊代码和普通代码
                for j, code in enumerate(batch_codes):
                    if code in ['sh000001', 'sz000001']:
                        special_codes.append(code)
                    else:
                        normal_codes.append((j, code))
                
                # 处理特殊代码
                if special_codes:
                    special_data = quotation.stocks(special_codes, prefix=True)  # type: ignore
                    if isinstance(special_data, dict):
                        data.update(special_data)
                
                # 处理普通代码
                if normal_codes:
                    normal_pure_codes = [pure_codes[j] for j, _ in normal_codes]
                    normal_data = quotation.stocks(normal_pure_codes)  # type: ignore
                    if isinstance(normal_data, dict):
                        # 重新映射键值
                        for j, code in normal_codes:
                            pure_code = pure_codes[j]
                            if pure_code in normal_data:
                                data[pure_code] = normal_data[pure_code]
                
                # 确保data是字典类型
                if not isinstance(data, dict):
                    data = {}
                if data:
                    for j, code in enumerate(batch_codes):
                        pure_code = pure_codes[j]
                        if pure_code in data and data[pure_code] and 'name' in data[pure_code]:
                            # 特殊处理：确保上证指数和平安银行正确映射
                            name = data[pure_code]['name']
                            # 根据完整代码前缀确定正确的名称
                            if pure_code == '000001':
                                if code.startswith('sh'):
                                    name = '上证指数'
                                elif code.startswith('sz'):
                                    name = '平安银行'
                            
                            # 确保指数类股票正确标识
                            if code in ['sh000001', 'sz000001']:
                                if code == 'sh000001':
                                    name = '上证指数'
                                elif code == 'sz000001':
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
            index_data: Union[Dict[str, Any], None] = quotation.stocks(['sh000001', 'sh000002', 'sh000300', 'sz399001', 'sz399006'], prefix=True)  # type: ignore
            if index_data:
                for code, info in index_data.items():
                    if info and 'name' in info:
                        stocks_data.append({
                            'code': code,
                            'name': info['name']
                        })
        except Exception as e:
            app_logger.warning(f"获取指数数据失败: {e}")
        
        # 获取港股数据
        hk_stocks = fetch_hk_stocks()
        stocks_data.extend(hk_stocks)
        
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
                     (code.startswith('hk') and not existing_name.startswith('hk')):
                    # 指数优先于个股，港股优先于旧数据
                    unique_stocks[code] = stock
            else:
                unique_stocks[code] = stock
        
        stocks_data = list(unique_stocks.values())
        
        app_logger.info(f"成功获取 {len(stocks_data)} 只股票数据（包括A股、指数和港股）")
        return stocks_data
        
    except Exception as e:
        app_logger.error(f"获取股票数据失败: {e}")
        # 出错时使用空列表
        app_logger.warning("获取股票数据失败，返回空列表")
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
        
        # 使用数据库更新而不是文件写入
        from stock_monitor.data.stock.stock_updater import incremental_update_stock_database
        return incremental_update_stock_database()
        
    except Exception as e:
        app_logger.error(f"更新股票数据库失败: {e}")
        # 即使更新失败，也尝试使用现有数据
        try:
            # 检查数据库中是否有数据
            from stock_monitor.data.stock.stock_db import stock_db
            stock_count = stock_db.get_all_stocks_count()
            if stock_count > 0:
                app_logger.info("使用现有的股票数据库")
                return True
        except Exception as fallback_e:
            app_logger.error(f"回退方案也失败: {fallback_e}")
        return False


def get_stock_list() -> List[Dict[str, str]]:
    """
    获取股票列表，从本地数据库读取
    
    Returns:
        List[Dict[str, str]]: 股票列表
    """
    try:
        from stock_monitor.data.stock.stock_db import stock_db
        return stock_db.get_all_stocks()
    except Exception as e:
        app_logger.error(f"无法从本地数据库加载股票数据: {e}")
        # 返回空列表
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
            'hk00700',   # 腾讯控股（示例港股）
        ]
        
        # 获取热门股票数据并存入缓存
        success_count = 0
        for stock_code in popular_stocks:
            try:
                # 根据股票代码类型选择不同的行情引擎
                if stock_code.startswith('hk'):
                    quotation = easyquotation.use('hkquote')
                    app_logger.debug(f"使用 hkquote 引擎预加载港股 {stock_code}")
                else:
                    quotation = easyquotation.use('sina')
                    app_logger.debug(f"使用 sina 引擎预加载股票 {stock_code}")
                
                # 统一使用带前缀的代码查询，避免代码混淆
                if stock_code.startswith(('sh', 'sz')):
                    # 对于带前缀的代码，直接使用prefix=True参数查询
                    max_retries = 3
                    retry_count = 0
                    data = None
                    
                    while retry_count < max_retries:
                        try:
                            data = quotation.stocks([stock_code], prefix=True)  # type: ignore
                            if data and isinstance(data, dict) and (stock_code in data):
                                break
                            retry_count += 1
                            app_logger.warning(f"预加载股票 {stock_code} 数据失败 (尝试 {retry_count}/{max_retries})")
                            if retry_count < max_retries:
                                time.sleep(1)  # 等待1秒后重试
                        except Exception as e:
                            retry_count += 1
                            app_logger.warning(f"预加载股票 {stock_code} 数据异常 (尝试 {retry_count}/{max_retries}): {e}")
                            if retry_count < max_retries:
                                time.sleep(1)  # 等待1秒后重试
                elif stock_code.startswith('hk'):
                    # 对于港股代码，使用hkquote引擎
                    try:
                        quotation_hk = easyquotation.use('hkquote')
                        max_retries = 3
                        retry_count = 0
                        data = None
                        
                        while retry_count < max_retries:
                            try:
                                # 移除前缀获取纯代码
                                pure_code = stock_code[2:] if stock_code.startswith('hk') else stock_code
                                data = quotation_hk.stocks([pure_code])  # type: ignore
                                if data and isinstance(data, dict) and (pure_code in data or any(data.values())):
                                    break
                                retry_count += 1
                                app_logger.warning(f"预加载港股 {stock_code} 数据失败 (尝试 {retry_count}/{max_retries})")
                                if retry_count < max_retries:
                                    time.sleep(1)  # 等待1秒后重试
                            except Exception as e:
                                retry_count += 1
                                app_logger.warning(f"预加载港股 {stock_code} 数据异常 (尝试 {retry_count}/{max_retries}): {e}")
                                if retry_count < max_retries:
                                    time.sleep(1)  # 等待1秒后重试
                    except Exception as e:
                        app_logger.error(f"初始化港股行情引擎失败: {e}")
                        data = None
                else:
                    # 对于不带前缀的代码，移除前缀获取纯代码
                    pure_code = stock_code
                    app_logger.debug(f"预加载请求代码: {pure_code}")
                    
                    # 获取股票数据，添加重试机制
                    max_retries = 3
                    retry_count = 0
                    data = None
                    
                    while retry_count < max_retries:
                        try:
                            data = quotation.stocks([pure_code])  # type: ignore
                            if data and isinstance(data, dict) and (pure_code in data or any(data.values())):
                                break
                            retry_count += 1
                            app_logger.warning(f"预加载股票 {stock_code} 数据失败 (尝试 {retry_count}/{max_retries})")
                            if retry_count < max_retries:
                                time.sleep(1)  # 等待1秒后重试
                        except Exception as e:
                            retry_count += 1
                            app_logger.warning(f"预加载股票 {stock_code} 数据异常 (尝试 {retry_count}/{max_retries}): {e}")
                            if retry_count < max_retries:
                                time.sleep(1)  # 等待1秒后重试
                
                if data and isinstance(data, dict):
                    # 存入缓存，设置较长的TTL（1小时）
                    from stock_monitor.utils.cache import global_cache
                    global_cache.set(f"stock_{stock_code}", data, ttl=3600)
                    app_logger.debug(f"预加载股票数据到缓存: {stock_code}")
                    success_count += 1
                else:
                    app_logger.warning(f"预加载股票 {stock_code} 数据失败，已达到最大重试次数")
                    
            except Exception as e:
                app_logger.warning(f"预加载股票 {stock_code} 数据失败: {e}")
                continue
        
        app_logger.info(f"热门股票数据预加载完成，成功加载 {success_count}/{len(popular_stocks)} 只股票")
        
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
        app_logger.info("股票数据库更新成功")
    else:
        app_logger.error("股票数据库更新失败")