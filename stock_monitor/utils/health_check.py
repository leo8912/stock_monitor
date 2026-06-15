"""
启动健康检查模块
在应用启动时验证关键组件状态
"""

import os
import time
from dataclasses import dataclass, field
from enum import Enum

from stock_monitor.utils.logger import app_logger


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class CheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    status: HealthStatus = HealthStatus.HEALTHY
    checks: list[CheckResult] = field(default_factory=list)
    startup_time_ms: float = 0.0

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)
        if result.status == HealthStatus.UNHEALTHY:
            self.status = HealthStatus.UNHEALTHY
        elif (
            result.status == HealthStatus.DEGRADED
            and self.status == HealthStatus.HEALTHY
        ):
            self.status = HealthStatus.DEGRADED

    def summary(self) -> str:
        lines = [f"健康检查: {self.status.value} ({self.startup_time_ms:.0f}ms)"]
        for c in self.checks:
            icon = {"healthy": "OK", "degraded": "WARN", "unhealthy": "FAIL"}[
                c.status.value
            ]
            msg = f" - {c.message}" if c.message else ""
            lines.append(f"  [{icon}] {c.name} ({c.latency_ms:.0f}ms){msg}")
        return "\n".join(lines)


def _timed_check(name: str, func, *args, **kwargs) -> CheckResult:
    """执行单个检查并计时"""
    start = time.monotonic()
    try:
        result = func(*args, **kwargs)
        latency = (time.monotonic() - start) * 1000
        if isinstance(result, CheckResult):
            result.latency_ms = latency
            return result
        return CheckResult(name=name, status=HealthStatus.HEALTHY, latency_ms=latency)
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return CheckResult(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            latency_ms=latency,
        )


def check_config() -> CheckResult:
    """检查配置文件可访问性"""
    try:
        from stock_monitor.config.manager import ConfigManager

        cfg = ConfigManager()
        _ = cfg.get("user_stocks", [])
        return CheckResult(name="配置文件", status=HealthStatus.HEALTHY)
    except Exception as e:
        return CheckResult(
            name="配置文件", status=HealthStatus.UNHEALTHY, message=str(e)
        )


def check_database() -> CheckResult:
    """检查数据库连接"""
    try:
        from stock_monitor.core.config.container import container
        from stock_monitor.data.stock.stock_db import StockDatabase

        db = container.get(StockDatabase)
        count = db.get_all_stocks_count()
        if count == 0:
            return CheckResult(
                name="数据库",
                status=HealthStatus.DEGRADED,
                message=f"数据库为空 ({count}条记录)",
            )
        return CheckResult(
            name="数据库", status=HealthStatus.HEALTHY, message=f"{count}条记录"
        )
    except Exception as e:
        return CheckResult(name="数据库", status=HealthStatus.UNHEALTHY, message=str(e))


def check_network() -> CheckResult:
    """检查网络连通性"""
    try:
        import urllib.request

        req = urllib.request.Request("https://www.baidu.com", method="HEAD")
        urllib.request.urlopen(req, timeout=5)
        return CheckResult(name="网络连接", status=HealthStatus.HEALTHY)
    except Exception as e:
        return CheckResult(
            name="网络连接", status=HealthStatus.DEGRADED, message=str(e)
        )


def check_dependencies() -> CheckResult:
    """检查关键依赖是否可用"""
    missing = []
    for mod in ["PyQt6", "pandas", "easyquotation"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return CheckResult(
            name="依赖检查",
            status=HealthStatus.DEGRADED,
            message=f"缺失: {', '.join(missing)}",
        )
    return CheckResult(name="依赖检查", status=HealthStatus.HEALTHY)


def check_disk_space() -> CheckResult:
    """检查磁盘空间"""
    try:
        config_dir = (
            os.path.dirname(app_logger.logger.handlers[0].baseFilename)
            if app_logger.logger.handlers
            else "."
        )
        stat = os.statvfs(config_dir)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        if free_mb < 100:
            return CheckResult(
                name="磁盘空间",
                status=HealthStatus.DEGRADED,
                message=f"剩余 {free_mb:.0f}MB",
            )
        return CheckResult(
            name="磁盘空间", status=HealthStatus.HEALTHY, message=f"{free_mb:.0f}MB可用"
        )
    except Exception:
        return CheckResult(
            name="磁盘空间", status=HealthStatus.HEALTHY, message="跳过检查"
        )


def run_health_check() -> HealthReport:
    """执行完整健康检查"""
    start = time.monotonic()
    report = HealthReport()

    checks = [
        ("配置文件", check_config),
        ("数据库", check_database),
        ("网络连接", check_network),
        ("依赖检查", check_dependencies),
        ("磁盘空间", check_disk_space),
    ]

    for name, check_func in checks:
        result = _timed_check(name, check_func)
        report.add(result)

    report.startup_time_ms = (time.monotonic() - start) * 1000
    return report
