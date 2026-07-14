# Draft: 暗盘统计模块独立化 & 模块化架构改进

## Intent: CLEAR
用户明确提出了三个问题：如何测试、是否独立模块、各模块是否都该模块化。

## Research Findings

### 问题1：收盘时未推送暗盘数据统计

**根因分析：**
`close_export_scheduler.py` 的 `_execute_export()` 是一个大方法，包含3个任务：
1. 导出暗盘资金Excel (`dark_trade_exporter.export_dark_trade_excel`)
2. 导出自选股技术指标 (`export_to_excel`)
3. 推送暗盘统计 (`dark_trade_stats.push_dark_trade_stats`)

调度器触发条件（全部需满足）：
- `_enabled = True`（需 UI 中启用）
- `_should_export_today()` — 周一至周五 + 15:05~15:30 + 当天未执行过
- `_running = True`（线程已启动）

**最可能的原因：** 调度器未被启用或未被启动。

**测试现状：**
- `CloseExportScheduler.trigger_now()` 可立即触发，但会执行全部3个任务
- 没有独立的CLI入口来只测试暗盘统计推送
- `test_dark_trade_stats.py` 全部mock，无法验证真实集成

### 问题2：暗盘统计是否应该独立模块

**当前状态：** `dark_trade_stats.py` 已经是独立模块，有清晰的3个函数：
- `calculate_dark_trade_stats()` — 计算统计
- `format_dark_trade_stats_message()` — 格式化消息
- `push_dark_trade_stats()` — 推送

**问题：** 被 `close_export_scheduler.py` 内联调用，无法独立运行和测试。

### 问题3：各功能模块是否都该模块化

**当前架构问题：**
- `close_export_scheduler.py._execute_export()` 是"上帝方法"，耦合3个不相关的任务
- 服务模块虽有清晰API，但缺少独立运行入口
- 没有统一的模块化模式（CLI入口、独立测试）

## User Decisions (已确认)
- **触发方式:** 独立调度器 → 重构 close_export_scheduler 为任务注册模式
- **模块化范围:** 重构调度器，所有子任务可独立触发
- **测试策略:** CLI + 集成测试（真实数据计算 + mock推送）

## Status: awaiting-approval
Plan written to `.omo/plans/dark-trade-stats-standalone.md`
