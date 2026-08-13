"""Process-wide OSDU application context.

The context is constructed once by the FastMCP lifespan and shared by every
tool invocation, so the auth handler's token cache survives across calls. A
lazy fallback keeps tools callable outside an MCP request (direct calls,
tests, scripts).
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field

from .auth_handler import AuthHandler


@dataclass
class AppContext:
    """Long-lived, shared dependencies for all OSDU tools.

    Attributes:
        _auth: Authentication handler, constructed on first access
    """

    _auth: AuthHandler | None = field(default=None, repr=False)

    @property
    def auth(self) -> AuthHandler:
        """Authentication handler, constructed on first use.

        Construction is deferred because AuthHandler raises when no credentials
        are configured; building it eagerly would prevent the server from
        starting instead of returning a per-tool authentication error.

        Returns:
            Shared authentication handler
        """
        if self._auth is None:
            self._auth = AuthHandler()
        return self._auth

    def close(self) -> None:
        """Release auth resources (AuthHandler.close() is synchronous)."""
        if self._auth is not None:
            self._auth.close()
            self._auth = None


_app_context: AppContext | None = None
_lock = threading.Lock()


def create_app_context() -> AppContext:
    """Build a fresh context without installing it.

    Returns:
        New application context
    """
    return AppContext()


def set_app_context(context: AppContext | None) -> None:
    """Install (or clear) the process-wide context.

    Args:
        context: Context to install, or None to clear it
    """
    global _app_context
    with _lock:
        _app_context = context


def reset_app_context() -> None:
    """Clear the cached context and release its resources."""
    global _app_context
    with _lock:
        ctx, _app_context = _app_context, None
    if ctx is not None:
        ctx.close()


def _from_request() -> AppContext | None:
    """Read the lifespan context off the active MCP request, if any.

    Uses sys.modules rather than an import so this module never imports
    server.py (server -> tools -> shared would be circular).

    Returns:
        Context from the active request, or None if unavailable
    """
    server_mod = sys.modules.get("osdu_wireline.server")
    if server_mod is None:
        return None

    try:
        ctx = server_mod.mcp.get_context().request_context.lifespan_context
    except (LookupError, ValueError, AttributeError):
        # Not inside a request, or no lifespan context available
        return None

    return ctx if isinstance(ctx, AppContext) else None


def get_app_context() -> AppContext:
    """Resolve the shared context: installed -> request lifespan -> lazy build.

    Returns:
        Shared application context

    Raises:
        OSMCPConfigError: If configuration is invalid
    """
    global _app_context
    if _app_context is not None:
        return _app_context

    ctx = _from_request()
    if ctx is not None:
        return ctx

    with _lock:
        if _app_context is None:
            _app_context = create_app_context()
        return _app_context
