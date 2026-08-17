"""GCP authentication via Application Default Credentials."""

import asyncio
import logging
from typing import Any, ClassVar

import google.auth
import google.auth.transport.requests
from google.auth.exceptions import DefaultCredentialsError, RefreshError

from ..env import get_env
from ..exceptions import OSMCPAuthError
from .base import AuthenticationMode

logger = logging.getLogger(__name__)

# OSDU authorizes by the caller's email address, which is only present in the
# token when identity scopes are requested. cloud-platform alone yields a token
# without an email claim, which OSDU rejects with 401.
DEFAULT_GCP_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_NO_CREDENTIALS_MESSAGE = (
    "GCP Application Default Credentials not found. "
    "Set up authentication using one of these methods:\n\n"
    "  Local Development:\n"
    "    gcloud auth application-default login\n\n"
    "  Service Account Key:\n"
    "    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json\n\n"
    "  For more info: https://cloud.google.com/docs/authentication/provide-credentials-adc"
)

_RELOGIN = "Run 'gcloud auth application-default login' to re-authenticate"


class GcpProvider:
    """Uses Application Default Credentials: key file, gcloud, or metadata server.

    Scopes default to DEFAULT_GCP_SCOPES and can be replaced with a
    comma-separated OSDU_MCP_AUTH_SCOPE.
    """

    mode: ClassVar[AuthenticationMode] = AuthenticationMode.GCP

    def __init__(self) -> None:
        """Resolve Application Default Credentials.

        Raises:
            OSMCPAuthError: If no GCP credentials are available
        """
        self._credentials: Any = None

        try:
            self._credentials, project = google.auth.default(scopes=_resolve_scopes())
        except DefaultCredentialsError:
            raise OSMCPAuthError(_NO_CREDENTIALS_MESSAGE)

        logger.info(f"Authentication mode: GCP, project: {project}")

    @classmethod
    def is_discoverable(cls) -> bool:
        """Probe whether ADC resolves without explicit configuration.

        Returns:
            True if google.auth finds credentials (gcloud login, metadata server)
        """
        try:
            credentials, _ = google.auth.default()
        except Exception as e:
            logger.debug(f"GCP auto-discovery unavailable: {e}")
            return False
        return bool(credentials)

    async def get_token(self) -> str:
        """Return the current access token, refreshing it when expired.

        Returns:
            Valid GCP access token string

        Raises:
            OSMCPAuthError: If the refresh fails
        """
        if not self._credentials.valid:
            logger.debug("GCP token invalid/expired, refreshing...")
            await self._refresh()
            logger.info("GCP token refreshed successfully")

        token = self._credentials.token
        if not token:
            raise OSMCPAuthError("GCP token is None after refresh")

        return str(token)

    def close(self) -> None:
        """Drop the credentials (they hold no OS resources of their own)."""
        self._credentials = None

    async def _refresh(self) -> None:
        """Refresh the credentials off the event loop.

        Raises:
            OSMCPAuthError: If the refresh fails
        """
        request: Any = google.auth.transport.requests.Request()

        try:
            # google-auth is synchronous, so keep it off the event loop
            await asyncio.get_running_loop().run_in_executor(
                None, self._credentials.refresh, request
            )
        except RefreshError as e:
            raise OSMCPAuthError(_describe_refresh_failure(str(e)))
        except Exception as e:
            raise OSMCPAuthError(f"Unexpected GCP authentication error: {e}")


def _resolve_scopes() -> list[str]:
    """Read OSDU_MCP_AUTH_SCOPE as a comma-separated list, or use the defaults.

    Returns:
        Scopes to request for the credentials
    """
    custom = get_env("OSDU_MCP_AUTH_SCOPE", "") or ""
    return [s.strip() for s in custom.split(",") if s.strip()] or DEFAULT_GCP_SCOPES


def _describe_refresh_failure(error: str) -> str:
    """Map a GCP refresh error onto actionable guidance.

    Args:
        error: Original exception text

    Returns:
        A user-facing message naming the fix
    """
    error_lower = error.lower()

    if "file not found" in error_lower or "no such file" in error_lower:
        return (
            "GCP credentials file not found. Check GOOGLE_APPLICATION_CREDENTIALS path"
        )
    if "expired" in error_lower:
        return f"GCP refresh token expired. {_RELOGIN}"
    if "invalid" in error_lower or "malformed" in error_lower:
        return f"GCP credentials invalid. {_RELOGIN}"
    return f"GCP token refresh failed: {error}"
