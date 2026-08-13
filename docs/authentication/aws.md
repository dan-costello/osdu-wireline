# AWS Authentication

## Method 1: AWS SSO (Development)

- **Setup**: Configure AWS SSO and log in
- **Environment Variables**:
  - `AWS_PROFILE`: Your AWS profile name
  - (Other OSDU config as usual)

**Example:**
```bash
aws sso login --profile dev-profile
claude mcp add osdu-mcp-server uvx "git+https://github.com/dan-costello/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AWS_PROFILE=dev-profile"
```

## Method 2: Access Keys (Production)

- **Setup**: Obtain AWS access keys
- **Environment Variables**:
  - `AWS_ACCESS_KEY_ID`: Your AWS access key
  - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
  - `AWS_REGION`: AWS region (e.g., us-east-1)

**Example:**
```bash
claude mcp add osdu-mcp-server uvx "git+https://github.com/dan-costello/osdu-mcp-server@main" \
  -e "OSDU_MCP_SERVER_URL=https://your-osdu.com" \
  -e "OSDU_MCP_SERVER_DATA_PARTITION=your-partition" \
  -e "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE" \
  -e "AWS_SECRET_ACCESS_KEY=your-secret-key" \
  -e "AWS_REGION=us-east-1"
```

## Method 3: IAM Roles (EC2/ECS/Lambda)

- **Setup**: Assign IAM role to your compute instance
- **Environment Variables**: None needed! Automatic credential discovery
- **Note**: Works on EC2, ECS/Fargate, Lambda with appropriate IAM roles

## Domain Configuration

OSDU deployments use different data domain formats for Access Control Lists (ACL). See [Domain Configuration](./domain.md) to set `OSDU_MCP_SERVER_DOMAIN` correctly and avoid ACL format errors.

---

Configure your MCP client: [Claude Code](../mcp-usage/claude_code.md) · [Claude Desktop](../mcp-usage/claude_desktop.md) · [VS Code](../mcp-usage/vs_code.md)
