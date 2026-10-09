# Azure Authentication

The server supports one authentication method: the OAuth authorization code grant. You sign in as yourself in the browser, and no token ever goes into configuration.

## Setup

- **App registration**: On the OSDU app registration (or a client registration authorized for it):
  - Under **Authentication**, add the **Mobile and desktop applications** platform with the redirect URI `http://localhost`. Entra ignores the port when matching localhost redirects, so an existing `http://localhost:8080` entry works too. The server listens on a free port it picks for each sign-in.
  - Set **Allow public client flows** to **Yes**
- **Environment Variables**:
  - `OSDU_GRANT_TYPE`: `authorization_code`
  - `OSDU_BASE_URL`: Base URL of the OSDU platform
  - `OSDU_PARTITION_ID`: Data partition ID
  - `OSDU_AUTH_CLIENT_ID`: The app registration's client ID
  - `OSDU_AUTH_DISCOVERY_URL`: Your tenant's authority URL, `https://login.microsoftonline.com/<tenant-id>`. For a sovereign cloud, use that cloud's host, e.g. `https://login.microsoftonline.us/<tenant-id>`.
  - `OSDU_AUTH_SCOPE`: The OSDU resource scope, e.g. `<osdu-app-id>/.default`. Required, because the signing-in client (for example the Azure CLI, `04b07795-8ddb-461a-bbee-02f9e1bf7b46`) is often not the OSDU app. If it isn't, that client must be authorized on the OSDU app; see [Authorization Setup](#authorization-setup).

**Example:**
```bash
claude mcp add osdu-wireline uvx --from /path/to/osdu_wireline.whl osdu-wireline \
  -e "OSDU_GRANT_TYPE=authorization_code" \
  -e "OSDU_BASE_URL=https://your-osdu.com" \
  -e "OSDU_PARTITION_ID=your-partition" \
  -e "OSDU_AUTH_CLIENT_ID=your-osdu-app-id" \
  -e "OSDU_AUTH_DISCOVERY_URL=https://login.microsoftonline.com/your-tenant-id" \
  -e "OSDU_AUTH_SCOPE=your-osdu-app-id/.default"
```

**How it works:**
- The first time a tool needs a token, the server opens your default browser to sign in. Finish within 5 minutes. If your MCP client times out that first call while you sign in, retry it.
- MSAL saves the tokens to `~/.osdu-wireline/msal_token_cache.bin`, encrypted by the OS: DPAPI on Windows, Keychain on macOS, libsecret on Linux. Every server instance shares this cache, and MSAL refreshes tokens silently, so later calls and restarts need no browser.
- The browser opens again only when your Entra session ends, for example after a password reset, a revoked session, or a Conditional Access policy asking you to sign in again.
- To switch users, delete the cache file. The next tool call opens the browser.

**Requirements:** The machine running the MCP client needs a browser and an OS keyring. If no encrypted storage is available (for example, Linux without libsecret), the server refuses rather than writing tokens unencrypted.

## Authorization Setup

If `OSDU_AUTH_CLIENT_ID` is the OSDU app itself, no additional setup is needed. If it is another client (for example the Azure CLI), authorize that client on the OSDU app:

1. **Navigate to your OSDU application** in **App registrations**
2. **Go to Expose an API** → **Authorized client applications**
3. **Click Add a client application**
4. **Enter the client ID** of the signing-in client (Azure CLI: `04b07795-8ddb-461a-bbee-02f9e1bf7b46`)
5. **Select the `user_impersonation` scope**
6. **Click Add**

**Common Issues:**
- **"Invalid resource"** or a consent error: the client hasn't been authorized. Follow the setup above, and check `OSDU_AUTH_SCOPE`.
- **"Azure did not recognize the authority"**: check `OSDU_AUTH_DISCOVERY_URL`.

## Domain Configuration

OSDU deployments use different data domain formats for Access Control Lists (ACL). See [Domain Configuration](./domain.md) to determine your data domain and avoid ACL format errors.

---

Configure your MCP client: [Claude Code](../mcp-usage/claude_code.md) · [Claude Desktop](../mcp-usage/claude_desktop.md) · [VS Code](../mcp-usage/vs_code.md)
