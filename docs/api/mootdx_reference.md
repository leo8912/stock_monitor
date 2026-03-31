# mootdx 接口参考文档

本文档详细说明了 `mootdx` 库在 A 股行情监控中的使用方法，特别是针对“主力逐笔成交统计”功能的实现参考。

## 1. 环境初始化
`mootdx` 通过通达信协议获取数据，默认使用标准行情（std）。

```python
from mootdx.quotes import Quotes

# 初始化标准行情引擎
client = Quotes.factory(market='std')
```

## 2. 核心接口说明

### 2.1 实时行情 (Quotes)
获取多只股票的最新价格报价。

- **方法**: `client.quotes(symbol=["600519", "000001"])`
- **返回值**: `pandas.DataFrame`
- **关键字段**:
    - `price`: 当前即时成交价。
    - `last_close`: 昨日收盘价。
    - `open`, `high`, `low`: 今日开盘、最高、最低。
    - `vol`: 今日累计总成交量（单位：**手**）。
    - `cur_vol`: 现数（即最后一笔成交量，单位：**手**）。
    - `bid1`~`bid5`: 买一至买五报价。
    - `ask1`~`ask5`: 卖一至卖五报价。

### 2.2 逐笔成交 (Transaction)
获取指定股票的当日成交明细，是实现“剔除100手以下单”的核心接口。

- **方法**: `client.transaction(symbol="600519", market=1, start=0, count=2000)`
    - `market`: 1 表示上海 (sh), 0 表示深圳 (sz)。
    - `start`: 记录起始偏移。
    - `count`: 获取记录条数。
- **返回值**: `pandas.DataFrame`
- **数据列**:
    - `time`: 成交时间 (HH:MM)。
    - `price`: 成交价格。
    - `vol`: 成交量（单位：**手**）。
    - `buyorsell`: 买卖方向 (0:买入B, 1:卖出S, 2:中性M)。

### 2.3 分笔数据 (Ticks)
获取当天的分笔走势数据（包含盘口信息）。

- **方法**: `client.ticks(symbol="600519", market=1)`
- **返回值**: `pandas.DataFrame`
- **特点**: 比 `quotes` 更详细，包含全天的时间轴报价序列。

## 3. 统计逻辑：剔除 100 手以下单

根据用户需求，统计当日“主力大单”流向（>100手）：

```python
# 假设从接口获取到 df = client.transaction(...)
# 1. 过滤：成交量 >= 100 (手)
big_orders = df[df['vol'] >= 100]

# 2. 分别汇总买入金额与卖出金额 (金额 = vol * 100 * price)
# 注意：vol 单位是手，汇总金额需乘以 100
large_money_in = (big_orders[big_orders['buyorsell'] == 0]['vol'] * 100 * big_orders['price']).sum()
large_money_out = (big_orders[big_orders['buyorsell'] == 1]['vol'] * 100 * big_orders['price']).sum()

# 3. 计算主力净流入
net_flow = large_money_in - large_money_out
```

## 4. 注意事项与限制
1. **服务器连接**: `mootdx` 会自动探测最快服务器，建议在程序初始化时调用一次。
2. **频率限制**: 通达信接口暂无硬性 API 密钥限制，但极高频请求可能触发服务器负载保护，建议单股轮询间隔不低于 5 秒。
3. **休市期**: 休市期间 `transaction` 接口通常不返回数据，建议在交易时段或使用 `history_transaction` 测试。
