"""综合技术分析 - 领益智造和万向钱潮"""

import akshare as ak


def analyze_stock(symbol, name):
    """综合分析单只股票"""
    print(f'\n{"="*60}')
    print(f"分析：{symbol} {name}")
    print(f'{"="*60}')

    try:
        # 获取日线数据
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily", start_date="20251001", adjust="qfq"
        )

        if df.empty or len(df) < 60:
            print("数据不足")
            return

        df = df.rename(
            columns={
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )

        df.ta.macd(append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.obv(append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=5, append=True)
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=60, append=True)

        # ===== 1. MACD 底背离检测 (多周期) =====
        print("\n【1. MACD 底背离检测】")

        # 日线级别
        recent_30 = df.iloc[-30:]
        prev_30 = df.iloc[-60:-30]

        price_low_idx = recent_30["close"].idxmin()
        price_low_val = recent_30.loc[price_low_idx, "close"]
        macd_hist_at_low = recent_30.loc[price_low_idx, "MACDh_12_26_9"]

        prev_price_low_idx = prev_30["close"].idxmin()
        prev_price_low_val = prev_30.loc[prev_price_low_idx, "close"]
        prev_macd_hist_at_low = prev_30.loc[prev_price_low_idx, "MACDh_12_26_9"]

        daily_divergence = (
            price_low_val < prev_price_low_val
            and macd_hist_at_low > prev_macd_hist_at_low
        )

        print(f'  日线级别：{"✓ 出现底背离" if daily_divergence else "× 无底背离"}')
        print(
            f"    - 近期低价：{price_low_val:.2f} vs 前期低价：{prev_price_low_val:.2f}"
        )
        print(f"    - MACD 柱：{macd_hist_at_low:.4f} vs {prev_macd_hist_at_low:.4f}")

        # 60 分钟级别 (用日内数据模拟)
        if len(df) >= 120:
            recent_15 = df.iloc[-15:]
            prev_15 = df.iloc[-30:-15]

            p_low_15 = recent_15["close"].min()
            p_low_prev_15 = prev_15["close"].min()
            m_low_15 = recent_15["MACDh_12_26_9"].min()
            m_low_prev_15 = prev_15["MACDh_12_26_9"].min()

            m60_divergence = p_low_15 < p_low_prev_15 and m_low_15 > m_low_prev_15
            print(f'  短周期级别：{"✓ 出现底背离" if m60_divergence else "× 无底背离"}')
        else:
            m60_divergence = False
            print("  短周期级别：数据不足")

        # ===== 2. 布林带位置 =====
        print("\n【2. 布林带位置】")
        bbl_cols = [c for c in df.columns if c.startswith("BBL_")]
        bbu_cols = [c for c in df.columns if c.startswith("BBU_")]
        bbb_cols = [c for c in df.columns if c.startswith("BBB_")]

        if bbl_cols and bbu_cols:
            current_price = df["close"].iloc[-1]
            lower_band = df[bbl_cols[0]].iloc[-1]
            upper_band = df[bbu_cols[0]].iloc[-1]
            bb_width = df[bbb_cols[0]].iloc[-1] if bbb_cols else None

            position = ""
            if current_price <= lower_band * 1.008:
                position = "🟢 下轨支撑位"
            elif current_price >= upper_band * 0.992:
                position = "🔴 上轨阻力位"
            else:
                position = "🟡 中轨震荡区"

            print(f"  当前位置：{position}")
            print(
                f"  价格：{current_price:.2f}, 下轨：{lower_band:.2f}, 上轨：{upper_band:.2f}"
            )

            # 收口检测
            if bbb_cols and len(df) >= 100:
                min_bb_width = df[bbb_cols[0]].iloc[-100:].min()
                is_squeeze = bb_width <= min_bb_width * 1.05
                print(f'  布林带收口：{"✓ 是 (变盘前兆)" if is_squeeze else "× 否"}')

        # ===== 3. OBV 吸筹检测 =====
        print("\n【3. OBV 资金流向】")
        if "OBV" in df.columns:
            obv_recent = df["OBV"].iloc[-20:]
            obv_ma5 = obv_recent.rolling(5).mean().iloc[-1]
            obv_avg = obv_recent.mean()

            accumulation = obv_ma5 > obv_avg * 1.05
            print(f'  OBV 吸筹信号：{"✓ 是" if accumulation else "× 否"}')
            print(f"  OBV 5 日均：{obv_ma5:.0f}, 20 日均：{obv_avg:.0f}")

        # ===== 4. RSI 超卖检测 =====
        print("\n【4. RSI 强弱指标】")
        rsi = df["RSI_14"].iloc[-1]
        rsi_status = ""
        if rsi > 70:
            rsi_status = "🔥 超买区 (警惕回调)"
        elif rsi < 30:
            rsi_status = "❄️ 超卖区 (反弹概率高)"
        else:
            rsi_status = "⚡ 中性区"

        print(f"  RSI(14): {rsi:.1f} - {rsi_status}")

        # ===== 5. 均线系统 =====
        print("\n【5. 均线排列】")
        c = df["close"].iloc[-1]
        e5 = df["EMA_5"].iloc[-1]
        e10 = df["EMA_10"].iloc[-1]
        e20 = df["EMA_20"].iloc[-1]
        e60 = df["EMA_60"].iloc[-1]

        if c > e5 > e10 > e20 > e60:
            trend = "🔴 多头排列 (强势)"
        elif c < e5 < e10 < e20 < e60:
            trend = "🟢 空头排列 (弱势)"
        else:
            trend = "🟡 混乱排列 (震荡)"

        print(f"  趋势：{trend}")
        print(
            f"  价格：{c:.2f}, EMA5: {e5:.2f}, EMA10: {e10:.2f}, EMA20: {e20:.2f}, EMA60: {e60:.2f}"
        )

        # ===== 6. 综合评分 =====
        print("\n【6. 综合评分】")
        score = 0

        if daily_divergence:
            score += 3
        if m60_divergence:
            score += 2
        if accumulation:
            score += 2
        if rsi < 30:
            score += 2
        elif rsi < 40:
            score += 1
        if "下轨支撑" in position:
            score += 2

        print(f"  总分：{score}/10")

        if score >= 7:
            recommendation = "⭐⭐⭐ 强烈关注 (多重底背离 + 超卖)"
        elif score >= 5:
            recommendation = "⭐⭐ 值得关注 (存在底背离信号)"
        elif score >= 3:
            recommendation = "⭐ 观察为主 (信号不明确)"
        else:
            recommendation = "⚠️ 暂不关注 (无明确信号)"

        print(f"  建议：{recommendation}")

        return {
            "symbol": symbol,
            "name": name,
            "divergence_level": "日线"
            if daily_divergence
            else ("短周期" if m60_divergence else "无"),
            "score": score,
        }

    except Exception as e:
        print(f"分析失败：{e}")
        return None


# 分析两只股票
results = []
results.append(analyze_stock("002600", "领益智造"))
results.append(analyze_stock("000887", "万向钱潮"))

# 对比总结
print(f'\n\n{"="*60}')
print("【对比总结】")
print(f'{"="*60}')
for r in results:
    if r:
        print(
            f"{r['symbol']} {r['name']}: 背离级别={r['divergence_level']}, 评分={r['score']}/10"
        )
