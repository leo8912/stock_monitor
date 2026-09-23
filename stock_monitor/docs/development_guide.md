# 开发指南

## 开发环境搭建

### 环境要求

- Python **3.11+**（CI / 打包使用 **3.13**，与 `pyproject.toml` 的 `requires-python` 一致）
- pip 包管理器
- Git

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/leo8912/stock_monitor.git
cd stock_monitor

# 2. 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发/测试依赖

# 4. 运行
python -m stock_monitor.main
```

## 架构概览

项目采用 **分层 + MVVM + 依赖注入**：

```
┌─────────────┐       ┌──────────────┐       ┌──────────────────┐
│   View      │ ←──── │  ViewModel   │ ←──── │  Service / Core  │
│  (ui/)      │       │ (view_models)│       │ (services/, core/)│
└─────────────┘       └──────────────┘       └──────────────────┘
                                                      │
                        ┌─────────────────────────────┼──────────────┐
                        ↓                             ↓              ↓
                ┌──────────────┐              ┌──────────────┐ ┌──────────────┐
                │   Data       │              │   Network    │ │   Models     │
                │  (data/)     │              │ (network/)   │ │  (models/)   │
                └──────────────┘              └──────────────┘ └──────────────┘
```

依赖方向约定（`tests/test_architecture_layers.py` 守卫）：
`ui → services → core → data → utils`，禁止下层导入上层。

### 关键组件

| 组件 | 位置 | 职责 |
|------|------|------|
| `DIContainer` | `core/config/container.py` | 依赖注入容器，管理组件生命周期 |
| `StockMonitorApp` | `core/application.py` | 应用生命周期管理 |
| `MainWindowViewModel` | `ui/view_models/main_window_view_model.py` | 主窗口业务逻辑，与 View 解耦 |
| `StockDataFetcher` | `core/data/stock_data_fetcher.py` | 多线程并发获取行情数据 |
| `DraggableWindowMixin` | `ui/mixins/draggable_window.py` | 窗口拖拽、置顶、任务栏隐藏 |
| `NetworkManager` | `network/manager.py` | 统一 HTTP 入口（超时、重试、镜像回退） |
| `AppUpdater` | `core/updater.py` + `core/app_update/` | 检查 / 下载 / 安装更新 |

### 设计原则

- **View 不含业务逻辑** — UI 通过 ViewModel 的信号/槽通信
- **耗时操作在后台线程** — `RefreshWorker`、`QuantWorker` 等通过 `QThread` 执行
- **组件经 DI 容器获取** — 避免「container 新建 + module 单例」双实例
- **更新检查/下载不堵 UI** — `UpdateCheckThread` / `UpdateDownloadThread` + 安全提示信号

## 代码规范

项目使用 **Ruff**（lint + format），配置在 `pyproject.toml`：

- 行长度上限：88 字符
- 命名：类名 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_CASE`
- 类型提示：Python **3.11+** 原生语法（`list`、`dict`、`X | None`）
- Pre-commit：ruff / ruff-format / check-yaml 等

## 测试

```bash
# 本地/CI 均建议 offscreen
set QT_QPA_PLATFORM=offscreen   # Windows
# export QT_QPA_PLATFORM=offscreen

python -m ruff check stock_monitor tests
python -m ruff format --check stock_monitor tests
python -m pytest -q -p no:cacheprovider
```

测试目录结构：

| 路径 | 说明 |
|------|------|
| `tests/test_*.py` | 默认单元测试（`pytest` 主集合） |
| `tests/integration/` | 依赖真实外部服务（默认 marker `integration` 排除） |
| `tests/smoke/` | GUI 冒烟（marker `gui`，默认排除） |
| `tests/tools/` | 测试辅助工具脚本 |

默认 `addopts` 已排除 `gui` / `integration`；需要时用 `-m gui` / `-m integration` 单独跑。

## 构建与发布

### 版本号管理

**唯一版本真源：`pyproject.toml` 的 `version`。**

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | 权威版本源；**变更此文件会触发** `pack-release.yml` 打包发布 |
| `stock_monitor/version.py` | 运行时解析：`pyproject.toml` > installed metadata > dev；**无需手写版本号** |
| `CHANGELOG.md` | 变更日志；发布时在顶部新增 `## [vX.Y.Z] - YYYY-MM-DD` 条目 |

发布步骤：

1. 改 `pyproject.toml` 的 `version`
2. 在 `CHANGELOG.md` 顶部写对应版本条目
3. 本地跑 `ruff` + `pytest`
4. `git commit` 并推送 `main`
5. CI（`ci.yml`）跑门禁；`pack-release.yml` 在 `pyproject.toml` 变更时 PyInstaller → SHA256 → GitHub Release

### 工作流

| 工作流 | 触发 | 内容 |
|--------|------|------|
| `.github/workflows/ci.yml` | 每次 push / PR | ruff check / format + pytest |
| `.github/workflows/pack-release.yml` | `pyproject.toml` 变更或手动 | 打包发布（不重复跑门禁） |

### 本地构建

一般由 GitHub Actions 打包。如有需要：

```bash
pyinstaller stock_monitor.spec
```

### 升级链路（简述）

1. 设置 → 检查更新：请求 `api.github.com/.../releases/latest`
2. 下载 ZIP：多 GitHub 加速镜像优先，失败回退官方 `browser_download_url`
3. SHA256：仅信任官方域名 / Release body
4. 解压临时目录 → 生成更新脚本 → 主程序退出 → BAT `xcopy` 替换 → 重启

用户文档见仓库根目录 [README.md](../../../README.md)；功能说明见 `docs/`。
