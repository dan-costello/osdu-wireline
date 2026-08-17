"""Manual OAuth Bearer token supplied through OSDU_MCP_USER_TOKEN."""

import logging
import time
from typing import ClassVar

import jwt

from ..env import get_env
from ..exceptions import OSMCPAuthError
from .base import AuthenticationMode

logger = logging.getLogger(__name__)

# Tokens closer than this to expiry still work, but warrant a warning so the
# operator can refresh before a long-running call fails mid-flight.
_EXPIRY_WARNING_SECONDS = 300


class UserTokenProvider:
    """Uses a Bearer token the operator supplies directly.

    The token is validated for shape and expiry on every retrieval, since the
    environment variable can be rotated while the server is running.
    """

    mode: ClassVar[AuthenticationMode] = AuthenticationMode.USER_TOKEN

    def __init__(self) -> None:
        """Initialize the provider."""
        logger.info("Authentication mode: USER_TOKEN (manual Bearer token)")

    async def get_token(self) -> str:
        """Read and validate the token from the environment.

        Returns:
            OAuth Bearer token string, without a "Bearer " prefix

        Raises:
            OSMCPAuthError: If the token is unset, malformed, or expired
        """
        token = get_env("OSDU_MCP_USER_TOKEN")
        if not token:
            raise OSMCPAuthError("USER_TOKEN mode but OSDU_MCP_USER_TOKEN not set")

        _validate_jwt_token(token)
        return token

    def close(self) -> None:
        """No resources to release."""


def _validate_jwt_token(token: str) -> None:
    """Validate JWT format and expiration.

    The signature, audience, and issuer are deliberately not checked: the OAuth
    provider already signed the token and the OSDU platform validates the rest.

    Args:
        token: JWT token to validate

    Raises:
        OSMCPAuthError: If the token is malformed or expired
    """
    try:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,  # Already verified by provider
                "verify_exp": False,  # Checked below so we can warn early
                "verify_aud": False,  # OSDU platform validates
            },
        )
    except jwt.DecodeError as e:
        raise OSMCPAuthError(f"Invalid JWT token format: {e}")

    if "exp" not in payload:
        logger.info("User token validation passed")
        return

    time_remaining = payload["exp"] - time.time()
    if time_remaining < 0:
        raise OSMCPAuthError("Token has expired")
    if time_remaining < _EXPIRY_WARNING_SECONDS:
        logger.warning(f"Token expires in {time_remaining:.0f} seconds")

    logger.info("User token validation passed")
