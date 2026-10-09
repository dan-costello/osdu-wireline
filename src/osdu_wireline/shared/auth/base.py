"""Credential provider protocol."""

from enum import Enum
from typing import Protocol, runtime_checkable

from ..exceptions import OSMCPAuthError


#: The only supported OAuth grant, the required value of OSDU_GRANT_TYPE.
class AuthenticationMode(Enum):
    """Supported authentication modes."""

    AUTHORIZATION_CODE = "authorization_code"


@runtime_checkable
class CredentialProvider(Protocol):
    """Supplies OSDU bearer tokens.

    Implementations acquire their credential lazily in ``get_token`` and raise
    OSMCPAuthError with setup instructions when it is missing.
    """

    async def get_token(self) -> str:
        """Return a valid access token, refreshing it when needed.

        Returns:
            Raw access token string, without a "Bearer " prefix
        """
        ...

    def close(self) -> None:
        """Release any credential resources held by this provider."""
        ...


async def check_credentials(provider: CredentialProvider) -> dict[str, str]:
    """Exercise a provider and describe the outcome.

    The provider's own message is carried through on failure: it names the fix
    ("verify OSDU_AUTH_DISCOVERY_URL"), and that guidance is only useful if it
    reaches the caller.

    Args:
        provider: Provider to exercise

    Returns:
        A report naming the grant type, and on failure the guidance the
        provider produced
    """
    report = {"grant_type": AuthenticationMode.AUTHORIZATION_CODE.value}

    try:
        await provider.get_token()
    except OSMCPAuthError as e:
        return {**report, "status": "invalid", "error": str(e)}

    return {**report, "status": "valid"}
