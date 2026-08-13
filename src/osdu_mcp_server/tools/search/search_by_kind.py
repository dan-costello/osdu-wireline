"""Find all records of specific type."""

from typing import Any

from ...shared.auth_handler import AuthHandler
from ...shared.clients import SearchClient
from ...shared.config_manager import ConfigManager
from ...shared.exceptions import handle_osdu_exceptions


@handle_osdu_exceptions
async def search_by_kind(
    kind: str,
    limit: int = 100,
    offset: int = 0,
    returnedFields: list[str] | None = None,
) -> dict[str, Any]:
    """Find all records of specific type.

    Args:
        kind: Kind pattern (supports wildcards)
        limit: Maximum results (default: 100, max: 1000)
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
    if not kind:
        raise ValueError("Kind parameter is required")

    if limit > 1000:
        limit = 1000

    config = ConfigManager()
    auth = AuthHandler(config)
    client = SearchClient(config, auth)

    try:
        return await client.search_by_kind(
            kind=kind,
            limit=limit,
            offset=offset,
            returnedFields=returnedFields,
        )
    finally:
        await client.close()
