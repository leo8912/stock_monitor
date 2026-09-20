"""暗盘 CSV 导出回归测试（T09 死代码清理后行为不变）

以 mock 的数据源驱动 ``export_dark_trade_csv``，断言生成的 CSV 表头与数据行
与清理前一致（全市场导出、暗盘/明盘/合计净流入单位换算、历史净流入列、
连续流入天数）。
"""

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from stock_monitor.services import dark_trade_exporter as exporter


class TestExportDarkTradeCsv(unittest.TestCase):
    def test_csv_content_preserved(self):
        today_str = datetime.now().strftime("%Y%m%d")
        today_record = {
            "3": 1,  # 市场=上海
            "4": "600519",  # 代码
            "6": "50000",  # 暗盘净流入（元）
            "7": "20000",  # 明盘净流入（元）
            "8": "70000",  # 主力净流入合计（元）
            "11": "0.8",  # 暗盘活跃度
            "14": "0.05",  # 换手率
            "16": "贵州茅台",  # 名称
            "17": "白酒",  # 板块1
            "18": "消费",  # 板块2
        }

        def fake_fetch(date):
            # 仅今日有暗盘记录，历史为空
            return [today_record] if date == today_str else []

        quotes = {
            "600519": {
                "name": "贵州茅台",
                "close": 1800.0,
                "pct_chg": 1.5,
                "volume": 12345,  # 手
                "amount": 2.2e8,  # 元
            }
        }

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "dark.csv"
            with (
                patch.object(exporter, "fetch_all_dark_trade", side_effect=fake_fetch),
                patch.object(exporter, "fetch_market_quotes_all", return_value=quotes),
                patch.object(
                    exporter,
                    "_get_recent_trade_dates",
                    return_value=[today_str, "20200102"],
                ),
            ):
                result = exporter.export_dark_trade_csv(
                    ["sh600519"], output_path=out, history_days=2
                )
            self.assertEqual(result, out)
            self.assertTrue(out.exists())
            with open(out, encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))

        self.assertEqual(len(rows), 2)  # 表头 + 1 数据行
        headers, row = rows[0], rows[1]

        # 前 15 列为固定列，之后为历史净流入日期列
        self.assertEqual(headers[:15], exporter._BASE_HEADERS)
        self.assertEqual(len(headers), 15 + 2)

        self.assertEqual(row[0], "600519")
        self.assertEqual(row[1], "SH")
        self.assertEqual(row[2], "贵州茅台")
        self.assertEqual(row[3], "1800.0")
        self.assertEqual(row[5], "123.45")  # 12345/100 手→万股
        self.assertEqual(row[6], "2.2")  # 2.2e8/1e8 元→亿
        self.assertEqual(row[7], "5.0")  # 暗盘净流入 50000/10000
        self.assertEqual(row[8], "2.0")  # 明盘净流入 20000/10000
        self.assertEqual(row[9], "7.0")  # 合计 70000/10000
        self.assertEqual(row[11], "5.0")  # 换手率 0.05*100
        self.assertEqual(row[12], "白酒")
        self.assertEqual(row[13], "消费")
        self.assertEqual(row[14], "1")  # 连续流入天数（仅今日为正）
        self.assertEqual(row[15], "5.0")  # 今日净流入列
        self.assertEqual(row[16], "")  # 昨日无数据


if __name__ == "__main__":
    unittest.main()
