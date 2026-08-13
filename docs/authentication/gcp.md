# GCP Authentication

## Method 1: gcloud CLI (Development)

- **Setup**: Run `gcloud auth application-default login`
- **Environment Variables**: None needed! Automatic credential discovery

**Example:**
```bash
gcloud auth application-default login
claude mcp add osdu-mcp-server uvx "git+https://github.com/dan-costello/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition"
```

## Method 2: Service Account Key (Production)

- **Setup**: Download service account JSON key
- **Environment Variables**:
  - `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON key

**Example:**
```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/dan-costello/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
```

## Method 3: Workload Identity (GKE)

- **Setup**: Configure Workload Identity on GKE
- **Environment Variables**: None needed! Automatic credential discovery
- **Note**: Works on GKE with Workload Identity configured

## Scopes

All GCP methods request `cloud-platform` plus the identity scopes `openid` and `userinfo.email` by default. The identity scopes grant no additional access — they make the caller's email address present in the token, which OSDU requires to resolve entitlements. Without them every OSDU request fails with `401 Access denied`.

- `OSDU_MCP_AUTH_SCOPE`: (Optional) Comma-separated list of scopes that replaces the defaults

**Example:**
```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/dan-costello/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "OSDU_MCP_AUTH_SCOPE=https://www.googleapis.com/auth/cloud-platform,openid,https://www.googleapis.com/auth/userinfo.email"
```

## Domain Configuration

OSDU deployments use different data domain formats for Access Control Lists (ACL). See [Domain Configuration](./domain.md) to set `OSDU_MCP_SERVER_DOMAIN` correctly and avoid ACL format errors.

---

Configure your MCP client: [Claude Code](../mcp-usage/claude_code.md) · [Claude Desktop](../mcp-usage/claude_desktop.md) · [VS Code](../mcp-usage/vs_code.md)
