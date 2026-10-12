"""开发脚本薄封装：核心实现已迁入 ``stock_monitor.services.reporting``。

打包/运行时一律从包内导入；本入口保留 CLI 用法::

    python scripts/reporting/export_stocks_to_excel.py --mode watchlist
"""

from __future__ import annotations

import sys

# 以脚本方式直接运行时，基于 __file__ 定位仓库根目录并置于 sys.path 最前，
# 避免依赖 CWD 或误用 site-packages 中的旧版本
if __package__ in (None, ""):
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
