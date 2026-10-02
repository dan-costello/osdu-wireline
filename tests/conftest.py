"""Shared test fixtures.

Tools resolve configuration from the environment and authentication from a
process-wide credential provider, so tests mock at the boundaries
(environment + HTTP) per ADR-010 rather than patching object construction
inside tool modules.
"""

import logging
import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from osdu_wireline.shared.auth import registry, reset_auth_provider

TEST_TOKEN = "test-token"

OSDU_TEST_ENV = {
    "OSDU_GRANT_TYPE": "authorization_code",
    "OSDU_BASE_URL": "https://test.osdu.com",
    "OSDU_PARTITION_ID": "opendes",
}


class StaticTokenProvider:
    """Credential provider returning a fixed token, so no browser opens."""

    def __init__(self, token: str = TEST_TOKEN):
        self.token = token

    async def get_token(self) -> str:
        return self.token

    def close(self) -> None:
        pass


def install_provider(provider) -> None:
    """Make `provider` the shared credential provider."""
    reset_auth_provider()
    registry._provider = provider


@contextmanager
def static_token():
    """Use a static-token provider for the duration of the block."""
    install_provider(StaticTokenProvider())
    yield


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
    """Server environment with a static-token credential provider."""
    with patch.dict(os.environ, OSDU_TEST_ENV):
        install_provider(StaticTokenProvider())
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
