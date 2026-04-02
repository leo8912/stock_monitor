# A股行情监控系统

本软件是一款专为A股投资者设计的实时行情监控桌面工具，采用 Python + PyQt6 开发，具有简洁美观的界面和丰富的功能。

![应用截图](docs/assets/image.png)

## ✨ 核心功能

- 📈 **实时行情监控** — 自选股最新价格、涨跌幅实时刷新，颜色渐变标识涨跌强度
- 🔒 **涨跌停封单** — 自动识别涨跌停股票并高亮显示封单手数
- 📊 **市场状态条** — 底部渐变色条可视化展示全市场涨跌分布（覆盖 5500+ 只股票）
- 🔍 **智能搜索** — 支持代码、名称、拼音、首字母等多种方式搜索添加自选股
- 🪟 **桌面悬浮** — 无边框透明窗口，拖拽移动，位置记忆，双击隐藏
- 🔄 **自动更新** — BAT 脚本无感热更新，SHA256 校验，支持备用下载源
- ⏰ **智能刷新** — 2~60 秒可调频率，开市/闭市自动切换刷新策略
- 🚀 **开机自启** — 支持跟随系统自动启动
- 🧹 **日志清理** — 自动清理 7 天前的日志文件

## 🛠 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| GUI 框架 | PyQt6 |
| 架构模式 | MVVM + 依赖注入 (DI Container) |
| 行情数据 | mootdx (腾讯/新浪备份源) |
| 数据存储 | SQLite |
| 构建打包 | PyInstaller + GitHub Actions CI/CD |
| 代码质量 | Ruff + Pre-commit |

## 📁 项目结构

```
stock_monitor/
├── main.py                     # 主程序入口
├── version.py                  # 版本号管理
├── config/                     # 配置管理
│   └── manager.py              # ConfigManager - 配置读写
├── core/                       # 核心业务逻辑
│   ├── application.py          # StockMonitorApp - 应用生命周期
│   ├── container.py            # DIContainer - 依赖注入容器
│   ├── startup.py              # 启动初始化逻辑
│   ├── stock_service.py        # 股票数据服务（门面）
│   ├── stock_data_fetcher.py   # 行情数据获取（多线程并发）
│   ├── stock_data_processor.py # 行情数据处理
│   ├── stock_data_validator.py # 数据校验
│   ├── stock_manager.py        # 股票管理器
│   ├── market_manager.py       # 市场状态管理
│   ├── updater.py              # 自动更新逻辑
│   ├── app_update/             # 更新子模块
│   └── workers/                # 后台 Worker 线程
│       ├── base.py             # BaseWorker - 工作线程基类
│       ├── refresh_worker.py   # 行情刷新 Worker
│       └── market_stats_worker.py # 市场统计 Worker
├── data/                       # 数据层
│   ├── fetcher.py              # 通用数据获取
│   ├── market/                 # 市场数据处理
│   └── stock/                  # 股票基础数据
├── network/                    # 网络请求封装
│   └── manager.py              # NetworkManager
├── ui/                         # 用户界面层
│   ├── main_window.py          # MainWindow - 主窗口
│   ├── constants.py            # UI 常量
│   ├── styles.py               # 样式管理
│   ├── view_models/            # ViewModel 层 (MVVM)
│   ├── components/             # UI 组件（股票表格等）
│   ├── dialogs/                # 对话框（设置、更新）
│   ├── widgets/                # 控件（市场状态条、搜索框）
│   ├── mixins/                 # Mixin（窗口拖拽、置顶）
│   └── models/                 # 数据模型
├── utils/                      # 工具模块
│   ├── logger.py               # 日志系统
│   ├── error_handler.py        # 全局异常处理
│   ├── session_cache.py        # 会话缓存
│   ├── stock_utils.py          # 股票工具函数
│   ├── helpers.py              # 通用辅助函数
│   └── log_cleaner.py          # 日志清理
└── resources/                  # 静态资源
    ├── icon.ico                # 应用图标
    └── stocks_base.db          # 基础股票数据库
```

## 🚀 快速开始

### 打包版（推荐）

1. 前往 [GitHub Releases](https://github.com/leo8912/stock_monitor/releases) 下载最新的 `stock_monitor.zip`
2. 解压到任意目录，双击 `stock_monitor.exe` 即可运行
3. 绿色软件，删除文件夹即可卸载，不写注册表

### 源码运行

```bash
# 克隆项目
git clone https://github.com/leo8912/stock_monitor.git
cd stock_monitor

# 安装依赖
pip install -r requirements.txt

# 运行
python -m stock_monitor.main
```

### 基本操作

- **右键** → 打开设置界面，管理自选股、调整刷新频率
- **拖拽** → 移动窗口位置（自动记忆）
- **双击** → 隐藏窗口
- **系统托盘** → 右键菜单恢复/退出

## 🔄 更新机制

采用 **BAT 脚本无感热更新**，流程如下：

1. 主程序下载 ZIP 更新包并校验 SHA256
2. 解压到临时目录并生成更新脚本
3. 主程序退出，BAT 脚本执行 `xcopy` 替换所有文件
4. 脚本重启主程序并自删除

优势：零外部依赖、彻底解决文件占用、GBK 编码兼容中文 Windows。

## 🏗 构建与发布

- 推送 `version.py` 变更到 `main` 分支自动触发 GitHub Actions 打包发布
- 版本号需同步更新：`pyproject.toml` + `version.py` + `CHANGELOG.md`
- 详见 [版本发布工作流](.agents/workflows/version-release.md)

## ❓ 常见问题

| 问题 | 解答 |
|------|------|
| 数据显示 "--" | 网络异常或股票停牌，稍后重试 |
| 窗口不显示 | 双击系统托盘图标恢复 |
| 数据不更新 | 确认在交易时间内（9:15-11:30, 13:00-15:00），检查网络连接 |
| 程序无法启动 | 检查杀毒软件是否拦截，确认文件完整 |
| 如何卸载 | 删除文件夹即可，绿色软件不留痕迹 |

## 📝 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)
