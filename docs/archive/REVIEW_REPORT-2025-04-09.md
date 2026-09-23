# A股行情监控系统 — 全项目代码审查报告

> **归档说明**：本报告为 2025-04-09 历史审查快照，仅作追溯；其中多数问题已在后续版本修复或重构中失效。当前工程状态请以根目录 `README.md`、`CHANGELOG.md` 与最新 CI 结果为准。

> 审查日期：2025-04-09
> 审查范围：stock_monitor/ 源码 (124文件)、tests/ 测试 (80+文件)
> 审查维度：代码质量、错误处理、并发安全、性能、架构设计、安全隐患、测试质量

---

## 📊 总览评分

| 模块 | 🔴严重 | 🟡中等 | 🟢建议 | 总计 |
|------|--------|--------|--------|------|
| 核心业务逻辑层 (core/) | 3 | 10 | 8 | 21 |
| UI层 (ui/) | 4 | 12 | 6 | 22 |
| 基础设施层 (utils/config/network/data/services) | 5 | 14 | 11 | 30 |
| **合计** | **12** | **36** | **25** | **73** |

---

## 一、核心业务逻辑层 (core/)

### 🔴 严重问题 (3个)

**C1. `backtest_engine.py` 死锁风险**
- 位置: `_evaluate_and_cache()` 持有 `self._lock` 后调用 `_save_cache()`，后者内部又 `with self._lock:`
- 问题: Python 的 `threading.Lock()` 不可重入，导致死锁
- 修复: 在锁内拷贝缓存数据，锁外写文件

**C2. `quant_engine.py` 类变量共享**
- 位置: `_market_benchmark_cache`/`_market_benchmark_lock` 是类变量
- 问题: 所有实例共享，而 LRU 缓存是实例级别的。多实例场景下行为不一致
- 修复: 改为实例变量或使用明确的类级缓存管理

**C3. `stock_manager.py` 线程池无关闭**
- 位置: `ThreadPoolExecutor` 永不关闭（全局单例）
- 问题: 任务队列可能持续堆积，资源泄漏
- 修复: 添加 `close()` 方法并注册 `atexit` 清理

### 🟡 中等问题 (10个)

| # | 文件 | 问题 |
|---|------|------|
| C4 | `backtest_engine.py` | `get_score_stats` 手写盈亏循环，未复用 `_run_backtest` 框架 |
| C5 | `quant_engine.py:446` | `except Exception: pass` 静默吞掉 RSI/EMA/RSRS 计算异常 |
| C6 | `stock_manager.py:138-142` | 无意义的 `json.dumps` → `json.loads` 序列化往返 |
| C7 | `stock_data_fetcher.py` | `get_quotation_engine` 每次调用都重新创建港股引擎，无缓存 |
| C8 | `quant_worker.py` | `self.config` 跨线程读写无保护 |
| C9 | `refresh_worker.py` | `_is_running` 用普通 bool 而非 `threading.Event` |
| C10 | 多个模块 | 全局单例泛滥（5个模块级实例），测试困难 |
| C11 | `quant_engine.py` | `fetch_large_orders_flow` 首次全量拉取可能创建巨大 DataFrame |
| C12 | `application.py` | `import traceback` 放在 except 块内 |
| C13 | `stock_data_processor.py` | 颜色常量硬编码与 UI 层不同步 |

### 🟢 建议 (8个)

| # | 文件 | 建议 |
|---|------|------|
| C14 | `cache_manager.py` | `LRUCache.cache` 属性暴露内部 OrderedDict，破坏线程安全 |
| C15 | `wave_analyzer.py` | `analyze_and_record` 永久修改全局 `FIB_TARGET_COEFFICIENTS` |
| C16 | `backtest_engine.py` | `_load_cache` 非原子写文件 |
| C17 | `application.py` | 直接调用 `MainWindow._shutdown_resources()` 私有方法 |
| C18 | `config_center.py` | `get_list` 默认值语义不清晰 |
| C19 | `stock_data_fetcher.py` | `close()` 在 atexit 时可能触发 logger 异常 |
| C20 | `stock_data_processor.py` | `_extract_price_info` 中重复的 `float()` 转换 |
| C21 | `stock_service.py` | `_init_sina_if_needed` 无锁保护 |

---

## 二、UI层 (ui/)

### 🔴 严重问题 (4个)

**U1. `system_tray.py` weakref 无保护**
- 位置: `self._main_window_ref()` 可能返回 None
- 问题: 所有调用方（`show_main_window`/`open_settings`/`quit_application`/`on_activated`）均未检查，可能抛 AttributeError 崩溃
- 修复: 添加 None 检查或使用 try/except

**U2. `wave_chart_dialog.py` 旧 QThread 泄漏**
- 位置: 快速切换周期/勾选子浪时
- 问题: 旧 `_WaveDataWorker` 引用被覆盖但仍在后台运行，信号仍连接，可能导致多个 worker 结果交叉更新 UI
- 修复: 启动新 worker 前先 `quit()` + `wait()` 旧 worker

**U3. `stock_comparison_dialog.py` 旧 worker 泄漏**
- 位置: 与 U2 相同模式
- 问题: 旧 `_DataLoadWorker` 引用被覆盖但仍在后台运行
- 修复: 同 U2

**U4. 暗盘数据竞争**
- 位置: `main_window_view_model.py:104-108`
- 问题: `_on_dark_trade_cache_updated` 和 `_on_data_updated` 可并发修改 `_latest_stock_data` 列表对象
- 修复: 先 copy 再修改

### 🟡 中等问题 (12个)

| # | 文件 | 问题 |
|---|------|------|
| U5 | `main_window.py:579` | `handle_context_menu` 每次右键新建 AppContextMenu 实例 |
| U6 | 多处 | 直接访问 `config_center._helper` 私有属性 |
| U7 | `market_status.py:9` | `MarketStatusBar` 固定 3px 高度在高 DPI 下几乎不可见 |
| U8 | `backtest_result_dialog.py:149` | `BacktestChartWidget.paintEvent` 硬编码 60px 条宽 |
| U9 | `taskbar_quote_bar.py:123-125` | `_EDGE_PAD`/`_COL_GAP` 未乘以 DPR |
| U10 | 三个 Dialog | 各自内联相同暗色主题 QSS，违反 DRY |
| U11 | `taskbar_quote_bar.py` | 每次 paintEvent 都遍历全部股票计算列宽，应缓存 |
| U12 | `settings_view_model.py` | `_perform_search` 在主线程执行 `load_stock_data()` 全量加载 |
| U13 | `main_window.py` | `quit_application` 中方法内 `import sys` 不规范 |
| U14 | `stock_table.py` | `update_data` 类型注解应为 `list[StockRowData]` |
| U15 | `constants.py` | 颜色常量与 dialog 内联值不一致 |
| U16 | `styles.py` | QSS 模板未缓存，每次字体变更都重读文件 |

### 🟢 建议 (6个)

| # | 文件 | 建议 |
|---|------|------|
| U17 | 多处 | `install_event_filters` 递归安装但无卸载逻辑 |
| U18 | `tray_quote_panel.py` | 托盘图标固定 32×32，在 200% DPI 下模糊 |
| U19 | `draggable_window.py` | WINDOWPOS 结构体在热路径中重复定义 |
| U20 | `settings_view_model.py` | `_test_thread` 属性未在 `__init__` 中初始化 |
| U21 | `wave_chart_dialog.py` | matplotlib `plt.rcParams` 全局污染 |
| U22 | `market_status.py` | 右键菜单每次重建不清理旧动作信号连接 |

---

## 三、基础设施层 (utils/config/network/data/services)

### 🔴 严重问题 (5个)

**I1. `stock_db.py` `get_db_pool()` TOCTOU 竞态**
- 位置: `stock_monitor/data/stock/stock_db.py:183-186`
- 问题: 全局函数在无锁情况下检查 `_db_pool is None` 并创建实例，两个线程可能创建不同实例导致连接泄漏
- 修复: 添加 `threading.Lock()` 保护

**I2. `wave_prediction_service.py` 写操作未使用写连接**
- 位置: `record_prediction` 和 `verify_prediction` 执行 INSERT/UPDATE 但使用 `_get_connection()`（读路径）
- 问题: 多线程同时写入可能导致 SQLite 乐观锁冲突
- 修复: 改为使用 `self.db._write_connection()`

**I3. `health_check.py` Windows 不兼容**
- 位置: `stock_monitor/utils/health_check.py:149`
- 问题: `os.statvfs()` 是 Unix 专有 API，Windows 上不存在
- 修复: 替换为 `shutil.disk_usage()`

**I4. `stock_fetcher.py` 模块级全局单例资源泄漏**
- 位置: `stock_monitor/data/fetcher.py:238`
- 问题: `stock_fetcher = StockFetcher()` 在 import 时立即创建 `ThreadPoolExecutor` 和 `NetworkManager`
- 修复: 改为懒初始化模式

**I5. `network_helper.py` HTTPS 强制转换文档不符**
- 位置: `stock_monitor/utils/network_helper.py:77-78`
- 问题: 文档声称返回 None，但实际抛出 `HTTPStatusError`
- 修复: 修正 docstring 或改为返回 None

### 🟡 中等问题 (14个)

| # | 文件 | 问题 |
|---|------|------|
| I6 | `network_helper.py` | `SafeRequest.get()` 和 `SafeRequest.post()` 各约 80 行，结构几乎完全相同 |
| I7 | `network_helper.py` | `safe_request_get/post` 静默吞没所有异常，丢失错误上下文 |
| I8 | `dark_trade/service.py` | 直接使用 `requests.get` 而非项目网络层 |
| I9 | `dark_trade/service.py` | `_manual_fetch_requested` 标志无线程保护 |
| I10 | `dark_trade/service.py` | `stop_service` 调用 `requestInterruption()` 但 `run()` 未检查 |
| I11 | `retry.py` | `network_retry` 和 `safe_retry` 功能几乎重复 |
| I12 | `config/manager.py` | `load_config()` 直接访问私有锁 `_instance_lock` |
| I13 | `logger.py` | `RedactionFilter` 在 `getMessage()` 失败时仅 DEBUG 级别日志 |
| I14 | `stock_db.py` | `_import_from_base_db` 使用 `INSERT OR REPLACE` 可能丢失更新时间 |
| I15 | `conftest.py` | 缺少常用 fixtures（`temp_db`、`mock_logger` 等） |
| I16 | `test_fetcher.py` | 缺少并行获取、去重、线程池关闭等关键测试 |
| I17 | `test_di_container.py` | 缺少并发安全和循环依赖测试 |
| I18 | `test_core_service.py` | 使用 unittest 风格与其他 pytest 风格不一致 |
| I19 | 多个测试文件 | 缺少网络异常分类、并发读写、大值测试 |

### 🟢 建议 (11个)

| # | 文件 | 建议 |
|---|------|------|
| I20 | `error_handler.py` | 文档应说明不会捕获 `BaseException` 子类 |
| I21 | `fetcher.py` | `convert` fallback 函数签名与 zhconv 不完全匹配 |
| I22 | `fetcher.py` | `_fetch_indices` 重新创建 `easyquotation.use("sina")` 实例 |
| I23 | `wave_prediction_service.py` | 模块级创建全局实例，应改为懒初始化 |
| I24 | `dark_trade/service.py` | `run()` 中 5s 分片 sleep 效率低 |
| I25 | `stock_db.py` | `ConnectionPool` 单例缺少测试隔离支持 |
| I26 | `test_symbol_resolver.py` | 空字符串测试预期异常类型不精确 |
| I27 | 多个模块 | 以下模块完全没有测试：logger、health_check、network_helper、retry、config/manager、network/manager、dark_trade/service、wave_prediction_service、stock_db |
| I28 | `conftest.py` | 缺少集成测试配置和测试数据库/网络 mock |
| I29 | `network_helper.py` | `SafeRequest` 应添加请求超时默认值 |
| I30 | `dark_trade/service.py` | 应使用 `threading.Event` 替代 bool 标志 |

---

## 四、亮点与正面评价 ✨

项目在以下方面做得很好：

1. **架构设计** — MVVM 模式 + 事件总线 + 信号解耦，代码结构清晰
2. **连接池设计** — 线程本地存储 + 全局写锁的方案正确
3. **日志脱敏机制** — 正则模式考虑周到，幂等设计
4. **配置管理** — 原子写入、损坏备份、迁移逻辑完善
5. **信号缓存** — 原子写入 (`os.replace`) 防止读方看到半截内容
6. **线程安全意识** — `QuantWorker` 使用 `_stop_event` + `_lock` 保护共享资源
7. **除零防护** — `backtest_engine.py` 中 `entry_price <= 0` 检查
8. **依赖注入** — `StockDataService` 支持可选的依赖注入

---

## 五、优先修复建议 (Top 10)

按影响排序：

| 优先级 | 问题 | 影响 |
|--------|------|------|
| 1 | **backtest_engine.py 死锁** (C1) | 回测功能完全不可用 |
| 2 | **get_db_pool() TOCTOU 竞态** (I1) | 数据库连接泄漏 |
| 3 | **wave_prediction_service 写操作** (I2) | 数据丢失风险 |
| 4 | **SystemTray weakref 无保护** (U1) | 应用崩溃 |
| 5 | **QThread 泄漏** (U2/U3) | 内存泄漏 + UI 更新混乱 |
| 6 | **暗盘数据竞争** (U4) | 数据不一致 |
| 7 | **health_check Windows 不兼容** (I3) | Windows 用户健康检查失效 |
| 8 | **stock_manager 线程池无关闭** (C3) | 资源泄漏 |
| 9 | **全局单例泛滥** (C10) | 测试困难、启动顺序耦合 |
| 10 | **测试覆盖缺口** (I27) | 9个核心模块无测试 |

---

*报告生成自自动代码审查，建议结合业务优先级逐步修复。*
