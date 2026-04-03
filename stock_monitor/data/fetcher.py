import io
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import easyquotation
import requests

from stock_monitor.utils.logger import app_logger

# 安全导入 zhconv
try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="zhconv")
        from zhconv import convert
except ImportError:
    app_logger.warning("无法导入 zhconv 库，将使用原样返回的替代函数")

    def convert(s, locale, update=None):  # type: ignore
        return s

except Exception as e:
    app_logger.warning(f"导入 zhconv 库时发生异常：{e}，将使用原样返回的替代函数")

    def convert(s, locale, update=None):  # type: ignore
        return s


# 常量定义
MAX_STOCKS_LIMIT = 10000
BATCH_SIZE = 800
PARALLEL_BATCHES = 5  # 并行批次数


class StockFetcher:
    """股票数据获取器（支持并行获取）"""

    def fetch_all_stocks(self) -> list[dict[str, str]]:
        """获取所有 A 股和港股数据（并行优化版）"""
        stocks_data = []

        try:
            a_stocks = self._fetch_a_stocks_parallel()
            stocks_data.extend(a_stocks)
        except Exception as e:
            app_logger.error(f"获取 A 股数据失败：{e}")

        try:
            indices = self._fetch_indices()
            stocks_data.extend(indices)
        except Exception as e:
            app_logger.error(f"获取指数数据失败：{e}")

        try:
            hk_stocks = self._fetch_hk_stocks()
            stocks_data.extend(hk_stocks)
        except Exception as e:
            app_logger.error(f"获取港股数据失败：{e}")

        return self._deduplicate_stocks(stocks_data)

    def _fetch_a_stocks_parallel(self) -> list[dict[str, str]]:
        """并行获取 A 股数据（使用 ThreadPoolExecutor）"""
        quotation = easyquotation.use("sina")
        stock_codes_str = quotation.stock_list  # type: ignore
        all_stock_codes = []
        for item in stock_codes_str:
            all_stock_codes.extend(item.split(","))

        if len(all_stock_codes) > MAX_STOCKS_LIMIT:
            app_logger.info(
                f"股票数量过多 ({len(all_stock_codes)})，限制处理前 {MAX_STOCKS_LIMIT} 只"
            )
            all_stock_codes = all_stock_codes[:MAX_STOCKS_LIMIT]

        # 分批
        batches = [
            all_stock_codes[i : i + BATCH_SIZE]
            for i in range(0, len(all_stock_codes), BATCH_SIZE)
        ]

        results = []
        app_logger.info(f"开始并行获取 A 股数据，共 {len(batches)} 个批次...")

        # 并行获取
        with ThreadPoolExecutor(max_workers=PARALLEL_BATCHES) as executor:
            futures = {
                executor.submit(self._fetch_batch, batch, quotation): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_result = future.result(timeout=60)
                    results.extend(batch_result)
                    app_logger.debug(
                        f"批次 {batch_idx + 1}/{len(batches)} 完成，获取 {len(batch_result)} 只股票"
                    )
                except Exception as e:
                    app_logger.warning(f"批次 {batch_idx + 1} 获取失败：{e}")

        app_logger.info(f"A 股数据获取完成，共 {len(results)} 只股票")
        return results

    def _fetch_batch(self, batch_codes: list[str], quotation) -> list[dict[str, str]]:
        """获取单个批次股票数据（供线程池调用）"""
        results = []
        try:
            # 分离特殊代码
            special_codes = [c for c in batch_codes if c in ["sh000001", "sz000001"]]
            normal_map = {
                c[2:] if c.startswith(("sh", "sz")) else c: c
                for c in batch_codes
                if c not in special_codes
            }

            data = {}
            if special_codes:
                spec_data = quotation.stocks(special_codes, prefix=True)  # type: ignore
                if isinstance(spec_data, dict):
                    data.update(spec_data)

            if normal_map:
                norm_data = quotation.stocks(list(normal_map.keys()))  # type: ignore
                if isinstance(norm_data, dict):
                    for p_code, info in norm_data.items():
                        if p_code in normal_map:
                            data[normal_map[p_code]] = info

            # 处理数据
            for code, info in data.items():
                if info and "name" in info:
                    name = info["name"]
                    if code == "sh000001":
                        name = "上证指数"
                    elif code == "sz000001":
                        name = "平安银行"
                    results.append({"code": code, "name": name})

        except Exception as e:
            app_logger.warning(f"获取批次股票数据失败：{e}")

        return results

    def _fetch_a_stocks(self) -> list[dict[str, str]]:
        """获取 A 股数据（串行兼容版本，保留向后兼容）"""
        quotation = easyquotation.use("sina")
        stock_codes_str = quotation.stock_list  # type: ignore
        all_stock_codes = []
        for item in stock_codes_str:
            all_stock_codes.extend(item.split(","))

        if len(all_stock_codes) > MAX_STOCKS_LIMIT:
            app_logger.info(
                f"股票数量过多 ({len(all_stock_codes)})，限制处理前 {MAX_STOCKS_LIMIT} 只"
            )
            all_stock_codes = all_stock_codes[:MAX_STOCKS_LIMIT]

        results = []
        for i in range(0, len(all_stock_codes), BATCH_SIZE):
            batch_codes = all_stock_codes[i : i + BATCH_SIZE]
            [c[2:] if c.startswith(("sh", "sz")) else c for c in batch_codes]

            try:
                special_codes = [
                    c for c in batch_codes if c in ["sh000001", "sz000001"]
                ]
                normal_map = {
                    c[2:] if c.startswith(("sh", "sz")) else c: c
                    for c in batch_codes
                    if c not in special_codes
                }

                data = {}
                if special_codes:
                    spec_data = quotation.stocks(special_codes, prefix=True)  # type: ignore
                    if isinstance(spec_data, dict):
                        data.update(spec_data)

                if normal_map:
                    norm_data = quotation.stocks(list(normal_map.keys()))  # type: ignore
                    if isinstance(norm_data, dict):
                        for p_code, info in norm_data.items():
                            if p_code in normal_map:
                                data[normal_map[p_code]] = info

                for code, info in data.items():
                    if info and "name" in info:
                        name = info["name"]
                        if code == "sh000001":
                            name = "上证指数"
                        elif code == "sz000001":
                            name = "平安银行"
                        results.append({"code": code, "name": name})

            except Exception as e:
                app_logger.warning(f"获取批次股票数据失败：{e}")

        return results

    def _fetch_indices(self) -> list[dict[str, str]]:
        """获取主要指数"""
        indices = ["sh000001", "sh000002", "sh000300", "sz399001", "sz399006"]
        quotation = easyquotation.use("sina")
        data = quotation.stocks(indices, prefix=True)  # type: ignore
        results = []
        if isinstance(data, dict):
            for code, info in data.items():
                if info and "name" in info:
                    results.append({"code": code, "name": info["name"]})
        return results

    def _fetch_hk_stocks(self) -> list[dict[str, str]]:
        """从 HKEX 获取港股数据"""
        app_logger.info("开始获取港股数据...")
        hkex_urls = [
            "https://www.hkex.com.hk/chi/services/trading/securities/securitieslists/ListOfSecurities_c.xlsx",
            "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx",
        ]

        content = None
        for url in hkex_urls:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://www.hkex.com.hk/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                }
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                content = response.content
                break
            except Exception as e:
                app_logger.warning(f"从 {url} 获取港股数据失败：{e}")

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
                        if isinstance(code, (int, float)):
                            code = str(int(code)).zfill(5)
                        elif isinstance(code, str) and code.isdigit():
                            code = code.zfill(5)
                        else:
                            continue

                        s_name = str(name).strip()
                        try:
                            s_name = convert(s_name, "zh-hans")
                            if "-" in s_name:
                                s_name = s_name.split("-")[0].strip()
                        except Exception:
                            pass

                        hk_stocks.append({"code": f"hk{code}", "name": s_name})
        except Exception as e:
            app_logger.error(f"解析港股数据失败：{e}")

        app_logger.info(f"获取到 {len(hk_stocks)} 只港股数据")
        return hk_stocks

    def _deduplicate_stocks(self, stocks: list[dict[str, str]]) -> list[dict[str, str]]:
        """去重处理"""
        seen = set()
        unique = []
        for stock in stocks:
            if stock["code"] not in seen:
                seen.add(stock["code"])
                unique.append(stock)
        return unique


# 全局单例
stock_fetcher = StockFetcher()
