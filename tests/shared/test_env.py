"""Tests for environment variable configuration accessors."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.env import (
    get_env,
    get_env_bool,
    require_env,
)
from osdu_wireline.shared.exceptions import OSMCPConfigError


def test_get_env_returns_value():
    """A set variable is returned as-is, without type coercion."""
    with patch.dict(os.environ, {"OSDU_BASE_URL": "https://osdu.com"}, clear=True):
        assert get_env("OSDU_BASE_URL") == "https://osdu.com"


def test_get_env_returns_default_when_unset():
    """An unset variable falls back to the default."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_env("OSDU_MCP_TEST_VALUE", "INFO") == "INFO"


def test_get_env_treats_empty_as_unset():
    """An empty value is indistinguishable from unset."""
    with patch.dict(os.environ, {"OSDU_MCP_TEST_VALUE": ""}, clear=True):
        assert get_env("OSDU_MCP_TEST_VALUE", "INFO") == "INFO"


def test_require_env_returns_value():
    """A set required variable is returned."""
    with patch.dict(os.environ, {"OSDU_BASE_URL": "https://osdu.com"}, clear=True):
        assert require_env("OSDU_BASE_URL") == "https://osdu.com"


def test_require_env_names_the_variable_when_missing():
    """The error tells the user exactly which variable to set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(OSMCPConfigError) as exc_info:
            require_env("OSDU_BASE_URL")

        assert "OSDU_BASE_URL" in str(exc_info.value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("1", True),
        (" true ", True),
        ("false", False),
        ("no", False),
        ("0", False),
        ("", False),
        ("maybe", False),
    ],
)
def test_get_env_bool_truth_table(value, expected):
    """Only true/yes/1 are truthy, case- and whitespace-insensitive."""
    with patch.dict(os.environ, {"OSDU_MCP_ENABLE_WRITE_MODE": value}, clear=True):
        assert get_env_bool("OSDU_MCP_ENABLE_WRITE_MODE") is expected


def test_get_env_bool_default_when_unset():
    """An unset variable uses the supplied default."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_env_bool("OSDU_MCP_TEST_FLAG") is False
        assert get_env_bool("OSDU_MCP_TEST_FLAG", True) is True
