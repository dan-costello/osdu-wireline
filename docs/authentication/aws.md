### AWS Authentication

**Method 1: AWS SSO (Development)**
- **Setup**: Configure AWS SSO and log in
- **Environment Variables**:
  - `AWS_PROFILE`: Your AWS profile name
  - (Other OSDU config as usual)

**Example:**
```bash
aws sso login --profile dev-profile
claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AWS_PROFILE=dev-profile"
```

**Method 2: Access Keys (Production)**
- **Setup**: Obtain AWS access keys
- **Environment Variables**:
  - `AWS_ACCESS_KEY_ID`: Your AWS access key
  - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
  - `AWS_REGION`: AWS region (e.g., us-east-1)

**Example:**
```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/danielscholl-osdu/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE" \
  -e "AWS_SECRET_ACCESS_KEY=your-secret-key" \
  -e "AWS_REGION=us-east-1"
```

**Method 3: IAM Roles (EC2/ECS/Lambda)**
- **Setup**: Assign IAM role to your compute instance
- **Environment Variables**: None needed! Automatic credential discovery
- **Note**: Works on EC2, ECS/Fargate, Lambda with appropriate IAM roles

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