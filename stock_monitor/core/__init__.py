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


def _log_import_failure(layer: str) -> None:
    """记录条件导入失败的原始异常；logger 不可用时兜底写 stderr，避免阻断 core 包导入。"""
    try:
        from stock_monitor.utils.logger import app_logger

        app_logger.warning(f"{layer} import failed", exc_info=True)
    except Exception:
        # 日志系统自身不可用：兜底写 stderr，确保导入失败信息不丢失
        import sys
        import traceback

        print(f"[core] {layer} import failed", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


# ============================================================================
# 配置层 (Config Layer)
# ============================================================================
try:
    from .config import DIContainer

    _config_available = True
except Exception:
    _config_available = False
    _log_import_failure("Config layer")

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
except Exception:
    _engine_available = False
    _log_import_failure("Engine layer")

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
except Exception:
    _data_available = False
    _log_import_failure("Data layer")

# ============================================================================
# 市场层 (Market Layer)
# ============================================================================
try:
    from .market import (
        MarketManager,
        StockManager,
    )

    _market_available = True
except Exception:
    _market_available = False
    _log_import_failure("Market layer")

# ============================================================================
# 解析层 (Resolvers Layer)
# ============================================================================
try:
    from .resolvers import (
        SymbolResolver,
    )

    _resolvers_available = True
except Exception:
    _resolvers_available = False
    _log_import_failure("Resolvers layer")

# ============================================================================
# 缓存层 (Cache Layer)
# ============================================================================
try:
    from .cache import (
        CacheWarmer,
    )

    _cache_available = True
except Exception:
    _cache_available = False
    _log_import_failure("Cache layer")

# ============================================================================
# 向后兼容导出 (Backward Compatibility)
# ============================================================================
try:
    from .stock_service import stock_data_service

    _stock_service_available = True
except Exception:
    _stock_service_available = False
    _log_import_failure("Stock service")

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
    __all__.extend(["CacheWarmer"])

# 向后兼容
if _stock_service_available:
    __all__.append("stock_data_service")
