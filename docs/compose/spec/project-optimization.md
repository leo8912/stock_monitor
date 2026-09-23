---
feature: project-optimization
status: delivered
updated: 2026-09-23
branch: main
commits: 9db2a55..2ddfab9
---

# 全项目激进优化（审查驱动重构）

## Report

**What was built** — 按三路全项目审查与用户确认的「激进优化、兼容可破」边界，在 `main` 工作区完成 T1–T10：UI Worker 生命周期与托盘 weakref 安全、Excel 导出迁入 `services/reporting`、线程池 atexit 关闭、会话缓存节流（全部写盘串行于 RLock）、配置原子默认写与批量 `set_deferred`+`flush`、`StockManager` 单实例与去 JSON 热路径往返、表格按需列宽、`NetworkManager` 统一 HTTP/重试、刷新 1–60s 与量化扫描/复盘时刻可配置、独立 `ci.yml`（Windows/py3.13）、去 black、Python ≥3.11、垃圾文件取消跟踪、README 重写。

**Verification** — 本地门禁（2026-09-23）：
- `.venv\Scripts\python.exe -m ruff check stock_monitor tests` → PASS
- `.venv\Scripts\python.exe -m ruff format --check stock_monitor tests` → PASS（214 files）
- `.venv\Scripts\python.exe -m pytest tests/ -q` → **778 passed, 9 skipped, 13 deselected**

独立 review 报出 3 项 critical（缺 no-resize 测试、缺 config_center 防抖测试、session 写竞态）均已修复并二次复审 FIXED。

**Journey log**
1. `git worktree add` 被沙箱拒绝；用户改为显式同意在 `main` 直接开发。
2. 子代理 bash 全部 `ask` 拒绝——pytest/ruff/git 只能在主代理执行。
3. 首个托盘行为测试构造真实 `QSystemTray` 导致 0xC0000409 崩溃，改为源码守卫断言。
4. `NetworkManager` 只捕 `RequestException` 吞不住 builtin `ConnectionError`，扩捕后网络测试全绿。
5. 初版 session 后台写在锁外，review 判为竞态；收敛为 RLock 内写盘后复审通过。

## [S1] Problem

用户要求以 compose-next 工作流对 A 股行情监控项目做全面审查并实施大范围重构优化。基线（2026-09-23，`9db2a55`）：

- 733 passed / 9 skipped；`ruff check` 在 `run_tests.py` 有 1 处 I001；`ruff format --check` 有 7 个文件待格式化。
- 三路审查确认：主线程每轮刷新 `fsync` 写会话缓存、表格每 tick 全量 `resizeColumnsToContents`、`StockManager` 双实例、`json.dumps` 往返、QThread 销毁前未 stop/wait、托盘 weakref 无 None 守卫、`scripts.reporting` 运行时导入在打包后会失败、CI 仅随 `pyproject.toml` 变更触发、双格式化器（black+ruff）、仓库内跟踪了 egg-info/测试输出垃圾、README 与真实结构/功能严重漂移。
- 变更边界（用户确认）：**激进优化，兼容可破**——可删废弃路径、改配置结构与默认值、调整界面与推送文案，长期可维护性优先。

## [S2] Design

### 架构主轴

1. **组合根单一实例**：删除模块级 `stock_manager` 等运行期单例的“第二实例”路径；Worker/ViewModel 一律从 `DIContainer` 取同一 `StockManager`。保留必要进程级门面，但禁止“container 新建 + module 单例”并存。
2. **热路径减负（UI 线程）**：
   - 会话缓存：去每轮 `fsync`；改为 **≥30s 节流 + 关机时强制 flush**，写盘放到后台单线程队列（或至少节流后在 worker 尾部写）。
   - 表格：仅当行数/布局变化或列内容最大宽度增长时 `resizeColumnsToContents`；否则跳过。
   - 删除 `StockManager` 中 `json.dumps`→`json.loads` 往返，直接传 `dict`。
   - 配置：`config_center.set` 批量/防抖落盘；默认配置创建改为 tmp+`os.replace` 原子写。
3. **线程与资源生命周期**：
   - `wave_chart_dialog` / `stock_comparison_dialog`：重载前 stop/disconnect 旧 worker；`closeEvent` 必须 stop+wait；用 generation 防止过期结果写 UI。
   - `close_export_scheduler.stop` 使用与其他 worker 一致的 `wait_for_thread_stop`。
   - `system_tray` 所有 `main_window` weakref 解引用前判 None。
   - `stock_fetcher`、`StockManager._executor` 注册 atexit/`shutdown` 关闭路径。
4. **网络与重试收敛**：新增单一 `utils/http_client`（或扩展 `network/manager`）作为唯一请求入口；`dark_trade/service`、`dark_trade_exporter`、`app_update/downloader` 改为走该入口；删除/委托 `network_helper` 与 `utils/retry` 重复实现中与之冲突的路径（允许保留薄封装）。
5. **打包正确性**：将 `scripts.reporting.export_stocks_to_excel` 迁入 `stock_monitor/services/excel_export/`（或 `services/reporting/`），更新 `settings_workers` / `quant_worker` / `close_export_scheduler` 导入；`scripts/` 仅留开发脚本。
6. **配置真源**：`ConfigKeys` + 默认值单一 schema 模块；量化扫描间隔、复盘时刻等硬编码迁入可配置键（见功能项）。
7. **工程化**：
   - 拆分 `.github/workflows/ci.yml`（push/PR：ruff + format + pytest + cov 阈值）与 `pack-release.yml`（仅 pyproject 版本变更或 tag/workflow_dispatch）。
   - 删除 black 配置与依赖；pre-commit ruff 版本与本地对齐；`requirements` 缓存键纳入 `pyproject.toml`。
   - `requires-python` 提升为 `>=3.11`；删除 py39 专用守卫测试中与 3.9 绑定的部分（若仅 AST 禁忌则保留对 3.11 有意义的检查可删）。
   - 从 git 删除并 gitignore：`stock_monitor.egg-info/`、`test_output.txt`、`test_error.txt`、`.pytest_tmp_clean/`（若仍跟踪）、过期 `REVIEW_REPORT.md` 可改存 `docs/archive/` 或删除并在 README 指向新审查结论。
8. **文档与产品面**：
   - 重写 README：真实目录树、完整功能列表（量化/暗盘/波浪/任务栏行情条/导出）、运行与版本流程（以 `pyproject.toml` 为唯一版本源，CI 触发路径一致）。
   - 刷新间隔：设置页提供 1–60s 自定义（spinbox），与 README 一致。
   - 量化设置迁入：扫描间隔、复盘触发时刻列表（原硬编码 `5*60`、`["11:35","15:05"]`）。

### 错误行为

- 托盘回调在主窗口已销毁时静默跳过（debug 日志），不抛 AttributeError。
- Worker 关窗：最多等待有界时间（如 3s），超时记 warning 并继续销毁前 requestInterruption。
- 会话/配置写盘失败：保留原子替换语义，失败仅日志，不打断行情刷新。

### 测试边界

- 新增/补强：session 节流、stock_manager 无 JSON 往返、托盘 weakref、wave/comparison worker teardown、excel 模块在包内可导入、config 原子默认写、CI 相关本地等价命令（ruff+pytest）。
- 不默认要求 GUI 真窗；`gui`/`integration` 标记维持默认排除。

## [S3] Out of Scope

- 完整 event-bus 替换全部 Qt 信号（仅修可证实的线程投递缺陷或维持现状并文档化）。
- 新推送渠道（Bark/Telegram/邮件）与完整产品路线图（可在 README/设置中留扩展点，不实现新渠道）。
- 上游数据源协议级优化、非 Windows 平台专项。
- 强制 coverage 一次性打到 70% 的历史模块全量补齐（CI 先接入测量与合理阈值，缺口后续迭代）。

## Tasks

- [x] T1: UI Worker 生命周期与托盘安全 — acceptance: wave/comparison 关窗或重载时旧 QThread 被 stop/wait，不再 Destroyed-while-running；tray 回调在 `main_window is None` 时不崩溃；相关单测通过 (covers: S2.3)
- [x] T2: 资源关闭与打包导入修复 — acceptance: `excel_export`（或等价包内路径）可 `python -c "import ..."` 成功且无 `from scripts.` 运行时导入；`StockManager`/`stock_fetcher` 在 shutdown/atexit 路径关闭线程池；测试通过 (covers: S2.5; depends: T1 可并行)
- [x] T3: 配置与会话热路径优化 — acceptance: 默认 config 原子写；会话缓存不再每轮主线程 fsync（节流+关机 flush 有测试）；`config_center.set` 防抖落盘有测试 (covers: S2.2)
- [x] T4: StockManager 单实例与去 JSON 往返 — acceptance: 全库无第二 `StockManager()` 运行路径与 `json.dumps`→`loads` 热路径往返；`fetch_and_process_stocks` 单测/既有测通过 (covers: S2.1, S2.2)
- [x] T5: 表格列宽/高度按需重排 — acceptance: 仅布局或内容变宽时 resize；既有 UI 数据更新测试通过并有用例覆盖“未变宽不 resize” (covers: S2.2)
- [x] T6: HTTP/重试收敛 — acceptance: dark_trade 与 exporter/downloader 主请求路径经统一客户端；重复 retry 策略收敛为一处可配置入口；相关测试通过 (covers: S2.4)
- [x] T7: 量化与刷新可配置化 — acceptance: 扫描间隔、复盘时刻、刷新 1–60s 进入配置键与设置页；硬编码移除；settings 往返测试通过 (covers: S2.6)
- [x] T8: 工程化（CI/black/垃圾文件/Python 版本）— acceptance: 存在独立 `ci.yml` 跑 lint+format+pytest；无 black 配置；egg-info/test_output 等不再被 git 跟踪且已 gitignore；`requires-python >=3.11`；本地 `ruff check`/`format --check`/`pytest` 全绿 (covers: S2.7)
- [x] T9: README 与结构文档重写 — acceptance: README 功能/目录/版本触发与仓库一致；运行命令可验证 (covers: S2.8)
- [x] T10: 回归测试补齐与全量验证 — acceptance: 上述行为均有测试；`ruff check stock_monitor tests`、`ruff format --check stock_monitor tests`、`pytest -q` 全部通过；记录命令与结果 (covers: S2 全部; depends: T1–T9)
