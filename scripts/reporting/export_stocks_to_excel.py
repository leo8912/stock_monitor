"""开发脚本薄封装：核心实现已迁入 ``stock_monitor.services.reporting``。

打包/运行时一律从包内导入；本入口保留 CLI 用法::

    python scripts/reporting/export_stocks_to_excel.py --mode watchlist
"""

from __future__ import annotations

import os
import sys

# 以脚本方式直接运行时，确保仓库根目录在 sys.path 上
if __package__ in (None, ""):
    sys.path.append(os.getcwd())

from stock_monitor.services.reporting.export_stocks_to_excel import (  # noqa: E402,F401
    compute_indicators,
    export_to_excel,
    fetch_realtime_stocks,
    get_watchlist,
    main,
    resolve_stock_name,
)

if __name__ == "__main__":
    main()
