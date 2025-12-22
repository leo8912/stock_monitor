# 开发指南

## 项目结构

请参考 [项目结构说明](project_structure.md) 文档了解项目的整体结构和各模块功能。

## 开发环境搭建

### 环境要求

- Python 3.7+
- pip 包管理器
- Git 版本控制系统

### 安装步骤

1. 克隆项目仓库：
   ```bash
   git clone <项目地址>
   cd stock_monitor
   ```

2. 创建虚拟环境（推荐）：
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # 开发环境额外依赖
   ```

## 代码规范

### 命名约定

- 类名使用 PascalCase（首字母大写）
- 函数和变量名使用 snake_case（下划线分隔）
- 常量使用 UPPER_CASE（大写字母加下划线）
- 私有成员使用下划线前缀（如 `_private_method`）

### 代码风格

遵循 PEP 8 Python 代码风格指南：
- 缩进使用 4 个空格
- 行长度不超过 79 个字符
- 适当使用空行分隔代码块
- 导入语句按照标准库、第三方库、本地库的顺序排列

### 文档字符串

所有公共函数和类都需要有文档字符串，格式如下：

```python
def function_name(param1: type, param2: type) -> return_type:
    """
    函数功能简述
    
    详细描述函数的作用、参数说明和返回值
    
    Args:
        param1: 参数1的说明
        param2: 参数2的说明
        
    Returns:
        返回值的说明
        
    Raises:
        ExceptionType: 异常说明
    """
    pass
```

### 类型提示

使用类型提示增强代码可读性：

```python
from typing import List, Dict, Optional

def process_stocks(stocks: List[str]) -> Dict[str, Optional[float]]:
    pass
```

## 模块开发指南

### UI模块开发

UI模块位于 `ui/` 目录下，包含三个子模块：

1. `components/`: 基础UI组件
2. `widgets/`: 复杂控件
3. `dialogs/`: 对话框

所有UI组件应继承自相应的Qt基类，并遵循以下原则：
- 在 `__init__` 方法中初始化UI
- 将事件处理方法单独定义
- 使用信号和槽机制处理组件间通信

### 核心业务逻辑开发

核心业务逻辑位于 `core/` 目录下，主要包括：

1. `stock_service.py`: 股票数据服务
2. `refresh_worker.py`: 数据刷新工作线程
3. `updater.py`: 应用更新器

开发注意事项：
- 业务逻辑应与UI分离
- 耗时操作应在后台线程执行
- 使用信号机制与UI线程通信

### 数据处理模块开发

数据处理模块位于 `data/` 目录下，分为 `market/` 和 `stock/` 两个子模块：

1. `market/`: 处理市场级别的数据
2. `stock/`: 处理个股数据

开发要点：
- 数据获取应有重试机制
- 对异常数据要有合理的处理方式
- 注意不同类型股票的数据差异

### 工具模块开发

工具模块位于 `utils/` 目录下，提供通用工具函数：

开发原则：
- 工具函数应该是无状态的
- 函数功能应单一明确
- 要有完善的异常处理

## 测试

### 单元测试

测试代码位于 `tests/` 目录下，使用 pytest 框架。

运行测试：
```bash
pytest tests/
```

编写测试的原则：
- 每个测试函数只测试一个功能点
- 使用 descriptive 的函数名
- 测试数据应尽量简单明确

### 测试覆盖率

目标测试覆盖率达到 80% 以上。

查看覆盖率报告：
```bash
pytest --cov=stock_monitor tests/
```

## 构建与发布

### 构建可执行文件

使用 PyInstaller 打包应用：

```bash
python build.py
```

### 发布流程

1. 更新版本号：修改 `version.py` 文件
2. 更新变更日志：编辑 `CHANGELOG.md`
3. 提交代码并推送到主分支
4. GitHub Actions 会自动构建并发布新版本

## Git 工作流

### 分支策略

- 主分支为 `main`，仅接受 Pull Request 合并
- 功能开发应在特性分支进行
- 分支命名规范：`feature/功能名称` 或 `bugfix/问题描述`

### 提交信息规范

提交信息需要清晰描述变更内容：
- 使用祈使句（如"添加股票搜索功能"）
- 第一行不超过 50 个字符
- 如需详细说明，在第二行空行后继续

### 提交前检查

每次提交前应：
1. 运行所有测试并确保通过
2. 检查代码风格
3. 确认变更日志已更新

## 常见问题

### 如何添加新的股票数据源？

1. 在 `core/stock_service.py` 中扩展 `StockDataService` 类
2. 实现对应的数据获取方法
3. 在 `data/market/quotation.py` 中添加数据处理逻辑

### 如何添加新的UI组件？

1. 在 `ui/components/` 或 `ui/widgets/` 中创建新组件
2. 继承合适的Qt基类
3. 在主窗口或对话框中实例化并使用

### 如何优化性能？

1. 检查是否有不必要的重复计算
2. 评估缓存策略是否合理
3. 分析线程使用是否高效
4. 检查网络请求是否可以合并
5. 实施动态LRU缓存优化，根据系统资源调整缓存大小

## 贡献指南

欢迎任何形式的贡献，包括但不限于：

1. Bug修复
2. 功能增强
3. 文档完善
4. 性能优化

贡献步骤：
1. Fork项目
2. 创建特性分支
3. 提交更改
4. 发起Pull Request

在提交PR前，请确保：
- 代码符合规范
- 测试全部通过
- 文档已相应更新