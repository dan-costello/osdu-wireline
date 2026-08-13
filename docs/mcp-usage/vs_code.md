### Direct Installation

To directly download and install this package from github without setting up a local development environment, you can use the following command:

```json
{
  "mcpServers": {
    "osdu-mcp-server": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://https://github.com/dan-costello/osdu-mcp-server@main",
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

### Local Development

If you are developing locally and want to test your changes, you can also use the local installation method:
```json
{
  "mcpServers": {
    "osdu-mcp-server": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "osdu-mcp-server"],
      "env": {
        "OSDU_MCP_SERVER_URL": "https://your-osdu.com",
        "OSDU_MCP_SERVER_DATA_PARTITION": "your-partition",
        "AZURE_CLIENT_ID": "your-client-id",
        "AZURE_TENANT_ID": "your-tenant"
      }
    }
  }
}
```