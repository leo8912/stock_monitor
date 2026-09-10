"""测试 akshare 各 API 格式，用于迁移 mootdx"""

import os

import requests as _requests

# 绕过系统代理
for k in [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
]:
    os.environ.pop(k, None)
# Monkey-patch requests to bypass proxy
_orig_request = _requests.Session.request


def _no_proxy_request(self, *a, **kw):
    self.trust_env = False
    return _orig_request(self, *a, **kw)


_requests.Session.request = _no_proxy_request

import akshare as ak

# 1. 日K线 (stock_zh_a_hist)
print("=== 1. stock_zh_a_hist (daily bars) ===")
df = ak.stock_zh_a_hist(
    symbol="000001",
    period="daily",
    start_date="20260801",
    end_date="20260910",
    adjust="qfq",
)
print("COLUMNS:", list(df.columns))
print(df.head(2).to_string())
print()

# 2. 指数日K线 (index_zh_a_hist)
print("=== 2. index_zh_a_hist (index daily) ===")
df2 = ak.index_zh_a_hist(
    symbol="000001", period="daily", start_date="20260801", end_date="20260910"
)
print("COLUMNS:", list(df2.columns))
print(df2.head(2).to_string())
print()

# 3. 分钟K线 (stock_zh_a_hist_min_em)
print("=== 3. stock_zh_a_hist_min_em (1min) ===")
df3 = ak.stock_zh_a_hist_min_em(symbol="000001", period="1", adjust="qfq")
print("COLUMNS:", list(df3.columns))
print(df3.head(2).to_string())
print(f"Total: {len(df3)}")
print()

# 4. 逐笔成交 (stock_intraday_em)
print("=== 4. stock_intraday_em (tick) ===")
try:
    df4 = ak.stock_intraday_em(symbol="000001")
    print("COLUMNS:", list(df4.columns))
    print(df4.head(2).to_string())
    print(f"Total: {len(df4)}")
except Exception as e:
    print(f"FAILED: {e}")
print()
