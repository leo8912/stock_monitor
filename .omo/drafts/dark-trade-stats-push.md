# Draft: dark-trade-stats-push

## Intent
CLEAR - 用户明确要增加暗盘统计推送功能

## Review Required
No

## Decisions
- 使用现有的 `fetch_all_dark_trade()` 获取历史数据
- 推送内容包含全市场统计和自选股明细
- 触发时机与现有Excel导出同时（15:05-15:30）

## Open Questions
- 是否需要配置项来控制推送开关？
- 推送消息格式是否需要调整？

## Status
awaiting-approval

## Pending Action
write .omo/plans/dark-trade-stats-push.md
