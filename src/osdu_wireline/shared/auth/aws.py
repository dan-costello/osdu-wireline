"""AWS authentication via the boto3 credential chain.

OSDU on AWS sits behind IAM-authenticated API Gateway, so this provider hands
back an STS session token rather than an OAuth Bearer token.
"""

import asyncio
import logging
from typing import Any, ClassVar

import boto3
from botocore.exceptions import ProfileNotFound

from ..exceptions import OSMCPAuthError
from .base import AuthenticationMode

logger = logging.getLogger(__name__)

_SESSION_DURATION_SECONDS = 3600

_NO_CREDENTIALS_MESSAGE = (
    "AWS credentials not found. "
    "Set up authentication using one of these methods:\n\n"
    "  AWS SSO:\n"
    "    aws sso login --profile <profile-name>\n"
    "    export AWS_PROFILE=<profile-name>\n\n"
    "  Access Keys:\n"
    "    export AWS_ACCESS_KEY_ID=...\n"
    "    export AWS_SECRET_ACCESS_KEY=...\n\n"
    "  For more info: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html"
)


class AwsProvider:
    """Uses boto3's credential chain: env vars, profiles, instance metadata, SSO."""

    mode: ClassVar[AuthenticationMode] = AuthenticationMode.AWS

    def __init__(self) -> None:
        """Open a boto3 session and confirm it resolves to a real identity.

        Raises:
            OSMCPAuthError: If no AWS credentials are available
        """
        try:
            self._session: Any = boto3.Session()
        except ProfileNotFound as e:
            raise OSMCPAuthError(
                f"AWS profile not found: {e}. "
                "Check AWS_PROFILE environment variable or ~/.aws/config"
            )

        if not self._session.get_credentials():
            raise OSMCPAuthError(_NO_CREDENTIALS_MESSAGE)

        identity = self._session.client("sts").get_caller_identity()
        logger.info(
            f"Authentication mode: AWS, account: {identity['Account']}, "
            f"user/role: {identity['Arn']}"
        )

    @classmethod
    def is_discoverable(cls) -> bool:
        """Probe whether boto3 can find credentials without explicit configuration.

        Returns:
            True if the boto3 chain resolves credentials (IAM role, SSO, config file)
        """
        try:
            return bool(boto3.Session().get_credentials())
        except Exception as e:
            logger.debug(f"AWS auto-discovery unavailable: {e}")
            return False

    async def get_token(self) -> str:
        """Return an STS session token.

        Returns:
            Session token string

        Raises:
            OSMCPAuthError: If token retrieval fails
        """
        sts = self._session.client("sts")

        try:
            # boto3 is synchronous, so keep it off the event loop
            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: sts.get_session_token(
                    DurationSeconds=_SESSION_DURATION_SECONDS
                ),
            )
        except Exception as e:
            raise OSMCPAuthError(f"AWS token retrieval failed: {e}")

        logger.info("AWS session token obtained successfully")
        return str(response["Credentials"]["SessionToken"])

    def close(self) -> None:
        """Drop the boto3 session (it holds no OS resources of its own)."""
        self._session = None
