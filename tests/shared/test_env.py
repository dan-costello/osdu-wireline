"""Tests for environment variable configuration accessors."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.env import (
    get_env,
    get_env_bool,
    get_env_int,
    get_setting,
    get_setting_int,
    require_env,
    require_setting,
    setting_names,
)
from osdu_wireline.shared.exceptions import OSMCPConfigError


def test_get_env_returns_value():
    """A set variable is returned as-is, without type coercion."""
    with patch.dict(os.environ, {"OSDU_SERVER_URL": "https://osdu.com"}, clear=True):
        assert get_env("OSDU_SERVER_URL") == "https://osdu.com"


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
    with patch.dict(os.environ, {"OSDU_SERVER_URL": "https://osdu.com"}, clear=True):
        assert require_env("OSDU_SERVER_URL") == "https://osdu.com"


def test_require_env_names_the_variable_when_missing():
    """The error tells the user exactly which variable to set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(OSMCPConfigError) as exc_info:
            require_env("OSDU_SERVER_URL")

        assert "OSDU_SERVER_URL" in str(exc_info.value)


def test_get_env_int_parses_and_falls_back():
    """Numeric values parse; unset or unparseable values use the default."""
    with patch.dict(os.environ, {"OSDU_TIMEOUT": "45"}, clear=True):
        assert get_env_int("OSDU_TIMEOUT", 30) == 45

    with patch.dict(os.environ, {}, clear=True):
        assert get_env_int("OSDU_TIMEOUT", 30) == 30

    with patch.dict(os.environ, {"OSDU_TIMEOUT": "soon"}, clear=True):
        assert get_env_int("OSDU_TIMEOUT", 30) == 30


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


def test_setting_reads_the_canonical_name():
    """OSDU_SERVER_URL is the documented spelling."""
    with patch.dict(os.environ, {"OSDU_SERVER_URL": "https://osdu.com"}, clear=True):
        assert require_setting("OSDU_SERVER_URL") == "https://osdu.com"


def test_setting_falls_back_to_the_legacy_name():
    """A configuration written before the rename keeps working."""
    with patch.dict(
        os.environ, {"OSDU_MCP_SERVER_URL": "https://legacy.osdu.com"}, clear=True
    ):
        assert require_setting("OSDU_SERVER_URL") == "https://legacy.osdu.com"


def test_canonical_name_wins_over_the_legacy_one():
    """With both set the canonical spelling is authoritative."""
    env = {
        "OSDU_SERVER_URL": "https://new.osdu.com",
        "OSDU_MCP_SERVER_URL": "https://old.osdu.com",
    }

    with patch.dict(os.environ, env, clear=True):
        assert require_setting("OSDU_SERVER_URL") == "https://new.osdu.com"


def test_missing_setting_names_both_spellings():
    """The error lists every variable name that would satisfy it."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(OSMCPConfigError) as exc_info:
            require_setting("OSDU_SERVER_URL")

    message = str(exc_info.value)
    assert "OSDU_SERVER_URL" in message
    assert "OSDU_MCP_SERVER_URL" in message


def test_get_setting_returns_default_when_nothing_is_set():
    """An unset setting with no legacy value falls back to the default."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_setting("OSDU_AUTH_SCOPE", "fallback") == "fallback"


def test_get_setting_int_reads_either_spelling():
    """Both the canonical and legacy timeout names parse."""
    with patch.dict(os.environ, {"OSDU_TIMEOUT": "45"}, clear=True):
        assert get_setting_int("OSDU_TIMEOUT", 30) == 45

    with patch.dict(os.environ, {"OSDU_MCP_SERVER_TIMEOUT": "60"}, clear=True):
        assert get_setting_int("OSDU_TIMEOUT", 30) == 60

    with patch.dict(os.environ, {}, clear=True):
        assert get_setting_int("OSDU_TIMEOUT", 30) == 30


def test_setting_names_lists_canonical_first():
    """Fallback order is canonical, then legacy."""
    assert setting_names("OSDU_USER_TOKEN") == (
        "OSDU_USER_TOKEN",
        "OSDU_MCP_USER_TOKEN",
    )
