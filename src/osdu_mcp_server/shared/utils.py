"""Utility functions for OSDU MCP Server."""

import uuid
from datetime import UTC, datetime


def get_timestamp() -> str:
    """Get current timestamp in ISO format.

    Returns:
        Current timestamp as ISO 8601 string
    """
    return datetime.now(UTC).isoformat().replace("+00:00", "") + "Z"


def get_trace_id() -> str:
    """Generate a unique trace ID for request correlation.

    Returns:
        A UUID string for request tracing
    """
    return str(uuid.uuid4())
