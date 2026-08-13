# Azure Authentication

## Method 1: Azure CLI (Development)

- **Setup**: Run `az login` before using the server
- **Environment Variables**:
  - `AZURE_CLIENT_ID`: Your OSDU application ID
  - `AZURE_TENANT_ID`: Your Azure tenant ID
  - No `AZURE_CLIENT_SECRET` needed

**Example:**
```bash
az login
claude mcp add osdu-wireline uvx "git+https://github.com/dan-costello/osdu-wireline@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AZURE_CLIENT_ID=your-osdu-app-id" \
  -e "AZURE_TENANT_ID=your-tenant-id"
```

## Method 2: Service Principal (Production)

- **Setup**: Create or use an existing service principal
- **Environment Variables**:
  - `AZURE_CLIENT_ID`: Service principal ID
  - `AZURE_CLIENT_SECRET`: Service principal secret
  - `AZURE_TENANT_ID`: Your Azure tenant ID
  - `OSDU_MCP_AUTH_SCOPE`: (Optional) Custom OAuth scope for v1.0 token environments (this variable has a different meaning on GCP — see [GCP Authentication](./gcp.md))

**Example:**
```bash
claude mcp add osdu-wireline uvx "git+https://github.com/dan-costello/osdu-wireline@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AZURE_CLIENT_ID=your-service-principal-id" \
  -e "AZURE_CLIENT_SECRET=your-service-principal-secret" \
  -e "AZURE_TENANT_ID=your-tenant-id"
```

## Authorization Setup

**When you need additional setup:**
- ✅ **Azure CLI auth**: Always requires authorization setup
- ✅ **External service principal**: Requires authorization setup  
- ❌ **OSDU app's own service principal**: No additional setup needed

**For Azure CLI or External Service Principal:**

1. **Navigate to your OSDU application** in **App registrations**
2. **Go to Expose an API** → **Authorized client applications**
3. **Click Add a client application**
4. **Enter the client ID**:
   - Azure CLI: `04b07795-8ddb-461a-bbee-02f9e1bf7b46`
   - External Service Principal: Your service principal's ID
5. **Select the `user_impersonation` scope**
6. **Click Add**

**Verify authentication:**
```bash
az account get-access-token --resource YOUR_AZURE_CLIENT_ID
```

**Common Issues:**
- **"Application not found"**: Azure CLI app doesn't exist in some tenants. Use service principal instead.
- **"Invalid resource"**: The client hasn't been authorized. Follow authorization setup above.
- **"Authentication failed"**: Verify your client ID matches your OSDU application or service principal.

## Domain Configuration

OSDU deployments use different data domain formats for Access Control Lists (ACL). See [Domain Configuration](./domain.md) to determine your data domain and avoid ACL format errors.

---

Configure your MCP client: [Claude Code](../mcp-usage/claude_code.md) · [Claude Desktop](../mcp-usage/claude_desktop.md) · [VS Code](../mcp-usage/vs_code.md)
