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

    def to_spatial_filter(self, field: str) -> dict[str, Any]:
        """Convert the bounding box to a spatial filter dictionary for OSDU Search API.

        `field` is required: geometry lives at a different path per kind
        (`data.SpatialLocation.Wgs84Coordinates` on a well,
        `data.SpatialArea.Wgs84Coordinates` on seismic trace data), and a default
        here would silently filter one kind on another kind's field.
        """
        return {
            "field": field,
            "byBoundingBox": {
                "topLeft": {"lat": self.max_latitude, "lon": self.min_longitude},
                "bottomRight": {"lat": self.min_latitude, "lon": self.max_longitude},
            },
        }


class SearchClient(OsduClient):
    """Client for OSDU Search service operations.

    This client is deliberately a thin transport: it returns the OSDU response
    unchanged. Deciding which fields to ask for and how to shape them is the job
    of the individual MCP tool, which owns a typed model for the kind it queries.
    """

    service = OSMCPService.SEARCH

    async def search_query(
        self,
        *,
        kind: str | list[str],
        returned_fields: list[str],
        query: str = "",
        limit: int = 50,
        offset: int = 0,
        bounding_box: BoundingBox | None = None,
        spatial_field: str | None = None,
    ) -> dict[str, Any]:
        """Execute a search query and return the OSDU response unchanged.

        Arguments are keyword-only so that no caller can search without stating
        both the kind it expects and the fields it intends to read. A
        `bounding_box` must be accompanied by the `spatial_field` its kind stores
        geometry in.
        """
        if not returned_fields:
            returned_fields = []

        if bounding_box and not spatial_field:
            raise ValueError("spatial_field is required when filtering by bounding_box")

        payload: dict[str, Any] = {
            "kind": kind,
            "query": query,
            "limit": limit,
            "offset": offset,
            "returnedFields": returned_fields,
        }
        if bounding_box and spatial_field:
            payload["spatialFilter"] = bounding_box.to_spatial_filter(spatial_field)

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
        return response
