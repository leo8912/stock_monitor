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

## 注意事项

1. 股票代码前缀规则：
   - `sh`: 上海证券交易所
   - `sz`: 深圳证券交易所

2. 对于指数和个股的区分，需要根据前缀和代码来判断

3. 接口返回的数据可能会有延迟，具体取决于数据源