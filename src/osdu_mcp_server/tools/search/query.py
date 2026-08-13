"""Execute search queries using Elasticsearch syntax."""

from typing import Any

from ...shared.clients import SearchClient
from ...shared.exceptions import handle_osdu_exceptions


@handle_osdu_exceptions
async def search_query(
    query: str,
    kind: str = "*:*:*:*",
    limit: int = 50,
    offset: int = 0,
    returnedFields: list[str] | None = None,
) -> dict[str, Any]:
    """Execute search queries using Elasticsearch syntax.

    Args:
        query: Elasticsearch query syntax
        kind: Kind pattern to search (default: "*:*:*:*")
        limit: Maximum results (default: 50, max: 1000)
        offset: Pagination offset (default: 0)
        returnedFields: Optional list of fields to return from the search API

    Returns:
        Dictionary containing search results with the following structure:
        {
            "success": true,
            "results": [
                {
                    "id": str,
                    "kind": str,
                    "data": {...},
                    "createTime": str,
                    "version": int (optional)
                }
            ],
            "totalCount": int,
            "searchMeta": {
                "query_executed": str,
                "execution_time_ms": int
            },
            "partition": str
        }
    """
    # Validate parameters
    if not query:
        raise ValueError("Query parameter is required")

    if limit > 1000:
        limit = 1000

    async with SearchClient() as client:
        result = await client.search_query(
            query=query,
            kind=kind,
            limit=limit,
            offset=offset,
            returnedFields=returnedFields,
        )
        return result
