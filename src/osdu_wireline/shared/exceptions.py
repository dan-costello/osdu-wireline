"""Error handling architecture for OSDU Wireline.

This module implements the exception hierarchy as defined in ADR-004.
"""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from mcp import McpError
from mcp.types import ErrorData


class OSMCPError(Exception):
    """Base exception for OSDU MCP operations."""

    error_prefix = "MCP Error"
    status_code: int | None = 500


class OSMCPAuthError(OSMCPError):
    """Authentication failures."""

    error_prefix = "Authentication error"
    status_code = 401


class OSMCPAPIError(OSMCPError):
    """OSDU API communication errors."""

    error_prefix = "OSDU API error"

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize API error with optional status code."""
        super().__init__(message)
        self.status_code = status_code
        if status_code:
            self.error_prefix = f"OSDU API error (HTTP {status_code})"


class OSMCPConfigError(OSMCPError):
    """Configuration validation errors."""

    error_prefix = "Configuration error"
    status_code = 400


class OSMCPConnectionError(OSMCPError):
    """Network and connection errors."""

    error_prefix = "Connection error"
    status_code = 503


class OSMCPValidationError(OSMCPError):
    """Input validation errors."""

    error_prefix = "Validation error"
    status_code = 400


def handle_osdu_exceptions(
    func: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Decorator to handle OSDU exceptions and convert them to MCP errors."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except OSMCPError as e:
            raise McpError(
                ErrorData(
                    code=e.status_code or 500,
                    message=f"{e.error_prefix}: {e}",
                )
            ) from e
        except Exception as e:
            raise McpError(
                ErrorData(
                    code=500,
                    message=f"Unexpected error in OSDU operation: {e}",
                )
            ) from e

    return wrapper
