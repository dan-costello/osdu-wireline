"""Tests for authentication mode detection and its precedence rules."""

import os
from unittest.mock import patch

import pytest

from osdu_wireline.shared.auth import AuthenticationMode, detect_provider
from osdu_wireline.shared.exceptions import OSMCPAuthError
from tests.conftest import AZURE_CREDENTIAL

from .conftest import make_jwt


def test_user_token_beats_every_other_credential():
    """A manually supplied token always wins, whatever else is configured."""
    env = {
        "OSDU_MCP_USER_TOKEN": make_jwt(),
        "AZURE_CLIENT_ID": "azure-id",
        "AWS_ACCESS_KEY_ID": "aws-key",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/key.json",
    }

    with patch.dict(os.environ, env, clear=True):
        assert detect_provider().mode is AuthenticationMode.USER_TOKEN


def test_azure_beats_aws_and_gcp():
    """Azure outranks the other clouds when its variables are present."""
    env = {"AZURE_CLIENT_ID": "azure-id", "AWS_ACCESS_KEY_ID": "aws-key"}

    with patch.dict(os.environ, env, clear=True):
        with patch(AZURE_CREDENTIAL):
            assert detect_provider().mode is AuthenticationMode.AZURE


def test_azure_detected_from_tenant_id_alone():
    """AZURE_TENANT_ID on its own is enough to select Azure."""
    with patch.dict(os.environ, {"AZURE_TENANT_ID": "test-tenant"}, clear=True):
        with patch(AZURE_CREDENTIAL):
            assert detect_provider().mode is AuthenticationMode.AZURE


def test_explicit_aws_beats_explicit_gcp(boto_session):
    """AWS is checked before GCP when both are explicitly configured."""
    env = {
        "AWS_ACCESS_KEY_ID": "aws-key",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/key.json",
    }

    with patch.dict(os.environ, env, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            assert detect_provider().mode is AuthenticationMode.AWS


def test_aws_profile_selects_aws(boto_session):
    """AWS_PROFILE alone selects AWS, as SSO users set nothing else."""
    with patch.dict(os.environ, {"AWS_PROFILE": "dev"}, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            assert detect_provider().mode is AuthenticationMode.AWS


def test_gcp_selected_from_explicit_key_path(gcp_credentials):
    """GOOGLE_APPLICATION_CREDENTIALS selects GCP."""
    with patch.dict(
        os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/key.json"}, clear=True
    ):
        with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
            assert detect_provider().mode is AuthenticationMode.GCP


def test_aws_auto_discovery_when_nothing_is_configured(boto_session):
    """With no env vars set, a discoverable IAM role or SSO session is used."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            assert detect_provider().mode is AuthenticationMode.AWS


def test_gcp_auto_discovery_when_aws_is_unavailable(gcp_credentials):
    """GCP discovery runs only after AWS discovery comes up empty."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("boto3.Session", side_effect=Exception("No AWS credentials")):
            with patch("google.auth.default", return_value=(gcp_credentials, "proj")):
                assert detect_provider().mode is AuthenticationMode.GCP


def test_no_credentials_lists_every_setup_option():
    """With nothing available, the error walks through all four modes."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("boto3.Session", side_effect=Exception("No AWS")):
            with patch("google.auth.default", side_effect=Exception("No GCP")):
                with pytest.raises(
                    OSMCPAuthError, match="No authentication credentials configured"
                ) as exc_info:
                    detect_provider()

    message = str(exc_info.value)
    for hint in ("OSDU_MCP_USER_TOKEN", "az login", "aws sso login", "gcloud auth"):
        assert hint in message
