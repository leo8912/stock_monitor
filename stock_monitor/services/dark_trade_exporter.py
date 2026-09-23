"""
暗盘资金数据 CSV 导出模块

收盘后生成一份全市场暗盘数据 CSV（东方财富「暗盘 + 明盘」口径），
便于其它工具/脚本直接处理。产品最终选择 CSV 方案（见 CHANGELOG），
因此不再提供 Excel 多 Sheet 导出。
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from stock_monitor.services.dark_trade.service import (
    DARKTRADE_TIMEOUT,
    _http_client,
    fetch_all_dark_trade,
)
from stock_monitor.services.dark_trade.utils import get_recent_trade_dates
from stock_monitor.utils.helpers import safe_float
from stock_monitor.utils.logger import app_logger

# ── 明盘行情API（东方财富市场实时数据）──────────────────────────────────────
_QUOTE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

# CSV 表头（历史净流入日期列在运行时追加）
_BASE_HEADERS = [
    "代码",
    "市场",
    "名称",
    "收盘价",
    "涨跌幅%",
    "成交量(万股)",
    "成交额(亿)",
    "暗盘净流入(万)",
    "明盘净流入(万)",
    "主力净流入合计(万)",
    "暗盘活跃度",
    "换手率%",
    "板块1",
    "板块2",
    "连续流入天数",
]


def _to_float(value, default: float = 0.0) -> float:
    """容错地把值转换为 float，失败返回默认值（共享实现见 utils.helpers.safe_float）。"""
    return safe_float(value, default)


def fetch_market_quotes_all() -> dict[str, dict]:
    """
    批量获取全市场 A 股明盘行情（收盘价、涨跌幅、成交量、成交额）
    返回: {code(6位): {close, pct_chg, volume, amount, ...}}
    """
    result: dict[str, dict] = {}
    # 分两个市场：上海(1) + 深圳(0)
    for fs in ["m:1+t:2,m:1+t:23", "m:0+t:6,m:0+t:80,m:0+t:81"]:
        pn = 1
        while True:
            params = {
                "pn": pn,
                "pz": 1000,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": fs,
                "fields": "f12,f14,f2,f3,f5,f6",
                # f12=代码 f14=名称 f2=收盘价 f3=涨跌幅 f5=成交量(手) f6=成交额
            }
            try:
                resp = _http_client.get(
                    _QUOTE_URL,
                    params=params,
                    headers=_HEADERS,
                    timeout=DARKTRADE_TIMEOUT,
                )
                if resp is None:
                    app_logger.warning(
                        f"[DarkExport] 获取明盘行情第{pn}页失败: request failed"
                    )
                    break
                data = resp.json().get("data", {}) or {}
                diff = data.get("diff", [])
            except Exception as e:
                app_logger.warning(f"[DarkExport] 获取明盘行情第{pn}页失败: {e}")
                break

            for item in diff:
                code = str(item.get("f12", "")).zfill(6)
                if code:
                    result[code] = {
                        "name": item.get("f14", ""),
                        "close": item.get("f2", 0),
                        "pct_chg": item.get("f3", 0),
                        "volume": item.get("f5", 0),  # 手
                        "amount": item.get("f6", 0),  # 元
                    }

            if len(diff) < 1000:
                break
            pn += 1
            if pn > 20:
                break

    app_logger.info(f"[DarkExport] 明盘行情获取完成: {len(result)} 只股票")
    return result


def _build_history_net(history_records: dict) -> dict:
    """构建历史净流入索引 {date: {code: net_wan}}（万元）。"""
    history_net: dict[str, dict[str, float]] = {}
    for d, recs in history_records.items():
        idx: dict[str, float] = {}
        for r in recs:
            code = r.get("4", "")
            if code:
                idx[code] = _to_float(r.get("6", 0)) / 10000
        history_net[d] = idx
    return history_net


def _calc_consecutive(hist_nets: list) -> int:
    """从最近日期起计算连续同向天数（流入为正、流出为负）。"""
    if not hist_nets or hist_nets[0] is None:
        return 0
    consecutive = 0
    if hist_nets[0] > 0:
        for v in hist_nets:
            if v is not None and v > 0:
                consecutive += 1
            else:
                break
    elif hist_nets[0] < 0:
        for v in hist_nets:
            if v is not None and v < 0:
                consecutive -= 1
            else:
                break
    return consecutive


def _build_row(r: dict, quote_map: dict, recent_dates: list, history_net: dict) -> dict:
    """将单条暗盘记录扩展为完整数据行。"""
    code = r.get("4", "")
    market_pfx = "SH" if r.get("3", 0) == 1 else "SZ"
    q = quote_map.get(code, {})

    # 暗盘净流入 = field "6"（万元）
    dark_net_wan = _to_float(r.get("6", 0)) / 10000
    # 明盘净流入 = field "7"（万元）
    regular_net_wan = _to_float(r.get("7", 0)) / 10000
    # 主力净流入合计 = field "8" = 暗盘 + 明盘（万元）
    total_net_wan = _to_float(r.get("8", 0)) / 10000
    activity = _to_float(r.get("11", 0))
    turnover = _to_float(r.get("14", 0))

    hist_nets = [history_net.get(d, {}).get(code, None) for d in recent_dates]

    return {
        "code": code,
        "market": market_pfx,
        "name": q.get("name", r.get("16", "")),
        "close": q.get("close", ""),
        "pct_chg": q.get("pct_chg", ""),
        # 手→万股
        "volume_wan": q.get("volume", 0) / 100 if q.get("volume") else "",
        # 元→亿
        "amount_yi": q.get("amount", 0) / 1e8 if q.get("amount") else "",
        "dark_net": dark_net_wan,
        "regular_net": regular_net_wan,
        "total_net": total_net_wan,
        "activity": activity,
        "turnover": turnover,
        "sector1": r.get("17", ""),
        "sector2": r.get("18", ""),
        "hist_nets": hist_nets,
        "consecutive": _calc_consecutive(hist_nets),
    }


def _build_headers(recent_dates: list) -> list:
    """构建 CSV 表头（追加最近 N 日净流入列）。"""
    headers = list(_BASE_HEADERS)
    for d in recent_dates:
        dt = datetime.strptime(d, "%Y%m%d")
        headers.append(f"{dt.month}/{dt.day}净流入(万)")
    return headers


def _row_values(row: dict) -> list:
    """将数据行转换为 CSV 写出值列表。"""
    vol = row["volume_wan"]
    amt = row["amount_yi"]
    turnover = row["turnover"]
    values = [
        row["code"],
        row["market"],
        row["name"],
        row["close"] if row["close"] != "" else "",
        row["pct_chg"] if row["pct_chg"] != "" else "",
        round(float(vol), 2) if vol != "" else "",
        round(float(amt), 4) if amt != "" else "",
        round(row["dark_net"], 2),
        round(row["regular_net"], 2),
        round(row["total_net"], 2),
        round(row["activity"], 4),
        round(turnover * 100, 2) if turnover is not None else "",
        row["sector1"],
        row["sector2"],
        row["consecutive"],
    ]
    values.extend(round(v, 2) if v is not None else "" for v in row["hist_nets"])
    return values


def export_dark_trade_csv(
    watchlist_codes: list,
    output_path=None,
    history_days: int = 5,
) -> Path:
    """
    收盘后导出暗盘数据CSV

    Args:
        watchlist_codes: 自选股代码列表（参数保留以兼容调用方；CSV 为**全市场**
            导出，不做自选股过滤）。
        output_path:    输出文件路径，默认 analysis_reports/dark_trade_YYYYMMDD.csv
        history_days:   历史天数（近N天的净流入数据列）

    Returns:
        实际保存的 Path 对象
    """
    today_str = datetime.now().strftime("%Y%m%d")

    if output_path is None:
        out_dir = Path("analysis_reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"dark_trade_{today_str}.csv"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    app_logger.info("[DarkExport] 开始生成暗盘CSV报表...")

    # ── 1. 抓取今日全量暗盘数据 ──────────────────────────────────────────────
    today_records = fetch_all_dark_trade(today_str)
    app_logger.info(f"[DarkExport] 今日暗盘记录: {len(today_records)} 条")

    # ── 2. 抓取近N-1天历史数据（今天已有，再取前N-1天）───────────────────────
    recent_dates = get_recent_trade_dates(history_days)  # [今天, 昨天, ...]
    history_records: dict[str, list[dict]] = {today_str: today_records}
    for d in recent_dates[1:]:
        try:
            recs = fetch_all_dark_trade(d)
            history_records[d] = recs
            app_logger.info(f"[DarkExport] {d} 历史暗盘: {len(recs)} 条")
        except Exception as e:
            app_logger.warning(f"[DarkExport] {d} 历史抓取失败: {e}")
            history_records[d] = []

    # ── 3. 获取今日明盘行情 ──────────────────────────────────────────────────
    app_logger.info("[DarkExport] 抓取明盘行情...")
    quote_map = fetch_market_quotes_all()

    # ── 4. 构建完整数据行 ────────────────────────────────────────────────────
    history_net = _build_history_net(history_records)
    all_rows = [
        _build_row(r, quote_map, recent_dates, history_net) for r in today_records
    ]

    # ── 5. 写 CSV ───────────────────────────────────────────────────────────
    headers = _build_headers(recent_dates)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for row in all_rows:
            writer.writerow(_row_values(row))

    app_logger.info(f"[DarkExport] CSV已保存: {output_path}")
    return output_path
