"""OSDU Search service client."""

from typing import Any

from ..logging_manager import get_logger
from ..osdu_client import OsduClient
from ..service_urls import OSMCPService, get_service_base_url

logger = get_logger(__name__)


class SearchClient(OsduClient):
    """Client for OSDU Search service operations."""

    def __init__(self, *args, **kwargs):
        """Initialize SearchClient with service-specific configuration."""
        super().__init__(*args, **kwargs)
        self._base_path = get_service_base_url(OSMCPService.SEARCH)

    async def post(self, path: str, data: Any = None, **kwargs: Any) -> dict[str, Any]:
        """Override post to include service base path."""
        full_path = f"{self._base_path}{path}"
        if data is None and "json" in kwargs:
            data = kwargs.pop("json")
        return await super().post(full_path, data, **kwargs)

    async def search_query(
        self,
        query: str,
        kind: str = "*:*:*:*",
        limit: int = 50,
        offset: int = 0,
        returnedFields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute general search query."""
        payload = {"kind": kind, "query": query, "limit": limit, "offset": offset}
        if returnedFields:
            payload["returnedFields"] = returnedFields

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
                simplified_result = {
                    "id": result.get("id"),
                    "kind": result.get("kind"),
                    "data": result.get("data", {}),
                    "createTime": result.get("createTime"),
                }
                if "version" in result:
                    simplified_result["version"] = result["version"]
                return simplified_result

            simplified_result: dict[str, Any] = {}
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
