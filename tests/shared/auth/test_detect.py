"""Tests for authentication mode detection and its precedence rules."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.auth import AuthenticationMode, detect_provider
from osdu_wireline.shared.exceptions import OSMCPAuthError
from tests.conftest import AZURE_CREDENTIAL

from .conftest import make_jwt


def test_user_token_beats_azure():
    """A manually supplied token wins over the Azure credential chain.

    This is how an operator overrides whatever `az login` resolved without
    having to log out of the CLI.
    """
    env = {"OSDU_USER_TOKEN": make_jwt(), "AZURE_CLIENT_ID": "azure-id"}

    with patch.dict(os.environ, env, clear=True):
        assert detect_provider().mode is AuthenticationMode.USER_TOKEN


def test_azure_detected_from_client_id():
    """AZURE_CLIENT_ID selects Azure."""
    with patch.dict(os.environ, {"AZURE_CLIENT_ID": "azure-id"}, clear=True):
        with patch(AZURE_CREDENTIAL):
            assert detect_provider().mode is AuthenticationMode.AZURE


def test_azure_detected_from_tenant_id_alone():
    """AZURE_TENANT_ID on its own is enough to select Azure."""
    with patch.dict(os.environ, {"AZURE_TENANT_ID": "test-tenant"}, clear=True):
        with patch(AZURE_CREDENTIAL):
            assert detect_provider().mode is AuthenticationMode.AZURE


def test_legacy_user_token_name_still_selects_user_token():
    """The pre-rename OSDU_MCP_USER_TOKEN spelling keeps working."""
    with patch.dict(os.environ, {"OSDU_MCP_USER_TOKEN": make_jwt()}, clear=True):
        assert detect_provider().mode is AuthenticationMode.USER_TOKEN


def test_canonical_user_token_name_wins_over_the_legacy_one():
    """With both spellings set, the canonical name is authoritative."""
    canonical = make_jwt()
    env = {"OSDU_USER_TOKEN": canonical, "OSDU_MCP_USER_TOKEN": make_jwt()}

    with patch.dict(os.environ, env, clear=True):
        assert os.environ["OSDU_USER_TOKEN"] == canonical
        assert detect_provider().mode is AuthenticationMode.USER_TOKEN


def test_aws_and_gcp_variables_no_longer_select_a_provider():
    """Cloud variables for the removed providers must not resolve.

    The AWS provider handed back an STS session token and the client sent it as
    an `Authorization: Bearer` header, which OSDU on AWS does not accept. Both
    it and the never-exercised GCP provider were removed, so their environment
    variables have to fall through to the "nothing configured" error rather
    than silently selecting something.
    """
    env = {
        "AWS_ACCESS_KEY_ID": "aws-key",
        "AWS_PROFILE": "dev",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/key.json",
    }

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(OSMCPAuthError, match="No authentication credentials"):
            detect_provider()


def test_no_credentials_lists_every_setup_option():
    """With nothing available, the error walks through both supported modes."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(
            OSMCPAuthError, match="No authentication credentials configured"
        ) as exc_info:
            detect_provider()

    message = str(exc_info.value)
    for hint in ("OSDU_USER_TOKEN", "az login", "AZURE_CLIENT_ID"):
        assert hint in message
