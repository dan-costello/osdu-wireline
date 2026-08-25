"""Tests for the Azure DefaultAzureCredential provider."""

import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError

from osdu_wireline.shared.auth.azure import AzureProvider
from osdu_wireline.shared.exceptions import OSMCPAuthError
from tests.conftest import AZURE_CREDENTIAL


def azure_token(token: str = "test-token", valid_for: int = 3600) -> AccessToken:
    """Build an AccessToken expiring the given number of seconds from now.

    Args:
        token: Token string
        valid_for: Seconds until expiry, negative for an already-expired token

    Returns:
        AccessToken instance
    """
    expires_on = int((datetime.now() + timedelta(seconds=valid_for)).timestamp())
    return AccessToken(token=token, expires_on=expires_on)


@pytest.fixture
def credential():
    """Patch DefaultAzureCredential and yield the instance it returns."""
    with patch(AZURE_CREDENTIAL) as cls:
        instance = MagicMock()
        cls.return_value = instance
        instance.cls = cls
        yield instance


async def test_token_scope_derived_from_client_id(credential):
    """With no explicit scope, the scope is derived from AZURE_CLIENT_ID."""
    credential.get_token.return_value = azure_token()

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        assert await AzureProvider().get_token() == "test-token"

    credential.get_token.assert_called_once_with("test-client-id/.default")


async def test_explicit_scope_is_passed_through_verbatim(credential):
    """OSDU_AUTH_SCOPE is a single scope string for Azure, not a list."""
    credential.get_token.return_value = azure_token("azure-token")

    with patch.dict(
        os.environ,
        {
            "AZURE_CLIENT_ID": "azure-id",
            "OSDU_AUTH_SCOPE": "api://azure-id/.default",
        },
        clear=True,
    ):
        assert await AzureProvider().get_token() == "azure-token"

    credential.get_token.assert_called_once_with("api://azure-id/.default")


async def test_valid_token_is_cached(credential):
    """A live token is reused instead of re-requested."""
    credential.get_token.return_value = azure_token("cached-token")

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        provider = AzureProvider()

        assert await provider.get_token() == "cached-token"
        assert await provider.get_token() == "cached-token"

    assert credential.get_token.call_count == 1


async def test_expired_token_is_refreshed(credential):
    """A token past its refresh buffer triggers a new request."""
    credential.get_token.side_effect = [
        azure_token("expired-token", valid_for=-3600),
        azure_token("new-token"),
    ]

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        provider = AzureProvider()

        assert await provider.get_token() == "expired-token"
        assert await provider.get_token() == "new-token"

    assert credential.get_token.call_count == 2


async def test_token_inside_refresh_buffer_is_refreshed(credential):
    """A token expiring within five minutes is replaced before it lapses."""
    credential.get_token.side_effect = [
        azure_token("almost-expired", valid_for=120),
        azure_token("new-token"),
    ]

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        provider = AzureProvider()

        assert await provider.get_token() == "almost-expired"
        assert await provider.get_token() == "new-token"


def test_service_principal_excludes_developer_credentials(credential):
    """A client secret means Service Principal auth, so CLI methods are excluded."""
    with patch.dict(
        os.environ,
        {"AZURE_CLIENT_ID": "test", "AZURE_CLIENT_SECRET": "test-secret"},
        clear=True,
    ):
        AzureProvider()

    kwargs = credential.cls.call_args.kwargs
    assert kwargs["exclude_azure_cli_credential"] is True
    assert kwargs["exclude_azure_powershell_credential"] is True
    assert kwargs["exclude_interactive_browser_credential"] is True


def test_without_secret_allows_cli_but_never_interactive(credential):
    """Without a secret, CLI and PowerShell are allowed; browser never is."""
    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test"}, clear=True):
        AzureProvider()

    kwargs = credential.cls.call_args.kwargs
    assert kwargs["exclude_azure_cli_credential"] is False
    assert kwargs["exclude_azure_powershell_credential"] is False
    assert kwargs["exclude_interactive_browser_credential"] is True


async def test_missing_client_id_is_reported_directly(credential):
    """Tenant-only configuration names the missing variable."""
    with patch.dict(os.environ, {"AZURE_TENANT_ID": "test-tenant"}, clear=True):
        with pytest.raises(OSMCPAuthError, match="AZURE_CLIENT_ID"):
            await AzureProvider().get_token()


@pytest.mark.parametrize(
    ("azure_error", "expected"),
    [
        ("Please run 'az login' to set up an account", "Please run 'az login'"),
        ("The refresh token has expired or is invalid", "token expired"),
        ("The scope format is invalid. AADSTS70011", "Invalid Azure client ID"),
        (
            "Environment variables are not fully configured",
            "No Azure credentials found",
        ),
        ("Something entirely unrecognized", "Please check your Azure credentials"),
    ],
)
async def test_authentication_errors_map_to_guidance(credential, azure_error, expected):
    """Azure failures become messages that name the fix."""
    credential.get_token.side_effect = ClientAuthenticationError(azure_error)

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        with pytest.raises(OSMCPAuthError, match=expected):
            await AzureProvider().get_token()


async def test_service_principal_failure_names_its_three_variables(credential):
    """With a secret configured, the error points at the SP variables."""
    credential.get_token.side_effect = ClientAuthenticationError(
        "Environment variables are not fully configured"
    )

    with patch.dict(
        os.environ,
        {"AZURE_CLIENT_ID": "test-client-id", "AZURE_CLIENT_SECRET": "test-secret"},
        clear=True,
    ):
        with pytest.raises(OSMCPAuthError) as exc_info:
            await AzureProvider().get_token()

    assert "Service Principal authentication failed" in str(exc_info.value)
    assert "AZURE_CLIENT_ID" in str(exc_info.value)


async def test_network_failure_is_distinguished_from_bad_credentials(credential):
    """A connectivity problem is not reported as an authentication problem."""
    credential.get_token.side_effect = Exception("Connection timeout")

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        with pytest.raises(OSMCPAuthError, match="Failed to connect to Azure"):
            await AzureProvider().get_token()


async def test_unexpected_error_stays_vague(credential):
    """Unrecognized failures do not leak internal detail to the caller."""
    credential.get_token.side_effect = Exception("Unknown error")

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        with pytest.raises(OSMCPAuthError, match="Authentication configuration error"):
            await AzureProvider().get_token()


def test_close_clears_cache_and_credential(credential):
    """Closing drops the cached token and closes the underlying credential."""
    credential.get_token.return_value = azure_token()

    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "test-client-id"}, clear=True):
        provider = AzureProvider()

    provider._cached_token = AccessToken("token", int(time.time()) + 3600)
    provider.close()

    assert provider._cached_token is None
    credential.close.assert_called_once()
