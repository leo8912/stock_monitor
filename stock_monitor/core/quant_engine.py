"""
量化分析引擎模块
"""

import time
from collections import deque

import numpy as np
import pandas as pd

from ..utils.logger import app_logger
from .financial_filter import FinancialFilter
from .market_manager import market_manager
from .symbol_resolver import SymbolResolver, SymbolType


class QuantEngine:
    """量化策略雷达"""

    FreqMap = {"15m": 1, "30m": 2, "60m": 3, "daily": 9}

    TF_CHINESE_MAP = {
        "15m": "15分钟",
        "30m": "30分钟",
        "60m": "60分钟",
        "daily": "日线",
    }

    # 大盘基准缓存，避免重复拉取
    _market_benchmark_cache = {}

    def __init__(self, mootdx_client):
        self.client = mootdx_client
        self._bars_cache = {}  # 缓存格式: {(symbol, cat): (df, timestamp)}
        self._cache_ttl = 60  # 缓存生存时间 (秒)
        self._large_order_cache = {}  # 大单流向缓存
        self.fin_filter = FinancialFilter()  # 基本面异常过滤器

    def _parse_symbol(
        self, symbol: str, market: int = None
    ) -> tuple[str, int, SymbolType]:
        """
        [ELEGANT] 委托 SymbolResolver 解析符号、市场与标的类型
        """
        config = SymbolResolver.resolve(symbol, market)
        return config.code, config.market, config.type

    def _validate_data(self, df: pd.DataFrame, stype: SymbolType) -> bool:
        """
        数据契约验证器：基于标的类型执行相应的一致性检查
        """
        if df is None or df.empty:
            return False

        # 1. 指数类型校验：价格点位不应小于 100 (典型个股价格)
        if stype == SymbolType.INDEX:
            last_price = df.iloc[-1]["close"]
            if last_price < 100:
                app_logger.warning(
                    f"数据契约冲突: 捕获到价格 {last_price}，不满足 INDEX 类型的基准点位要求。"
                )
                return False

        # 2. 通用性日期完整性检查 (可选扩展)
        return True

    def fetch_bars(
        self, symbol: str, market: int = None, category: int = 9, offset: int = 250
    ) -> pd.DataFrame:
        """
        [ELEGANT] 稳健的 K 线获取逻辑，通过 SymbolResolver 自动确定抓取策略
        """
        import time

        now = time.time()

        # 1. 解析初始参数与元数据
        config = SymbolResolver.resolve(symbol, market)
        cache_key = (
            f"{SymbolResolver.get_market_prefix(config.market)}{config.code}",
            category,
        )

        # 2. 检查缓存
        if cache_key in self._bars_cache:
            df, ts = self._bars_cache[cache_key]
            if now - ts < self._cache_ttl:
                return df.copy()

        # 3. 核心抓取循环 (候选路径自动回退)
        # 候选集包含: [首选解析代码] + [解析器提供的备选代码]
        candidate_paths = [(config.code, config.market)] + config.alternates

        final_df = None
        for code_p, market_p in candidate_paths:
            try:
                # 抓取数据 (传入类型标识以触发协议自适应)
                df = self._do_fetch(
                    code_p, market_p, category, offset, stype=config.type
                )

                # 执行数据契约校验
                if self._validate_data(df, config.type):
                    final_df = df
                    break
            except Exception as e:
                app_logger.error(f"代码 {code_p} 数据抓取或解析异常: {e}")
                continue

        if final_df is not None and not final_df.empty:
            # 数据后处理
            final_df = final_df.reset_index(drop=True)
            if "datetime" in final_df.columns:
                final_df = final_df.drop_duplicates(subset=["datetime"])
                final_df = final_df.sort_values("datetime", ascending=True).reset_index(
                    drop=True
                )

            # 更新并限制缓存
            self._bars_cache[cache_key] = (final_df, now)
            if len(self._bars_cache) > 500:
                self._bars_cache.pop(next(iter(self._bars_cache)))
            return final_df

        return pd.DataFrame()

    def _do_fetch(
        self,
        symbol: str,
        market: int,
        category: int,
        offset: int,
        stype: SymbolType = SymbolType.STOCK,
    ) -> pd.DataFrame:
        """
        执行底层数据抓取，支持协议自适应 (INDEX 专用接口)
        """
        # [ELEGANT] 针对指数类型，使用专用的 index 接口，避开 bars 接口的二进制解析 bug
        api_method = (
            self.client.index if stype == SymbolType.INDEX else self.client.bars
        )

        if offset <= 800:
            return api_method(
                symbol=symbol, market=market, category=category, start=0, offset=offset
            )
        else:
            chunks = []
            for start in range(0, offset, 800):
                current_offset = min(800, offset - start)
                chunk = api_method(
                    symbol=symbol,
                    market=market,
                    category=category,
                    start=start,
                    offset=current_offset,
                )
                if chunk is not None and not chunk.empty:
                    chunks.append(chunk)
                else:
                    break
            return pd.concat(chunks) if chunks else pd.DataFrame()

    def check_macd_bullish_divergence(
        self, df: pd.DataFrame, window: int = 30, end_idx: int = None
    ) -> bool:
        try:
            if "MACDh_12_26_9" not in df.columns:
                df.ta.macd(append=True)
            curr = df if end_idx is None else df.iloc[: end_idx + 1]
            if len(curr) < window * 2:
                return False
            cols = [c for c in df.columns if c.startswith("MACDh_")]
            if not cols:
                return False
            m_col = cols[0]
            recent = curr.iloc[-window:]
            prev = curr.iloc[-window * 2 : -window]
            ri = recent["close"].idxmin()
            pi = prev["close"].idxmin()
            if (
                recent.loc[ri, "close"] < prev.loc[pi, "close"]
                and recent.loc[ri, m_col] > prev.loc[pi, m_col]
            ):
                if ri >= curr.index[-5]:
                    return True
            return False
        except Exception:
            return False

    def check_bbands_squeeze(self, df: pd.DataFrame, end_idx: int = None) -> bool:
        try:
            curr = df if end_idx is None else df.iloc[: end_idx + 1]
            if len(curr) < 100:
                return False
            cols = [c for c in curr.columns if c.startswith("BBB_")]
            if not cols:
                return False
            bw = curr[cols[0]].iloc[-1]
            return bw <= curr[cols[0]].iloc[-100:].min() * 1.05
        except Exception:
            return False

    def calculate_rsrs(
        self, df: pd.DataFrame, n: int = 18, m: int = 600
    ) -> tuple[float, float]:
        """
        计算 RSRS (阻力支撑相对强度) 指标
        返回: (zscore, slope)
        """
        try:
            if len(df) < n + m:
                return 0.0, 0.0

            # 1. 计算斜率序列 (Slope)
            # 为了性能，只计算最近 M+1 个斜率用于标准化
            slopes = []
            highs = df["high"].values
            lows = df["low"].values

            # 使用 rolling window 计算斜率
            for i in range(len(df) - m, len(df)):
                y = highs[i - n + 1 : i + 1]
                x = lows[i - n + 1 : i + 1]
                slope = np.polyfit(x, y, 1)[0]
                slopes.append(slope)

            # 2. 标准化 (Z-Score)
            curr_slope = slopes[-1]
            history_slopes = np.array(slopes)
            mean_s = np.mean(history_slopes)
            std_s = np.std(history_slopes)

            zscore = (curr_slope - mean_s) / std_s if std_s != 0 else 0
            return round(zscore, 3), round(curr_slope, 3)
        except Exception as e:
            app_logger.warning(f"RSRS 计算失败: {e}")
            return 0.0, 0.0

    def detect_obv_accumulation(self, symbol: str, df: pd.DataFrame) -> list:
        """
        [NEW] OBV 低位吸筹检测入口，保持与 QuantWorker 兼容
        """
        if self.check_accumulation(df):
            # 获取最近一根 K 线的时间
            last_time = df.iloc[-1]["datetime"] if not df.empty else ""
            return [{"level": "日线", "time": last_time}]
        return []

    def check_accumulation(self, df: pd.DataFrame, end_idx: int = None) -> bool:
        try:
            if "OBV" not in df.columns:
                df.ta.obv(append=True)
            curr = df if end_idx is None else df.iloc[: end_idx + 1]
            if len(curr) < 20:
                return False
            r20 = curr.iloc[-20:]
            vty = (r20["high"].max() - r20["low"].min()) / (r20["low"].min() + 1e-9)
            if vty < 0.10:
                return r20["OBV"].rolling(5).mean().iloc[-1] > r20["OBV"].mean() * 1.05
            return False
        except Exception:
            return False

    def get_bbands_position_desc(self, df: pd.DataFrame) -> str:
        """价格相对于布林带的位置，用 emoji 简洁标注"""
        try:
            tmp = df.copy()
            tmp.ta.bbands(length=20, std=2, append=True)
            bbl = [c for c in tmp.columns if c.startswith("BBL_")]
            bbu = [c for c in tmp.columns if c.startswith("BBU_")]
            bbb = [c for c in tmp.columns if c.startswith("BBB_")]
            if not bbl or not bbu:
                return " 🟡 中位震荡"
            c = tmp["close"].iloc[-1]
            lower_band = tmp[bbl[0]].iloc[-1]
            upper_band = tmp[bbu[0]].iloc[-1]
            is_sq = (
                len(tmp) >= 100
                and bbb
                and tmp[bbb[0]].iloc[-1] <= tmp[bbb[0]].iloc[-100:].min() * 1.05
            )
            sq = "-变盘" if is_sq else ""
            if c <= lower_band * 1.008:
                return f" 🟢 下轨支撑{sq}"
            elif c >= upper_band * 0.992:
                return f" 🔴 上轨阻力{sq}"
            else:
                return f" 🟡 中位震荡{sq}"
        except Exception:
            return ""

    def calculate_comprehensive_indicators(self, df: pd.DataFrame) -> dict:
        """计算核心技术指标并返回易读的汇总，用于微信推送描述"""
        if df.empty or len(df) < 60:
            return {}
        try:
            res = {}
            # 1. 均线分析 (EMA5, 10, 20, 60)
            df.ta.ema(length=5, append=True)
            df.ta.ema(length=10, append=True)
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=60, append=True)

            c = df["close"].iloc[-1]
            e5, e10, e20, e60 = (
                df["EMA_5"].iloc[-1],
                df["EMA_10"].iloc[-1],
                df["EMA_20"].iloc[-1],
                df["EMA_60"].iloc[-1],
            )

            # 判断大趋势
            if c > e20 > e60:
                res["trend"] = "🔴 多头"
            elif c < e20 < e60:
                res["trend"] = "🟢 空头"
            else:
                res["trend"] = "🟡 震荡"

            # 压力支撑位提示
            if c > e5 > e10:
                res["support"] = f"EMA5 ({e5:.2f})"
            elif c < e5:
                res["resistance"] = f"EMA5 ({e5:.2f})"

            # 2. RSI 分析
            df.ta.rsi(length=14, append=True)
            rsi = df["RSI_14"].iloc[-1]
            if rsi > 70:
                res["strength"] = "🔥 极强/超买"
            elif rsi < 30:
                res["strength"] = "❄️ 极弱/超卖"
            else:
                res["strength"] = f"⚡ 强弱度:{rsi:.0f}"

            # 3. 成交量脉冲 (Volume Pulse)
            vol_avg20 = df["volume"].rolling(20).mean().iloc[-1]
            vol_curr = df["volume"].iloc[-1]
            if vol_curr > vol_avg20 * 2.0:
                res["pulse"] = f"🚀 异常放量 (x{vol_curr / vol_avg20:.1f})"

            return res
        except Exception as e:
            app_logger.warning(f"指标计算异常: {e}")
            return {}

    def get_market_relative_strength(self) -> float:
        """获取个股相对于大盘的强弱。当前取上证指数 (sh000001) 同比涨跌幅。"""
        try:
            idx_symbol = "000001"
            idx_market = 1  # SH

            # 检查基准缓存 (1分钟有效期)
            import time

            now_ts = time.time()
            if "benchmark" in self._market_benchmark_cache:
                cache_val, ts = self._market_benchmark_cache["benchmark"]
                if now_ts - ts < 60:
                    return cache_val

            idx_info = self.get_latest_price_info(idx_symbol, idx_market)
            idx_pct = idx_info.get("pct", 0.0)
            self._market_benchmark_cache["benchmark"] = (idx_pct, now_ts)
            return idx_pct
        except Exception:
            return 0.0

    def calculate_intensity_score(
        self, df: pd.DataFrame, signals: list[dict], end_idx: int = None
    ) -> int:
        """
        根据信号组合与技术面状态，计算利好/利空得分 [-5, 5]
        """
        if df.empty:
            return 0

        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 20:
            return 0

        score = 0
        signal_names = [s["name"] for s in signals]

        # 1. 核心信号权重
        if "MACD底背离" in signal_names:
            score += 3
        if "OBV碎步吸筹" in signal_names:
            score += 2

        # 2. 辅助技术面验证
        try:
            # 提高性能：如果列已经存在则不再重新计算整个 series
            if "RSI_14" not in df.columns:
                df.ta.rsi(length=14, append=True)
            if "EMA_5" not in df.columns:
                df.ta.ema(length=5, append=True)
            if "EMA_20" not in df.columns:
                df.ta.ema(length=20, append=True)
            if "EMA_60" not in df.columns:
                df.ta.ema(length=60, append=True)

            rsi = (
                df["RSI_14"].iloc[end_idx]
                if end_idx is not None
                else df["RSI_14"].iloc[-1]
            )
            if rsi < 30:
                score += 1  # 超卖区增加反弹概率
            elif rsi > 70:
                score -= 1  # 超买区风险

            # 均线多头排列验证 (EMA5 > 10 > 20 > 60)
            c = curr["close"].iloc[-1]
            e5 = (
                df["EMA_5"].iloc[end_idx]
                if end_idx is not None
                else df["EMA_5"].iloc[-1]
            )
            e20 = (
                df["EMA_20"].iloc[end_idx]
                if end_idx is not None
                else df["EMA_20"].iloc[-1]
            )
            e60 = (
                df["EMA_60"].iloc[end_idx]
                if end_idx is not None
                else df["EMA_60"].iloc[-1]
            )

            if c > e5 > e20 > e60:
                score += 1
            elif c < e5 < e20 < e60:
                score -= 3  # 极弱势

            # 3. RSRS 评分
            z, s = self.calculate_rsrs(curr)
            if z > 0.7:
                score += 1
            elif z < -0.7:
                score -= 1
        except Exception:
            pass

        # 限制范围在 [-5, 5]
        return max(-5, min(5, score))

    def calculate_market_sentiment_factor(self) -> tuple[float, str]:
        """
        计算市场环境因子评分 [-3, 1.5]
        """
        sentiment = market_manager.get_sentiment()
        up_ratio = sentiment.up_ratio

        # 优化为更平稳且梯度鲜明的反馈
        if up_ratio > 0.8:
            return 1.5, "🔥 极佳/普涨牛市"
        if up_ratio > 0.6:
            return 1.0, "🔴 偏强/赚钱效应好"
        if up_ratio > 0.4:
            return 0.0, "🟡 中性/存量博弈"
        if up_ratio > 0.2:
            return -1.5, "🟢 偏弱/亏钱效应"
        return -3.0, "❄️ 极弱/恐慌普跌"

    def calculate_intensity_score_with_symbol(
        self, symbol: str, df: pd.DataFrame, signals: list[dict]
    ) -> tuple[int, dict]:
        """
        扩展版评分逻辑：支持传入 symbol 进行综合审计（财务、资金、环境）
        返回: (最终总分, 审计详情字典)
        """
        base_score = self.calculate_intensity_score(df, signals)

        # 1. 环境因子 (Market Sentiment)
        m_factor, m_desc = self.calculate_market_sentiment_factor()

        # 2. 资金流因子 (Money Flow)
        buy, sell, net = self.fetch_large_orders_flow(symbol)
        flow_factor = 0
        if buy + sell > 0:
            ratio = net / (buy + sell)
            if ratio > 0.15:
                flow_factor = 1.0  # 净流入显著
            elif ratio < -0.15:
                flow_factor = -1.5  # 净流出显著

        # 3. 财务审计 (Fundamental)
        audit = self.fin_filter.get_financial_audit(symbol)

        # 4. 综合总分计算
        # 总分 = 技术得分 + 环境因子 + 资金因子 + 财务偏移
        final_score = base_score + m_factor + flow_factor + audit.get("score_offset", 0)

        # 5. 核心风控熔断逻辑
        # 财务风险等级：红色禁止评分超过0
        if audit.get("rating") == "🔴":
            final_score = min(0, final_score)

        # 市场系统性风险：强制不发出强力买入建议 (超过0分)
        if m_factor <= -3.0:
            final_score = min(-1.0, final_score)

        audit["market_sentiment"] = {"factor": m_factor, "desc": m_desc}
        audit["money_flow"] = {
            "buy": buy,
            "sell": sell,
            "net": net,
            "factor": flow_factor,
        }

        return int(max(-5, min(5, final_score))), audit

    def get_latest_price_info(self, symbol: str, market: int = None) -> dict:
        """获取最新价格和涨跌幅（从日线K线计算）"""
        try:
            df = self.fetch_bars(symbol, market, category=9, offset=3)
            if df.empty or len(df) < 2:
                return {}
            now = df.iloc[-1]["close"]
            prev = df.iloc[-2]["close"]
            pct = ((now - prev) / prev * 100) if prev != 0 else 0
            return {"price": now, "pct": pct}
        except Exception:
            return {}

    def scan_all_timeframes(self, symbol: str, market: int = None) -> list[dict]:
        """全量扫描，按大周期→小周期排序返回"""
        results = []
        for tf, cat in self.FreqMap.items():
            try:
                df = self.fetch_bars(symbol, market, cat, offset=250)
                if df.empty or len(df) < 50:
                    continue
                df.ta.macd(append=True)
                pos = self.get_bbands_position_desc(df)
                if self.check_macd_bullish_divergence(df):
                    results.append(
                        {"tf": tf, "category": cat, "name": "MACD底背离", "desc": pos}
                    )
                if cat in (3, 9) and self.check_accumulation(df):
                    results.append(
                        {
                            "tf": tf,
                            "category": cat,
                            "name": "OBV碎步吸筹",
                            "desc": f"(主力蓄势){pos}",
                        }
                    )

                # 3. RSRS 择时信号
                z, _ = self.calculate_rsrs(df)
                if z > 1.0:
                    results.append(
                        {
                            "tf": tf,
                            "category": cat,
                            "name": "RSRS极强",
                            "desc": f"阻力极小(Z:{z})",
                        }
                    )
                elif z > 0.7:
                    results.append(
                        {
                            "tf": tf,
                            "category": cat,
                            "name": "RSRS走强",
                            "desc": f"突破压力(Z:{z})",
                        }
                    )
            except Exception as e:
                app_logger.error(f"周期 {tf} 扫描异常 [{symbol}]: {e}")

        # 按大周期到小周期排序：daily > 60m > 30m > 15m
        order = {"daily": 0, "60m": 1, "30m": 2, "15m": 3}
        return sorted(results, key=lambda x: order.get(x["tf"], 9))

    def _find_subsequence(self, full_seq: list, sub_seq: list) -> int:
        """
        在 full_seq 中反向查找 sub_seq，返回 sub_seq 结束位置的索引。
        即返回 full_seq 中全新数据的起始偏移量。
        如果没找到，返回 -1。
        """
        if not sub_seq:
            return 0
        n = len(full_seq)
        m = len(sub_seq)
        if m > n:
            return -1
        # 从后往前匹配（增量数据在最后）
        for i in range(n - m, -1, -1):
            if full_seq[i : i + m] == sub_seq:
                return i + m
        return -1

    def fetch_large_orders_flow(self, code: str) -> tuple[float, float, float]:
        """
        获取单只股票从当日开盘起的所有主动大单买入/卖出量 (单位：手)
        过滤条件：仅统计单笔 >= 100手的成交记录。
        """
        if self.client is None:
            return (0.0, 0.0, 0.0)

        try:
            if not code.startswith(("sh", "sz")):
                return (0.0, 0.0, 0.0)

            market = 1 if code.startswith("sh") else 0
            pure_code = code[2:]
            today = time.strftime("%Y-%m-%d")

            # 初始化或重置日期缓存（每天开盘清零）
            is_first_fetch = False
            if (
                code not in self._large_order_cache
                or self._large_order_cache[code]["last_date"] != today
            ):
                self._large_order_cache[code] = {
                    "last_tail": [],  # 上次处理结果的末尾 N 条记录（用于精确匹配增量）
                    "buy_vol": 0.0,
                    "sell_vol": 0.0,
                    # 最近6次调用的增量（默认刷新5秒→约6次=30秒窗口）
                    "buy_deltas": deque([0.0] * 6, maxlen=6),
                    "sell_deltas": deque([0.0] * 6, maxlen=6),
                    "last_date": today,
                }
                is_first_fetch = True

            cache = self._large_order_cache[code]

            # 记录调用前的大单量，用于计算本次增量
            buy_before = cache["buy_vol"]
            sell_before = cache["sell_vol"]

            BATCH_SIZE = 2000

            if is_first_fetch:
                # ====== 首次拉取：循环获取全量当日数据 ======
                dfs = []
                offset = 0
                while True:
                    df = self.client.transaction(
                        symbol=pure_code, market=market, start=offset, count=BATCH_SIZE
                    )
                    if df is None or df.empty:
                        break

                    # 正确的分页累进，API实际返回长度决定 offset 的推移
                    actual_count = len(df)
                    dfs.append(df)

                    if actual_count < 500:
                        break

                    offset += actual_count
                    if offset >= 50000:
                        break

                if not dfs:
                    app_logger.debug(f"{code} 首次大单获取无结果，尝试使用历史缓存")
                    return (cache.get("buy_vol", 0.0), cache.get("sell_vol", 0.0), 0.0)

                full_df = pd.concat(dfs[::-1], ignore_index=True)

                # 统计所有大单 (真实金额超过 50万 人民币)
                full_df = full_df[full_df["time"] >= "09:15"]
                full_df["amount"] = full_df["price"] * full_df["vol"] * 100
                big_orders = full_df[full_df["amount"] >= 500000]
                if not big_orders.empty:
                    cache["buy_vol"] = float(
                        big_orders[big_orders["buyorsell"] == 0]["amount"].sum()
                    )
                    cache["sell_vol"] = float(
                        big_orders[big_orders["buyorsell"] == 1]["amount"].sum()
                    )

                # 记录最后 10 条的指纹
                tail_records = (
                    full_df[["time", "vol", "buyorsell"]].tail(10).values.tolist()
                )
                cache["last_tail"] = tail_records

                app_logger.debug(
                    f"{code} 首次大单总条数{len(full_df)}，买{cache['buy_vol']:.0f}卖{cache['sell_vol']:.0f}"
                )

            else:
                # ====== 增量拉取：只请求最新 batch，倒序匹配 ======
                df = self.client.transaction(
                    symbol=pure_code, market=market, start=0, count=BATCH_SIZE
                )

                if df is None or df.empty:
                    cache["buy_deltas"].append(0.0)
                    cache["sell_deltas"].append(0.0)
                    return (
                        cache["buy_vol"],
                        cache["sell_vol"],
                        sum(cache["buy_deltas"]) - sum(cache["sell_deltas"]),
                    )

                new_records = df[["time", "vol", "buyorsell"]].values.tolist()
                last_tail = cache["last_tail"]

                start_idx = self._find_subsequence(new_records, last_tail)

                if start_idx == -1:
                    app_logger.warning(
                        f"{code} 增量匹配失败(指纹断层)，重置缓存下回合拉全量"
                    )
                    self._large_order_cache.pop(code, None)
                    cache["buy_deltas"].append(0.0)
                    cache["sell_deltas"].append(0.0)
                    return (
                        cache["buy_vol"],
                        cache["sell_vol"],
                        sum(cache["buy_deltas"]) - sum(cache["sell_deltas"]),
                    )

                new_added_df = df.iloc[start_idx:]

                if not new_added_df.empty:
                    new_added_df = new_added_df.copy()
                    new_added_df = new_added_df[new_added_df["time"] >= "09:15"]
                    new_added_df["amount"] = (
                        new_added_df["price"] * new_added_df["vol"] * 100
                    )
                    big_orders = new_added_df[new_added_df["amount"] >= 500000]
                    if not big_orders.empty:
                        cache["buy_vol"] += float(
                            big_orders[big_orders["buyorsell"] == 0]["amount"].sum()
                        )
                        cache["sell_vol"] += float(
                            big_orders[big_orders["buyorsell"] == 1]["amount"].sum()
                        )

                    cache["last_tail"] = (
                        df[["time", "vol", "buyorsell"]].tail(10).values.tolist()
                    )

                delta_buy = cache["buy_vol"] - buy_before
                delta_sell = cache["sell_vol"] - sell_before
                cache["buy_deltas"].append(delta_buy)
                cache["sell_deltas"].append(delta_sell)

            recent_net = sum(cache["buy_deltas"]) - sum(cache["sell_deltas"])
            return (cache["buy_vol"], cache["sell_vol"], recent_net)

        except Exception as e:
            app_logger.warning(f"获取 {code} 全量大单数据失败: {e}")
            cached = self._large_order_cache.get(code, {})
            return (cached.get("buy_vol", 0.0), cached.get("sell_vol", 0.0), 0.0)
