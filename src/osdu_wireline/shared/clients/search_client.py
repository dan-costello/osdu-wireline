"""OSDU Search service client."""

import logging
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..service_urls import OSMCPService
from .base import OsduClient

logger = logging.getLogger(__name__)


class BoundingBox(BaseModel):
    min_latitude: float = Field(ge=-90, le=90)
    max_latitude: float = Field(ge=-90, le=90)
    min_longitude: float = Field(ge=-180, le=180)
    max_longitude: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def _ordered(self) -> "BoundingBox":
        if self.min_latitude > self.max_latitude:
            raise ValueError("min_latitude must be <= max_latitude")
        if self.min_longitude > self.max_longitude:
            raise ValueError("min_longitude must be <= max_longitude")
        return self

    def to_spatial_filter(self) -> dict[str, Any]:
        """Convert the bounding box to a spatial filter dictionary for OSDU Search API."""
        return {
            "field": "data.SpatialLocation.Wgs84Coordinates",
            "byBoundingBox": {
                "topLeft": {"lat": self.max_latitude, "lon": self.min_longitude},
                "bottomRight": {"lat": self.min_latitude, "lon": self.max_longitude},
            },
        }


class SearchClient(OsduClient):
    """Client for OSDU Search service operations."""

    service = OSMCPService.SEARCH

    async def search_query(
        self,
        query: str,
        kind: str = "*:*:*:*",
        limit: int = 50,
        offset: int = 0,
        bounding_box: BoundingBox | None = None,
        returnedFields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute general search query."""
        payload = {"kind": kind, "query": query, "limit": limit, "offset": offset}
        if returnedFields:
            payload["returnedFields"] = returnedFields
        if bounding_box:
            payload["spatialFilter"] = bounding_box.to_spatial_filter()

        logger.info(
            f"Executing search query: {query}",
            extra={
                "query": query,
                "kind": kind,
                "limit": limit,
                "operation": "search_query",
            },
        )

        response = await self.post("/query", json=payload)

        logger.debug(f"Search query response: {response}")
        return self._standardize_response(response, query, returnedFields)

    async def search_by_id(self, record_id: str, limit: int = 10) -> dict[str, Any]:
        """Execute ID-specific search."""
        query = f'id:("{record_id}")'
        payload = {"kind": "*:*:*:*", "query": query, "limit": limit}

        logger.info(
            f"Executing ID search: {record_id}",
            extra={"record_id": record_id, "operation": "search_by_id"},
        )

        response = await self.post("/query", json=payload)
        return self._standardize_response(response, query)

    async def search_by_kind(
        self,
        kind: str,
        limit: int = 100,
        offset: int = 0,
        returnedFields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute kind-specific search."""
        payload = {"kind": kind, "query": "", "limit": limit, "offset": offset}
        if returnedFields:
            payload["returnedFields"] = returnedFields

        logger.info(
            f"Executing kind search: {kind}", {**payload, "operation": "search_by_kind"}
        )

        response = await self.post("/query", json=payload)
        return self._standardize_response(response, f"kind:{kind}", returnedFields)

    def _standardize_response(
        self,
        osdu_response: dict[str, Any],
        query: str,
        returned_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Convert OSDU Search API response to MCP format."""
        returned_fields_set = set(returned_fields or [])

        def _project_result(result: dict[str, Any]) -> dict[str, Any]:
            if not returned_fields_set:
                simplified_result: dict[str, Any] = {
                    "id": result.get("id"),
                    "kind": result.get("kind"),
                    "data": result.get("data", {}),
                    "createTime": result.get("createTime"),
                }
                if "version" in result:
                    simplified_result["version"] = result["version"]
                return simplified_result

            simplified_result = {}
            for field_name in returned_fields_set:
                if field_name in result:
                    simplified_result[field_name] = result[field_name]
                elif field_name == "data" and "data" in result:
                    simplified_result["data"] = result["data"]

            if "id" in result and "id" not in simplified_result:
                simplified_result["id"] = result["id"]

            return simplified_result

        # Filter OSDU response to include only essential fields for AI consumption
        simplified_results = [
            _project_result(result) for result in osdu_response.get("results", [])
        ]

        return {
            "success": True,
            "results": simplified_results,
            "totalCount": osdu_response.get("totalCount", 0),
            "searchMeta": {
                "query_executed": query,
                "execution_time_ms": osdu_response.get("took", 0),
            },
            "partition": self._data_partition,
        }
