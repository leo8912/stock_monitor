# 暗盘统计推送功能

## TL;DR (For humans)

每天收盘后，自动推送暗盘统计数据到企业微信。包含：
1. **全市场统计**：3天净流入股票数、5天流入次数>3天的股票数、合计净流入金额
2. **自选股统计**：每只自选股的3天净流入、5天流入天数、合计流入金额

## 背景

用户希望在收盘后收到暗盘资金流向的统计推送，便于快速了解市场整体暗盘动向和自选股的暗盘表现。

## 需求分析

### 推送内容

```
📊 暗盘资金统计 (2026-07-03)

【全市场概览】
• 近3日净流入股票数：XXX 只
• 近5日流入天数>3天：XXX 只
• 合计净流入金额：XXX 亿元

【自选股暗盘明细】
代码    名称    3日净流入(万)  5日流入天数  合计流入(万)
600519  贵州茅台  +1234.56      4天         +5678.90
000858  五粮液    -234.56       2天         +1234.56
...
```

### 数据来源

- 使用现有的 `fetch_all_dark_trade()` 获取历史暗盘数据
- 计算3日净流入、5日流入天数、合计净流入

### 触发时机

- 收盘后15:05-15:30，与现有Excel导出同时触发
- 或单独触发

## 实现方案

### 1. 新增文件：`stock_monitor/services/dark_trade_stats.py`

```python
"""
暗盘统计数据计算与推送模块
"""

def calculate_dark_trade_stats(
    watchlist_codes: list[str],
    history_days: int = 5,
) -> dict:
    """
    计算暗盘统计数据

    Returns:
        {
            "market_summary": {
                "inflow_3day_count": int,  # 近3日净流入股票数
                "inflow_5day_gt3_count": int,  # 5日流入天数>3天的股票数
                "total_inflow_wan": float,  # 合计净流入金额(万元)
            },
            "watchlist_details": [
                {
                    "code": str,
                    "name": str,
                    "inflow_3day_wan": float,  # 3日净流入(万元)
                    "inflow_5day_count": int,  # 5日流入天数
                    "total_inflow_wan": float,  # 合计流入(万元)
                }
            ]
        }
    """
    pass

def format_dark_trade_stats_message(stats: dict) -> str:
    """格式化暗盘统计推送消息"""
    pass

def push_dark_trade_stats(config: dict, watchlist_codes: list[str]) -> bool:
    """推送暗盘统计到企业微信"""
    pass
```

### 2. 修改文件：`stock_monitor/services/close_export_scheduler.py`

在 `_execute_export()` 中添加暗盘统计推送：

```python
# 3. 推送暗盘统计
try:
    from stock_monitor.services.dark_trade_stats import push_dark_trade_stats
    from stock_monitor.core.config_center import config_center

    user_stocks = config_center.user_stocks
    push_dark_trade_stats(config_center._manager.config, user_stocks)
except Exception as e:
    app_logger.error(f"[CloseExportScheduler] 暗盘统计推送失败: {e}")
```

### 3. 修改文件：`stock_monitor/services/dark_trade_service.py`

添加信号用于触发推送：

```python
dark_stats_push_requested = QtCore.pyqtSignal()
```

## 验证方案

1. **单元测试**：测试 `calculate_dark_trade_stats()` 计算逻辑
2. **集成测试**：测试推送消息格式
3. **手动测试**：在收盘时段触发导出，验证推送内容

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `stock_monitor/services/dark_trade_stats.py` | 新增 | 暗盘统计计算与推送 |
| `stock_monitor/services/close_export_scheduler.py` | 修改 | 添加推送触发 |
| `tests/test_dark_trade_stats.py` | 新增 | 单元测试 |
