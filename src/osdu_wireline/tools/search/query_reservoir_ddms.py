"""Search OSDU Reservoir DDMS for 3d and 2d grid data"""

from typing import Any

from ...shared.clients import ReservoirDDMSClient
from ...shared.exceptions import handle_osdu_exceptions


@handle_osdu_exceptions
async def query_available_dataspaces(name_pattern: str | None = None) -> dict[str, Any]:
    """Search the OSDU Reservoir DDMS for the list of available dataspaces. These are commonly named for a user, geographic area, or project name.

    Args:
        name_pattern (str | None): A name to search for. Can be a partial match. Optional - if omitted, returns full list of dataspaces.

    """
    async with ReservoirDDMSClient() as client:
        return await client.list_dataspaces(search_substring=name_pattern)


@handle_osdu_exceptions
async def query_dataspace_files(
    dataspace_name: str, item_pattern: str | None = None
) -> dict[str, Any]:
    """Search a specific dataspace for an object whose name or uid matches a pattern.

    Args:
        dataspace_name (str): Which dataspace to search. Use query_available_dataspaces to get list of available dataspaces.
        item_pattern (str | None): substring to search for in item name or URI.
    """
    async with ReservoirDDMSClient() as client:
        return await client.search_dataspace(
            dataspace_name, search_substring=item_pattern
        )
