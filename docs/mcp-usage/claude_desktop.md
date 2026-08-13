# Claude Desktop

> **Note:** `OSDU_MCP_SERVER_URL` and `OSDU_MCP_SERVER_DATA_PARTITION` are always required.
> The remaining environment variables depend on your cloud provider — the examples below use
> Azure. See the auth guide for your provider:
> [Azure](../authentication/azure.md) · [AWS](../authentication/aws.md) ·
> [GCP](../authentication/gcp.md) · [Manual OAuth token](../authentication/manual_oauth.md)

Claude Desktop is configured through `claude_desktop_config.json`, which you can open from
**Settings → Developer → Edit Config**. Its location on disk is:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Restart Claude Desktop after editing the file for changes to take effect.

## Direct Installation

To download and run this package from GitHub without setting up a local development environment:

```json
{
  "mcpServers": {
    "osdu-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/dan-costello/osdu-mcp-server@main",
        "osdu-mcp-server"
      ],
      "env": {
        "OSDU_MCP_SERVER_URL": "https://your-osdu.com",
        "OSDU_MCP_SERVER_DATA_PARTITION": "your-partition",
        "AZURE_CLIENT_ID": "your-client-id",
        "AZURE_TENANT_ID": "your-tenant-id"
      }
    }
  }
}
```

## Local Development

If you are developing locally and want to test your changes, point the server at your checkout.
Claude Desktop does not inherit your shell's working directory, so pass `--directory` with an
absolute path:

```json
{
  "mcpServers": {
    "osdu-mcp-server": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/osdu-mcp-server", "osdu-mcp-server"],
      "env": {
        "OSDU_MCP_SERVER_URL": "https://your-osdu.com",
        "OSDU_MCP_SERVER_DATA_PARTITION": "your-partition",
        "AZURE_CLIENT_ID": "your-client-id",
        "AZURE_TENANT_ID": "your-tenant-id"
      }
    }
  }
}
```
