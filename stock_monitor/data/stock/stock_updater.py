"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 SQLite 数据库
"""

import json
import time
import os
from typing import List, Dict, Any, Union
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.helpers import resource_path
from stock_monitor.data.stock.stock_db import stock_db
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
        # 出错时返回本地缓存的港股数据
        try:
            from stock_monitor.data.stock.stock_db import stock_db
            hk_stocks = stock_db.get_stocks_by_market_type('HK')
            app_logger.info(f"使用本地缓存数据，获取到 {len(hk_stocks)} 只港股")
            return hk_stocks
        except Exception as local_e:
            app_logger.error(f"获取本地港股数据也失败: {local_e}")
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
                        normal_codes.append(query_codes[j])
                
                # 处理特殊代码
                if special_codes:
                    special_data = quotation.stocks(special_codes, prefix=True)  # type: ignore
                    if isinstance(special_data, dict):
                        data.update(special_data)
                
                # 处理普通代码
                if normal_codes:
                    normal_data = quotation.stocks(normal_codes)  # type: ignore
                    if isinstance(normal_data, dict):
                        # 映射回原始代码
                        for pure_code, stock_info in normal_data.items():
                            # 查找对应的原始代码
                            for orig_code, q_code in zip(batch_codes, query_codes):
                                if q_code == pure_code:
                                    data[orig_code] = stock_info
                                    break
                
                # 处理返回数据
                if isinstance(data, dict):
                    for code, info in data.items():
                        if info and 'name' in info:
                            stocks_data.append({
                                'code': code,
                                'name': info['name']
                            })
                            
                app_logger.debug(f"成功获取批次 {i//batch_size + 1} 的股票数据，共 {len(data)} 条")
                
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
        # 出错时使用本地缓存数据
        try:
            from stock_monitor.data.stock.stock_db import stock_db
            stocks_data = stock_db.get_all_stocks()
            app_logger.info(f"使用本地缓存数据，获取到 {len(stocks_data)} 只股票")
            return stocks_data
        except Exception as local_e:
            app_logger.error(f"获取本地股票数据也失败: {local_e}")
            return []


def update_stock_database() -> bool:
    """
    更新本地股票数据库
    
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
        inserted_count = stock_db.insert_stocks(stocks_data)
        
        app_logger.info(f"股票数据库更新完成，共 {inserted_count} 只股票")
        return True
        
    except Exception as e:
        app_logger.error(f"更新股票数据库失败: {e}")
        return False


def incremental_update_stock_database() -> bool:
    """
    增量更新本地股票数据库
    
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
        
        # 为股票数据添加拼音信息
        app_logger.info("开始为股票数据添加拼音信息...")
        for stock in stocks_data:
            name = stock['name']
            # 去除*ST、ST等前缀，避免影响拼音识别
            base = name.replace('*', '').replace('ST', '').replace(' ', '')
            # 生成全拼
            from pypinyin import lazy_pinyin, Style
            full_pinyin = ''.join(lazy_pinyin(base))
            # 生成首字母缩写
            abbr = ''.join(lazy_pinyin(base, style=Style.FIRST_LETTER))
            stock['pinyin'] = full_pinyin.lower()
            stock['abbr'] = abbr.lower()
        
        app_logger.info("拼音信息处理完成")
        
        # 使用数据库更新而不是文件写入
        inserted_count = stock_db.insert_stocks(stocks_data)
        
        app_logger.info(f"股票数据库增量更新完成，共处理 {len(stocks_data)} 只股票，实际更新 {inserted_count} 只股票")
        return True
        
    except Exception as e:
        app_logger.error(f"增量更新股票数据库失败: {e}")
        return False