# OSDU Wireline

[![CI](https://github.com/dan-costello/osdu-wireline/actions/workflows/ci.yml/badge.svg)](https://github.com/dan-costello/osdu-wireline/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%20|%203.13%20|%203.14-blue)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with ty](https://img.shields.io/badge/type%20checked-ty-261230.svg)](https://github.com/astral-sh/ty)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green)](https://modelcontextprotocol.io)

A Model Context Protocol (MCP) server that provides AI assistants with access to OSDU platform capabilities.

> *An independent project. Not affiliated with, endorsed by, or an official product of The Open Group or the OSDU Forum. OSDU is a trademark of The Open Group.*

## TOC

1. [Purpose](#purpose)
2. [Configuration](#configuration)
   - [Connecting to MCP Clients](#connecting-to-mcp-clients)
3. [Authentication](#authentication)
   - [Authentication Priority](#authentication-priority)
   - [Authentication Methods](#authentication-methods)
4. [Usage](#usage)
    - [Prompts](#prompts)
    - [Resources](#resources)
    - [Tools](#tools)
5. [Environment Variables](#environment-variables)

## Purpose

This server enables AI assistants to interact with OSDU platform services including search, data management, and schema operations through the MCP protocol.  

Forked from [OSDU MCP Server](https://github.com/danielscholl/osdu-mcp-server) to help me learn more about MCP and OSDU in general.

## Configuration

All configuration is supplied through environment variables, set in your MCP client's `env` block.
See [Environment Variables](#environment-variables) for the complete reference.

`OSDU_MCP_SERVER_URL` and `OSDU_MCP_SERVER_DATA_PARTITION` are validated at startup: if either is
missing the server writes the missing variable name to stderr and exits with status 1, rather than
starting and failing every tool call. Your MCP client will report the server as failed to start;
the message is in its server log.

Credentials are deliberately *not* checked at startup, so that re-authenticating (`az login`)
fixes a running server without restarting your MCP client. Use the `health_check` tool to see the current authentication status
and, when it fails, the reason.

### Connecting to MCP Clients
This server currently uses stdio for communication with MCP clients. Below are examples of how to configure the server for different MCP clients:
 - [Claude Code](./docs/mcp-usage/claude_code.md)
 - [Claude Desktop](./docs/mcp-usage/claude_desktop.md)
 - [VS Code](./docs/mcp-usage/vs_code.md)

## Authentication

The server never accepts a token or a server URL as a tool argument. Both come from its own
environment, so neither passes through the assistant's context, where prompt injection could read
a token or point it at another host.

### Authentication Priority

The server detects your authentication provider in this priority order:

1. **Manual Token** (highest priority) - `OSDU_USER_TOKEN`
2. **Azure** - `AZURE_CLIENT_ID` or `AZURE_TENANT_ID`

Azure uses `DefaultAzureCredential`, which covers `az login`, service principal environment
variables, and managed identity. Interactive browser sign-in is excluded: this server speaks
JSON-RPC over stdio, so a credential that wants to print to the console or open a browser cannot
run here.

**AWS and GCP are not supported.** Both providers were removed rather than left in place: the AWS
one returned an STS session token and sent it as an `Authorization: Bearer` header, which OSDU on
AWS does not accept, and neither had ever been exercised against a live platform.

### Authentication Methods
 - [Azure](./docs/authentication/azure.md)
 - [Manual OAuth Token](./docs/authentication/manual_oauth.md)  
 - [Domain Configuration (all providers)](./docs/authentication/domain.md)

## Usage

### Prompts
- **guide_search_patterns**: Search pattern guidance for OSDU operations with Elasticsearch syntax examples
- **guide_record_lifecycle**: Complete record lifecycle workflow, from creation through cleanup

### Resources
- **reference://quick-start-workflows.md**: Common workflows and operational tips
- **reference://acl-format-examples.json**: ACL format examples for different OSDU environments
- **reference://search-query-patterns.json**: Proven search query patterns for record validation
- **template://legal-tag-template.json**: Working legal tag template structure
- **template://processing-parameter-record.json**: Complete record template for ProcessingParameterType

### Tools

#### Foundation
- **health_check**: Check OSDU platform connectivity and service health

#### Partition Service
- **partition_list**: List all accessible OSDU partitions
- **partition_get**: Retrieve configuration for a specific partition
- **partition_create**: Create a new partition (write-protected)
- **partition_update**: Update partition properties (write-protected)
- **partition_delete**: Delete a partition (write-protected)

#### Entitlements Service
- **entitlements_mine**: Get groups for the current authenticated user

#### Legal Service
- **legaltag_list**: List all legal tags
- **legaltag_get**: Get specific legal tag
- **legaltag_get_properties**: Get allowed property values
- **legaltag_search**: Search legal tags with filters
- **legaltag_batch_retrieve**: Get multiple tags at once
- **legaltag_create**: Create new legal tag (write-protected)
- **legaltag_update**: Update legal tag (write-protected)
- **legaltag_delete**: Delete legal tag (delete-protected)

#### Schema Service
- **schema_list**: List available schemas with optional filtering
- **schema_get**: Retrieve complete schema by ID
- **schema_search**: Advanced schema discovery with rich filtering and text search
- **schema_create**: Create a new schema (write-protected)
- **schema_update**: Update an existing schema (write-protected)

#### Search Service
- **search_query**: Execute search queries using Elasticsearch syntax
- **search_by_id**: Find specific records by ID
- **search_by_kind**: Find all records of specific type

#### Storage Service
- **storage_create_update_records**: Create or update records (write-protected)
- **storage_get_record**: Get latest version of a record by ID
- **storage_get_record_version**: Get specific version of a record
- **storage_list_record_versions**: List all versions of a record
- **storage_query_records_by_kind**: Get record IDs of a specific kind
- **storage_fetch_records**: Retrieve multiple records at once
- **storage_delete_record**: Logically delete a record (delete-protected)
- **storage_purge_record**: Permanently delete a record (delete-protected)

## Environment Variables

**Server** — `OSDU_MCP_SERVER_URL` and `OSDU_MCP_SERVER_DATA_PARTITION` are required; the server
raises a configuration error on the first tool call without them.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_SERVER_URL` | Yes | — | Base URL of the OSDU platform, e.g. `https://osdu.contoso.com` |
| `OSDU_DATA_PARTITION` | Yes | — | Data partition ID, e.g. `opendes` |
| `OSDU_TIMEOUT` | No | `30` | HTTP request timeout in seconds |

These five connection and credential variables were previously prefixed `OSDU_MCP_`
(`OSDU_MCP_SERVER_URL`, `OSDU_MCP_SERVER_DATA_PARTITION`, `OSDU_MCP_SERVER_TIMEOUT`,
`OSDU_MCP_USER_TOKEN`, `OSDU_MCP_AUTH_SCOPE`). Those spellings are still accepted, so an
existing configuration keeps working; where both are set the unprefixed name wins. They are
shared with DGI's `dgimcp` OSDU import server, which reads the same variables so that it too
resolves its own credentials. Settings that configure *this server* rather than the connection
(the write and delete gates, the log level) keep the `OSDU_MCP_` prefix.

**Authentication** — the provider is detected from whichever of these is set; see
[Authentication](#authentication) for the priority order and per-provider guides.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_USER_TOKEN` | No | — | OAuth bearer token; selects manual-token mode, which takes priority over Azure |
| `AZURE_CLIENT_ID` | No | — | Azure app registration client ID; required once Azure mode is selected |
| `AZURE_TENANT_ID` | No | — | Azure tenant ID; setting either Azure variable selects Azure mode |
| `AZURE_CLIENT_SECRET` | No | — | Azure client secret, for service principal authentication |
| `OSDU_AUTH_SCOPE` | No | `{AZURE_CLIENT_ID}/.default` | Overrides the OAuth scope requested from Azure |

**Write and delete protection** — the tools marked write-protected and delete-protected above are
disabled by default and must be enabled explicitly. The two gates are separate, so you can allow
data creation and updates while keeping strict control over destructive operations.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_MCP_ENABLE_WRITE_MODE` | No | `false` | Enables create and update operations across all services |
| `OSDU_MCP_ENABLE_DELETE_MODE` | No | `false` | Enables delete and purge operations |

**Logging**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_MCP_LOG_LEVEL` | No | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Applies to this server's own loggers; third-party libraries stay at `INFO`. Logs go to stderr. An unrecognized value falls back to `INFO` rather than failing to start. |

Log lines are plain text on stderr. Operations that carry structured fields print them on an
indented `key=value` continuation line beneath the message, so a line can be read on its own or
grepped by field:

```text
INFO     osdu_wireline.tools.partition.get: Partition get requested
    tool=partition_get action=partition_get_request partition_id=opendes include_sensitive=False

WARNING  osdu_wireline.shared.clients.storage_client: Deleting record
    record_id=opendes:doc:123 operation=delete_record destructive=True
```

Values containing spaces, quotes, or `=` are quoted. For `ERROR` entries the traceback follows the
fields.

Boolean variables accept `true`, `yes`, or `1` (case-insensitive); anything else is false.
