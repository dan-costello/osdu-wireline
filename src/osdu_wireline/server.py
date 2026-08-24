"""MCP server instance for OSDU platform integration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .prompts import guide_record_lifecycle, guide_search_patterns
from .resources import get_workflow_resources
from .shared.auth import reset_auth_provider
from .shared.env import require_env
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
from .tools.search import query_well_trajectories, query_wellbores, query_wells
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
async def app_lifespan(server: FastMCP) -> AsyncGenerator[None]:
    """Release the shared credentials when the server shuts down.

    The provider itself is built lazily on first use, so a process with no
    credentials configured still starts and reports the error per tool call.

    Args:
        server: FastMCP server instance

    Yields:
        Nothing; tools resolve their own dependencies
    """
    try:
        # Nothing to do on startup; tools resolve their own dependencies
        yield None
    finally:
        # Runs on server shutdown
        reset_auth_provider()


def verify_startup() -> None:
    """Fail before serving when required server configuration is missing.

    Credentials are deliberately not checked here. The cloud providers
    re-acquire on expiry, so a running server heals when the operator
    re-authenticates; refusing to start would instead force an MCP client
    restart, and would move the provider's setup guidance out of the tool
    response and into a log file.

    Raises:
        OSMCPConfigError: If required server configuration is missing
    """
    require_env("OSDU_MCP_SERVER_URL")
    require_env("OSDU_MCP_SERVER_DATA_PARTITION")


SERVER_INSTRUCTIONS = """
OSDU Wireline bridges AI assistants to OSDU platform services: partitions, entitlements,
legal tags, schemas, search, and storage.

Start with `health_check` to confirm connectivity and authentication before other operations.

Write operations (create, update) and delete operations (delete, purge) are disabled by
default and must be enabled separately via the OSDU_MCP_ENABLE_WRITE_MODE and
OSDU_MCP_ENABLE_DELETE_MODE environment variables. Calls to protected tools fail with a
permission error until the matching gate is enabled.

Read the `reference://quick-start-workflows.md` resource for common workflows and operational
tips."""


mcp = FastMCP("OSDU Wireline", instructions=SERVER_INSTRUCTIONS, lifespan=app_lifespan)

# Register MCP resources
for resource in get_workflow_resources():
    mcp.add_resource(resource)

# Register prompts
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
mcp.tool()(query_wells)
mcp.tool()(query_well_trajectories)
mcp.tool()(query_wellbores)

# Register storage tools
mcp.tool()(storage_create_update_records)
mcp.tool()(storage_get_record)
mcp.tool()(storage_get_record_version)
mcp.tool()(storage_list_record_versions)
mcp.tool()(storage_query_records_by_kind)
mcp.tool()(storage_fetch_records)
mcp.tool()(storage_delete_record)
mcp.tool()(storage_purge_record)
