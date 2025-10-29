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
```

### 3. 获取股票代码列表

```python
# 获取股票代码列表
stock_list = quotation.stock_list
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

2. 对于指数和个股的区分，需要根据前缀和代码来判断

3. 接口返回的数据可能会有延迟，具体取决于数据源

4. 频繁请求可能触发反爬虫机制，请合理控制请求频率

5. 某些字段在不同数据源中可能有所不同，请以实际返回数据为准