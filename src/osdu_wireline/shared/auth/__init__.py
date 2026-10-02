"""Authentication for OSDU Wireline.

The only supported grant is Azure authorization code: the user signs in
through the system browser and MSAL keeps the tokens in an OS-encrypted cache.
OSDU_GRANT_TYPE must be set to `authorization_code`.
"""

from .base import CredentialProvider, check_credentials
from .registry import get_auth_provider, reset_auth_provider

__all__ = [
    "CredentialProvider",
    "check_credentials",
    "get_auth_provider",
    "reset_auth_provider",
]
