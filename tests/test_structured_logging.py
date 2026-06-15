"""Tests for structured logging"""

import logging

from stock_monitor.utils.logger import Logger


class TestLogger:
    def test_basic_logging(self):
        logger = Logger(name="test_basic", log_level=logging.DEBUG)
        # Should not raise
        logger.info("test message")
        logger.debug("debug message")
        logger.warning("warning message")
        logger.error("error message")

    def test_structured_logging(self):
        logger = Logger(name="test_structured", log_level=logging.DEBUG)
        # Should not raise
        logger.info_ctx("fetching data", symbol="sh600000", action="fetch")
        logger.warning_ctx("slow query", duration_ms=1500)
        logger.error_ctx("connection failed", host="example.com", port=443)

    def test_log_with_context_no_extra(self):
        logger = Logger(name="test_ctx", log_level=logging.DEBUG)
        logger.log_with_context(logging.INFO, "simple message")
