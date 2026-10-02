"""Tests for the Azure user sign-in provider."""

import asyncio
import logging
import os
import threading
import time
from typing import Any
from unittest.mock import patch

import msal
import pytest
import requests

from osdu_wireline.shared.auth import authorization_code
from osdu_wireline.shared.auth.authorization_code import AuthorizationCodeProvider
from osdu_wireline.shared.exceptions import OSMCPAuthError

ACCOUNT = {"home_account_id": "user-1", "username": "user@example.com"}


def token_result(access: str = "access-1", expires_in: int = 3600) -> dict:
    """Build an MSAL success result."""
    return {
        "access_token": access,
        "expires_in": expires_in,
        "refresh_token": "secret-refresh-token",
        "id_token_claims": {"preferred_username": "user@example.com"},
    }


def error_result(error: str, codes: list[int] | None = None) -> dict:
    """Build an MSAL error result."""
    return {"error": error, "error_codes": codes or [], "error_description": "AADSTS"}


class FakeApp:
    """Stands in for msal.PublicClientApplication."""

    def __init__(self, accounts=None, silent=None, interactive: Any = None):
        self.accounts = list(accounts or [])
        self.silent = silent
        self.interactive: Any = (
            interactive if interactive is not None else token_result()
        )
        self.removed = []
        self.silent_calls = []
        self.interactive_calls = []

    def get_accounts(self):
        return list(self.accounts)

    def remove_account(self, account):
        self.removed.append(account)
        self.accounts.remove(account)

    def acquire_token_silent_with_error(self, scopes, account):
        self.silent_calls.append((scopes, account))
        if isinstance(self.silent, Exception):
            raise self.silent
        return self.silent

    def acquire_token_interactive(self, scopes, **kwargs):
        self.interactive_calls.append((scopes, kwargs))
        if isinstance(self.interactive, Exception):
            raise self.interactive
        if callable(self.interactive):
            return self.interactive(kwargs)
        self.accounts = [ACCOUNT]
        return self.interactive


@pytest.fixture
def user_env():
    """Environment selecting user sign-in mode."""
    env = {
        "OSDU_AUTH_CLIENT_ID": "test-client-id",
        "OSDU_AUTH_DISCOVERY_URL": "https://login.microsoftonline.com/test-tenant/",
        "OSDU_AUTH_SCOPE": "osdu-app-id/.default",
    }
    with patch.dict(os.environ, env, clear=True):
        yield env


def use_app(app: FakeApp):
    """Make the provider build this fake app."""
    return patch.object(authorization_code, "_build_app", return_value=app)


async def test_empty_cache_signs_in_through_the_browser(user_env):
    """With no cached account, the provider signs in interactively."""
    app = FakeApp()

    with use_app(app):
        assert await AuthorizationCodeProvider().get_token() == "access-1"

    assert app.silent_calls == []
    ((scopes, kwargs),) = app.interactive_calls
    assert scopes == ["osdu-app-id/.default"]
    assert kwargs["prompt"] == "select_account"
    assert kwargs["timeout"] == authorization_code._SIGN_IN_TIMEOUT_SECONDS


async def test_cached_account_is_used_silently(user_env):
    """A signed-in account never opens the browser."""
    app = FakeApp(accounts=[ACCOUNT], silent=token_result("silent-1"))

    with use_app(app):
        assert await AuthorizationCodeProvider().get_token() == "silent-1"

    assert app.silent_calls == [(["osdu-app-id/.default"], ACCOUNT)]
    assert app.interactive_calls == []


@pytest.mark.parametrize(
    "silent",
    [None, error_result("invalid_grant"), error_result("interaction_required")],
)
async def test_expired_session_signs_in_again(user_env, silent):
    """When the cached sign-in can't be renewed, the browser opens."""
    app = FakeApp(accounts=[ACCOUNT], silent=silent)

    with use_app(app):
        assert await AuthorizationCodeProvider().get_token() == "access-1"

    assert len(app.interactive_calls) == 1


async def test_stale_accounts_are_removed_before_sign_in(user_env):
    """The cache keeps exactly one user, so silent lookup is unambiguous."""
    other = {"home_account_id": "user-2"}
    app = FakeApp(accounts=[ACCOUNT, other], silent=error_result("invalid_grant"))

    with use_app(app):
        await AuthorizationCodeProvider().get_token()

    assert app.removed == [ACCOUNT, other]


async def test_access_token_is_cached(user_env):
    """A valid access token is reused without asking MSAL again."""
    app = FakeApp(accounts=[ACCOUNT], silent=token_result())

    with use_app(app):
        provider = AuthorizationCodeProvider()
        await provider.get_token()
        await provider.get_token()

    assert len(app.silent_calls) == 1


async def test_expiring_access_token_is_renewed(user_env):
    """A token inside the expiry buffer is renewed on the next call."""
    app = FakeApp(accounts=[ACCOUNT], silent=token_result(expires_in=60))

    with use_app(app):
        provider = AuthorizationCodeProvider()
        await provider.get_token()
        await provider.get_token()

    assert len(app.silent_calls) == 2


async def test_concurrent_calls_share_one_sign_in(user_env):
    """Parallel tool calls must not each open a browser."""
    release = threading.Event()

    def slow_sign_in(_kwargs):
        release.wait(5)
        return token_result()

    app = FakeApp(interactive=slow_sign_in)

    with use_app(app):
        provider = AuthorizationCodeProvider()
        calls = [asyncio.create_task(provider.get_token()) for _ in range(5)]
        await asyncio.sleep(0.05)
        release.set()
        assert await asyncio.gather(*calls) == ["access-1"] * 5

    assert len(app.interactive_calls) == 1


@pytest.mark.parametrize(
    "outcome",
    [
        msal.BrowserInteractionTimeoutError("User did not complete the flow in time"),
        error_result("access_denied"),
    ],
)
async def test_incomplete_sign_in_asks_for_a_retry(user_env, outcome):
    """A timed-out or cancelled sign-in says how to try again."""
    app = FakeApp(interactive=outcome)

    with use_app(app), pytest.raises(OSMCPAuthError, match="Retry in a minute"):
        await AuthorizationCodeProvider().get_token()


async def test_missing_browser_fails_fast(user_env):
    """When no browser opens, the call fails instead of waiting out the timeout."""

    def no_browser(kwargs):
        kwargs["auth_uri_callback"]("https://login.example/authorize")

    app = FakeApp(interactive=no_browser)

    with use_app(app), pytest.raises(OSMCPAuthError, match="Retry in a minute"):
        await AuthorizationCodeProvider().get_token()


async def test_rejected_sign_in_does_not_reopen_the_browser(user_env):
    """One tool call requests several tokens; a rejection opens one window."""
    app = FakeApp(interactive=error_result("invalid_request", [54006]))

    with use_app(app):
        provider = AuthorizationCodeProvider()
        for _ in range(4):
            with pytest.raises(OSMCPAuthError, match="check your Azure"):
                await provider.get_token()

    assert len(app.interactive_calls) == 1


async def test_abandoned_sign_in_reopens_after_a_wait(user_env):
    """A timed-out sign-in blocks new windows briefly, then allows a retry."""
    app = FakeApp(interactive=msal.BrowserInteractionTimeoutError("timeout"))

    with use_app(app):
        provider = AuthorizationCodeProvider()
        for _ in range(3):
            with pytest.raises(OSMCPAuthError, match="Retry in a minute"):
                await provider.get_token()
        assert len(app.interactive_calls) == 1

        app.interactive = token_result()
        later = time.time() + authorization_code._SIGN_IN_RETRY_SECONDS + 1
        with patch.object(authorization_code.time, "time", return_value=later):
            assert await provider.get_token() == "access-1"

    assert len(app.interactive_calls) == 2


async def test_rejection_logs_entra_description(user_env, caplog):
    """The log carries Entra's explanation so the cause can be diagnosed."""
    result = error_result("invalid_request", [54006])
    result["error_description"] = "AADSTS54006: explanation.\r\nTrace ID: abc"
    app = FakeApp(interactive=result)

    with use_app(app), pytest.raises(OSMCPAuthError):
        await AuthorizationCodeProvider().get_token()

    assert "AADSTS54006: explanation." in caplog.text
    assert "Trace ID" not in caplog.text


@pytest.mark.parametrize(
    ("error", "codes", "expected"),
    [
        ("invalid_client", [7000218], "Allow public client flows"),
        ("invalid_request", [7000215], "Allow public client flows"),
        ("invalid_scope", [], "OSDU_AUTH_SCOPE"),
        ("invalid_request", [65001], "OSDU_AUTH_SCOPE"),
        ("invalid_request", [90002], "OSDU_AUTH_DISCOVERY_URL"),
        ("unauthorized_client", [], "OSDU_AUTH_CLIENT_ID"),
        ("temporarily_unavailable", [], "check your Azure configuration"),
    ],
)
async def test_errors_map_to_guidance(user_env, error, codes, expected):
    """Each known rejection names the setting or portal option to fix."""
    app = FakeApp(accounts=[ACCOUNT], silent=error_result(error, codes))

    with use_app(app), pytest.raises(OSMCPAuthError, match=expected):
        await AuthorizationCodeProvider().get_token()


async def test_network_failure_is_distinguished(user_env):
    """An unreachable endpoint is reported as a network problem."""
    app = FakeApp(accounts=[ACCOUNT], silent=requests.ConnectionError("down"))

    with use_app(app), pytest.raises(OSMCPAuthError, match="network connection"):
        await AuthorizationCodeProvider().get_token()


async def test_tokens_never_reach_errors_or_logs(user_env, caplog):
    """Neither access nor refresh tokens are logged or put in errors."""
    caplog.set_level(logging.DEBUG)
    app = FakeApp()

    with use_app(app):
        await AuthorizationCodeProvider().get_token()

    assert "access-1" not in caplog.text
    assert "secret-refresh-token" not in caplog.text

    app = FakeApp(accounts=[ACCOUNT], silent=error_result("invalid_client"))
    with use_app(app), pytest.raises(OSMCPAuthError) as exc_info:
        await AuthorizationCodeProvider().get_token()
    assert "secret-refresh-token" not in str(exc_info.value)


async def test_close_drops_the_access_token(user_env):
    """After close, the next call asks MSAL again."""
    app = FakeApp(accounts=[ACCOUNT], silent=token_result())

    with use_app(app):
        provider = AuthorizationCodeProvider()
        await provider.get_token()
        provider.close()
        await provider.get_token()

    assert len(app.silent_calls) == 2


@pytest.mark.parametrize(
    "missing", ["OSDU_AUTH_CLIENT_ID", "OSDU_AUTH_DISCOVERY_URL", "OSDU_AUTH_SCOPE"]
)
async def test_missing_settings_are_reported(user_env, missing):
    """The client, the authority, and the OSDU scope are all required."""
    del os.environ[missing]

    with pytest.raises(OSMCPAuthError, match=missing):
        await AuthorizationCodeProvider().get_token()


def test_reserved_scopes_are_stripped(user_env):
    """MSAL adds offline_access, openid, and profile itself and rejects them."""
    os.environ["OSDU_AUTH_SCOPE"] = "api://osdu/.default offline_access openid profile"

    assert authorization_code._read_config().scopes == ["api://osdu/.default"]


def test_authority_is_normalized(user_env):
    """A trailing slash on the authority is dropped."""
    assert (
        authorization_code._read_config().authority
        == "https://login.microsoftonline.com/test-tenant"
    )


async def test_unavailable_keyring_is_reported(user_env, tmp_path):
    """Without encrypted storage the provider refuses rather than use plaintext."""
    with (
        patch.object(authorization_code, "_CACHE_PATH", tmp_path / "cache.bin"),
        patch.object(
            authorization_code.msal_extensions,
            "build_encrypted_persistence",
            side_effect=ImportError("No module named 'gi'"),
        ),
        pytest.raises(OSMCPAuthError, match="OS keyring"),
    ):
        await AuthorizationCodeProvider().get_token()


async def test_unrecognized_authority_is_reported(user_env, tmp_path):
    """MSAL's authority discovery failure points at OSDU_AUTH_DISCOVERY_URL."""
    with (
        patch.object(
            authorization_code,
            "_build_cache",
            return_value=msal.SerializableTokenCache(),
        ),
        patch.object(
            authorization_code.msal,
            "PublicClientApplication",
            side_effect=ValueError("Unable to get authority configuration"),
        ),
        pytest.raises(OSMCPAuthError, match="OSDU_AUTH_DISCOVERY_URL"),
    ):
        await AuthorizationCodeProvider().get_token()
