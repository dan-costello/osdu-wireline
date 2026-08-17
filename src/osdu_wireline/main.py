"""Main entry point for OSDU Wireline."""

import sys

from .server import mcp, verify_startup
from .shared.exceptions import OSMCPError


def main() -> None:
    """Validate the environment, then run the MCP server."""
    try:
        verify_startup()
    except OSMCPError as e:
        # stdout carries the MCP protocol on the stdio transport, so diagnostics
        # must go to stderr, where MCP clients surface them in their logs.
        sys.stderr.write(f"{e.error_prefix}: {e}\n")
        raise SystemExit(1) from e

    mcp.run()


if __name__ == "__main__":
    main()
