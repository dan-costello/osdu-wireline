"""Tests for the AWS boto3 credential provider."""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ProfileNotFound

from osdu_wireline.shared.auth import AuthenticationMode
from osdu_wireline.shared.auth.aws import AwsProvider
from osdu_wireline.shared.exceptions import OSMCPAuthError

AWS_ENV = {"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"}


async def test_returns_sts_session_token(boto_session):
    """The provider hands back the STS session token."""
    boto_session.client.return_value.get_session_token.return_value = {
        "Credentials": {
            "SessionToken": "aws-session-token-123",
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }
    }

    with patch.dict(os.environ, AWS_ENV, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            provider = AwsProvider()

            assert await provider.get_token() == "aws-session-token-123"
            assert provider.mode is AuthenticationMode.AWS


async def test_session_token_requests_one_hour(boto_session):
    """Session tokens are requested with an explicit duration."""
    sts = boto_session.client.return_value
    sts.get_session_token.return_value = {"Credentials": {"SessionToken": "tok"}}

    with patch.dict(os.environ, AWS_ENV, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            await AwsProvider().get_token()

    sts.get_session_token.assert_called_once_with(DurationSeconds=3600)


def test_missing_credentials_names_the_setup_options(boto_session):
    """Construction fails when boto3 resolves no credentials."""
    boto_session.get_credentials.return_value = None

    with patch.dict(os.environ, AWS_ENV, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            with pytest.raises(OSMCPAuthError, match="AWS credentials not found"):
                AwsProvider()


def test_unknown_profile_points_at_the_config_file():
    """A bad AWS_PROFILE names the variable and the config file."""
    with patch.dict(os.environ, {"AWS_PROFILE": "nope"}, clear=True):
        with patch("boto3.Session", side_effect=ProfileNotFound(profile="nope")):
            with pytest.raises(OSMCPAuthError, match="AWS profile not found"):
                AwsProvider()


async def test_token_retrieval_failure_is_wrapped(boto_session):
    """An STS failure surfaces as an auth error, not a boto3 exception."""
    boto_session.client.return_value.get_session_token.side_effect = Exception(
        "STS error"
    )

    with patch.dict(os.environ, AWS_ENV, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            provider = AwsProvider()

            with pytest.raises(OSMCPAuthError, match="AWS token retrieval failed"):
                await provider.get_token()


def test_is_discoverable_reports_resolvable_credentials(boto_session):
    """Discovery is true when the boto3 chain resolves credentials."""
    with patch("boto3.Session", return_value=boto_session):
        assert AwsProvider.is_discoverable() is True


def test_is_discoverable_is_false_without_credentials():
    """Discovery is false when the chain yields nothing."""
    empty = MagicMock()
    empty.get_credentials.return_value = None

    with patch("boto3.Session", return_value=empty):
        assert AwsProvider.is_discoverable() is False


def test_is_discoverable_swallows_probe_failures():
    """A raising boto3 is treated as "not discoverable", not as a crash."""
    with patch("boto3.Session", side_effect=Exception("no AWS")):
        assert AwsProvider.is_discoverable() is False


def test_close_releases_the_session(boto_session):
    """Closing drops the boto3 session."""
    with patch.dict(os.environ, AWS_ENV, clear=True):
        with patch("boto3.Session", return_value=boto_session):
            provider = AwsProvider()

    provider.close()

    assert provider._session is None
