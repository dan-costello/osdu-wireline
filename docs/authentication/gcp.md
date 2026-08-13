#### GCP Authentication

**Method 1: gcloud CLI (Development)**
- **Setup**: Run `gcloud auth application-default login`
- **Environment Variables**: None needed! Automatic credential discovery

**Example:**
```bash
gcloud auth application-default login
claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition"
```

**Method 2: Service Account Key (Production)**
- **Setup**: Download service account JSON key
- **Environment Variables**:
  - `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON key

**Example:**
```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
```

**Method 3: Workload Identity (GKE)**
- **Setup**: Configure Workload Identity on GKE
- **Environment Variables**: None needed! Automatic credential discovery
- **Note**: Works on GKE with Workload Identity configured

**Scopes**

All GCP methods request `cloud-platform` plus the identity scopes `openid` and `userinfo.email` by default. The identity scopes grant no additional access — they make the caller's email address present in the token, which OSDU requires to resolve entitlements. Without them every OSDU request fails with `401 Access denied`.

- `OSDU_MCP_AUTH_SCOPE`: (Optional) Comma-separated list of scopes that replaces the defaults

**Example:**
```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "OSDU_MCP_AUTH_SCOPE=https://www.googleapis.com/auth/cloud-platform,openid,https://www.googleapis.com/auth/userinfo.email"
```

### Domain Configuration (Azure, AWS, GCP)

**Critical for ACL Format**: OSDU deployments use different data domain formats for Access Control Lists (ACL). Configure your data domain to avoid ACL format errors:

```json
"env": {
  "OSDU_MCP_SERVER_DOMAIN": "contoso.com"
}
```

**Data Domain Examples:**
- Standard OSDU: `contoso.com` (default)
- Microsoft OSDU: `dataservices.energy`
- Microsoft Internal: `msft-osdu-test.org`

**Data Domain Detection Methods:**
1. **Environment Variable** (Recommended): Set `OSDU_MCP_SERVER_DOMAIN`
2. **Use Entitlements Tool**: Run `entitlements_mine()` to see your group format
3. **Check with Administrator**: Ask your OSDU administrator for the correct data domain

**Important**: The data domain is the internal OSDU data system domain used in ACL group emails, not the FQDN from your server URL.

If not set, the server will attempt to extract the domain from your server URL. For more guidance, use the MCP resource: `ReadMcpResourceTool(server="osdu-mcp-server", uri="file://acl-format-examples.json")`.