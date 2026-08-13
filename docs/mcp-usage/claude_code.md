# Claude Code CLI

> **Note:** `OSDU_MCP_SERVER_URL` and `OSDU_MCP_SERVER_DATA_PARTITION` are always required.
> The remaining environment variables depend on your cloud provider — the example below uses
> Azure. See the auth guide for your provider:
> [Azure](../authentication/azure.md) · [AWS](../authentication/aws.md) ·
> [GCP](../authentication/gcp.md) · [Manual OAuth token](../authentication/manual_oauth.md)

To add this MCP server using the Claude Code CLI:

```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/dan-costello/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AZURE_CLIENT_ID=your-client-id" \
  -e "AZURE_TENANT_ID=your-tenant-id"
```
