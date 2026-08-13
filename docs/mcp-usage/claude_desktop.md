# Claude Desktop

> **Note:** `OSDU_MCP_SERVER_URL` and `OSDU_MCP_SERVER_DATA_PARTITION` are always required.
> The remaining environment variables depend on your cloud provider — the example below uses
> Azure.  
> 
> See the auth guide for your provider:  
> [Azure](../authentication/azure.md) · [AWS](../authentication/aws.md) ·
> [GCP](../authentication/gcp.md) · [Manual OAuth token](../authentication/manual_oauth.md)

Claude Desktop is configured through `claude_desktop_config.json`, which you can open from
**Settings → Developer → Edit Config**. 

Open the .json file in the folder that opens, and add an entry to the mcpServers config.

```json
{
  "mcpServers": {
    "osdu-wireline": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/dan-costello/osdu-wireline@main",
        "osdu-wireline"
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

Restart Claude Desktop after editing the file for changes to take effect.
