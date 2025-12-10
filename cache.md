# 项目缓存机制说明

## 1. 全局数据缓存 (global_cache)

### 描述
使用LRU（最近最少使用）策略的通用数据缓存，主要用于缓存实时股票行情数据。

### 实现文件
- [stock_monitor/utils/cache.py](file:///d:/code/stock/stock_monitor/utils/cache.py)

### 缓存特征
- **缓存类型**: LRU缓存（最近最少使用）
- **默认TTL**: 30秒
- **最大容量**: 1000项
- **市场感知TTL**: 
  - 开市期间：使用默认TTL（30秒）
  - 闭市期间：TTL延长至10倍（最长1小时）

### 使用场景
1. 实时股票行情数据缓存
2. 热门股票数据预加载缓存

### 缓存键命名规则
- 股票数据: `stock_{股票代码}` 如 `stock_sh600460`

### TTL详情
1. **普通股票数据**:
   - 开市期间: 30秒
   - 闭市期间: 300秒（5分钟）

2. **预加载热门股票数据**:
   - 所有时间: 3600秒（1小时）

### 使用示例
```python
# 获取带市场感知TTL的缓存数据
cached_data = global_cache.get_with_market_aware_ttl(cache_key)

# 设置缓存数据
global_cache.set(cache_key, stock_data, ttl=ttl)
```

## 2. 股票基础数据缓存 (global_stock_cache)

### 描述
专门用于缓存股票基础数据（如股票代码、名称等），避免频繁读取文件。

### 实现文件
- [stock_monitor/utils/stock_cache.py](file:///d:/code/stock/stock_monitor/utils/stock_cache.py)

### 缓存特征
- **缓存类型**: 简单内存缓存
- **TTL**: 300秒（5分钟）
- **数据来源**: [stock_basic.json](file:///d:/code/stock/stock_monitor/resources/stock_basic.json) 文件

### 使用场景
1. 股票搜索功能
2. 股票代码补全
3. 股票名称查询

### TTL详情
- 所有时间: 300秒（5分钟）

### 使用示例
```python
# 获取股票基础数据
stock_data = global_stock_cache.get_stock_data()
```

## 3. 缓存使用位置汇总

### 股票数据服务
文件: [stock_monitor/core/stock_service.py](file:///d:/code/stock/stock_monitor/core/stock_service.py)
- 用途: 缓存个股实时行情数据
- TTL: 开市期间30秒，闭市期间300秒

### 市场数据更新器
文件: [stock_monitor/data/market/updater.py](file:///d:/code/stock/stock_monitor/data/market/updater.py)
- 用途: 缓存预加载的热门股票数据
- TTL: 3600秒（1小时）

## 4. 缓存清理机制

### 自动清理
- LRU策略自动淘汰最久未使用的缓存项
- 获取缓存时自动检查并删除过期项

### 手动清理
- `cleanup_expired()`: 清理所有过期缓存项
- `force_cleanup()`: 强制清理一半最旧的缓存项
- `clear()`: 清除指定或全部缓存项

## 5. 缓存监控

### 统计信息
通过 `get_stats()` 方法可以获得以下统计信息：
- 总缓存项数
- 过期缓存项数
- 有效缓存项数
- 最大缓存容量
- 使用率百分比