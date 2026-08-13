"""Tests for the shared application context focusing on behavior."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.app_context import (
    AppContext,
    create_app_context,
    get_app_context,
    reset_app_context,
    set_app_context,
)
from osdu_wireline.shared.auth_handler import AuthenticationMode
from osdu_wireline.shared.osdu_client import OsduClient

# USER_TOKEN mode has the highest priority and needs no cloud SDK calls
TEST_ENV = {
    "OSDU_MCP_SERVER_URL": "https://test-osdu.com",
    "OSDU_MCP_SERVER_DATA_PARTITION": "test-partition",
    "OSDU_MCP_USER_TOKEN": "test-token",
}


@pytest.fixture(autouse=True)
def clean_context():
    """Ensure each test starts and ends without a cached context."""
    reset_app_context()
    yield
    reset_app_context()


def test_get_app_context_caches_instance():
    """Repeated calls return the same context instead of rebuilding it."""
    with patch.dict(os.environ, TEST_ENV):
        first = get_app_context()
        second = get_app_context()

        assert first is second


def test_context_clients_read_configuration():
    """Clients built from the shared context pick up server settings."""
    with patch.dict(os.environ, TEST_ENV):
        client = OsduClient(get_app_context().auth)

        assert client.server_url == "https://test-osdu.com"
        assert client.data_partition == "test-partition"


def test_set_and_reset_app_context():
    """An installed context is returned, and reset clears it."""
    with patch.dict(os.environ, TEST_ENV):
        installed = create_app_context()
        set_app_context(installed)

        assert get_app_context() is installed

        reset_app_context()

        assert get_app_context() is not installed


def test_reset_app_context_without_context():
    """Resetting when nothing is installed is a no-op."""
    reset_app_context()
    reset_app_context()


def test_auth_is_shared_across_accesses():
    """The auth handler is built once and reused, preserving its token cache."""
    with patch.dict(os.environ, TEST_ENV):
        context = get_app_context()

        assert context.auth is context.auth
        assert context.auth.mode == AuthenticationMode.USER_TOKEN


def test_auth_construction_is_deferred():
    """Building a context does not construct the auth handler.

    Deferral keeps a credential-less environment from breaking server startup;
    the authentication error surfaces per tool call instead.
    """
    with patch.dict(os.environ, TEST_ENV):
        context = create_app_context()

        assert context._auth is None


def test_close_releases_auth():
    """Closing the context releases the auth handler."""
    with patch.dict(os.environ, TEST_ENV):
        context = create_app_context()
        assert context.auth is not None

        context.close()

        assert context._auth is None


@pytest.mark.asyncio
async def test_lifespan_installs_and_clears_context():
    """The server lifespan shares one context for the duration of the run."""
    from osdu_wireline.server import app_lifespan, mcp

    with patch.dict(os.environ, TEST_ENV):
        async with app_lifespan(mcp) as context:
            assert isinstance(context, AppContext)
            assert get_app_context() is context

        # Context is cleared on shutdown, so a new one is built afterwards
        assert get_app_context() is not context
