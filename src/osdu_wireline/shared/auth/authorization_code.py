"""Azure user sign-in, with tokens kept in MSAL's encrypted cache.

The operator configures the app registration (OSDU_AUTH_CLIENT_ID), the
tenant's authority URL (OSDU_AUTH_DISCOVERY_URL), and the OSDU resource
(OSDU_AUTH_SCOPE). The first time a token is needed and the cache holds no
usable sign-in, the server opens the system browser for an interactive sign-in. MSAL listens on a localhost redirect, so
the MCP stdio channel is never touched.

MSAL owns the refresh token from then on: it rotates it, and persists it to a
cache encrypted by the OS (DPAPI, Keychain, or libsecret), so restarts sign in
silently. No token ever passes through configuration.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import msal
import msal_extensions
import requests

from ..env import require_env
from ..exceptions import OSMCPAuthError

logger = logging.getLogger(__name__)

# Refresh this far ahead of expiry so a token cannot lapse mid-request.
_EXPIRY_BUFFER_SECONDS = 300

# How long an interactive sign-in may wait for the user to finish in the browser.
_SIGN_IN_TIMEOUT_SECONDS = 300

# After a sign-in is abandoned, wait this long before opening the browser again,
# so the token requests of one tool call cannot each open a window.
_SIGN_IN_RETRY_SECONDS = 60

_CACHE_PATH = Path.home() / ".osdu-wireline" / "msal_token_cache.bin"


# Errors that a fresh interactive sign-in resolves.
_SIGN_IN_ERRORS = {"invalid_grant", "interaction_required"}

# AADSTS codes that call for specific guidance rather than the generic message.
_NEEDS_SECRET_CODES = {7000215, 7000218}
_SCOPE_CODES = {65001, 70011}
_UNKNOWN_TENANT_CODES = {90002}

_AUTHORITY_MESSAGE = (
    "Azure did not recognize the authority. Please verify "
    "OSDU_AUTH_DISCOVERY_URL, e.g. https://login.microsoftonline.com/<tenant-id>"
)
_NETWORK_MESSAGE = (
    "Failed to connect to Azure authentication service. "
    "Please check your network connection"
)
_KEYRING_MESSAGE = (
    "User sign-in needs an OS keyring to store tokens encrypted (libsecret on "
    "Linux). Install one and retry"
)
_SIGN_IN_INCOMPLETE_MESSAGE = (
    "Sign-in was not completed. Retry in a minute to open the browser again"
)


class _SignInIncompleteError(Exception):
    """The browser could not be opened for an interactive sign-in."""


class _SignInRejectedError(OSMCPAuthError):
    """Entra rejected the sign-in; another attempt fails the same way."""


@dataclass(frozen=True)
class _UserConfig:
    """Settings for user sign-in, read from the environment at the point of use."""

    client_id: str
    authority: str
    scopes: list[str]


class AuthorizationCodeProvider:
    """Signs the user in through the browser, caching the access token."""

    def __init__(self) -> None:
        """Initialize the provider; nothing is acquired until first use."""
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._app: msal.PublicClientApplication | None = None
        self._lock = asyncio.Lock()
        # The last failed sign-in, and when the browser may open again.
        self._sign_in_failure: OSMCPAuthError | None = None
        self._sign_in_retry_at = 0.0

        logger.info("Authentication: authorization code (user sign-in)")

    async def get_token(self) -> str:
        """Return a cached access token, or acquire one through MSAL.

        Returns:
            Valid Azure access token

        Raises:
            OSMCPAuthError: If no token can be acquired
        """
        if self._access_token and self._is_access_token_valid():
            return self._access_token

        # Concurrent tool calls must share one sign-in, not each open a browser.
        async with self._lock:
            token = self._access_token
            if not (token and self._is_access_token_valid()):
                token, expires_in = await asyncio.to_thread(self._acquire)
                self._access_token = token
                self._expires_at = time.time() + expires_in
            return token

    def close(self) -> None:
        """Clear the cached access token."""
        self._access_token = None
        self._expires_at = 0.0

    def _is_access_token_valid(self) -> bool:
        """Check whether the cached access token is outside the refresh buffer."""
        return time.time() < self._expires_at - _EXPIRY_BUFFER_SECONDS

    def _acquire(self) -> tuple[str, int]:
        """Acquire a token silently, signing in through the browser if needed.

        Returns:
            The access token and its lifetime in seconds

        Raises:
            OSMCPAuthError: If no token can be acquired
        """
        config = _read_config()
        try:
            if self._app is None:
                self._app = _build_app(config)
            app = self._app

            result = None
            accounts = app.get_accounts()
            if accounts:
                result = app.acquire_token_silent_with_error(
                    config.scopes, account=accounts[0]
                )
            if result is None or result.get("error") in _SIGN_IN_ERRORS:
                result = self._sign_in_once(app, config.scopes)
        except requests.RequestException:
            raise OSMCPAuthError(_NETWORK_MESSAGE)
        except msal_extensions.persistence.PersistenceError:
            raise OSMCPAuthError(_KEYRING_MESSAGE)

        access_token = result.get("access_token")
        if "error" in result or not isinstance(access_token, str):
            raise OSMCPAuthError(_describe_failure(result))

        logger.info("Azure token obtained for signed-in user")
        return access_token, int(result.get("expires_in", 3600))

    def _sign_in_once(
        self, app: msal.PublicClientApplication, scopes: list[str]
    ) -> dict[str, Any]:
        """Sign in, unless a recent attempt failed.

        A tool call can request several tokens, so without this every request
        after a failed sign-in would open another browser window. A rejection is
        remembered until restart, since only a configuration change fixes it;
        an abandoned sign-in may be retried after a short wait.

        Args:
            app: MSAL public client
            scopes: Scopes to request

        Returns:
            MSAL's token result

        Raises:
            OSMCPAuthError: If this or a recent sign-in failed
        """
        if self._sign_in_failure and time.time() < self._sign_in_retry_at:
            raise self._sign_in_failure

        try:
            result = _sign_in(app, scopes)
            if "error" in result or "access_token" not in result:
                raise _SignInRejectedError(_describe_failure(result))
        except _SignInRejectedError as e:
            self._sign_in_failure, self._sign_in_retry_at = e, float("inf")
            raise
        except OSMCPAuthError as e:
            self._sign_in_failure = e
            self._sign_in_retry_at = time.time() + _SIGN_IN_RETRY_SECONDS
            raise

        self._sign_in_failure = None
        return result


def _read_config() -> _UserConfig:
    """Read the user sign-in settings.

    Returns:
        Settings for sign-in

    Raises:
        OSMCPAuthError: If a required setting is missing
    """
    client_id = require_env("OSDU_AUTH_CLIENT_ID")
    authority = require_env("OSDU_AUTH_DISCOVERY_URL")
    scope = require_env("OSDU_AUTH_SCOPE")
    scopes = list(scope.split())

    return _UserConfig(
        client_id=client_id, authority=authority.rstrip("/"), scopes=scopes
    )


def _build_cache() -> msal.SerializableTokenCache:
    """Open the OS-encrypted token cache, shared across server processes.

    Returns:
        A token cache MSAL reads and writes through on every operation

    Raises:
        OSMCPAuthError: If the OS offers no encrypted storage
    """
    try:
        _CACHE_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        persistence = msal_extensions.build_encrypted_persistence(str(_CACHE_PATH))
    except (ImportError, RuntimeError, OSError) as e:
        # Never fall back to plaintext: the cache holds a long-lived refresh token.
        logger.warning(f"Encrypted token storage is unavailable: {e}")
        raise OSMCPAuthError(_KEYRING_MESSAGE)
    return msal_extensions.PersistedTokenCache(persistence)


def _build_app(config: _UserConfig) -> msal.PublicClientApplication:
    """Build the MSAL public client for the configured app registration.

    Args:
        config: Sign-in settings

    Returns:
        A public client backed by the encrypted cache

    Raises:
        OSMCPAuthError: If the authority is not recognized
    """
    cache = _build_cache()
    try:
        return msal.PublicClientApplication(
            config.client_id, authority=config.authority, token_cache=cache
        )
    except ValueError:
        # MSAL raises ValueError when authority discovery fails.
        raise OSMCPAuthError(_AUTHORITY_MESSAGE)


def _sign_in(app: msal.PublicClientApplication, scopes: list[str]) -> dict[str, Any]:
    """Sign the user in through the system browser.

    Args:
        app: MSAL public client
        scopes: Scopes to request

    Returns:
        MSAL's token result

    Raises:
        OSMCPAuthError: If the sign-in was not completed
    """
    # Keep one user in the cache, so silent acquisition is never ambiguous.
    for account in app.get_accounts():
        app.remove_account(account)

    def no_browser(_auth_uri: str) -> None:
        raise _SignInIncompleteError

    logger.info("Opening a browser to sign in to OSDU")
    try:
        result = app.acquire_token_interactive(
            scopes,
            prompt="select_account",
            timeout=_SIGN_IN_TIMEOUT_SECONDS,
            auth_uri_callback=no_browser,
        )
    except (msal.BrowserInteractionTimeoutError, _SignInIncompleteError):
        raise OSMCPAuthError(_SIGN_IN_INCOMPLETE_MESSAGE)

    if result.get("error") == "access_denied":
        raise OSMCPAuthError(_SIGN_IN_INCOMPLETE_MESSAGE)

    username = result.get("id_token_claims", {}).get("preferred_username")
    if username:
        logger.info(f"Signed in to OSDU as {username}")
    return result


def _describe_failure(result: dict[str, Any]) -> str:
    """Map an MSAL error result onto actionable guidance.

    Args:
        result: MSAL's token result

    Returns:
        A user-facing message naming the fix
    """
    error = str(result.get("error", "unknown_error"))
    codes = {code for code in result.get("error_codes", []) if isinstance(code, int)}
    # Entra's description names the cause and a trace ID, never a token.
    description = str(result.get("error_description", "")).splitlines()[:1]
    logger.warning(
        f"Azure sign-in rejected: {error} (AADSTS {sorted(codes)}) "
        f"{' '.join(description)}"
    )

    if codes & _NEEDS_SECRET_CODES:
        return (
            "This app registration requires a client secret. User sign-in needs "
            "a public client: enable 'Allow public client flows' on the app "
            "registration"
        )
    if codes & _SCOPE_CODES or error == "invalid_scope":
        return (
            "Azure rejected the requested scope. Please verify OSDU_AUTH_CLIENT_ID "
            "and OSDU_AUTH_SCOPE"
        )
    if codes & _UNKNOWN_TENANT_CODES:
        return _AUTHORITY_MESSAGE
    if error in ("invalid_client", "unauthorized_client"):
        return (
            "Azure rejected the client. Please verify OSDU_AUTH_CLIENT_ID and "
            "OSDU_AUTH_DISCOVERY_URL"
        )
    return "Azure sign-in failed. Please check your Azure configuration"
