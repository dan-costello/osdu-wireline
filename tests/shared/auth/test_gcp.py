"""Tests for the GCP Application Default Credentials provider."""

import os
from unittest.mock import patch

import pytest
from google.auth.exceptions import DefaultCredentialsError, RefreshError

from osdu_wireline.shared.auth import AuthenticationMode
from osdu_wireline.shared.auth.gcp import DEFAULT_GCP_SCOPES, GcpProvider
from osdu_wireline.shared.exceptions import OSMCPAuthError

GCP_ENV = {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/key.json"}


async def test_returns_current_token_when_valid(gcp_credentials):
    """A live credential is used without a refresh round trip."""
    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            provider = GcpProvider()

            assert await provider.get_token() == "gcp-token"
            assert provider.mode is AuthenticationMode.GCP

    gcp_credentials.refresh.assert_not_called()


async def test_expired_credential_is_refreshed(gcp_credentials):
    """An invalid credential is refreshed before its token is read."""
    gcp_credentials.valid = False
    gcp_credentials.token = "gcp-token-123"

    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            with patch("google.auth.transport.requests.Request"):
                provider = GcpProvider()

                assert await provider.get_token() == "gcp-token-123"

    gcp_credentials.refresh.assert_called_once()


async def test_identity_scopes_requested_by_default(gcp_credentials):
    """OSDU resolves entitlements by email, so identity scopes are required."""
    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "p")) as adc:
            GcpProvider()

    assert adc.call_args.kwargs["scopes"] == DEFAULT_GCP_SCOPES
    assert "https://www.googleapis.com/auth/userinfo.email" in DEFAULT_GCP_SCOPES


async def test_custom_scope_replaces_the_defaults(gcp_credentials):
    """OSDU_MCP_AUTH_SCOPE overrides rather than extends the defaults."""
    env = {**GCP_ENV, "OSDU_MCP_AUTH_SCOPE": "https://example.com/auth/custom-scope"}

    with patch.dict(os.environ, env, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "p")) as adc:
            GcpProvider()

    assert adc.call_args.kwargs["scopes"] == ["https://example.com/auth/custom-scope"]


async def test_custom_scope_parses_comma_separated_list(gcp_credentials):
    """A comma-separated scope list is split and stripped."""
    env = {
        **GCP_ENV,
        "OSDU_MCP_AUTH_SCOPE": " openid , https://www.googleapis.com/auth/userinfo.email ",
    }

    with patch.dict(os.environ, env, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "p")) as adc:
            GcpProvider()

    assert adc.call_args.kwargs["scopes"] == [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ]


def test_missing_credentials_names_the_setup_options():
    """Construction fails with actionable setup instructions."""
    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", side_effect=DefaultCredentialsError()):
            with pytest.raises(
                OSMCPAuthError, match="GCP Application Default Credentials not found"
            ):
                GcpProvider()


@pytest.mark.parametrize(
    ("refresh_error", "expected"),
    [
        ("Token expired", "GCP refresh token expired"),
        ("credentials are malformed", "GCP credentials invalid"),
        ("file not found at path", "GCP credentials file not found"),
        ("something unrecognized", "GCP token refresh failed"),
    ],
)
async def test_refresh_errors_map_to_guidance(gcp_credentials, refresh_error, expected):
    """Refresh failures become messages that name the fix."""
    gcp_credentials.valid = False
    gcp_credentials.refresh.side_effect = RefreshError(refresh_error)

    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            with patch("google.auth.transport.requests.Request"):
                provider = GcpProvider()

                with pytest.raises(OSMCPAuthError, match=expected):
                    await provider.get_token()


async def test_unexpected_refresh_error_is_wrapped(gcp_credentials):
    """A non-RefreshError during refresh still surfaces as an auth error."""
    gcp_credentials.valid = False
    gcp_credentials.refresh.side_effect = ValueError("boom")

    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            with patch("google.auth.transport.requests.Request"):
                provider = GcpProvider()

                with pytest.raises(OSMCPAuthError, match="Unexpected GCP"):
                    await provider.get_token()


async def test_empty_token_after_refresh_is_an_error(gcp_credentials):
    """A refresh that yields no token fails rather than sending an empty header."""
    gcp_credentials.valid = True
    gcp_credentials.token = None

    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            provider = GcpProvider()

            with pytest.raises(OSMCPAuthError, match="GCP token is None"):
                await provider.get_token()


def test_is_discoverable_reports_resolvable_credentials(gcp_credentials):
    """Discovery is true when ADC resolves."""
    with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
        assert GcpProvider.is_discoverable() is True


def test_is_discoverable_swallows_probe_failures():
    """A raising google.auth is treated as "not discoverable", not as a crash."""
    with patch("google.auth.default", side_effect=Exception("no GCP")):
        assert GcpProvider.is_discoverable() is False


def test_close_releases_the_credentials(gcp_credentials):
    """Closing drops the credentials."""
    with patch.dict(os.environ, GCP_ENV, clear=True):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            provider = GcpProvider()

    provider.close()

    assert provider._credentials is None
