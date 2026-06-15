"""Tests for health check module"""

from stock_monitor.utils.health_check import (
    CheckResult,
    HealthReport,
    HealthStatus,
    _timed_check,
)


class TestHealthReport:
    def test_initial_status_healthy(self):
        report = HealthReport()
        assert report.status == HealthStatus.HEALTHY

    def test_add_degraded(self):
        report = HealthReport()
        report.add(CheckResult(name="db", status=HealthStatus.DEGRADED, message="slow"))
        assert report.status == HealthStatus.DEGRADED

    def test_add_unhealthy_overrides_degraded(self):
        report = HealthReport()
        report.add(CheckResult(name="a", status=HealthStatus.DEGRADED))
        report.add(CheckResult(name="b", status=HealthStatus.UNHEALTHY))
        assert report.status == HealthStatus.UNHEALTHY

    def test_summary_format(self):
        report = HealthReport()
        report.add(
            CheckResult(name="config", status=HealthStatus.HEALTHY, latency_ms=1.5)
        )
        summary = report.summary()
        assert "healthy" in summary
        assert "config" in summary
        assert "OK" in summary

    def test_summary_with_failure(self):
        report = HealthReport()
        report.add(
            CheckResult(name="net", status=HealthStatus.UNHEALTHY, message="timeout")
        )
        summary = report.summary()
        assert "FAIL" in summary
        assert "timeout" in summary


class TestTimedCheck:
    def test_successful_check(self):
        def ok():
            return CheckResult(name="test", status=HealthStatus.HEALTHY)

        result = _timed_check("test", ok)
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms >= 0

    def test_failed_check(self):
        def fail():
            raise RuntimeError("boom")

        result = _timed_check("test", fail)
        assert result.status == HealthStatus.UNHEALTHY
        assert "boom" in result.message
