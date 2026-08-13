# Domain Configuration

Applies to all cloud providers.

**Critical for ACL Format**: OSDU deployments use different data domain formats for Access Control Lists (ACL). Know your data domain before writing records, so you can supply the right ACL groups and avoid ACL format errors.

The server does not configure the domain for you — it is not a setting. It is the value you write into the `acl.viewers` and `acl.owners` entries of a record, in the form `data.default.viewers@{partition}.{domain}`.

**Data Domain Examples:**
- Standard OSDU: `contoso.com`
- Microsoft OSDU: `dataservices.energy`
- Microsoft Internal: `msft-osdu-test.org`

**Data Domain Detection Methods:**
1. **Use Entitlements Tool**: Run `entitlements_mine()` to see your group format
2. **Check with Administrator**: Ask your OSDU administrator for the correct data domain

**Important**: The data domain is the internal OSDU data system domain used in ACL group emails, not the FQDN from your server URL.

For more guidance, use the MCP resource: `ReadMcpResourceTool(server="osdu-wireline", uri="file://acl-format-examples.json")`.

---

Authentication guides: [Azure](./azure.md) · [AWS](./aws.md) · [GCP](./gcp.md) · [Manual OAuth token](./manual_oauth.md)
