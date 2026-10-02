"""Environment variable access for OSDU Wireline configuration.

All configuration is supplied through environment variables, read at the point
of use.

Connection and credential settings use the `OSDU_*` names shared with other
OSDU apps (OSDU_BASE_URL, OSDU_PARTITION_ID, OSDU_GRANT_TYPE, OSDU_AUTH_*).
Server-only settings (the write and delete gates, the log level) keep the
`OSDU_MCP_` prefix: they configure this server, not the connection.
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
