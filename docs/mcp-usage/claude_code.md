### Claude Code CLI

To add this MCP server using the Claude Code CLI:

```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AZURE_CLIENT_ID=your-client-id" \
  -e "AZURE_TENANT_ID=your-tenant-id"
```