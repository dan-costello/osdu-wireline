"""Credential provider protocol shared by every authentication mode.

Each supported cloud gets its own provider module implementing this protocol,
so a mode's initialization, token retrieval, and cleanup all live together.
"""

from enum import Enum
from typing import ClassVar, Protocol, runtime_checkable

from ..exceptions import OSMCPAuthError


class AuthenticationMode(Enum):
    """Supported authentication modes."""

    USER_TOKEN = "user_token"  # noqa: S105 - enum value, not a credential
    AZURE = "azure"  # Azure DefaultAzureCredential


@runtime_checkable
class CredentialProvider(Protocol):
    """Supplies OSDU bearer tokens for one authentication mode.

    Implementations acquire their credential in ``__init__`` and raise
    OSMCPAuthError with mode-specific setup instructions when it is missing.
    """

    #: Mode this provider implements, used for logging and diagnostics.
    mode: ClassVar[AuthenticationMode]

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

    The provider's own message is carried through on failure: each mode raises
    guidance naming the fix ("run 'az login'", "gcloud auth application-default
    login"), and that guidance is only useful if it reaches the caller.

    Args:
        provider: Provider to exercise

    Returns:
        A report naming the authentication mode, and on failure the guidance
        the provider produced
    """
    report = {"mode": provider.mode.value}

    try:
        await provider.get_token()
    except OSMCPAuthError as e:
        return {**report, "status": "invalid", "error": str(e)}

    return {**report, "status": "valid"}
