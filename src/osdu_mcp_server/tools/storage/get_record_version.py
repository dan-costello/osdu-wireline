"""Tool for getting a specific version of a record."""

from ...shared.clients.storage_client import StorageClient
from ...shared.exceptions import handle_osdu_exceptions
from ...shared.logging_manager import get_logger

logger = get_logger(__name__)


@handle_osdu_exceptions
async def storage_get_record_version(
    id: str, version: int, attributes: list[str] | None = None
) -> dict:
    """Get a specific version of a record by ID.

    Args:
        id: Required string - Record ID
        version: Required integer - Record version
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
        # Get the specific record version
        record = await client.get_record_version(id, version, attributes)

        # Build response
        result = {
            "success": True,
            "record": record,
            "partition": client.data_partition,
        }

        logger.info(
            f"Retrieved record {id} version {version}",
            extra={
                "record_id": id,
                "version": version,
                "operation": "get_record_version",
                "has_attributes": bool(attributes),
            },
        )

        return result
