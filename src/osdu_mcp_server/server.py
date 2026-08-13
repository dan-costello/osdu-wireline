"""MCP server instance for OSDU platform integration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .prompts import guide_record_lifecycle, guide_search_patterns, list_mcp_assets
from .resources import get_workflow_resources
from .shared.app_context import (
    AppContext,
    create_app_context,
    set_app_context,
)
from .tools.entitlements import (
    entitlements_mine,
)
from .tools.health_check import health_check
from .tools.legal import (
    legaltag_batch_retrieve,
    legaltag_create,
    legaltag_delete,
    legaltag_get,
    legaltag_get_properties,
    legaltag_list,
    legaltag_search,
    legaltag_update,
)
from .tools.partition import (
    partition_create,
    partition_delete,
    partition_get,
    partition_list,
    partition_update,
)
from .tools.schema import (
    schema_create,
    schema_get,
    schema_list,
    schema_search,
    schema_update,
)
from .tools.search import (
    search_by_id,
    search_by_kind,
    search_query,
)
from .tools.storage import (
    storage_create_update_records,
    storage_delete_record,
    storage_fetch_records,
    storage_get_record,
    storage_get_record_version,
    storage_list_record_versions,
    storage_purge_record,
    storage_query_records_by_kind,
)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Construct shared config and auth once per server process.

    Args:
        server: FastMCP server instance

    Yields:
        Application context shared by all tool invocations
    """
    context = create_app_context()
    set_app_context(context)

    try:
        yield context
    finally:
        set_app_context(None)
        context.close()


# Create FastMCP server instance
mcp = FastMCP("OSDU MCP Server", lifespan=app_lifespan)

# Register MCP resources
for resource in get_workflow_resources():
    mcp.add_resource(resource)

# Register prompts
mcp.prompt()(list_mcp_assets)
mcp.prompt()(guide_search_patterns)
mcp.prompt()(guide_record_lifecycle)

# Register tools
mcp.tool()(health_check)

# Register partition tools
mcp.tool()(partition_list)
mcp.tool()(partition_get)
mcp.tool()(partition_create)
mcp.tool()(partition_update)
mcp.tool()(partition_delete)

# Register entitlements tools
mcp.tool()(entitlements_mine)

# Register legal tools
mcp.tool()(legaltag_list)
mcp.tool()(legaltag_get)
mcp.tool()(legaltag_get_properties)
mcp.tool()(legaltag_search)
mcp.tool()(legaltag_batch_retrieve)
mcp.tool()(legaltag_create)
mcp.tool()(legaltag_update)
mcp.tool()(legaltag_delete)

# Register schema tools
mcp.tool()(schema_list)
mcp.tool()(schema_get)
mcp.tool()(schema_search)
mcp.tool()(schema_create)
mcp.tool()(schema_update)

# Register search tools
mcp.tool()(search_query)
mcp.tool()(search_by_id)
mcp.tool()(search_by_kind)

# Register storage tools
mcp.tool()(storage_create_update_records)
mcp.tool()(storage_get_record)
mcp.tool()(storage_get_record_version)
mcp.tool()(storage_list_record_versions)
mcp.tool()(storage_query_records_by_kind)
mcp.tool()(storage_fetch_records)
mcp.tool()(storage_delete_record)
mcp.tool()(storage_purge_record)
