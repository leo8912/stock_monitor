import easyquotation


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# 测试获取市场数据的方法
try:
    q = easyquotation.use("sina")
    data = q.market_snapshot(prefix=True)
except Exception as e:
    raise SystemExit(f"获取行情失败（网络/引擎错误）: {e}") from e

if not data:
    raise SystemExit("行情数据为空")

up = 0
down = 0
flat = 0
total = 0

for _code, stock in data.items():
    name = stock.get("name", "")
    # 跳过指数类数据，只统计个股
    if "指数" in name or "Ａ股" in name:
        continue

    close = _to_float(stock.get("close", 0))
    now = _to_float(stock.get("now", 0))

    if close == 0:
        flat += 1
    elif now > close:
        up += 1
    elif now < close:
        down += 1
    else:
        flat += 1

    total += 1

print(f"上涨: {up}, 下跌: {down}, 平盘: {flat}, 总计: {total}")
if total > 0:
    print(
        f"上涨比例: {up / total * 100:.2f}%, 下跌比例: {down / total * 100:.2f}%, 平盘比例: {flat / total * 100:.2f}%"
    )
