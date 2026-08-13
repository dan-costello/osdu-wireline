# Domain Configuration

Applies to all cloud providers.

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

---

Authentication guides: [Azure](./azure.md) · [AWS](./aws.md) · [GCP](./gcp.md) · [Manual OAuth token](./manual_oauth.md)
