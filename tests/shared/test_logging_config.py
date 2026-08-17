"""Tests for structured log formatting and logger configuration.

These drive a local logger with its own StringIO handler rather than pytest's
caplog: caplog captures records before formatting, so it cannot see whether the
formatter renders the `extra=` fields at all.
"""

import io
import logging
import os
import sys
from unittest.mock import patch

import pytest

from osdu_wireline.shared.logging_config import (
    ExtraFormatter,
    configure_logging,
    get_log_level,
)


@pytest.fixture
def emit():
    """Format a record through ExtraFormatter and return the output text."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(ExtraFormatter())

    logger = logging.getLogger("osdu_wireline_formatter_test")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    def _emit(*args, **kwargs) -> str:
        stream.truncate(0)
        stream.seek(0)
        logger.info(*args, **kwargs)
        return stream.getvalue()

    yield _emit

    logger.handlers.clear()


def test_extras_render_as_key_value_pairs(emit):
    """The structured fields callers pass are visible in the output."""
    output = emit(
        "Partition get requested",
        extra={"tool": "partition_get", "partition_id": "opendes"},
    )

    assert "Partition get requested" in output
    assert "tool=partition_get" in output
    assert "partition_id=opendes" in output


def test_extras_go_on_an_indented_continuation_line(emit):
    """The message stays skimmable; fields sit underneath it."""
    lines = (
        emit("Deleting record", extra={"destructive": True}).rstrip("\n").split("\n")
    )

    assert len(lines) == 2
    assert lines[0].endswith("Deleting record")
    assert lines[1].startswith("    ")
    assert lines[1].strip() == "destructive=True"


def test_record_without_extras_is_a_single_line(emit):
    """No extras means no empty continuation line."""
    output = emit("Retrieved legal tag properties successfully")

    assert output.count("\n") == 1
    assert output.startswith("INFO     osdu_wireline_formatter_test: ")


def test_standard_record_attributes_never_leak(emit):
    """Only caller-supplied fields appear, not LogRecord's own attributes."""
    output = emit("Partition get requested", extra={"tool": "partition_get"})

    for attribute in (
        "pathname=",
        "levelno=",
        "msg=",
        "funcName=",
        "lineno=",
        "created=",
        "name=",
        "args=",
    ):
        assert attribute not in output


def test_exception_keeps_both_fields_and_traceback(emit):
    """logger.exception() must not have its extras buried by the traceback."""
    try:
        raise ValueError("boom")
    except ValueError:
        output = emit(
            "Partition get failed",
            exc_info=True,
            extra={"error_type": "ValueError"},
        )

    assert "error_type=ValueError" in output
    assert "Traceback (most recent call last)" in output
    assert "ValueError: boom" in output
    # Fields come first, so a long traceback does not push them out of view
    assert output.index("error_type=") < output.index("Traceback")


@pytest.mark.parametrize(
    "value",
    ["has spaces", "key=value", "it's quoted", 'say "hi"'],
)
def test_ambiguous_values_are_quoted(emit, value):
    """A value that could run into its neighbours is repr'd, not left bare."""
    output = emit("Legal tag created", extra={"note": value})

    assert f"note={value}" not in output
    assert f"note={value!r}" in output


def test_plain_values_are_not_quoted(emit):
    """Ordinary values stay unquoted, so lines stay readable."""
    output = emit(
        "Record deleted",
        extra={"record_id": "opendes:doc:123", "count": 4, "destructive": True},
    )

    assert "record_id=opendes:doc:123" in output
    assert "count=4" in output
    assert "destructive=True" in output


def test_unrenderable_value_does_not_break_the_line(emit):
    """A broken __str__ must not turn a log line into a formatter error."""

    class Hostile:
        def __str__(self):
            raise RuntimeError("cannot render")

        def __repr__(self):
            raise RuntimeError("cannot render either")

    output = emit("Schema search completed", extra={"filters": Hostile()})

    assert "Schema search completed" in output
    assert "filters=<unrenderable>" in output


def test_configure_logging_targets_the_package_root(restore_package_logger):
    """Configuring `osdu_wireline` covers every module's __name__ logger."""
    with patch.dict(os.environ, {}, clear=True):
        configure_logging()

    logger = logging.getLogger("osdu_wireline")
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, ExtraFormatter)

    # A module logger inherits the handler without configuring anything itself
    child = logging.getLogger("osdu_wireline.tools.partition.get")
    assert child.handlers == []
    assert child.getEffectiveLevel() == logging.INFO


def test_configure_logging_writes_to_stderr(restore_package_logger):
    """stdout carries the MCP protocol on stdio and must stay clean."""
    with patch.dict(os.environ, {}, clear=True):
        configure_logging()

    handler = logging.getLogger("osdu_wireline").handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr


def test_configure_logging_does_not_propagate(restore_package_logger):
    """FastMCP's root handler would otherwise print every record twice."""
    with patch.dict(os.environ, {}, clear=True):
        configure_logging()

    assert logging.getLogger("osdu_wireline").propagate is False


def test_configure_logging_is_idempotent(restore_package_logger):
    """Calling twice replaces the handler rather than stacking a second one."""
    with patch.dict(os.environ, {}, clear=True):
        configure_logging()
        configure_logging()

    assert len(logging.getLogger("osdu_wireline").handlers) == 1


def test_configure_logging_applies_the_configured_level(restore_package_logger):
    """OSDU_MCP_LOG_LEVEL reaches the logger, not just get_log_level()."""
    with patch.dict(os.environ, {"OSDU_MCP_LOG_LEVEL": "ERROR"}, clear=True):
        configure_logging()

    assert logging.getLogger("osdu_wireline").level == logging.ERROR


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("DEBUG", "DEBUG"),
        ("debug", "DEBUG"),
        (" warning ", "WARNING"),
        ("CRITICAL", "CRITICAL"),
        ("chatty", "INFO"),
        ("", "INFO"),
    ],
)
def test_get_log_level_normalizes_and_falls_back(value, expected):
    """Any unrecognized value degrades to INFO rather than failing to start."""
    with patch.dict(os.environ, {"OSDU_MCP_LOG_LEVEL": value}, clear=True):
        assert get_log_level() == expected


def test_get_log_level_defaults_to_info():
    """An unset variable means INFO."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_log_level() == "INFO"


def test_get_log_level_is_always_accepted_by_setlevel():
    """The returned name comes from logging's registry, so setLevel never raises."""
    with patch.dict(os.environ, {"OSDU_MCP_LOG_LEVEL": "nonsense"}, clear=True):
        logging.getLogger("osdu_wireline_level_test").setLevel(get_log_level())
