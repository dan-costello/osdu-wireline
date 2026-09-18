"""OSDU ReservoirDDMS service client."""

import logging
import re
from typing import Any, cast

from ..exceptions import OSMCPAPIError
from ..service_urls import OSMCPService
from .base import OsduClient

logger = logging.getLogger(__name__)


class ReservoirDDMSClient(OsduClient):
    """Client for OSDU Reservoir DDMS operations."""

    service = OSMCPService.RESERVOIRDDMS

    async def list_dataspaces(
        self, *, search_substring: str | None = None
    ) -> list[str]:
        """Retrieve a list of dataspaces available under the Reservoir DDMS on this OSDU instance.

        Args:
            search_substring: Optional string for filtering returned dataspace ides
        """

        try:
            resp = await self.get("/dataspaces")
        except OSMCPAPIError as e:
            if e.status_code == 404:
                logger.info("No dataspaces found")
                return []
            logger.exception("API error listing dataspaces")
            raise

        if not isinstance(resp, list):
            logger.warning(f"Unexpected response format: {type(resp)}")
            return []

        items = cast("list[dict[str, Any]]", resp)

        ids: list[str] = []
        for item in items:
            match = re.search(r"dataspace\('([^']+)'\)", item.get("uri", ""))
            if match:
                dataspace_id = match.group(1)
                if (
                    not search_substring
                    or search_substring.lower() in dataspace_id.lower()
                ):
                    ids.append(dataspace_id)

        logger.info(f"Retrieved {len(ids)} dataspaces")
        return ids
