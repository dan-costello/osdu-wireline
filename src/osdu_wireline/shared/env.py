"""Environment variable access for OSDU Wireline configuration.

All configuration is supplied through environment variables, read at the point
of use.

Connection and credential settings have two accepted spellings. The canonical
`OSDU_*` names are shared with the DGI `dgimcp` OSDU import server, which talks
to the same platform and reads the same variables so that neither server has to
accept a token or a server URL as a tool argument. The older `OSDU_MCP_*`
spellings still resolve, so an existing configuration keeps working.

Server-only settings (the write and delete gates, the log level) keep the
`OSDU_MCP_` prefix: they configure this server, not the connection.
"""

import os

from .exceptions import OSMCPConfigError

#: Legacy spellings accepted for each canonical setting, in fallback order.
_ALIASES: dict[str, tuple[str, ...]] = {
    "OSDU_SERVER_URL": ("OSDU_MCP_SERVER_URL",),
    "OSDU_DATA_PARTITION": ("OSDU_MCP_SERVER_DATA_PARTITION",),
    "OSDU_TIMEOUT": ("OSDU_MCP_SERVER_TIMEOUT",),
    "OSDU_USER_TOKEN": ("OSDU_MCP_USER_TOKEN",),
    "OSDU_AUTH_SCOPE": ("OSDU_MCP_AUTH_SCOPE",),
}


def setting_names(name: str) -> tuple[str, ...]:
    """List every environment variable name a setting is read from.

    Args:
        name: Canonical setting name

    Returns:
        The canonical name followed by any accepted legacy spellings
    """
    return (name, *_ALIASES.get(name, ()))


def get_setting(name: str, default: str | None = None) -> str | None:
    """Read a setting from its canonical name, falling back to legacy spellings.

    Args:
        name: Canonical setting name
        default: Value to return when no accepted name is set

    Returns:
        The first value found, or the default
    """
    for candidate in setting_names(name):
        value = get_env(candidate)
        if value is not None:
            return value
    return default


def require_setting(name: str) -> str:
    """Read a required setting, falling back to legacy spellings.

    Args:
        name: Canonical setting name

    Returns:
        The first value found

    Raises:
        OSMCPConfigError: If no accepted name is set
    """
    value = get_setting(name)
    if value is None:
        accepted = " or ".join(setting_names(name))
        raise OSMCPConfigError(
            f"Required configuration not found. Set environment variable {accepted}"
        )
    return value


def get_setting_int(name: str, default: int) -> int:
    """Read an integer setting, falling back to legacy spellings.

    Args:
        name: Canonical setting name
        default: Value to return when unset or unparseable

    Returns:
        The parsed integer, or the default
    """
    value = get_setting(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


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
