# A股行情监控系统

实时 A 股行情监控桌面工具，基于 **Python + PyQt6**。支持自选股实时刷新、量化预警、暗盘资金、波浪形态分析、任务栏内嵌行情条与多种导出能力。

![应用截图](docs/assets/image.png)

**当前版本**: **v4.9.0**（唯一版本来源：[`pyproject.toml`](pyproject.toml)）

## ✨ 功能特性

### 行情与主界面
- **实时行情监控** — 自选股价格/涨跌幅实时刷新，颜色渐变标识涨跌强度
- **涨跌停封单** — 自动识别涨跌停并高亮封单手数
- **市场状态条** — 底部渐变色条展示全市场涨跌分布（覆盖 5500+ 只股票）
- **智能搜索** — 支持代码、名称、拼音、首字母添加自选股
- **桌面悬浮** — 无边框透明窗口，拖拽移动、位置记忆、双击隐藏
- **智能刷新** — 刷新间隔 **1–60 秒**自由输入（默认 5 秒），开市/闭市自动切换策略
- **开机自启 / 托盘** — 系统托盘菜单恢复/退出，支持跟随系统启动

### 量化预警（quant）
- 多周期扫描：**15m / 30m / 60m / 日线** 后台静默拉取并计算
- 指标信号：MACD/RSI/KDJ/布林/OBV/EMA 等顶底背离、金叉死叉、放量脉冲、策略共振
- 推送渠道：企业微信 Webhook / 应用消息，支持防抖（最低评分、同信号冷却、多信号合并）
- 定时复盘：按配置时刻窗口触发日报，当日同类型去重
- 回测引擎与信号对比弹窗

### 暗盘资金（dark trade）
- 后台定时抓取东方财富暗盘数据，主界面列缓存查询
- 收盘后自动/手动 Excel 导出与统计推送（`services/dark_trade`、`close_export_scheduler`）

### 波浪形态（wave）
- `core/engine/wave_analyzer` 波浪识别与 `wave_report` 报告
- 波浪图表对话框（`ui/dialogs/wave_chart_dialog`）与预测服务

### 任务栏行情条
- Windows 任务栏内嵌滚动行情条（`ui/widgets/taskbar_quote_bar`），复刻 TrafficMonitor 思路
- 自动轮播、滚轮翻页、explorer 重启后自动重嵌入；失败降级到托盘

### 导出与数据
- 自选股历史数据与指标导出（见 [docs/自选股历史数据与指标导出指南.md](docs/自选股历史数据与指标导出指南.md)）
- 暗盘/统计 Excel 导出、收盘自动导出调度
- SQLite 本地缓存与基础股票库（`resources/stocks_base.db`）

### 自动更新
- BAT 脚本无感热更新，SHA256 校验，支持备用下载源
- 日志自动清理（默认保留 7 天）

## 🛠 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python **3.11+**（CI / 打包使用 **3.13**） |
| GUI | PyQt6 |
| 架构 | 分层（core / services / models）+ DI + MVVM |
| 行情数据 | mootdx / 东方财富等多源（含腾讯/新浪备份） |
| 存储 | SQLite |
| 质量 | Ruff（lint + format）+ pytest + pre-commit |
| 打包 | PyInstaller + GitHub Actions |

## 📁 项目结构

```
stock_monitor/
├── main.py                      # 入口：python -m stock_monitor.main
├── version.py                   # 版本解析（读 pyproject.toml）
├── config/
│   └── manager.py               # ConfigManager — 配置读写与默认值
├── core/
│   ├── application.py           # StockMonitorApp — 应用生命周期
│   ├── config_center.py         # 统一配置中心
│   ├── stock_service.py         # 股票数据门面
│   ├── event_bus.py             # 进程内事件总线
│   ├── engine/                  # 量化引擎 / 波浪 / 回测 / 财务过滤
│   │   ├── quant_engine.py
│   │   ├── quant_indicators.py
│   │   ├── wave_analyzer.py
│   │   └── backtest_engine.py
│   ├── market/                  # 市场状态与股票管理
│   ├── data/                    # 行情拉取、校验、适配
│   ├── workers/                 # 后台 Worker（刷新/市场/量化）
│   ├── cache/                   # 缓存预热
│   └── app_update/              # 检查/下载/安装更新
├── services/                    # 领域服务
│   ├── notifier.py              # 推送通知
│   ├── dark_trade/              # 暗盘抓取/统计/导出/推送
│   ├── reporting/               # 包内 Excel 导出（打包可用）
│   ├── wave_prediction_service.py
│   └── close_export_scheduler.py
├── models/
│   └── stock_data.py            # 行情行数据模型
├── data/                        # 底层数据源（market / stock）
├── network/                     # 统一 HTTP NetworkManager
├── ui/
│   ├── main_window.py
│   ├── view_models/             # MVVM ViewModel
│   ├── components/              # 股票表格、系统托盘
│   ├── dialogs/                 # 设置（分页）、对比、波浪、回测
│   ├── widgets/                 # 市场状态条、任务栏行情条、搜索
│   └── models/
├── utils/                       # 日志、异常、会话缓存、重试等
└── resources/                   # icon.ico、stocks_base.db
```

## 🚀 快速开始

### 打包版（推荐）

1. 前往 [GitHub Releases](https://github.com/leo8912/stock_monitor/releases) 下载最新 `stock_monitor.zip`
2. 解压后双击 `stock_monitor.exe`
3. 绿色软件：删除目录即可卸载

### 源码运行

```bash
git clone https://github.com/leo8912/stock_monitor.git
cd stock_monitor

# Python 3.11+（建议 3.13，与 CI 一致）
pip install -r requirements.txt
# 开发依赖（pytest / ruff / pre-commit）
pip install -r requirements-dev.txt

# 运行（推荐模块方式）
python -m stock_monitor.main
```

### 基本操作

- **右键** → 设置（自选股、刷新频率 1–60 秒、量化、暗盘导出等）
- **拖拽** → 移动窗口（自动记忆位置）
- **双击** → 隐藏窗口
- **系统托盘** → 恢复 / 退出

## 🧪 开发与质量门禁

```bash
# 静态检查
python -m ruff check stock_monitor tests
python -m ruff format --check stock_monitor tests

# 单元测试（本地/CI 均建议 offscreen）
set QT_QPA_PLATFORM=offscreen   # Windows
# export QT_QPA_PLATFORM=offscreen
python -m pytest -q -p no:cacheprovider

# pre-commit
pre-commit install
pre-commit run --all-files
```

### CI / 发布工作流

| 工作流 | 触发 | 内容 |
|--------|------|------|
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | **push + pull_request** | Python 3.13 → 装依赖 → `QT_QPA_PLATFORM=offscreen` → ruff check / format --check → `pytest -q` |
| [`.github/workflows/pack-release.yml`](.github/workflows/pack-release.yml) | 推送变更 `pyproject.toml` 或手动 | 质量门禁 → PyInstaller 打包 → SHA256 → GitHub Release |

版本号以 **`pyproject.toml`** 的 `version` 为准；发布时同步更新 `CHANGELOG.md`。打包缓存 key 含 `pyproject.toml` 与 requirements 文件。

## 🔄 更新机制

1. 主程序下载 ZIP 并校验 SHA256  
2. 解压到临时目录并生成更新脚本  
3. 主程序退出，BAT 执行 `xcopy` 替换文件  
4. 脚本重启主程序并自删除  

零外部依赖，兼容中文 Windows（GBK）。

## ❓ 常见问题

| 问题 | 解答 |
|------|------|
| 数据显示 `--` | 网络异常或停牌，稍后重试 |
| 窗口不显示 | 双击托盘图标恢复 |
| 数据不更新 | 确认交易时段（约 9:15–11:30、13:00–15:00），检查网络 |
| 无法启动 | 检查杀毒拦截与文件完整性 |
| 卸载 | 删除程序目录即可 |

## 📝 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。
