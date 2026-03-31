from mootdx.quotes import Quotes

client = Quotes.factory(market="std")

# 获取 start=0 800条，了解时间范围
df0 = client.transaction(symbol="600519", market=1, start=0, count=800)
print(
    f"start=0  拿到 {len(df0)} 条, 时间范围: {df0['time'].iloc[0]} ~ {df0['time'].iloc[-1]}"
)

df1 = client.transaction(symbol="600519", market=1, start=800, count=800)
if not df1.empty:
    print(
        f"start=800 拿到 {len(df1)} 条, 时间范围: {df1['time'].iloc[0]} ~ {df1['time'].iloc[-1]}"
    )
    if len(df1) < 800:
        print("  => start=800 返回不足800条，说明当日总记录 < 1600")
else:
    print("start=800 返回空")

# 关键测试：用一个已知的 last_index 调用，看是否拿到更新的数据
# 先记录10秒等待，然后用之前的计数作为start
import time

old_count = len(df0) + len(df1)
print(f"\n当前总记录估计: {old_count}，等待5秒后再次拉取...")
time.sleep(5)

df_new = client.transaction(symbol="600519", market=1, start=old_count, count=800)
if df_new is not None and not df_new.empty:
    print(f"start={old_count} 拿到 {len(df_new)} 条  => 5秒内有新成交")
    print(df_new[["time", "vol", "buyorsell"]].head(10).to_string())
else:
    print(f"start={old_count} 拿到 0 条  => 说明start计数偏移正确但5秒无新大单")

# 再次用start=0看看是否总是返回同一批数据
df0_again = client.transaction(symbol="600519", market=1, start=0, count=5)
print(
    f"\nstart=0 再次拉5条: {df0_again['time'].tolist() if not df0_again.empty else '空'}"
)
print("  => 如果时间与第一次的 start=0 相同，则说明start从当天最早记录开始")
