"""Multi-cloud authentication for OSDU Wireline.

One provider module per mode, selected by `detect_provider`:

- `user_token`: manual OAuth Bearer token via OSDU_MCP_USER_TOKEN
- `azure`: DefaultAzureCredential
- `aws`: boto3 SDK credentials
- `gcp`: Application Default Credentials
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
