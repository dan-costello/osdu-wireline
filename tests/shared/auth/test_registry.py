"""Tests for the process-wide credential provider and its lifecycle."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.auth import (
    check_credentials,
    get_auth_provider,
    reset_auth_provider,
)
from osdu_wireline.shared.auth.authorization_code import AuthorizationCodeProvider
from osdu_wireline.shared.clients import OsduClient
from osdu_wireline.shared.exceptions import OSMCPAuthError
from tests.conftest import OSDU_TEST_ENV, StaticTokenProvider, install_provider


def test_authorization_code_grant_builds_the_sign_in_provider():
    """OSDU_GRANT_TYPE=authorization_code selects user sign-in."""
    with patch.dict(os.environ, OSDU_TEST_ENV, clear=True):
        assert isinstance(get_auth_provider(), AuthorizationCodeProvider)


@pytest.mark.parametrize("grant_type", [None, "client_credentials", "AUTHCODE"])
def test_other_grant_types_are_rejected_with_setup_guidance(grant_type):
    """A missing or unsupported grant lists every required variable."""
    env = {k: v for k, v in OSDU_TEST_ENV.items() if k != "OSDU_GRANT_TYPE"}
    if grant_type:
        env["OSDU_GRANT_TYPE"] = grant_type

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(OSMCPAuthError) as exc_info:
            get_auth_provider()

    message = str(exc_info.value)
    for name in (
        "OSDU_GRANT_TYPE=authorization_code",
        "OSDU_BASE_URL",
        "OSDU_PARTITION_ID",
        "OSDU_AUTH_CLIENT_ID",
        "OSDU_AUTH_DISCOVERY_URL",
        "OSDU_AUTH_SCOPE",
    ):
        assert name in message


def test_provider_is_shared_across_calls():
    """Repeated calls return the same provider, preserving its token cache."""
    with patch.dict(os.environ, OSDU_TEST_ENV):
        assert get_auth_provider() is get_auth_provider()


def test_reset_rebuilds_on_next_use():
    """Resetting drops the provider so the next call builds afresh."""
    with patch.dict(os.environ, OSDU_TEST_ENV):
        first = get_auth_provider()

        reset_auth_provider()

        assert get_auth_provider() is not first


def test_reset_without_a_provider_is_a_noop():
    """Resetting when nothing was built never raises."""
    reset_auth_provider()
    reset_auth_provider()


def test_reset_closes_the_provider():
    """Resetting releases the provider's resources."""
    with patch.dict(os.environ, OSDU_TEST_ENV):
        provider = get_auth_provider()

        with patch.object(provider, "close") as close:
            reset_auth_provider()

    close.assert_called_once()


def test_client_defaults_to_the_shared_provider():
    """A client built without an explicit provider borrows the shared one."""
    with patch.dict(os.environ, OSDU_TEST_ENV):
        client = OsduClient()

        assert client.auth is get_auth_provider()
        assert client.server_url == "https://test.osdu.com"
        assert client.data_partition == "opendes"


def test_construction_is_deferred_until_first_use():
    """Importing and resetting never touches credentials.

    Construction raises when auth is not configured, so it must not run until
    a tool actually needs a token.
    """
    with patch.dict(os.environ, {}, clear=True):
        with patch("osdu_wireline.shared.auth.registry._build_provider") as build:
            reset_auth_provider()

            build.assert_not_called()


async def test_check_credentials_reports_success():
    """A provider that yields a token reports valid, naming the grant type."""
    report = await check_credentials(StaticTokenProvider())

    assert report == {"grant_type": "authorization_code", "status": "valid"}


async def test_check_credentials_carries_the_providers_guidance():
    """An auth failure reports invalid *and* why, rather than a bare flag.

    The provider's message names the fix, so discarding it would leave the
    caller knowing only that something is wrong.
    """
    provider = StaticTokenProvider()
    guidance = "Azure did not recognize the authority. Please verify ..."
    with patch.object(provider, "get_token", side_effect=OSMCPAuthError(guidance)):
        report = await check_credentials(provider)

    assert report["status"] == "invalid"
    assert report["grant_type"] == "authorization_code"
    assert report["error"] == guidance


async def test_check_credentials_omits_error_on_success():
    """A healthy provider reports no error key at all."""
    report = await check_credentials(StaticTokenProvider())

    assert "error" not in report


async def test_server_starts_without_any_credentials():
    """The lifespan must not fail when auth is not configured.

    Building the provider eagerly would stop the server from starting; the
    error belongs on the first tool call instead.
    """
    from osdu_wireline.server import app_lifespan, mcp

    with patch.dict(os.environ, {}, clear=True):
        async with app_lifespan(mcp):
            with pytest.raises(OSMCPAuthError):
                get_auth_provider()


async def test_lifespan_releases_the_provider_on_shutdown():
    """Shutting the server down clears the shared provider."""
    from osdu_wireline.server import app_lifespan, mcp

    with patch.dict(os.environ, OSDU_TEST_ENV):
        async with app_lifespan(mcp):
            provider = StaticTokenProvider()
            install_provider(provider)

        assert get_auth_provider() is not provider
