"""Tests for logging manager."""

import json
import logging
import os
import unittest
from unittest.mock import patch

from osdu_wireline.shared.logging_manager import (
    JSONFormatter,
    LoggingManager,
    configure_logging,
    get_logger,
)


class TestLoggingManager(unittest.TestCase):
    """Tests for the LoggingManager class."""

    def setUp(self):
        """Set up test environment."""
        # Save and reset test logger state before each test
        self.test_logger = logging.getLogger("osdu_mcp_test")
        self.test_handlers = self.test_logger.handlers.copy()
        self.test_level = self.test_logger.level
        self.test_logger.handlers = []

    def tearDown(self):
        """Clean up test environment."""
        # Restore test logger state after each test
        self.test_logger.handlers = self.test_handlers
        self.test_logger.setLevel(self.test_level)

    def test_logging_disabled(self):
        """Test that logging is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            manager = LoggingManager()
            manager.configure()

        # Verify the osdu_mcp_test logger is set to ERROR level
        assert logging.getLogger("osdu_mcp_test").level == logging.ERROR

    def test_logging_enabled(self):
        """Test that logging is configured when enabled."""
        env = {"OSDU_MCP_LOGGING_ENABLED": "true", "OSDU_MCP_LOGGING_LEVEL": "INFO"}
        with (
            patch.dict(os.environ, env, clear=True),
            patch("osdu_wireline.shared.logging_manager.sys.modules", {}),
        ):
            manager = LoggingManager()

            # Get the osdu_mcp logger and remove any existing handlers
            test_logger = logging.getLogger("osdu_mcp")
            for handler in test_logger.handlers[:]:
                test_logger.removeHandler(handler)

            manager.configure()

            # Verify log level
            assert test_logger.level == logging.INFO

    def test_json_formatter(self):
        """Test JSON formatter formats logs correctly."""
        # Create formatter directly
        formatter = JSONFormatter()

        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test_path",
            lineno=42,
            msg="Test message",
            args={},
            exc_info=None,
        )

        # Add extra fields
        record.extra = {"test_field": "test_value"}

        # Format the record
        formatted = formatter.format(record)

        # Parse the JSON
        log_json = json.loads(formatted)

        # Verify JSON structure
        assert log_json["level"] == "INFO"
        assert log_json["message"] == "Test message"
        assert log_json["tool"] == "test_logger"
        assert "timestamp" in log_json
        assert "trace_id" in log_json

    def test_get_logger(self):
        """Test get_logger returns configured logger."""
        env = {"OSDU_MCP_LOGGING_ENABLED": "true", "OSDU_MCP_LOGGING_LEVEL": "INFO"}
        with patch.dict(os.environ, env, clear=True):
            # Get a logger
            logger = get_logger("test_module")

        # Verify logger is configured with correct name
        assert logger.name == "osdu_mcp_test.test_module"

    def test_configure_global(self):
        """Test the global configure_logging function."""
        env = {"OSDU_MCP_LOGGING_ENABLED": "true", "OSDU_MCP_LOGGING_LEVEL": "DEBUG"}
        with patch.dict(os.environ, env, clear=True):
            # Configure logging using global function
            configure_logging()

            # Verify we didn't modify the root logger
            root_logger = logging.getLogger()
            assert root_logger.level == logging.WARNING  # Default root logger level


if __name__ == "__main__":
    unittest.main()
