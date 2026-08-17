"""Logging configuration for OSDU Wireline.

Log calls throughout this package carry structured fields via the standard
``extra=`` keyword. The formatter here renders those fields, which the standard
library's default formatting silently discards.
"""

import logging
import sys

from .env import get_env

# Attributes the standard library puts on every record. Derived from a throwaway
# record rather than hardcoded, so it stays correct as LogRecord gains fields
# across Python versions; "message" and "asctime" are added by Formatter itself.
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", logging.NOTSET, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}

# Characters that make a bare value ambiguous once it sits in a key=value list.
_NEEDS_QUOTING = frozenset(" \t\n\r\"'=")


def _render_value(value: object) -> str:
    """Render one extra field's value for a key=value pair.

    Args:
        value: Value passed in an ``extra`` dict

    Returns:
        The value as text, quoted when it would otherwise run into its neighbours
    """
    try:
        text = str(value)
        if any(char in _NEEDS_QUOTING for char in text):
            return repr(value)
        return text
    except Exception:
        # Broad on purpose: an unrenderable field must cost one value, not the
        # whole log line and a formatter traceback on stderr.
        return "<unrenderable>"


class ExtraFormatter(logging.Formatter):
    """Formatter that renders ``extra=`` fields alongside the message.

    Output is one header line, then an indented ``key=value`` line when the
    record carries extra fields, then any traceback:

        WARNING  osdu_wireline.tools.legal.delete: Legal tag deleted
            operation=delete_legaltag tag_name=opendes-public destructive=True
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a record as a header line plus its structured fields.

        Args:
            record: Log record

        Returns:
            The formatted entry, spanning multiple lines when there are extras
            or exception information
        """
        lines = [f"{record.levelname:<8} {record.name}: {record.getMessage()}"]

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS
        }
        if extras:
            rendered = " ".join(
                f"{key}={_render_value(value)}" for key, value in extras.items()
            )
            lines.append(f"    {rendered}")

        # After the extras, so logger.exception() keeps both its fields and its
        # traceback rather than one burying the other.
        if record.exc_info:
            lines.append(self.formatException(record.exc_info))
        if record.stack_info:
            lines.append(self.formatStack(record.stack_info))

        return "\n".join(lines)


def get_log_level() -> str:
    """Read OSDU_MCP_LOG_LEVEL, falling back to INFO when unset or unrecognized.

    Returns:
        A level name from logging's own registry, so setLevel always accepts it
    """
    value = (get_env("OSDU_MCP_LOG_LEVEL", "INFO") or "INFO").strip().upper()
    if value in logging.getLevelNamesMapping():
        return value
    return "INFO"


def configure_logging() -> None:
    """Attach the structured formatter to this package's logger.

    Configures the package-root logger, so every module's
    ``logging.getLogger(__name__)`` is covered without changing its call sites.
    Third-party loggers are left alone and keep flowing through whatever handler
    the root logger holds.

    Safe to call more than once; the previous handler is replaced.
    """
    logger = logging.getLogger("osdu_wireline")
    logger.setLevel(get_log_level())

    for existing in logger.handlers[:]:
        logger.removeHandler(existing)

    # stderr explicitly: stdout carries the MCP protocol on the stdio transport,
    # and a log line written there would corrupt the JSON-RPC framing.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ExtraFormatter())
    logger.addHandler(handler)

    # FastMCP installs its own handler on the root logger, which would print
    # every one of our records a second time without its extra fields.
    logger.propagate = False
