"""Authentication mode detection and the process-wide credential provider.

The provider is built once and shared by every tool invocation so its token
cache survives across calls.
"""

import threading

from ..env import get_env
from ..exceptions import OSMCPAuthError
from .aws import AwsProvider
from .azure import AzureProvider
from .base import CredentialProvider
from .gcp import GcpProvider
from .user_token import UserTokenProvider

_NO_CREDENTIALS_MESSAGE = (
    "No authentication credentials configured. Set up one of:\n\n"
    "  Manual Token (Highest Priority):\n"
    "    export OSDU_MCP_USER_TOKEN=your-bearer-token\n\n"
    "  Azure (Automatic):\n"
    "    az login\n"
    "    OR export AZURE_CLIENT_ID=... AZURE_TENANT_ID=...\n\n"
    "  AWS (Automatic):\n"
    "    aws sso login\n"
    "    OR export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...\n\n"
    "  GCP (Automatic):\n"
    "    gcloud auth application-default login\n"
    "    OR export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json\n\n"
    "  See: https://github.com/dan-costello/osdu-wireline#authentication"
)


def detect_provider() -> CredentialProvider:
    """Select a credential provider by precedence.

    Explicitly configured credentials always win over auto-discovery, and a
    manually supplied token wins over everything.

    Returns:
        Provider for the detected authentication mode

    Raises:
        OSMCPAuthError: If no authentication credentials are found
    """
    if get_env("OSDU_MCP_USER_TOKEN"):
        return UserTokenProvider()

    if get_env("AZURE_CLIENT_ID") or get_env("AZURE_TENANT_ID"):
        return AzureProvider()

    if get_env("AWS_ACCESS_KEY_ID") or get_env("AWS_PROFILE"):
        return AwsProvider()

    if get_env("GOOGLE_APPLICATION_CREDENTIALS"):
        return GcpProvider()

    if AwsProvider.is_discoverable():
        return AwsProvider()

    if GcpProvider.is_discoverable():
        return GcpProvider()

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
