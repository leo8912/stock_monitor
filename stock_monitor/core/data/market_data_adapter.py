"""
市场数据适配器模块
替代 mootdx，使用 easyquotation + 腾讯/新浪 API 提供统一接口。

提供与 mootdx Quotes 客户端兼容的接口方法:
  - bars(symbol, market, category, start, offset)  → K线 DataFrame
  - index(symbol, market, category, start, offset) → 指数 K线 DataFrame
  - quotes(symbol=[...]) → 实时行情 DataFrame
  - transaction(symbol, market, start, count) → 逐笔成交 DataFrame
  - stocks(market=0/1) → 股票列表 DataFrame

数据源:
  - 日/周/月K线: 腾讯 web.ifzq.gtimg.cn (前复权)
  - 分钟K线(5/15/30/60m): 新浪 money.finance.sina.com.cn
  - 实时行情: easyquotation (新浪)
  - 逐笔成交: 无可靠替代 (返回空 DataFrame，调用方已降级)
"""

from __future__ import annotations

import pandas as pd
import requests

from stock_monitor.utils.logger import app_logger

# ====== 常量 ======
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
_REQUEST_TIMEOUT = 10  # 秒

# mootdx category → 腾讯 period 映射 (日/周/月)
_CATEGORY_TO_TENCENT_PERIOD = {
    4: "day",
    5: "week",
    6: "month",
    9: "day",
}

# mootdx category → 新浪 scale 映射 (分钟)
_CATEGORY_TO_SINA_SCALE = {
    0: 5,  # 5m
    1: 15,  # 15m
    2: 30,  # 30m
    3: 60,  # 60m
    7: 5,  # 1m → fallback to 5m (新浪不支持1m)
    8: 60,  # 120m → fallback to 60m (新浪不支持120m)
}

# 是否为日/周/月类K线
_DAILY_CATEGORIES = {4, 5, 6, 9}


def _market_prefix(market: int) -> str:
    """market int → 'sh' / 'sz'"""
    return "sh" if market == 1 else "sz"


def _tencent_kline_url(symbol: str, market: int, period: str, count: int = 250) -> str:
    """构造腾讯 K线 API URL (start_date/end_date 留空)"""
    prefix = _market_prefix(market)
    return (
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={prefix}{symbol},{period},,,{count},qfq"
    )


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class MarketDataAdapter:
    """
    市场数据适配器 — 模拟 mootdx Quotes 接口。
    使用 easyquotation (新浪) 获取实时行情，腾讯 K线 API 获取历史 K线。
    """

    def __init__(self):
        import easyquotation

        self._sina = easyquotation.use("sina")
        self._session = requests.Session()
        self._session.headers.update(_DEFAULT_HEADERS)

    # ------------------------------------------------------------------
    #  K线接口（bars / index）
    # ------------------------------------------------------------------

    def bars(
        self,
        symbol: str,
        market: int = 0,
        category: int = 9,
        start: int = 0,
        offset: int = 250,
        count: int = None,
        **_kwargs,
    ) -> pd.DataFrame:
        """获取个股 K线数据（兼容 mootdx bars 接口签名）"""
        if count is not None:
            offset = count
        total_needed = start + offset

        if category in _DAILY_CATEGORIES:
            # 日/周/月 K线 → 腾讯 API
            period = _CATEGORY_TO_TENCENT_PERIOD.get(category, "day")
            df = self._fetch_tencent_kline(symbol, market, period, total_needed)
        else:
            # 分钟 K线 → 新浪 API
            scale = _CATEGORY_TO_SINA_SCALE.get(category)
            if scale is None:
                app_logger.warning(f"不支持的K线周期 category={category}")
                return pd.DataFrame()
            df = self._fetch_sina_kline(symbol, market, scale, total_needed)

        if df is None or df.empty:
            return pd.DataFrame()

        # mootdx 语义: start=最近端偏移量，offset=取多少条
        return df.tail(offset).reset_index(drop=True)

    def index(
        self,
        symbol: str,
        market: int = 0,
        category: int = 9,
        start: int = 0,
        offset: int = 250,
        count: int = None,
        **_kwargs,
    ) -> pd.DataFrame:
        """获取指数 K线数据（与 bars 相同实现，指数走同一 API）"""
        return self.bars(symbol, market, category, start, offset, count=count)

    def _fetch_tencent_kline(
        self, symbol: str, market: int, period: str, count: int = 250
    ) -> pd.DataFrame | None:
        """从腾讯 K线 API 拉取日/周/月K线数据"""
        url = _tencent_kline_url(symbol, market, period, count)
        try:
            resp = self._session.get(url, timeout=_REQUEST_TIMEOUT)
            raw = resp.json()
            data = raw.get("data", {})
            prefix = _market_prefix(market)
            stock_data = data.get(f"{prefix}{symbol}", {})

            if not isinstance(stock_data, dict):
                app_logger.debug(
                    f"腾讯K线数据格式异常: {prefix}{symbol} data={type(stock_data)}"
                )
                return None

            # 腾讯返回格式: qfqday / day / qfqweek / qfqmonth 等
            klines = stock_data.get(f"qfq{period}") or stock_data.get(period, [])
            if not klines:
                app_logger.debug(f"腾讯K线无数据: {prefix}{symbol} period={period}")
                return None

            rows = []
            for kline in klines:
                if len(kline) < 6:
                    continue
                dt_str = str(kline[0])
                # 日线补充收盘时间以统一格式
                if len(dt_str) <= 10:
                    dt_str += " 15:00"

                rows.append(
                    {
                        "datetime": dt_str,
                        "open": _safe_float(kline[1]),
                        "close": _safe_float(kline[2]),
                        "high": _safe_float(kline[3]),
                        "low": _safe_float(kline[4]),
                        "vol": _safe_float(kline[5]),
                        "amount": _safe_float(kline[5]) * _safe_float(kline[2]) * 100,
                    }
                )

            if not rows:
                return None

            df = pd.DataFrame(rows)
            df["datetime"] = pd.to_datetime(df["datetime"])
            return df

        except Exception as e:
            app_logger.warning(f"腾讯K线获取失败 [{symbol} period={period}]: {e}")
            return None

    def _fetch_sina_kline(
        self, symbol: str, market: int, scale: int, count: int = 250
    ) -> pd.DataFrame | None:
        """
        从新浪 K线 API 拉取分钟级K线数据。
        scale: 5/15/30/60 (分钟)
        """
        prefix = _market_prefix(market)
        sina_code = f"{prefix}{symbol}"
        url = (
            f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
            f"/CN_MarketData.getKLineData?symbol={sina_code}&scale={scale}&datalen={count}"
        )
        try:
            resp = self._session.get(
                url,
                timeout=_REQUEST_TIMEOUT,
                headers={**_DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn"},
            )
            klines = resp.json()
            if not klines or not isinstance(klines, list):
                return None

            rows = []
            for item in klines:
                dt_str = item.get("day", "")
                if not dt_str:
                    continue
                # 新浪返回 "2026-09-10 14:30:00" → 去掉秒
                if len(dt_str) > 16:
                    dt_str = dt_str[:16]

                rows.append(
                    {
                        "datetime": dt_str,
                        "open": _safe_float(item.get("open")),
                        "close": _safe_float(item.get("close")),
                        "high": _safe_float(item.get("high")),
                        "low": _safe_float(item.get("low")),
                        "vol": _safe_float(item.get("volume")),
                        "amount": _safe_float(item.get("volume"))
                        * _safe_float(item.get("close"))
                        * 100,
                    }
                )

            if not rows:
                return None

            df = pd.DataFrame(rows)
            df["datetime"] = pd.to_datetime(df["datetime"])
            return df

        except Exception as e:
            app_logger.warning(f"新浪K线获取失败 [{sina_code} scale={scale}]: {e}")
            return None

    # ------------------------------------------------------------------
    #  实时行情接口（quotes）
    # ------------------------------------------------------------------

    def quotes(self, symbol: list[str] = None, **_kwargs) -> pd.DataFrame:
        """
        获取实时行情（兼容 mootdx quotes 接口）。
        symbol: 如 ['000001', 'sh600519'] 或 ['600519', '000001']
        返回 DataFrame，列名兼容 mootdx: price, last_close, open, high, low, vol, ...
        """
        if not symbol:
            return pd.DataFrame()

        try:
            # easyquotation.sina 接受纯数字代码
            clean_codes = []
            code_map = {}  # clean_code → original code
            for s in symbol:
                # 去掉 sh/sz 前缀
                clean = s[2:] if s.startswith(("sh", "sz")) else s
                clean_codes.append(clean)
                code_map[clean] = s

            raw = self._sina.stocks(clean_codes)
            if not raw:
                return pd.DataFrame()

            rows = []
            for clean_code in clean_codes:
                info = raw.get(clean_code)
                if not info or not isinstance(info, dict):
                    continue
                row = {
                    "code": code_map.get(clean_code, clean_code),
                    "price": _safe_float(info.get("now")),
                    "last_close": _safe_float(info.get("close")),
                    "open": _safe_float(info.get("open")),
                    "high": _safe_float(info.get("high")),
                    "low": _safe_float(info.get("low")),
                    "vol": _safe_float(info.get("volume")),
                    "cur_vol": _safe_float(info.get("turnover", 0))
                    / max(_safe_float(info.get("now", 1)), 0.01),
                    "amount": _safe_float(info.get("turnover")),
                    "bid1": _safe_float(info.get("bid1")),
                    "bid_vol1": _safe_float(info.get("bid1_volume")),
                    "ask1": _safe_float(info.get("ask1")),
                    "ask_vol1": _safe_float(info.get("ask1_volume")),
                    "name": info.get("name", ""),
                }
                rows.append(row)

            return pd.DataFrame(rows) if rows else pd.DataFrame()

        except Exception as e:
            app_logger.warning(f"easyquotation 行情获取失败: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    #  逐笔成交接口（transaction）
    # ------------------------------------------------------------------

    def transaction(
        self,
        symbol: str,
        market: int = 0,
        start: int = 0,
        count: int = 2000,
        **_kwargs,
    ) -> pd.DataFrame:
        """
        获取逐笔成交数据（兼容 mootdx transaction 接口）。
        返回 DataFrame，列: time, price, vol, buyorsell

        注意：当前无可靠的第三方逐笔数据源完全替代 mootdx 的 TDX 逐笔接口。
        返回空 DataFrame 表示无数据。调用方已有降级逻辑。
        """
        # 尝试 akshare 逐笔接口（东方财富分钟成交）
        try:
            return self._fetch_akshare_transaction(symbol, market, start, count)
        except Exception:
            pass

        return pd.DataFrame()

    def _fetch_akshare_transaction(
        self, symbol: str, market: int, start: int, count: int
    ) -> pd.DataFrame:
        """通过 akshare 获取逐笔数据"""
        try:
            import akshare as ak

            prefix = _market_prefix(market)
            full_code = f"{prefix}{symbol}"
            df = ak.stock_intraday_em(symbol=full_code)
            if df is None or df.empty:
                return pd.DataFrame()

            # akshare stock_intraday_em 返回列:
            # 成交时间, 成交价, 涨跌幅, 成交量, 成交额, 动态市盈率, 买卖类型
            result = pd.DataFrame()
            result["time"] = df.iloc[:, 0].astype(str)  # 成交时间
            result["price"] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
            result["vol"] = pd.to_numeric(df.iloc[:, 3], errors="coerce")
            # 买卖类型: 买盘/卖盘/中性
            if df.shape[1] > 5:
                buy_sell = df.iloc[:, 5].astype(str)
                result["buyorsell"] = buy_sell.map(
                    {"买盘": 0, "卖盘": 1, "中性": 2}
                ).fillna(2)
            else:
                result["buyorsell"] = 2

            # 处理 start/offset
            if start > 0:
                result = result.iloc[start:]
            if count and len(result) > count:
                result = result.tail(count)

            return result.reset_index(drop=True)

        except Exception as e:
            app_logger.debug(f"akshare 逐笔获取失败 [{symbol}]: {e}")
            raise

    # ------------------------------------------------------------------
    #  股票列表接口（stocks）
    # ------------------------------------------------------------------

    def stocks(self, market: int = 0) -> pd.DataFrame:
        """
        获取指定市场的全部股票列表（兼容 mootdx stocks 接口）。
        返回 DataFrame，列: code, name
        """
        try:
            prefix = _market_prefix(market)
            # easyquotation stock_list 返回一个包含逗号分隔代码字符串的列表
            raw_list = self._sina.stock_list
            if not raw_list:
                return pd.DataFrame(columns=["code", "name"])

            # stock_list 可能是一个 list，其中第一个元素是逗号分隔的代码字符串
            all_codes_str = raw_list[0] if isinstance(raw_list, list) else str(raw_list)
            all_codes = [c.strip() for c in all_codes_str.split(",") if c.strip()]

            # 筛选对应市场
            market_codes = [c for c in all_codes if c.startswith(prefix)]

            # 获取名称 — 批量查询
            pure_codes = [c[2:] for c in market_codes]
            names = {}
            if pure_codes:
                # 分批查询，每批最多50只
                batch_size = 50
                for i in range(0, len(pure_codes), batch_size):
                    batch = pure_codes[i : i + batch_size]
                    try:
                        raw_data = self._sina.stocks(batch)
                        if raw_data:
                            for code, info in raw_data.items():
                                if isinstance(info, dict):
                                    names[code] = info.get("name", code)
                                else:
                                    names[code] = code
                    except Exception:
                        for code in batch:
                            names[code] = code

            rows = []
            for full_code in market_codes:
                pure = full_code[2:]
                rows.append({"code": pure, "name": names.get(pure, pure)})

            return (
                pd.DataFrame(rows) if rows else pd.DataFrame(columns=["code", "name"])
            )

        except Exception as e:
            app_logger.warning(f"获取股票列表失败 (market={market}): {e}")
            return pd.DataFrame(columns=["code", "name"])
