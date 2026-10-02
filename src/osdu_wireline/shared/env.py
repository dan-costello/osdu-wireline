"""Environment variable access for OSDU Wireline configuration.

All configuration is supplied through environment variables, read at the point
of use.

Connection and credential settings use `OSDU_*` names (`OSDU_SERVER_URL`,
`OSDU_AUTH_CLIENT_ID`, ...) shared with other apps that talk to the same
platform. Server-only settings (the write and delete gates, the log level) use
the `OSDU_MCP_` prefix: they configure this server, not the connection.
"""

import os

from .exceptions import OSMCPConfigError


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a string environment variable.

    Args:
        name: Environment variable name
        default: Value to return when the variable is unset or empty

    Returns:
        The variable's value, or the default
    """
    value = os.environ.get(name)
    if not value:
        return default
    return value


def require_env(name: str) -> str:
    """Read a required string environment variable.

    Args:
        name: Environment variable name

    Returns:
        The variable's value

    Raises:
        OSMCPConfigError: If the variable is unset or empty
    """
    value = os.environ.get(name)
    if not value:
        raise OSMCPConfigError(
            f"Required configuration not found. Set environment variable {name}"
        )
    return value


def get_env_int(name: str, default: int) -> int:
    """Read an integer environment variable.

    Args:
        name: Environment variable name
        default: Value to return when the variable is unset or unparseable

    Returns:
        The parsed integer, or the default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def get_env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable.

    Args:
        name: Environment variable name
        default: Value to return when the variable is unset

    Returns:
        True for "true", "yes", or "1" (case-insensitive); False otherwise
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "yes", "1")
