"""Shared test fixtures.

Tools now resolve configuration and authentication from a process-wide app
context, so tests mock at the boundaries (environment + HTTP) per ADR-010
rather than patching object construction inside tool modules.
"""

import os
import time
from unittest.mock import patch

import jwt
import pytest

from osdu_wireline.shared.app_context import reset_app_context

# USER_TOKEN mode validates JWT structure and expiry, so use a real token
TEST_TOKEN = jwt.encode(
    {"sub": "test-user", "exp": int(time.time()) + 3600},
    "test-secret",
    algorithm="HS256",
)

# OSDU_MCP_USER_TOKEN selects USER_TOKEN auth mode, which needs no cloud SDKs
OSDU_TEST_ENV = {
    "OSDU_MCP_SERVER_URL": "https://test.osdu.com",
    "OSDU_MCP_SERVER_DATA_PARTITION": "opendes",
    "OSDU_MCP_USER_TOKEN": TEST_TOKEN,
}


@pytest.fixture(autouse=True)
def clean_app_context():
    """Ensure no context leaks between tests.

    Without this the lazily built context would cache the first test's
    environment and later tests patching os.environ would silently reuse it.
    """
    reset_app_context()
    yield
    reset_app_context()


@pytest.fixture
def osdu_env():
    """Minimal environment for building a real config and auth handler."""
    with patch.dict(os.environ, OSDU_TEST_ENV):
        yield


@pytest.fixture
def sent_json():
    """Read back the JSON body aioresponses actually received.

    Registering a URL with aioresponses only asserts the path, so a request
    that sends no body at all still matches. Use this to assert on the body.
    """

    def _sent_json(mocked, method: str, url: str):
        for (call_method, call_url), calls in (mocked.requests or {}).items():
            if call_method == method and str(call_url) == url:
                return calls[0].kwargs.get("json")
        raise AssertionError(f"no {method} request recorded for {url}")

    return _sent_json
