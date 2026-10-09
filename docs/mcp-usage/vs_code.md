# VS Code

> **Note:** All six environment variables below are required. `OSDU_GRANT_TYPE` must be
> exactly `authorization_code`, as shown; every other value is a placeholder to replace
> with your own. See the
> [Azure authentication guide](../authentication/azure.md) for the app registration setup.
>
> On the first tool call the server opens your browser to sign in; after that, tokens
> are cached and later calls and restarts sign in silently.

## Direct Installation

To directly download and install this package from github without setting up a local development environment, you can use the following command:

```json
{
  "servers": {
    "osdu-wireline": {
      "type": "stdio",
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

## Local Development

If you are developing locally and want to test your changes, you can also use the local installation method:
```json
{
  "servers": {
    "osdu-wireline": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "osdu-wireline"],
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
