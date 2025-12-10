# easyquotation 库 API 使用说明

## 简介

easyquotation 是一个用于获取中国股票行情信息的 Python 库，支持新浪、腾讯等数据源。

## 安装

```bash
pip install easyquotation
```

## 基本使用

### 1. 导入和初始化

```python
import easyquotation

# 使用新浪数据源
quotation = easyquotation.use('sina')

# 使用腾讯数据源
quotation = easyquotation.use('tencent')  # 或 'qq'
```

### 2. 获取实时行情数据

#### 获取单只或多只股票数据

```python
# 获取不带前缀的股票数据
data = quotation.stocks(['000001', '000002'])
# 返回: {'000001': {...}, '000002': {...}}

# 获取带前缀的股票数据
data = quotation.stocks(['sh000001', 'sz000002'], prefix=True)
# 返回: {'sh000001': {...}, 'sz000002': {...}}
```

#### 获取所有股票数据

```python
# 获取所有股票数据
all_data = quotation.all
```

#### 获取市场快照

```python
# 获取市场快照数据
snapshot = quotation.market_snapshot(prefix=True)
```

#### 获取实时行情

```python
# 获取实时行情数据
real_data = quotation.real(['000001', '000002'])

# 支持直接指定前缀
real_data = quotation.real('sh000001')

# 同时获取指数和行情（prefix必须为True）
real_data = quotation.real(['sh000001', 'sz000001'], prefix=True)
```

### 3. 获取股票代码列表

```python
# 获取股票代码列表
stock_list = quotation.stock_list
```

## 其他数据源

### 港股日K线图

```python
import easyquotation
quotation = easyquotation.use("daykline")
data = quotation.real(['00001','00700'])
print(data)
```

返回数据格式：
```python
{
    '00001': [
        ['2017-10-09', '352.00', '349.00', '353.00', '348.60', '13455864.00'],  # [日期, 今开, 今收, 最高, 最低, 成交量]
        ['2017-10-10', '350.80', '351.20', '352.60', '349.80', '10088970.00'],
    ],
    '00700': [
        # ...
    ]
}
```

### 腾讯港股实时行情

```python
import easyquotation
quotation = easyquotation.use("hkquote")
data = quotation.real(['00001','00700'])
print(data)
```

返回数据格式：
```python
{
    '00001': {
        'stock_code': '00001',  # 股票代码
        'lotSize': '"100',     # 每手数量
        'name': '长和',         # 股票名称
        'price': '97.20',       # 股票当前价格
        'lastPrice': '97.75',   # 股票昨天收盘价格
        'openPrice': '97.75',   # 股票今天开盘价格
        'amount': '1641463.0',  # 股票成交量 
        'time': '2017/11/29 15:38:58',  # 当前时间
        'high': '98.05',        # 当天最高价格
        'low': '97.15'          # 当天最低价格
    }
}
```

### 集思录(JSL)行情

```python
quotation = easyquotation.use('jsl')

# 可选：设置cookie以获取更多数据
quotation.set_cookie('从浏览器获取的集思录 Cookie')

# 指数ETF查询接口
etf_data = quotation.etfindex(index_id="", min_volume=0, max_discount=None, min_discount=None)
```

ETF数据返回格式：
```python
{
    "510050": {
        "fund_id": "510050",           # 代码
        "fund_nm": "50ETF",            # 名称
        "price": "2.066",              # 现价
        "increase_rt": "0.34%",        # 涨幅
        "volume": "71290.96",          # 成交额(万元)
        "index_nm": "上证50",           # 指数
        "pe": "9.038",                 # 指数PE
        "pb": "1.151",                 # 指数PB
        "index_increase_rt": "0.45%",  # 指数涨幅
        "estimate_value": "2.0733",    # 估值
        "fund_nav": "2.0730",          # 净值
        "nav_dt": "2016-03-11",        # 净值日期
        "discount_rt": "-0.34%",       # 溢价率
        "creation_unit": "90",         # 最小申赎单位(万份)
        "amount": "1315800",           # 份额
        "unit_total": "271.84",        # 规模(亿元)
        "index_id": "000016",          # 指数代码
        "last_time": "15:00:00",       # 价格最后时间(未确定)
        "last_est_time": "23:50:02",   # 估值最后时间(未确定)
    }
}
```

## 数据结构说明

### 股票数据字段

| 字段名 | 说明 |
|--------|------|
| name | 股票名称 |
| open | 开盘价 |
| close | 收盘价 |
| now | 当前价 |
| high | 最高价 |
| low | 最低价 |
| buy | 买入价 |
| sell | 卖出价 |
| turnover | 成交量 |
| volume | 成交额 |
| bid1_volume ~ bid5_volume | 买一到买五的量 |
| bid1 ~ bid5 | 买一到买五的价格 |
| ask1_volume ~ ask5_volume | 卖一到卖五的量 |
| ask1 ~ ask5 | 卖一到卖五的价格 |
| date | 日期 |
| time | 时间 |

## 特殊情况处理

### 1. 上证指数与平安银行代码冲突

- `000001` 在不同市场代表不同标的：
  - `sh000001`: 上证指数
  - `sz000001`: 平安银行

### 2. A股指数与万科Ａ代码冲突

- `000002` 在不同市场代表不同标的：
  - `sh000002`: Ａ股指数
  - `sz000002`: 万科Ａ

## 常用指数代码

| 代码 | 名称 |
|------|------|
| sh000001 | 上证指数 |
| sh000002 | Ａ股指数 |
| sh000300 | 沪深300 |
| sz399001 | 深证成指 |
| sz399006 | 创业板指 |

## 最佳实践

### 1. 股票代码处理

为了确保正确识别股票，建议始终使用带前缀的股票代码：
```python
# 推荐方式
stock_data = quotation.stocks(['sh600000', 'sz000001'], prefix=True)

# 不推荐方式（可能导致代码冲突）
stock_data = quotation.stocks(['600000', '000001'])
```

### 2. 错误处理

在获取股票数据时，应当添加适当的错误处理机制：
```python
try:
    data = quotation.stocks(['sh600000'])
    if data:
        # 处理数据
        process_stock_data(data)
    else:
        print("未获取到股票数据")
except Exception as e:
    print(f"获取股票数据时发生错误: {e}")
```

### 3. 数据缓存

对于频繁访问的数据，建议使用缓存机制以减少网络请求：
```python
import time

# 简单的缓存实现
cache = {}
CACHE_TTL = 60  # 缓存60秒

def get_stock_data_with_cache(stock_codes):
    cache_key = ','.join(stock_codes)
    current_time = time.time()
    
    # 检查缓存是否存在且未过期
    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            return data
    
    # 缓存未命中或已过期，重新获取数据
    try:
        data = quotation.stocks(stock_codes)
        cache[cache_key] = (data, current_time)
        return data
    except Exception as e:
        print(f"获取股票数据失败: {e}")
        return None
```

### 4. 批量处理

当需要获取大量股票数据时，建议分批处理以避免请求超时：
```python
def get_all_stocks_batch(stock_codes, batch_size=50):
    all_data = {}
    
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i+batch_size]
        try:
            batch_data = quotation.stocks(batch)
            all_data.update(batch_data)
        except Exception as e:
            print(f"获取批次数据失败: {e}")
            continue
    
    return all_data
```

## 注意事项

1. 股票代码前缀规则：
   - `sh`: 上海证券交易所
   - `sz`: 深圳证券交易所
   - `hk`: 港股

2. 对于指数和个股的区分，需要根据前缀和代码来判断

3. 接口返回的数据可能会有延迟，具体取决于数据源

4. 频繁请求可能触发反爬虫机制，请合理控制请求频率

5. 某些字段在不同数据源中可能有所不同，请以实际返回数据为准

6. 更新内置全市场股票代码：
```python
easyquotation.update_stock_codes()
```