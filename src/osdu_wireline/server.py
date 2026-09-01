"""MCP server instance for OSDU platform integration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .prompts import guide_record_lifecycle, guide_search_patterns
from .resources import get_workflow_resources
from .shared.auth import reset_auth_provider
from .shared.env import require_setting
from .tools.health_check import health_check
from .tools.search import (
    query_seismic_datasets,
    query_seismic_trace_data,
    query_well_logs,
    query_well_marker_sets,
    query_well_trajectories,
    query_wells,
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
    require_setting("OSDU_SERVER_URL")
    require_setting("OSDU_DATA_PARTITION")


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


# Register search tools
mcp.tool()(query_wells)
mcp.tool()(query_well_trajectories)
mcp.tool()(query_well_logs)
mcp.tool()(query_well_marker_sets)
mcp.tool()(query_seismic_trace_data)
mcp.tool()(query_seismic_datasets)
