"""OSDU ReservoirDDMS service client."""

import logging
import re
from typing import Any
from urllib.parse import quote

from ..exceptions import OSMCPAPIError, OSMCPValidationError
from ..service_urls import OSMCPService
from .base import OsduClient

logger = logging.getLogger(__name__)


class ReservoirDDMSClient(OsduClient):
    """Client for OSDU Reservoir DDMS operations."""

    service = OSMCPService.RESERVOIRDDMS

    async def search_dataspace(
        self, dataspace: str, *, search_substring: str | None = None
    ) -> dict[str, Any]:
        """Retrieve the resources held in a single dataspace.

        Args:
            dataspace: Dataspace id, e.g. "carl/volve_horizons"
            search_substring: Optional string for filtering the returned
                resources by uri or name

        Raises:
            OSMCPValidationError: If the dataspace does not exist in this partition
            OSMCPAPIError: For API errors
        """
        encoded_name = quote(dataspace, safe="")
        url = f"/dataspaces/{encoded_name}/resources/all"
        logger.debug("Requesting %s", url)

        try:
            resp = await self.get(url)
        except OSMCPAPIError as e:
            if e.status_code == 404:
                await self._raise_if_unknown_dataspace(dataspace, e)
            logger.exception("API error listing resources of dataspace %r", dataspace)
            raise
        logger.debug("Response: %r", resp)

        if not isinstance(resp, list):
            logger.warning("Unexpected response format: %s", type(resp))
            return {"items": [], "totalCount": 0, "error": "Internal error"}

        formatted_items = [
            {"uri": item.get("uri") or "", "name": item.get("name") or ""}
            for item in resp
        ]

        if not search_substring:
            return {"items": formatted_items, "totalCount": len(formatted_items)}

        substring_lower = search_substring.lower()
        filtered_items = [
            i
            for i in formatted_items
            if substring_lower in i["uri"].lower()
            or substring_lower in i["name"].lower()
        ]
        return {"items": filtered_items, "totalCount": len(formatted_items)}

    async def list_dataspaces(
        self, *, search_substring: str | None = None
    ) -> dict[str, Any]:
        """Retrieve a list of dataspaces available under the Reservoir DDMS on this OSDU instance.

        Args:
            search_substring: Optional string for filtering returned dataspace ids

        Raises:
            OSMCPAPIError: For API errors
        """

        try:
            resp = await self.get("/dataspaces")
        except OSMCPAPIError:
            # Not swallowing a 404 here: /dataspaces is a collection endpoint
            # and returns an empty list when there are none, so a 404 means the
            # route itself is wrong and should be visible to the caller.
            logger.exception("API error listing dataspaces")
            raise

        if not isinstance(resp, list):
            logger.warning("Unexpected response format: %s", type(resp))
            return {"dataspaces": [], "totalCount": 0, "error": "Internal error"}

        ids: list[str] = []
        for item in resp:
            match = re.search(r"dataspace\('([^']+)'\)", item.get("uri") or "")
            if match:
                dataspace_id = match.group(1)
                if (
                    not search_substring
                    or search_substring.lower() in dataspace_id.lower()
                ):
                    ids.append(dataspace_id)

        logger.info(f"Retrieved {len(ids)} dataspaces")
        return {"dataspaces": ids, "totalCount": len(ids)}

    async def _raise_if_unknown_dataspace(
        self, dataspace: str, cause: OSMCPAPIError
    ) -> None:
        """Turn a 404 into a validation error when the dataspace truly is absent."""
        try:
            available = await self.list_dataspaces()
        except OSMCPAPIError:
            logger.warning(
                "Could not list dataspaces to check whether %r exists", dataspace
            )
            return

        if dataspace not in available:
            raise OSMCPValidationError(
                f"Dataspace {dataspace!r} not available in this partition. "
                f"Available dataspaces: {available}"
            ) from cause
