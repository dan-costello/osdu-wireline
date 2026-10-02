# Claude Code CLI

> **Note:** All six environment variables below are required. See the
> [Azure authentication guide](../authentication/azure.md) for the app registration setup.

To add this MCP server using the Claude Code CLI:

```bash
claude mcp add osdu-wireline uvx "git+https://github.com/dan-costello/osdu-wireline@main" \
  -e "OSDU_GRANT_TYPE=authorization_code" \
  -e "OSDU_BASE_URL=https://your-osdu.com" \
  -e "OSDU_PARTITION_ID=your-partition" \
  -e "OSDU_AUTH_CLIENT_ID=your-client-id" \
  -e "OSDU_AUTH_DISCOVERY_URL=https://login.microsoftonline.com/your-tenant-id" \
  -e "OSDU_AUTH_SCOPE=your-osdu-app-id/.default"
```
