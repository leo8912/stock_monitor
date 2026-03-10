# 开发指南

## 开发环境搭建

### 环境要求

- Python 3.9+
- pip 包管理器
- Git

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/leo8912/stock_monitor.git
cd stock_monitor

# 2. 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发/测试依赖

# 4. 运行
python -m stock_monitor.main
```

## 架构概览

项目采用 **MVVM + 依赖注入** 架构：

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   View      │ ←──── │  ViewModel   │ ←──── │   Service   │
│  (ui/)      │       │ (view_models)│       │  (core/)    │
└─────────────┘       └──────────────┘       └─────────────┘
                                                    │
                              ┌─────────────────────┤
                              ↓                     ↓
                      ┌──────────────┐      ┌──────────────┐
                      │   Data       │      │   Network    │
                      │  (data/)     │      │ (network/)   │
                      └──────────────┘      └──────────────┘
```

### 关键组件

| 组件 | 位置 | 职责 |
|------|------|------|
| `DIContainer` | `core/container.py` | 依赖注入容器，管理所有组件生命周期 |
| `StockMonitorApp` | `core/application.py` | 应用生命周期管理 |
| `MainWindowViewModel` | `ui/view_models/` | 主窗口业务逻辑，与 View 解耦 |
| `StockDataFetcher` | `core/stock_data_fetcher.py` | 多线程并发获取行情数据 |
| `DraggableWindowMixin` | `ui/mixins/draggable_window.py` | 窗口拖拽、置顶、任务栏隐藏 |

### 设计原则

- **View 不含业务逻辑** — UI 组件通过 ViewModel 的信号/槽通信
- **耗时操作在后台线程** — `RefreshWorker`、`MarketStatsWorker` 等通过 `QThread` 执行
- **所有组件通过 DI 容器获取** — 禁止全局单例，统一通过 `container.resolve()` 获取依赖

## 代码规范

项目使用 **Ruff** 作为 Linter，配置在 `pyproject.toml` 中：

- 行长度上限：88 字符
- 命名：类名 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_CASE`
- 类型提示：使用 Python 3.9+ 原生语法（`list`, `dict` 而非 `List`, `Dict`）
- Pre-commit 钩子自动检查格式

## 测试

```bash
# 运行全部测试
pytest tests/

# 查看覆盖率
pytest --cov=stock_monitor tests/
```

测试目录结构：
- `tests/unit/` — 核心业务逻辑单元测试
- `tests/integration/` — 集成测试

## 构建与发布

### 版本号管理

版本号分布在 **3 个文件**中，必须同步修改：

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | 权威版本源，CI 从此提取版本号 |
| `stock_monitor/version.py` | 运行时版本 + CI 触发器 |
| `CHANGELOG.md` | 变更日志，CI 提取写入 Release |

发布流程详见 [版本发布工作流](../../.agents/workflows/version-release.md)。

### 本地构建

GitHub Actions 自动构建，一般无需本地打包。如有需要：

```bash
pyinstaller stock_monitor.spec
```
