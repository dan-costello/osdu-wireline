"""Tests for startup validation and the console entry point.

Server configuration is validated before serving because it comes from the MCP
client's config file and cannot be fixed without a restart. Credentials are
deliberately *not* validated here - see `test_startup_does_not_touch_credentials`.
"""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.main import main
from osdu_wireline.server import verify_startup
from osdu_wireline.shared.exceptions import OSMCPConfigError

SERVER_ENV = {
    "OSDU_SERVER_URL": "https://test.osdu.com",
    "OSDU_DATA_PARTITION": "opendes",
}


def test_verify_startup_passes_with_server_config():
    """Both required variables present is enough to start."""
    with patch.dict(os.environ, SERVER_ENV, clear=True):
        verify_startup()


@pytest.mark.parametrize(
    "missing",
    ["OSDU_SERVER_URL", "OSDU_DATA_PARTITION"],
)
def test_verify_startup_names_the_missing_variable(missing):
    """A missing variable is reported by name, not as a generic failure."""
    env = {k: v for k, v in SERVER_ENV.items() if k != missing}

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(OSMCPConfigError, match=missing):
            verify_startup()


def test_startup_does_not_touch_credentials():
    """Startup must not resolve credentials, even when none are configured.

    Credentials are refreshable out of band - `az login` fixes a running
    server - so validating them here would force an MCP client restart for a
    problem that heals itself.
    """
    with patch.dict(os.environ, SERVER_ENV, clear=True):
        with patch("osdu_wireline.shared.auth.registry.detect_provider") as detect:
            verify_startup()

    detect.assert_not_called()


def test_main_runs_the_server_when_configuration_is_valid(restore_package_logger):
    """A valid environment hands off to the MCP server."""
    with patch.dict(os.environ, SERVER_ENV, clear=True):
        with patch("osdu_wireline.main.mcp") as mcp:
            main()

    mcp.run.assert_called_once()


def test_main_exits_without_starting_the_server(capsys, restore_package_logger):
    """A misconfigured environment exits non-zero and never serves."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("osdu_wireline.main.mcp") as mcp:
            with pytest.raises(SystemExit) as exc_info:
                main()

    assert exc_info.value.code == 1
    mcp.run.assert_not_called()


def test_main_writes_diagnostics_to_stderr_only(capsys, restore_package_logger):
    """Nothing may reach stdout: it carries the MCP protocol on stdio."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("osdu_wireline.main.mcp"):
            with pytest.raises(SystemExit):
                main()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "OSDU_SERVER_URL" in captured.err
    assert "Configuration error" in captured.err
