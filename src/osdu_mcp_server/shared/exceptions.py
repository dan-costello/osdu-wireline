"""Error handling architecture for OSDU MCP Server.

This module implements the exception hierarchy as defined in ADR-004.
"""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, overload

from mcp import McpError
from mcp.types import ErrorData


class OSMCPError(Exception):
    """Base exception for OSDU MCP operations."""


class OSMCPAuthError(OSMCPError):
    """Authentication failures."""


class OSMCPAPIError(OSMCPError):
    """OSDU API communication errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize API error with optional status code."""
        super().__init__(message)
        self.status_code = status_code


class OSMCPConfigError(OSMCPError):
    """Configuration validation errors."""


class OSMCPConnectionError(OSMCPError):
    """Network and connection errors."""


class OSMCPValidationError(OSMCPError):
    """Input validation errors."""


@overload
def handle_osdu_exceptions(
    func: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]: ...


@overload
def handle_osdu_exceptions(
    *,
    default_message: str = ...,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, Any]]],
    Callable[..., Coroutine[Any, Any, Any]],
]: ...


def handle_osdu_exceptions(  # noqa: C901 - existing complexity, tracked as debt
    func: Callable[..., Coroutine[Any, Any, Any]] | None = None,
    *,
    default_message: str = "OSDU operation failed",
) -> (
    Callable[..., Coroutine[Any, Any, Any]]
    | Callable[
        [Callable[..., Coroutine[Any, Any, Any]]],
        Callable[..., Coroutine[Any, Any, Any]],
    ]
):
    """Decorator to handle OSDU exceptions and convert them to MCP errors.

    Args:
        func: Async function to wrap (provided by decoration)
        default_message: Default error message if none provided

    Returns:
        Decorated async function that handles OSDU exceptions
    """

    def decorator(
        wrapped_func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(wrapped_func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await wrapped_func(*args, **kwargs)
            except OSMCPAuthError as e:
                raise McpError(
                    ErrorData(code=401, message=f"Authentication error: {e!s}")
                )
            except OSMCPAPIError as e:
                status = f" (HTTP {e.status_code})" if e.status_code else ""
                code = e.status_code or 500
                raise McpError(
                    ErrorData(code=code, message=f"OSDU API error{status}: {e!s}")
                )
            except OSMCPConfigError as e:
                raise McpError(
                    ErrorData(code=400, message=f"Configuration error: {e!s}")
                )
            except OSMCPConnectionError as e:
                raise McpError(ErrorData(code=503, message=f"Connection error: {e!s}"))
            except OSMCPValidationError as e:
                raise McpError(ErrorData(code=400, message=f"Validation error: {e!s}"))
            except OSMCPError as e:
                raise McpError(ErrorData(code=500, message=f"{default_message}: {e!s}"))
            except Exception as e:
                raise McpError(
                    ErrorData(
                        code=500,
                        message=f"Unexpected error in OSDU operation: {e!s}",
                    )
                )

        return wrapper

    if func is None:
        # Called with parameters: @handle_osdu_exceptions(default_message="...")
        return decorator
    # Called without parameters: @handle_osdu_exceptions
    return decorator(func)
