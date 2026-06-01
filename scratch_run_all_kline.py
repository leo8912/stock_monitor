import os
import re
import subprocess

stocks = [
    {"code": "000559", "name": "万向钱潮"},
    {"code": "600879", "name": "航天电子"},
    {"code": "605296", "name": "神农集团"},
    {"code": "688110", "name": "东芯股份"},
    {"code": "600452", "name": "涪陵电力"},
    {"code": "002384", "name": "东山精密"},
]

out_dir = r"C:\Users\leo89\.gemini\antigravity-ide\brain\b834177c-eb63-4be2-97da-5bb29fbac8d9\scratch"
os.makedirs(out_dir, exist_ok=True)

# 确保中文字符不报错
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

master_report = []

print("=" * 60)
print("开始运行批量 K线与量能 深度分析...")
print("=" * 60)

for s in stocks:
    code = s["code"]
    name = s["name"]
    print(f"正在分析 {name} ({code})...")

    cmd = [
        r"d:\code\stock\.venv\Scripts\python.exe",
        r"skills/a-stock-kline-analyzer/scripts/kline_analyzer.py",
        "--code",
        code,
        "--days",
        "30",
        "--realtime",
        "--report",
    ]

    try:
        res = subprocess.run(cmd, env=env, capture_output=True, check=True)
        report_text = res.stdout.decode("utf-8", errors="ignore")

        # 保存详细报告文本
        report_file = os.path.join(out_dir, f"report_{code}.txt")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_text)

        # 提取关键信息
        # 1. 价格和涨跌幅
        price_match = re.search(r"最新价:\s*([\d\.]+)\s*元", report_text)
        change_match = re.search(r"涨跌幅:\s*([-\+\d\.]+)%", report_text)

        # 2. 技术评分
        score_match = re.search(r"技术评分:\s*([-\+\d\.]+)\s*分", report_text)

        # 3. 综合判断
        judgment_match = re.search(r"综合判断:\s*([^\s]+)", report_text)

        # 4. 操作建议
        advice_match = re.search(r"操作建议\s*─+\s*([^\n]+)", report_text)
        if not advice_match:
            # 兼容不同版本正则
            advice_match = re.search(
                r"【八、综合判断与操作建议】\s*\n\s*8.1 结论\s*─+\s*综合判断:\s*[^\n]+\n\s*判断说明:\s*[^\n]+\n\s*明日预测:\s*[^\n]+\n\s*8.2 操作建议\s*─+\s*([^\n]+)",
                report_text,
            )

        # 5. MACD, RSI, MA
        macd_match = re.search(r"MACD:\s*([^\n]+)", report_text)
        rsi_match = re.search(r"RSI\(14\):\s*([^\n]+)", report_text)

        price = price_match.group(1) if price_match else "N/A"
        change = change_match.group(1) if change_match else "N/A"
        score = score_match.group(1) if score_match else "0.0"
        judgment = judgment_match.group(1).strip() if judgment_match else "中性"
        advice = advice_match.group(1).strip() if advice_match else "观望"
        macd_sig = macd_match.group(1).strip() if macd_match else "N/A"
        rsi_val = rsi_match.group(1).strip() if rsi_match else "N/A"

        # 提取K线形态
        shapes = []
        shape_rows = re.findall(
            r"│\s*(\d{4}-\d{2}-\d{2})\s*│\s*([^\s│]+)\s*│\s*([^\s│]+)\s*│", report_text
        )
        for row in shape_rows[:2]:  # 最近两个形态
            shapes.append(f"{row[0]} {row[1]}({row[2]})")
        shapes_str = " | ".join(shapes) if shapes else "无明显形态"

        # 提取量能
        vol_match = re.search(r"量比\s*│\s*([\d\.]+)", report_text)
        vol_ratio = vol_match.group(1) if vol_match else "N/A"

        master_report.append(
            {
                "code": code,
                "name": name,
                "price": price,
                "change": change,
                "score": score,
                "judgment": judgment,
                "advice": advice,
                "macd": macd_sig,
                "rsi": rsi_val,
                "shapes": shapes_str,
                "vol_ratio": vol_ratio,
            }
        )
        print(f"Success: {name} completed")

    except Exception as e:
        print(f"Failed: {name} error: {e}")
        # 如果获取出错，提供占位
        master_report.append(
            {
                "code": code,
                "name": name,
                "price": "获取失败",
                "change": "N/A",
                "score": "0.0",
                "judgment": "未知",
                "advice": "失败重试",
                "macd": "N/A",
                "rsi": "N/A",
                "shapes": "N/A",
                "vol_ratio": "N/A",
            }
        )

# 写入汇总Markdown报告
md_path = r"C:\Users\leo89\.gemini\antigravity-ide\brain\b834177c-eb63-4be2-97da-5bb29fbac8d9\K线与量能技术分析汇总报告.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# 📊 6只关注股 K线指标与量能深度复盘汇总报告\n\n")
    f.write(
        "本报告由量化智能体调用 `a-stock-kline-analyzer` (A股K线分析工具v1.0.6) 自动生成，融合了实时行情、量能比对、多空技术指标（MA/MACD/RSI/布林带）及K线形态识别。\n\n"
    )

    f.write("## 📈 核心指标一览表\n\n")
    f.write(
        "| 股票代码/名称 | 最新价 | 今日涨跌幅 | 技术评分 | 综合多空判断 | 成交量比 | 核心操作建议 |\n"
    )
    f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |\n")
    for r in master_report:
        f.write(
            f"| **{r['name']} ({r['code']})** | {r['price']} | {r['change']}% | **{r['score']}** | {r['judgment']} | {r['vol_ratio']} | {r['advice']} |\n"
        )

    f.write("\n---\n\n")
    f.write("## 🔍 个股技术面/量能深度点评\n\n")

    for r in master_report:
        code = r["code"]
        name = r["name"]
        f.write(f"### 📍 {name} ({code})\n")
        f.write(
            f"* **基本量化指标**: 现价 **{r['price']}元**，今日涨幅 **{r['change']}%**，中期强弱度 RSI **{r['rsi']}**，MACD **{r['macd']}**。\n"
        )
        f.write(f"* **量能状态 (量比: {r['vol_ratio']})**: ")
        ratio_f = float(r["vol_ratio"]) if r["vol_ratio"] != "N/A" else 1.0
        if ratio_f > 1.5:
            f.write(
                "量比大于1.5，呈现**放量**特征，多空资金博弈激烈，主力有介入迹象。\n"
            )
        elif ratio_f < 0.7:
            f.write(
                "量比小于0.7，呈现**缩量**特征，市场关注度降温，呈无量震荡阴跌态势。\n"
            )
        else:
            f.write("量能处于正常区间，未见明显放量或缩量异动，趋势延续概率大。\n")

        f.write(f"* **近期K线识别形态**: `{r['shapes']}`\n")

        score_f = float(r["score"])
        f.write(f"* **技术分析评分**: **{r['score']}分** (评分区间: -5 至 +5)\n")
        f.write("* **综合评级 & 指引**: ")
        if score_f > 4.0:
            f.write(
                "> [!TIP]\n> **强烈看多**。多项趋势与动能指标共振向上，主力扫货强劲，回踩支撑即为买点。建议**持有或加仓**。\n"
            )
        elif score_f > 1.0:
            f.write(
                "> [!NOTE]\n> **温和看多/偏多**。多数指标积极，下有核心支撑，形态良性，建议**持有/低吸**。\n"
            )
        elif score_f < -1.0:
            f.write(
                "> [!WARNING]\n> **偏空/破位**。指标出现死叉或破位下行，均线空头排列。建议**果断减仓/防守避险**。\n"
            )
        else:
            f.write(
                "> [!IMPORTANT]\n> **中性偏空**。趋势多空均衡或微弱偏空，建议**观望，控制仓位**。\n"
            )
        f.write("\n\n")

print(f"汇总报告生成成功，文件路径: {md_path}")
