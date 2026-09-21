"""OSDU ReservoirDDMS service client."""

import logging
import re
from typing import Any, cast
from urllib.parse import quote

from ..exceptions import OSMCPAPIError
from ..service_urls import OSMCPService
from .base import OsduClient

logger = logging.getLogger(__name__)


class ReservoirDDMSClient(OsduClient):
    """Client for OSDU Reservoir DDMS operations."""

    service = OSMCPService.RESERVOIRDDMS

    async def search_dataspace(
        self, dataspace: str, search_substring: str | None = None
    ) -> list[dict[str, Any]]:
        all_dataspaces = await self.list_dataspaces()

        if dataspace not in all_dataspaces:
            raise ValueError(
                f"Requested dataspace not available in this partition. Available dataspaces: {all_dataspaces}"
            )

        try:
            encoded_name = quote(dataspace, safe="")
            url = f"/dataspaces/{encoded_name}/resources/all"
            logger.debug("Requesting %s", url)
            resp = await self.get(url)
            logger.debug("Response: %r", resp)
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
        formatted_items = [
            {"uri": i.get("uri", ""), "name": i.get("name", "")} for i in items
        ]

        if not search_substring:
            return formatted_items

        return [
            i
            for i in formatted_items
            if (
                search_substring.lower() in i.get("uri", "").lower()
                or search_substring.lower() in i.get("name", "").lower()
            )
        ]

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
