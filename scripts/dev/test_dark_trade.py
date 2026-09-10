"""测试暗盘资金数据获取"""

from datetime import datetime

from stock_monitor.services.dark_trade.service import (
    build_net_flow_index,
    fetch_all_dark_trade,
)

today = datetime.now().strftime("%Y%m%d")
print(f"Testing dark trade fetch for {today}...")

records = fetch_all_dark_trade(today)
print(f"Total records: {len(records)}")

if records:
    for i, r in enumerate(records[:3]):
        code = r.get("4", "?")
        name = r.get("0", "?")
        net = r.get("6", 0)
        print(f"  Record {i+1}: code={code}, name={name}, net_flow={net}")

    index = build_net_flow_index(records)
    print(f"\nIndexed {len(index)} stocks")

    sorted_items = sorted(index.items(), key=lambda x: x[1], reverse=True)[:5]
    print("Top 5 by net flow (wan):")
    for code, flow in sorted_items:
        print(f"  {code}: {flow:.2f} wan")
else:
    print("No records returned - API may be unavailable!")
