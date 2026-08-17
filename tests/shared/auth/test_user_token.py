"""Tests for the manual Bearer token provider."""

import logging
import os
import time
from unittest.mock import patch

import pytest

from osdu_wireline.shared.auth import AuthenticationMode
from osdu_wireline.shared.auth.user_token import UserTokenProvider
from osdu_wireline.shared.exceptions import OSMCPAuthError

from .conftest import make_jwt


async def test_returns_token_from_environment():
    """A valid token is handed back unchanged, without a Bearer prefix."""
    token = make_jwt(exp=time.time() + 7200)

    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": token}):
        provider = UserTokenProvider()

        assert await provider.get_token() == token
        assert provider.mode is AuthenticationMode.USER_TOKEN


async def test_rejects_expired_token():
    """An expired token fails rather than being sent to OSDU."""
    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": make_jwt(time.time() - 3600)}):
        provider = UserTokenProvider()

        with pytest.raises(OSMCPAuthError, match="expired"):
            await provider.get_token()


async def test_rejects_malformed_token():
    """A string that is not a JWT fails with a format error."""
    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": "not-a-valid-jwt"}):
        provider = UserTokenProvider()

        with pytest.raises(OSMCPAuthError, match="Invalid JWT token format"):
            await provider.get_token()


async def test_token_expiring_soon_still_works_but_warns(caplog):
    """A token close to expiry is accepted, with a warning for the operator."""
    token = make_jwt(exp=time.time() + 120)

    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": token}):
        provider = UserTokenProvider()

        with caplog.at_level(logging.WARNING):
            assert await provider.get_token() == token

        assert "expires in" in caplog.text


async def test_token_without_expiry_is_accepted():
    """A JWT carrying no exp claim is passed through for OSDU to judge."""
    import jwt as jwt_lib

    token = jwt_lib.encode({"sub": "test-user"}, "secret", algorithm="HS256")

    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": token}):
        provider = UserTokenProvider()

        assert await provider.get_token() == token


async def test_missing_token_is_an_error():
    """Losing the variable after construction fails loudly.

    The token is re-read on every call so it can be rotated at runtime.
    """
    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": make_jwt()}):
        provider = UserTokenProvider()

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(OSMCPAuthError, match="OSDU_MCP_USER_TOKEN not set"):
            await provider.get_token()


def test_close_is_a_noop():
    """Closing releases nothing and never raises."""
    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": make_jwt()}):
        UserTokenProvider().close()
