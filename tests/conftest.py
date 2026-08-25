"""Shared test fixtures.

Tools resolve configuration from the environment and authentication from a
process-wide credential provider, so tests mock at the boundaries
(environment + HTTP) per ADR-010 rather than patching object construction
inside tool modules.
"""

import logging
import os
import time
from unittest.mock import patch

import jwt
import pytest

from osdu_wireline.shared.auth import reset_auth_provider

# Patch target for Azure tests. The symbol must be patched where it is used,
# so keep this in one place rather than spelling the path out at every site.
AZURE_CREDENTIAL = "osdu_wireline.shared.auth.azure.DefaultAzureCredential"

# USER_TOKEN mode validates JWT structure and expiry, so use a real token
TEST_TOKEN = jwt.encode(
    {"sub": "test-user", "exp": int(time.time()) + 3600},
    "test-secret",
    algorithm="HS256",
)

# OSDU_USER_TOKEN selects USER_TOKEN auth mode, which needs no cloud SDKs
OSDU_TEST_ENV = {
    "OSDU_SERVER_URL": "https://test.osdu.com",
    "OSDU_DATA_PARTITION": "opendes",
    "OSDU_USER_TOKEN": TEST_TOKEN,
}


@pytest.fixture(autouse=True)
def clean_auth_provider():
    """Ensure no credential provider leaks between tests.

    Without this the lazily built provider would cache the first test's
    environment and later tests patching os.environ would silently reuse it.
    """
    reset_auth_provider()
    yield
    reset_auth_provider()


@pytest.fixture
def restore_package_logger():
    """Undo configure_logging()'s effect on the package-root logger.

    configure_logging() installs a handler and sets propagate=False on the
    process-wide `osdu_wireline` logger. Left in place that would hide records
    from pytest's caplog, which captures by propagation to the root logger, so
    any test that configures logging must hand the logger back as it found it.
    """
    logger = logging.getLogger("osdu_wireline")
    handlers = logger.handlers[:]
    level = logger.level
    propagate = logger.propagate

    yield logger

    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


@pytest.fixture
def osdu_env():
    """Minimal environment for building a real credential provider."""
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
