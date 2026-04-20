"""
核心模块 (Core Module)

分层架构设计:
- config/       配置和依赖注入管理
- engine/       量化分析引擎和指标计算
- data/         数据获取、处理和验证
- market/       市场状态和股票管理
- resolvers/    符号解析和API管理
- cache/        缓存预热和性能优化
- workers/      后台任务和定时扫描
- app_update/   应用更新和版本管理

这种分层设计提供了:
✓ 清晰的模块边界和职责分离
✓ 低耦合、高内聚的架构
✓ 易于测试和维护的代码组织
✓ 支持并行开发和扩展
"""

# ============================================================================
# 配置层 (Config Layer)
# ============================================================================
try:
    from .config import DIContainer

    _config_available = True
except (ImportError, ModuleNotFoundError):
    _config_available = False

# ============================================================================
# 引擎层 (Engine Layer)
# ============================================================================
try:
    from .engine import (
        BacktestEngine,
        FinancialFilter,
        QuantEngine,
    )

    _engine_available = True
except (ImportError, ModuleNotFoundError):
    _engine_available = False

# ============================================================================
# 数据层 (Data Layer)
# ============================================================================
try:
    from .data import (
        StockDataFetcher,
        StockDataProcessor,
        StockDataValidator,
    )

    _data_available = True
except (ImportError, ModuleNotFoundError):
    _data_available = False

# ============================================================================
# 市场层 (Market Layer)
# ============================================================================
try:
    from .market import (
        MarketManager,
        StockManager,
    )

    _market_available = True
except Exception as e:
    _market_available = False
    print(f"Market layer import warning: {e}")

# ============================================================================
# 解析层 (Resolvers Layer)
# ============================================================================
try:
    from .resolvers import (
        SymbolResolver,
    )

    _resolvers_available = True
except (ImportError, ModuleNotFoundError):
    _resolvers_available = False

# ============================================================================
# 缓存层 (Cache Layer)
# ============================================================================
try:
    from .cache import (
        CacheWarmer,
        PerformanceMonitor,
    )

    _cache_available = True
except (ImportError, ModuleNotFoundError):
    _cache_available = False

# ============================================================================
# 向后兼容导出 (Backward Compatibility)
# ============================================================================
try:
    from .stock_service import stock_data_service

    _stock_service_available = True
except (ImportError, ModuleNotFoundError):
    _stock_service_available = False

# ============================================================================
# 公开接口 (__all__)
# ============================================================================
__all__ = []

# 配置层
if _config_available:
    __all__.extend(["DIContainer"])

# 引擎层
if _engine_available:
    __all__.extend(["QuantEngine", "BacktestEngine", "FinancialFilter"])

# 数据层
if _data_available:
    __all__.extend(["StockDataFetcher", "StockDataProcessor", "StockDataValidator"])

# 市场层
if _market_available:
    __all__.extend(["MarketManager", "StockManager"])

# 解析层
if _resolvers_available:
    __all__.extend(["SymbolResolver"])

# 缓存层
if _cache_available:
    __all__.extend(["CacheWarmer", "PerformanceMonitor"])

# 向后兼容
if _stock_service_available:
    __all__.append("stock_data_service")
