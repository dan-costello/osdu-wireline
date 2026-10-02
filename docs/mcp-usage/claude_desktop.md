# Claude Desktop

> **Note:** All six environment variables below are required. See the
> [Azure authentication guide](../authentication/azure.md) for the app registration setup.

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
        "OSDU_GRANT_TYPE": "authorization_code",
        "OSDU_BASE_URL": "https://your-osdu.com",
        "OSDU_PARTITION_ID": "your-partition",
        "OSDU_AUTH_CLIENT_ID": "your-client-id",
        "OSDU_AUTH_DISCOVERY_URL": "https://login.microsoftonline.com/your-tenant-id",
        "OSDU_AUTH_SCOPE": "your-osdu-app-id/.default"
      }
    }
  }
}
```

Restart Claude Desktop after editing the file for changes to take effect.
