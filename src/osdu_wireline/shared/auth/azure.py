"""Azure authentication via DefaultAzureCredential."""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential

from ..env import get_env
from ..exceptions import OSMCPAuthError
from .base import AuthenticationMode

if TYPE_CHECKING:
    from azure.core.credentials import AccessToken

logger = logging.getLogger(__name__)

# Refresh this far ahead of expiry so a token cannot lapse mid-request.
_EXPIRY_BUFFER = timedelta(minutes=5)

_CLI_LOGIN_MESSAGE = (
    "Authentication failed. Please run 'az login' before using OSDU Wireline"
)
_EXPIRED_MESSAGE = (
    "Azure authentication token expired. Please run 'az login' to refresh"
)
_INVALID_SCOPE_MESSAGE = (
    "Invalid Azure client ID. Please verify your AZURE_CLIENT_ID is correct"
)


class AzureProvider:
    """Uses the Azure identity chain, caching tokens for their lifetime."""

    mode: ClassVar[AuthenticationMode] = AuthenticationMode.AZURE

    def __init__(self) -> None:
        """Build a DefaultAzureCredential scoped to the available credentials."""
        # A client secret means Service Principal auth, so the developer-machine
        # methods are excluded. Interactive browser is never appropriate for a
        # server process, and VS Code's credential is excluded in production.
        has_client_secret = bool(get_env("AZURE_CLIENT_SECRET"))

        self._credential = DefaultAzureCredential(
            exclude_interactive_browser_credential=True,
            exclude_azure_cli_credential=has_client_secret,
            exclude_azure_powershell_credential=has_client_secret,
            exclude_visual_studio_code_credential=True,
        )
        self._cached_token: AccessToken | None = None

        logger.info("Authentication mode: AZURE (DefaultAzureCredential)")

    async def get_token(self) -> str:
        """Return a cached token, or acquire a fresh one.

        Returns:
            Valid Azure access token

        Raises:
            OSMCPAuthError: If authentication fails
        """
        if self._is_cached_token_valid() and self._cached_token:
            return self._cached_token.token

        client_id = get_env("AZURE_CLIENT_ID")
        if not client_id:
            raise OSMCPAuthError(
                "AZURE_CLIENT_ID environment variable is required for Azure authentication"
            )

        scope = get_env("OSDU_MCP_AUTH_SCOPE") or f"{client_id}/.default"
        try:
            self._cached_token = self._credential.get_token(scope)
        except ClientAuthenticationError as e:
            raise OSMCPAuthError(_describe_auth_failure(str(e)))
        except Exception as e:
            error_message = str(e).lower()
            if "connection" in error_message or "timeout" in error_message:
                raise OSMCPAuthError(
                    "Failed to connect to Azure authentication service. "
                    "Please check your network connection"
                )
            # Unexpected error - keep details out of the user-facing message
            raise OSMCPAuthError(
                "Authentication configuration error. Please check your environment setup"
            )

        logger.info("Azure token obtained successfully")
        return self._cached_token.token

    def close(self) -> None:
        """Clear the cached token and close the underlying credential."""
        self._cached_token = None
        if hasattr(self._credential, "close"):
            self._credential.close()

    def _is_cached_token_valid(self) -> bool:
        """Check whether the cached token is still usable.

        Returns:
            True if a token is cached and not within the refresh buffer
        """
        if not self._cached_token:
            return False

        expiry = datetime.fromtimestamp(self._cached_token.expires_on, UTC)
        return datetime.now(UTC) < (expiry - _EXPIRY_BUFFER)


def _describe_auth_failure(error: str) -> str:
    """Map an Azure authentication error onto actionable guidance.

    Args:
        error: Original exception text

    Returns:
        A user-facing message naming the fix
    """
    error = error.lower()

    if bool(get_env("AZURE_CLIENT_SECRET")):
        no_credentials = (
            "Service Principal authentication failed. Please check your "
            "AZURE_CLIENT_ID, AZURE_TENANT_ID, and AZURE_CLIENT_SECRET"
        )
    else:
        no_credentials = (
            "No Azure credentials found. Please set up Service Principal "
            "credentials or run 'az login' for CLI authentication"
        )

    known_causes = {
        "az login": _CLI_LOGIN_MESSAGE,
        "azurecli": _CLI_LOGIN_MESSAGE,
        "expired": _EXPIRED_MESSAGE,
        "refresh token": _EXPIRED_MESSAGE,
        "invalid_scope": _INVALID_SCOPE_MESSAGE,
        "scope format is invalid": _INVALID_SCOPE_MESSAGE,
        "no accounts were found": no_credentials,
        "environment variables are not fully configured": no_credentials,
    }

    for marker, message in known_causes.items():
        if marker in error:
            return message

    return "Authentication failed. Please check your Azure credentials"
