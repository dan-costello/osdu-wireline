# Claude Code CLI

> **Note:** All six environment variables below are required. `OSDU_GRANT_TYPE` must be
> exactly `authorization_code`, as shown; every other value is a placeholder to replace
> with your own. See the
> [Azure authentication guide](../authentication/azure.md) for the app registration setup.
>
> On the first tool call the server opens your browser to sign in; after that, tokens
> are cached and later calls and restarts sign in silently.

To add this MCP server using the Claude Code CLI:

```bash
claude mcp add osdu-wireline \
  -e "OSDU_GRANT_TYPE=authorization_code" \
  -e "OSDU_BASE_URL=https://your-osdu.com" \
  -e "OSDU_PARTITION_ID=your-partition" \
  -e "OSDU_AUTH_CLIENT_ID=your-client-id" \
  -e "OSDU_AUTH_DISCOVERY_URL=https://login.microsoftonline.com/your-tenant-id" \
  -e "OSDU_AUTH_SCOPE=your-osdu-app-id/.default" \
  -- uvx --from "git+https://github.com/dan-costello/osdu-wireline@main" osdu-wireline
```
