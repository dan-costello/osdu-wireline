"""Authentication mode detection and the process-wide credential provider.

The provider is built once and shared by every tool invocation so its token
cache survives across calls.
"""

import threading

from ..env import get_env, get_setting
from ..exceptions import OSMCPAuthError
from .azure import AzureProvider
from .base import CredentialProvider
from .user_token import UserTokenProvider

_NO_CREDENTIALS_MESSAGE = (
    "No authentication credentials configured. Set up one of:\n\n"
    "  Manual Token (Highest Priority):\n"
    "    export OSDU_USER_TOKEN=your-bearer-token\n\n"
    "  Azure:\n"
    "    az login\n"
    "    OR export AZURE_CLIENT_ID=... AZURE_TENANT_ID=...\n\n"
    "  See: https://github.com/dan-costello/osdu-wireline#authentication"
)


def detect_provider() -> CredentialProvider:
    """Select a credential provider by precedence.

    A manually supplied token wins over the Azure credential chain, so an
    operator can override whatever `az login` would resolve without logging out.

    Returns:
        Provider for the detected authentication mode

    Raises:
        OSMCPAuthError: If no authentication credentials are found
    """
    if get_setting("OSDU_USER_TOKEN"):
        return UserTokenProvider()

    if get_env("AZURE_CLIENT_ID") or get_env("AZURE_TENANT_ID"):
        return AzureProvider()

    raise OSMCPAuthError(_NO_CREDENTIALS_MESSAGE)


_provider: CredentialProvider | None = None
_lock = threading.Lock()


def get_auth_provider() -> CredentialProvider:
    """Return the shared credential provider, building it on first use.

    Construction is deferred because detection raises when no credentials are
    configured; building it eagerly would stop the server from starting instead
    of surfacing an authentication error from the tool that needed it.

    Returns:
        Process-wide credential provider
    """
    global _provider
    if _provider is not None:
        return _provider

    with _lock:
        if _provider is None:
            _provider = detect_provider()
        return _provider


def reset_auth_provider() -> None:
    """Release the shared provider so the next call rebuilds it."""
    global _provider
    with _lock:
        provider, _provider = _provider, None
    if provider is not None:
        provider.close()
