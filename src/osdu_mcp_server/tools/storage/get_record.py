"""Tool for getting a record by ID."""

from ...shared.clients.storage_client import StorageClient
from ...shared.exceptions import handle_osdu_exceptions
from ...shared.logging_manager import get_logger

logger = get_logger(__name__)


@handle_osdu_exceptions
async def storage_get_record(id: str, attributes: list[str] | None = None) -> dict:
    """Get the latest version of a record by ID.

    Args:
        id: Required string - Record ID
        attributes: Optional array of strings - Specific data fields to return

    Returns:
        Dictionary containing record information with the structure:
        {
            "success": true,
            "record": {
                "id": str,
                "kind": str,
                "version": int,
                "acl": {...},
                "legal": {...},
                "data": {...},
                "createTime": str,
                "createUser": str,
                ...
            },
            "partition": str
        }
    """
    async with StorageClient() as client:
        # Get the record
        record = await client.get_record(id, attributes)

        # Build response
        logger.info(
            f"Retrieved record {id}",
            extra={
                "record_id": id,
                "operation": "get_record",
                "has_attributes": bool(attributes),
            },
        )

        return {
            "success": True,
            "record": record,
            "partition": client.data_partition,
        }
