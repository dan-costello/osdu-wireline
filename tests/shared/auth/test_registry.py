"""Tests for the process-wide credential provider and its lifecycle."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.auth import (
    AuthenticationMode,
    check_credentials,
    get_auth_provider,
    reset_auth_provider,
)
from osdu_wireline.shared.clients import OsduClient
from osdu_wireline.shared.exceptions import OSMCPAuthError

from .conftest import make_jwt

# USER_TOKEN has the highest priority and needs no cloud SDK calls
TEST_ENV = {
    "OSDU_SERVER_URL": "https://test-osdu.com",
    "OSDU_DATA_PARTITION": "test-partition",
    "OSDU_USER_TOKEN": make_jwt(),
}


def test_provider_is_shared_across_calls():
    """Repeated calls return the same provider, preserving its token cache."""
    with patch.dict(os.environ, TEST_ENV):
        assert get_auth_provider() is get_auth_provider()
        assert get_auth_provider().mode is AuthenticationMode.USER_TOKEN


def test_reset_rebuilds_on_next_use():
    """Resetting drops the provider so the next call detects afresh."""
    with patch.dict(os.environ, TEST_ENV):
        first = get_auth_provider()

        reset_auth_provider()

        assert get_auth_provider() is not first


def test_reset_without_a_provider_is_a_noop():
    """Resetting when nothing was built never raises."""
    reset_auth_provider()
    reset_auth_provider()


def test_reset_closes_the_provider():
    """Resetting releases the provider's resources."""
    with patch.dict(os.environ, TEST_ENV):
        provider = get_auth_provider()

        with patch.object(provider, "close") as close:
            reset_auth_provider()

    close.assert_called_once()


def test_client_defaults_to_the_shared_provider():
    """A client built without an explicit provider borrows the shared one."""
    with patch.dict(os.environ, TEST_ENV):
        client = OsduClient()

        assert client.auth is get_auth_provider()
        assert client.server_url == "https://test-osdu.com"
        assert client.data_partition == "test-partition"


def test_detection_is_deferred_until_first_use():
    """Importing and resetting never touches credentials.

    Detection raises when nothing is configured, so it must not run until a
    tool actually needs a token.
    """
    with patch.dict(os.environ, {}, clear=True):
        with patch("osdu_wireline.shared.auth.registry.detect_provider") as detect:
            reset_auth_provider()

            detect.assert_not_called()


async def test_check_credentials_reports_success():
    """A provider that yields a token reports valid, naming the mode."""
    with patch.dict(os.environ, TEST_ENV):
        report = await check_credentials(get_auth_provider())

    assert report == {"mode": "user_token", "status": "valid"}


async def test_check_credentials_carries_the_providers_guidance():
    """An auth failure reports invalid *and* why, rather than a bare flag.

    The provider's message names the fix, so discarding it would leave the
    caller knowing only that something is wrong.
    """
    with patch.dict(os.environ, TEST_ENV):
        provider = get_auth_provider()

    guidance = "Azure authentication token expired. Please run 'az login' to refresh"
    with patch.object(provider, "get_token", side_effect=OSMCPAuthError(guidance)):
        report = await check_credentials(provider)

    assert report["status"] == "invalid"
    assert report["mode"] == "user_token"
    assert report["error"] == guidance


async def test_check_credentials_omits_error_on_success():
    """A healthy provider reports no error key at all."""
    with patch.dict(os.environ, TEST_ENV):
        report = await check_credentials(get_auth_provider())

    assert "error" not in report


async def test_server_starts_without_any_credentials():
    """The lifespan must not fail when no credentials are configured.

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

    with patch.dict(os.environ, TEST_ENV):
        async with app_lifespan(mcp):
            provider = get_auth_provider()

        assert get_auth_provider() is not provider
