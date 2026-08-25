"""Authentication for OSDU Wireline.

One provider module per mode, selected by `detect_provider`:

- `user_token`: manual OAuth Bearer token via OSDU_USER_TOKEN
- `azure`: DefaultAzureCredential

AWS and GCP providers were removed: the AWS one returned an STS session token
and sent it as an `Authorization: Bearer` header, which OSDU on AWS does not
accept, and neither was ever exercised against a live platform.
"""

from .base import AuthenticationMode, CredentialProvider, check_credentials
from .registry import detect_provider, get_auth_provider, reset_auth_provider

__all__ = [
    "AuthenticationMode",
    "CredentialProvider",
    "check_credentials",
    "detect_provider",
    "get_auth_provider",
    "reset_auth_provider",
]
