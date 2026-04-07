# P1-4 文件迁移指南 (Migration Guide)

## 目录

1. [迁移概览](#迁移概览)
2. [前置检查](#前置检查)
3. [Phase 1 - 配置层迁移](#phase-1---配置层迁移)
4. [Phase 2 - 引擎层迁移](#phase-2---引擎层迁移)
5. [Phase 3 - 数据层迁移](#phase-3---数据层迁移)
6. [Phase 4 - 市场与解析层迁移](#phase-4---市场与解析层迁移)
7. [Phase 5 - 缓存层迁移](#phase-5---缓存层迁移)
8. [验证和测试](#验证和测试)
9. [故障排除](#故障排除)

---

## 迁移概览

### 目标和范围
- **目标:** 将 core/ 下的 18 个文件从扁平结构迁移到 6 个分层目录
- **范围:** core/ 层下的所有模块，不涉及 UI、services、workers 等
- **持续时间:** 约 1-2 小时
- **风险:** 低 (充分的测试覆盖)
- **回滚:** 可通过 git 恢复

### 迁移策略
1. **分阶段迁移:** 按依赖关系从低到高迁移
2. **一次性更新导入:** 完成文件移动后批量更新所有导入
3. **充分测试:** 每个阶段后运行测试验证
4. **向后兼容:** 保持顶层导出，确保现有代码不破坏

### 成功标准
- ✅ 所有 122 个测试通过
- ✅ 应用可正常启动
- ✅ 无导入错误
- ✅ 无运行时异常

---

## 前置检查

### 检查清单
```bash
# 1. 验证 git 状态
$ git status
# 应该显示工作目录清洁

# 2. 验证测试状态
$ pytest tests/ -v
# 应该显示 122 passed

# 3. 列出 core/ 文件
$ ls -la stock_monitor/core/*.py | wc -l
# 应该显示 ~20 个文件

# 4. 验证新目录存在
$ ls -ld stock_monitor/core/{config,engine,data,market,resolvers,cache}
# 应该显示 6 个目录
```

### 所需信息
- 当前 git branch: `main` 或 `dev`
- Python 版本: 3.13.11
- pytest 已安装: pytest 9.0.2

### 备份计划
```bash
# 迁移前备份
$ git commit -am "Before P1-4 architecture migration"
$ git tag -a p1-4-before-migration -m "Backup before migration"
```

---

## Phase 1 - 配置层迁移

### 目标
从 core/ 根目录迁移配置相关文件到 core/config/

### 文件列表
```
源:                          目标:
core/service_config.py   →   core/config/service_config.py
core/container.py        →   core/config/container.py
core/startup.py          →   core/config/startup.py
```

### 迁移步骤

#### 步骤 1.1 - 检查源文件
```bash
# 验证源文件存在
ls -la stock_monitor/core/{service_config.py,container.py,startup.py}
```

#### 步骤 1.2 - 复制文件
```bash
# 复制到新目录
cp stock_monitor/core/service_config.py stock_monitor/core/config/
cp stock_monitor/core/container.py stock_monitor/core/config/
cp stock_monitor/core/startup.py stock_monitor/core/config/
```

#### 步骤 1.3 - 更新 config/__init__.py
编辑 `stock_monitor/core/config/__init__.py`：
```python
"""
配置和依赖注入层 (Config & DI Layer)

职责:
- 应用配置管理 (参数、环境变量)
- 依赖注入容器 (组件生命周期)
- 启动流程协调 (初始化顺序)
"""

from .service_config import ServiceConfig, load_config, save_config
from .container import DIContainer
from .startup import startup_application

__all__ = [
    "ServiceConfig",
    "load_config",
    "save_config",
    "DIContainer",
    "startup_application",
]
```

#### 步骤 1.4 - 查找和更新导入
找出所有导入这些模块的文件：
```bash
# 搜索导入
grep -r "from.*service_config import\|from.*container import\|from.*startup import" \
    stock_monitor/ --include="*.py" | grep -v ".pyc"
```

**需要更新的文件 (~7 个):**
- stock_monitor/main.py
- stock_monitor/tests/test_*.py (多个)
- stock_monitor/ui/app.py

**更新模式:**
```python
# 旧的
from stock_monitor.core.service_config import ServiceConfig

# 新的
from stock_monitor.core.config import ServiceConfig
```

#### 步骤 1.5 - 删除原始文件
```bash
# 删除旧位置的文件
rm stock_monitor/core/service_config.py
rm stock_monitor/core/container.py
rm stock_monitor/core/startup.py
```

#### 步骤 1.6 - 验证
```bash
# 导入测试
python -c "from stock_monitor.core.config import DIContainer; print('✓ 导入正常')"

# 运行测试
pytest tests/test_container.py -v
```

---

## Phase 2 - 引擎层迁移

### 目标
从 core/ 根目录迁移量化引擎相关文件到 core/engine/

### 文件列表
```
源:                               目标:
core/quant_engine.py         →   core/engine/quant_engine.py
core/quant_engine_constants.py   →   core/engine/constants.py
core/financial_filter.py     →   core/engine/financial_filter.py
core/backtest_engine.py      →   core/engine/backtest_engine.py
```

### 迁移步骤

#### 步骤 2.1 - 复制文件
```bash
cp stock_monitor/core/quant_engine.py stock_monitor/core/engine/
cp stock_monitor/core/quant_engine_constants.py stock_monitor/core/engine/constants.py
cp stock_monitor/core/financial_filter.py stock_monitor/core/engine/
cp stock_monitor/core/backtest_engine.py stock_monitor/core/engine/
```

#### 步骤 2.2 - 更新 engine/__init__.py
```python
"""
量化分析引擎层 (Quant Engine Layer)

职责:
- 技术指标计算 (MACD, RSI, RSRS, OBV, BB, Volume)
- 交易信号生成
- 策略回测
- 财务数据过滤
"""

from .quant_engine import QuantEngine
from .constants import (
    INDICATOR_PARAMS,
    RSI_PERIODS,
    MACD_PARAMS,
    # ... 其他常量
)
from .financial_filter import FinancialFilter
from .backtest_engine import BacktestEngine

__all__ = [
    "QuantEngine",
    "FinancialFilter",
    "BacktestEngine",
    "INDICATOR_PARAMS",
    "RSI_PERIODS",
    "MACD_PARAMS",
]
```

#### 步骤 2.3 - 更新内部导入
编辑 `core/engine/quant_engine.py`：
```python
# 旧的
from .quant_engine_constants import INDICATOR_PARAMS

# 新的
from .constants import INDICATOR_PARAMS
```

#### 步骤 2.4 - 搜索和更新外部导入
```bash
grep -r "from.*quant_engine import\|from.*financial_filter import\|from.*backtest_engine import" \
    stock_monitor/ --include="*.py" | grep -v "core/engine"
```

**更新模式:**
```python
# 旧的
from stock_monitor.core.quant_engine import QuantEngine

# 新的
from stock_monitor.core.engine import QuantEngine
```

#### 步骤 2.5 - 删除原始文件
```bash
rm stock_monitor/core/quant_engine.py
rm stock_monitor/core/quant_engine_constants.py
rm stock_monitor/core/financial_filter.py
rm stock_monitor/core/backtest_engine.py
```

#### 步骤 2.6 - 验证
```bash
# 导入测试
python -c "from stock_monitor.core.engine import QuantEngine; print('✓ 引擎导入正常')"

# 运行引擎测试 (关键)
pytest tests/test_quant_engine.py -v
pytest tests/test_financial_filter.py -v
pytest tests/test_backtest_engine.py -v
```

---

## Phase 3 - 数据层迁移

### 目标
从 core/ 根目录迁移数据处理文件到 core/data/

### 文件列表
```
源:                               目标:
core/stock_data_fetcher.py   →   core/data/fetcher.py
core/stock_data_processor.py →   core/data/processor.py
core/stock_data_validator.py →   core/data/validator.py
```

### 迁移步骤

#### 步骤 3.1 - 复制和重命名文件
```bash
cp stock_monitor/core/stock_data_fetcher.py stock_monitor/core/data/fetcher.py
cp stock_monitor/core/stock_data_processor.py stock_monitor/core/data/processor.py
cp stock_monitor/core/stock_data_validator.py stock_monitor/core/data/validator.py
```

#### 步骤 3.2 - 更新 data/__init__.py
```python
"""
数据处理层 (Data Layer)

职责:
- 多源数据获取 (mootdx, akshare)
- 数据转换和标准化
- 数据完整性验证
- 容错和降级处理
"""

from .fetcher import StockDataFetcher, MarketDataFetcher
from .processor import StockDataProcessor
from .validator import StockDataValidator

__all__ = [
    "StockDataFetcher",
    "MarketDataFetcher",
    "StockDataProcessor",
    "StockDataValidator",
]
```

#### 步骤 3.3 - 搜索和更新导入
```bash
grep -r "from.*stock_data_fetcher\|from.*stock_data_processor\|from.*stock_data_validator" \
    stock_monitor/ --include="*.py" | grep -v "core/data"
```

**更新模式:**
```python
# 旧的
from stock_monitor.core.stock_data_fetcher import StockDataFetcher

# 新的
from stock_monitor.core.data import StockDataFetcher
```

#### 步骤 3.4 - 删除原始文件
```bash
rm stock_monitor/core/stock_data_fetcher.py
rm stock_monitor/core/stock_data_processor.py
rm stock_monitor/core/stock_data_validator.py
```

#### 步骤 3.5 - 验证
```bash
# 导入测试
python -c "from stock_monitor.core.data import StockDataFetcher; print('✓ 数据层导入正常')"

# 运行测试
pytest tests/test_core_fetcher.py -v
pytest tests/test_stock_data_processor.py -v
pytest tests/test_core_validator.py -v
```

---

## Phase 4 - 市场与解析层迁移

### 目标
迁移市场管理和符号解析文件

### 文件列表
```
A. 市场层 (Market Layer):
core/market_manager.py   →   core/market/market_manager.py
core/stock_manager.py    →   core/market/stock_manager.py

B. 解析层 (Resolvers Layer):
core/symbol_resolver.py  →   core/resolvers/symbol_resolver.py
core/mootdx_registry.py  →   core/resolvers/mootdx_registry.py
```

### 迁移步骤 (市场层)

#### 步骤 4A.1 - 复制文件
```bash
cp stock_monitor/core/market_manager.py stock_monitor/core/market/
cp stock_monitor/core/stock_manager.py stock_monitor/core/market/
```

#### 步骤 4A.2 - 更新 market/__init__.py
```python
"""
市场管理层 (Market Layer)

职责:
- 市场开闭市状态管理
- 股票基本信息维护
- 交易时间处理
"""

from .market_manager import MarketManager
from .stock_manager import StockManager

__all__ = ["MarketManager", "StockManager"]
```

#### 步骤 4A.3 - 搜索和更新导入
```bash
grep -r "from.*market_manager\|from.*stock_manager" \
    stock_monitor/ --include="*.py" | grep -v "core/market"
```

### 迁移步骤 (解析层)

#### 步骤 4B.1 - 复制文件
```bash
cp stock_monitor/core/symbol_resolver.py stock_monitor/core/resolvers/
cp stock_monitor/core/mootdx_registry.py stock_monitor/core/resolvers/
```

#### 步骤 4B.2 - 更新 resolvers/__init__.py
```python
"""
符号解析层 (Resolvers Layer)

职责:
- 证券代码规范化和转换
- 多市场代码映射
- API 客户端生命周期管理
"""

from .symbol_resolver import SymbolResolver, SymbolType
from .mootdx_registry import MootdxRegistry

__all__ = ["SymbolResolver", "SymbolType", "MootdxRegistry"]
```

#### 步骤 4B.3 - 搜索和更新导入
```bash
grep -r "from.*symbol_resolver\|from.*mootdx_registry" \
    stock_monitor/ --include="*.py" | grep -v "core/resolvers"
```

#### 步骤 4C - 删除原始文件
```bash
rm stock_monitor/core/market_manager.py
rm stock_monitor/core/stock_manager.py
rm stock_monitor/core/symbol_resolver.py
rm stock_monitor/core/mootdx_registry.py
```

#### 步骤 4D - 验证
```bash
pytest tests/test_market_manager.py -v
pytest tests/test_symbol_resolver.py -v
```

---

## Phase 5 - 缓存层迁移

### 文件列表
```
源:                        目标:
core/cache_warmer.py   →   core/cache/cache_warmer.py
```

### 迁移步骤

#### 步骤 5.1 - 复制文件
```bash
cp stock_monitor/core/cache_warmer.py stock_monitor/core/cache/
```

#### 步骤 5.2 - 更新 cache/__init__.py
```python
"""
缓存和优化层 (Cache & Optimization Layer)

职责:
- 缓存预热和管理
- 指标计算优化
- 性能监测和诊断
"""

from .cache_warmer import (
    CacheWarmer,
    IndicatorComputationOptimizer,
    PerformanceMonitor,
)

__all__ = [
    "CacheWarmer",
    "IndicatorComputationOptimizer",
    "PerformanceMonitor",
]
```

#### 步骤 5.3 - 搜索和更新导入
```bash
grep -r "from.*cache_warmer" stock_monitor/ --include="*.py" | grep -v "core/cache"
```

#### 步骤 5.4 - 删除原始文件
```bash
rm stock_monitor/core/cache_warmer.py
```

#### 步骤 5.5 - 验证
```bash
pytest tests/test_cache_warmer_p1_2.py -v
```

---

## 验证和测试

### 完整验证清单

#### 步骤 1 - 导入验证
```python
# 测试所有新导入路径
from stock_monitor.core.config import DIContainer
from stock_monitor.core.engine import QuantEngine, BacktestEngine
from stock_monitor.core.data import StockDataFetcher
from stock_monitor.core.market import MarketManager
from stock_monitor.core.resolvers import SymbolResolver
from stock_monitor.core.cache import CacheWarmer

# 向后兼容导入
from stock_monitor.core import MarketManager, StockManager
```

#### 步骤 2 - 运行所有测试
```bash
# 运行完整测试套件
pytest tests/ -v --tb=short

# 预期结果: 122 passed, 2 skipped
```

#### 步骤 3 - 运行应用
```bash
# 测试应用启动
python -m stock_monitor.main

# 验证:
# ✓ 应用窗口打开
# ✓ 无导入错误
# ✓ 无运行时异常
```

#### 步骤 4 - 目录验证
```bash
# 验证新目录结构
find stock_monitor/core -name "__init__.py" -type f | sort

# 预期输出:
# stock_monitor/core/__init__.py
# stock_monitor/core/cache/__init__.py
# stock_monitor/core/config/__init__.py
# stock_monitor/core/data/__init__.py
# stock_monitor/core/engine/__init__.py
# stock_monitor/core/market/__init__.py
# stock_monitor/core/resolvers/__init__.py
```

#### 步骤 5 - 导入映射验证
```bash
# 验证旧导入路径的文件已删除
ls stock_monitor/core/quant_engine.py 2>&1
# 预期: No such file or directory

# 验证新导入路径的文件存在
ls stock_monitor/core/engine/quant_engine.py
# 预期: 文件存在
```

---

## 故障排除

### 常见问题和解决方案

#### Q1: ImportError: 无法导入某个模块
```python
# 错误示例
ImportError: cannot import name 'QuantEngine' from 'stock_monitor.core'

# 解决方案
1. 检查新目录结构是否正确
2. 检查 __init__.py 是否有正确的导出
3. 检查是否有循环导入
4. 清理 __pycache__ 文件夹

$ find stock_monitor -name "__pycache__" -type d -exec rm -rf {} +
$ python -m py_compile stock_monitor/core/engine/__init__.py
```

#### Q2: 测试失败 ModuleNotFoundError
```bash
# 错误
ModuleNotFoundError: No module named 'stock_monitor.core.quant_engine'

# 解决方案
1. 检查旧文件是否已删除
2. 检查新导入语句是否更新
3. 重新安装包

$ pip install -e .
$ pytest tests/test_quant_engine.py -v
```

#### Q3: 循环导入 (Circular Import)
```python
# 症状
ImportError: cannot import name 'X' from partially initialized module 'Y'

# 解决方案
1. 检查层间依赖是否遵循单向流
2. 使用 TYPE_CHECKING 处理可选导入
3. 延迟导入 (import inside function if needed)
```

#### Q4: 旧导入仍然工作（意外）
```python
# 如果旧导入 "from stock_monitor.core.quant_engine import ..."
# 仍然有效，说明有两个问题：
# 1. 旧文件未删除
# 2. 或新导出未配置

# 解决方案
$ rm stock_monitor/core/quant_engine.py
$ grep -r "from stock_monitor.core.quant_engine" tests/ --include="*.py"
# 更新所有导入
```

### 回滚步骤
如果发生严重问题，可以回滚：
```bash
# 回滚到迁移前
$ git reset --hard p1-4-before-migration

# 或逐个步骤回滚
$ git reset --hard HEAD~1
$ git revert HEAD
```

---

## 迁移清单

### Pre-Migration
- [ ] 创建 git 备份分支
- [ ] 运行所有测试确保绿灯
- [ ] 清理 __pycache__

### Phase 1 - Config
- [ ] 复制 service_config.py, container.py, startup.py
- [ ] 更新 config/__init__.py
- [ ] 更新所有 from 导入
- [ ] 删除旧文件
- [ ] 运行配置相关测试 ✓

### Phase 2 - Engine
- [ ] 复制所有引擎文件
- [ ] 更新 engine/__init__.py
- [ ] 更新所有 from 导入
- [ ] 删除旧文件
- [ ] 运行引擎测试 ✓ (122/122)

### Phase 3 - Data
- [ ] 复制所有数据文件
- [ ] 更新 data/__init__.py
- [ ] 更新所有 from 导入
- [ ] 删除旧文件
- [ ] 运行数据测试 ✓

### Phase 4 - Market & Resolvers
- [ ] 复制市场和解析文件
- [ ] 更新 market/__init__.py
- [ ] 更新 resolvers/__init__.py
- [ ] 更新所有 from 导入
- [ ] 删除旧文件
- [ ] 运行相关测试 ✓

### Phase 5 - Cache
- [ ] 复制缓存文件
- [ ] 更新 cache/__init__.py
- [ ] 更新所有 from 导入
- [ ] 删除旧文件
- [ ] 运行缓存测试 ✓

### Post-Migration
- [ ] 运行完整测试套件 (122/122 expected)
- [ ] 验证应用启动无误
- [ ] 验证新导入路径工作
- [ ] 验证向后兼容导出工作
- [ ] 更新文档
- [ ] 提交 git 变更
- [ ] 创建 tag: `p1-4-migration-complete`

---

## 总结

这个迁移指南提供了系统的、经过验证的方法来将 core/ 层从扁平结构重组为清晰的分层架构。

**关键原则:**
1. **分阶段:** 按依赖关系逐步迁移
2. **充分验证:** 每个阶段都有清晰的验证步骤
3. **可回滚:** 每个阶段都可以独立回滚
4. **向后兼容:** 保持顶层导出，确保现有代码继续工作

预计完成时间: **1-2 小时**

成功标准: **122/122 tests passing + 零导入错误**
