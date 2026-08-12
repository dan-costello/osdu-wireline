"""Tool for querying records by kind."""

from ...shared.clients.storage_client import StorageClient
from ...shared.exceptions import handle_osdu_exceptions
from ...shared.logging_manager import get_logger

logger = get_logger(__name__)


@handle_osdu_exceptions
async def storage_query_records_by_kind(
    kind: str, limit: int = 10, cursor: str | None = None
) -> dict:
    """Get record IDs of a specific kind.

    Args:
        kind: Required string - Kind to query for
        limit: Optional integer - Maximum number of results (default: 10)
        cursor: Optional string - Cursor for pagination

    Returns:
        Dictionary containing query results with the structure:
        {
            "success": true,
            "cursor": str,
            "results": [
                "record-id-1",
                "record-id-2",
                ...
            ],
            "count": int,
            "partition": str
        }
    """
    async with StorageClient() as client:
        # Query records by kind
        response = await client.query_records_by_kind(kind, limit, cursor)

        # Build response
        result = {
            "success": True,
            "cursor": response.get("cursor"),
            "results": response.get("results", []),
            "count": len(response.get("results", [])),
            "partition": client.data_partition,
        }

        logger.info(
            f"Found {result['count']} records of kind {kind}",
            extra={
                "kind": kind,
                "record_count": result["count"],
                "limit": limit,
                "operation": "query_records_by_kind",
                "has_cursor": bool(cursor),
            },
        )

        return result
