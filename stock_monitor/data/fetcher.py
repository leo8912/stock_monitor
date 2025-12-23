"""
股票数据获取模块
负责从外部源（如Sina API, HKEX等）获取原始股票数据
"""
import io

import requests
import easyquotation
from typing import List, Dict, Union, Any, Optional
from stock_monitor.utils.logger import app_logger

# 安全导入zhconv
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

class StockFetcher:
    """股票数据获取器"""
    
    def fetch_all_stocks(self) -> List[Dict[str, str]]:
        """
        获取所有A股和港股数据
        
        Returns:
            List[Dict[str, str]]: 股票列表 [{'code': '...', 'name': '...'}, ...]
        """
        stocks_data = []
        
        # 1. 获取A股数据
        try:
            a_stocks = self._fetch_a_stocks()
            stocks_data.extend(a_stocks)
        except Exception as e:
            app_logger.error(f"获取A股数据失败: {e}")
            
        # 2. 获取主要指数
        try:
             indices = self._fetch_indices()
             stocks_data.extend(indices)
        except Exception as e:
             app_logger.error(f"获取指数数据失败: {e}")

        # 3. 获取港股数据
        try:
            hk_stocks = self._fetch_hk_stocks()
            stocks_data.extend(hk_stocks)
        except Exception as e:
            app_logger.error(f"获取港股数据失败: {e}")
            
        # 4. 去重
        return self._deduplicate_stocks(stocks_data)

    def _fetch_a_stocks(self) -> List[Dict[str, str]]:
        """获取A股数据"""
        quotation = easyquotation.use('sina')
        # 获取所有代码
        stock_codes_str = quotation.stock_list # type: ignore
        all_stock_codes = []
        for item in stock_codes_str:
            all_stock_codes.extend(item.split(','))
            
        # 限制数量
        max_stocks = 10000
        if len(all_stock_codes) > max_stocks:
             app_logger.info(f"股票数量过多 ({len(all_stock_codes)})，限制处理前 {max_stocks} 只")
             all_stock_codes = all_stock_codes[:max_stocks]
             
        # 分批获取
        batch_size = 800
        results = []
        
        for i in range(0, len(all_stock_codes), batch_size):
            batch_codes = all_stock_codes[i:i+batch_size]
            pure_codes = [c[2:] if c.startswith(('sh', 'sz')) else c for c in batch_codes]
            
            try:
                # 获取数据
                # 分离特殊代码(如000001)
                special_codes = [c for c in batch_codes if c in ['sh000001', 'sz000001']]
                normal_map = {c[2:] if c.startswith(('sh', 'sz')) else c : c for c in batch_codes if c not in special_codes}
                
                data = {}
                if special_codes:
                    spec_data = quotation.stocks(special_codes, prefix=True) # type: ignore
                    if isinstance(spec_data, dict):
                        data.update(spec_data)
                
                if normal_map:
                    norm_data = quotation.stocks(list(normal_map.keys())) # type: ignore
                    if isinstance(norm_data, dict):
                         # Map back to full code
                         for p_code, info in norm_data.items():
                             if p_code in normal_map:
                                 data[normal_map[p_code]] = info
                                 
                # Process
                for code, info in data.items():
                    if info and 'name' in info:
                        name = info['name']
                        # Fix names for 000001 conflict
                        if code == 'sh000001': name = '上证指数'
                        elif code == 'sz000001': name = '平安银行'
                        
                        results.append({'code': code, 'name': name})
                        
            except Exception as e:
                app_logger.warning(f"获取批次股票数据失败: {e}")
                
        return results

    def _fetch_indices(self) -> List[Dict[str, str]]:
        """获取主要指数"""
        indices = ['sh000001', 'sh000002', 'sh000300', 'sz399001', 'sz399006']
        quotation = easyquotation.use('sina')
        data = quotation.stocks(indices, prefix=True) # type: ignore
        results = []
        if isinstance(data, dict):
            for code, info in data.items():
                if info and 'name' in info:
                    results.append({'code': code, 'name': info['name']})
        return results

    def _fetch_hk_stocks(self) -> List[Dict[str, str]]:
        """从HKEX获取港股数据"""
        app_logger.info("开始获取港股数据...")
        hkex_urls = [
            "https://www.hkex.com.hk/chi/services/trading/securities/securitieslists/ListOfSecurities_c.xlsx",
            "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
        ]
        
        content = None
        for url in hkex_urls:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://www.hkex.com.hk/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                content = response.content
                break
            except Exception as e:
                app_logger.warning(f"从 {url} 获取港股数据失败: {e}")
                
        if not content:
            return []
            
        hk_stocks = []
        try:
             import pandas as pd
             df = pd.read_excel(io.BytesIO(content), header=1)
             if len(df.columns) >= 2:
                code_col, name_col = df.columns[0], df.columns[1]
                for _, row in df.iterrows():
                    code, name = row[code_col], row[name_col]
                    if pd.notna(code) and pd.notna(name):
                        # Format code
                        if isinstance(code, (int, float)): code = str(int(code)).zfill(5)
                        elif isinstance(code, str) and code.isdigit(): code = code.zfill(5)
                        else: continue
                        
                        # Format name
                        s_name = str(name).strip()
                        try:
                            s_name = convert(s_name, 'zh-hans')
                            if '-' in s_name: s_name = s_name.split('-')[0].strip()
                        except: pass
                        
                        hk_stocks.append({'code': f'hk{code}', 'name': s_name})
        except Exception as e:
            app_logger.error(f"解析港股Excel失败: {e}")
            
        return hk_stocks

    def _deduplicate_stocks(self, stocks: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """去重，指数优先"""
        unique = {}
        for s in stocks:
            code = s['code']
            if code in unique:
                existing_name = unique[code]['name']
                curr_name = s['name']
                # Index priority logic
                if (code == 'sh000001' and curr_name == '上证指数') or \
                   ('指数' in curr_name and '指数' not in existing_name):
                       unique[code] = s
            else:
                unique[code] = s
        return list(unique.values())

# Global instance
stock_fetcher = StockFetcher()
