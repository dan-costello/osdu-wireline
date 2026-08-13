#### Manual OAuth Token (Any Provider)

**Use Case**: Custom OAuth providers, testing, or unsupported clouds

- **Setup**: Obtain OAuth Bearer token from your provider
- **Environment Variables**:
  - `OSDU_MCP_USER_TOKEN`: Your OAuth Bearer token (JWT format)
  - **Priority**: This method ALWAYS takes precedence over all others

**Example:**
```bash
# Obtain token from your OAuth provider
TOKEN=$(your-oauth-command)

claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "OSDU_MCP_USER_TOKEN=$TOKEN"
```

**Token Requirements:**
- Valid JWT format (header.payload.signature)
- Not expired
- Server warns if token expires within 5 minutes

**Security Notes:**
- Tokens are validated for format and expiration
- Tokens are never logged
- Tokens must be refreshed manually when they expire