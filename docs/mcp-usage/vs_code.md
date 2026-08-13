# VS Code

> **Note:** `OSDU_MCP_SERVER_URL` and `OSDU_MCP_SERVER_DATA_PARTITION` are always required.
> The remaining environment variables depend on your cloud provider — the example below uses
> Azure.  
> 
> See the auth guide for your provider:  
> [Azure](../authentication/azure.md) · [AWS](../authentication/aws.md) ·
> [GCP](../authentication/gcp.md) · [Manual OAuth token](../authentication/manual_oauth.md)

## Direct Installation

To directly download and install this package from github without setting up a local development environment, you can use the following command:

```json
{
  "mcpServers": {
    "osdu-wireline": {
      "type": "stdio",
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

## Local Development

If you are developing locally and want to test your changes, you can also use the local installation method:
```json
{
  "mcpServers": {
    "osdu-wireline": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "osdu-wireline"],
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
