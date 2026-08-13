"""Tool for getting current user's groups."""

import logging

from ...shared.clients.entitlements_client import EntitlementsClient
from ...shared.exceptions import handle_osdu_exceptions

logger = logging.getLogger(__name__)


@handle_osdu_exceptions
async def entitlements_mine() -> dict:
    """Get groups for the current authenticated user.

    Returns:
        Dictionary containing group information with the following structure:
        {
            "success": bool,
            "groups": [
                {
                    "name": str,
                    "email": str,
                    "description": str
                }
            ],
            "count": int,
            "partition": str
        }
    """
    async with EntitlementsClient() as client:
        # Get current partition
        partition = client.data_partition

        # Get user's groups
        response = await client.get_my_groups()

        # Process response
        groups = response.get("groups", [])

        # Build simplified response
        result = {
            "success": True,
            "groups": groups,
            "count": len(groups),
            "partition": partition,
        }

        logger.info(
            "Retrieved user groups successfully",
            extra={"count": len(groups), "partition": partition},
        )

        return result
