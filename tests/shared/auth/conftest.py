"""Helpers shared by the per-provider authentication tests."""

import time
from unittest.mock import MagicMock

import jwt
import pytest


def make_jwt(exp: float | None = None) -> str:
    """Build a signed test JWT.

    Args:
        exp: Expiration timestamp, defaulting to one hour from now

    Returns:
        Encoded JWT string
    """
    if exp is None:
        exp = time.time() + 3600

    return jwt.encode({"sub": "test-user", "exp": exp}, "secret", algorithm="HS256")


@pytest.fixture
def boto_session():
    """A boto3 Session mock whose STS client reports a valid identity.

    Returns:
        Mock session instance, with `.client()` returning the STS mock
    """
    session = MagicMock()
    session.get_credentials.return_value = MagicMock()

    sts = MagicMock()
    sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    session.client.return_value = sts

    return session


@pytest.fixture
def gcp_credentials():
    """GCP credentials mock that is already valid and holds a token.

    Returns:
        Mock credentials object
    """
    credentials = MagicMock()
    credentials.valid = True
    credentials.token = "gcp-token"
    return credentials
