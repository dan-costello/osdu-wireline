"""The process-wide credential provider.

The provider is built once and shared by every tool invocation so its token
cache survives across calls.
"""

import threading

from ..env import get_env
from ..exceptions import OSMCPAuthError
from .authorization_code import AuthorizationCodeProvider
from .base import AuthenticationMode, CredentialProvider

_SETUP_MESSAGE = (
    f"OSDU_GRANT_TYPE must be set to {AuthenticationMode.AUTHORIZATION_CODE}. Configure:\n\n"
    f"    OSDU_GRANT_TYPE={AuthenticationMode.AUTHORIZATION_CODE}\n"
    "    OSDU_BASE_URL=<base_url>\n"
    "    OSDU_PARTITION_ID=<partition>\n"
    "    OSDU_AUTH_CLIENT_ID=<azure_client_id>\n"
    "    OSDU_AUTH_DISCOVERY_URL=https://login.microsoftonline.com/<tenant_id>\n"
    "    OSDU_AUTH_SCOPE=<osdu_app_id>/.default\n\n"
    "  See: https://github.com/dan-costello/osdu-wireline#authentication"
)


def _build_provider() -> CredentialProvider:
    """Build the provider for the configured grant type.
    Currently only accepts

    Returns:
        Provider for the authorization code grant

    Raises:
        OSMCPAuthError: If OSDU_GRANT_TYPE is missing or unsupported
    """
    if get_env("OSDU_GRANT_TYPE") != "authorization_code":
        raise OSMCPAuthError(_SETUP_MESSAGE)
    return AuthorizationCodeProvider()


_provider: CredentialProvider | None = None
_lock = threading.Lock()


def get_auth_provider() -> CredentialProvider:
    """Return the shared credential provider, building it on first use.

    Construction is deferred because it raises when auth is not configured;
    building it eagerly would stop the server from starting instead of
    surfacing an authentication error from the tool that needed it.

    Returns:
        Process-wide credential provider
    """
    global _provider
    if _provider is not None:
        return _provider

    with _lock:
        if _provider is None:
            _provider = _build_provider()
        return _provider


def reset_auth_provider() -> None:
    """Release the shared provider so the next call rebuilds it."""
    global _provider
    with _lock:
        provider, _provider = _provider, None
    if provider is not None:
        provider.close()
