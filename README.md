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
   - [Azure Authorization Code](#azure-authorization-code)
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

`OSDU_BASE_URL` and `OSDU_PARTITION_ID` are validated at startup: if either is missing the server
writes the missing variable name to stderr and exits with status 1, rather than starting and
failing every tool call. Your MCP client will report the server as failed to start; the message is
in its server log.

Credentials are deliberately *not* checked at startup, so that signing in again fixes a running
server without restarting your MCP client. Use the `health_check` tool to see the current
authentication status and, when it fails, the reason.

### Connecting to MCP Clients
This server currently uses stdio for communication with MCP clients. Below are examples of how to configure the server for different MCP clients:
 - [Claude Code](./docs/mcp-usage/claude_code.md)
 - [Claude Desktop](./docs/mcp-usage/claude_desktop.md)
 - [VS Code](./docs/mcp-usage/vs_code.md)

## Authentication

The server never accepts a token or a server URL as a tool argument. Both come from its own
environment, so neither passes through the assistant's context, where prompt injection could read
a token or point it at another host.

### Azure Authorization Code

The only supported authentication is the Azure OAuth authorization code grant. Configure:

```
OSDU_GRANT_TYPE=authorization_code
OSDU_BASE_URL=<base_url>
OSDU_PARTITION_ID=<partition>
OSDU_AUTH_CLIENT_ID=<azure_client_id>
OSDU_AUTH_DISCOVERY_URL=https://login.microsoftonline.com/<tenant_id>
OSDU_AUTH_SCOPE=<osdu_app_id>/.default
```

The first time a tool needs a token, the server opens your browser to sign in. MSAL keeps the
tokens in a cache encrypted by the OS, so later calls and restarts sign in silently. No token is
ever put in configuration. See the [Azure guide](./docs/authentication/azure.md) for the app
registration setup.

 - [Azure](./docs/authentication/azure.md)
 - [Domain Configuration](./docs/authentication/domain.md)

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
Typed, domain-specific tools. Each targets a single OSDU kind and returns a
declared set of fields.
- **query_wells**: Find wells by bounding box, country, basin or source
- **query_well_trajectories**: Trajectories for a list of well IDs, a field, or both
- **query_well_logs**: Well logs for a list of well IDs, a field, or both, including the curves each log holds
- **query_well_marker_sets**: Marker sets for a list of well IDs, a field, or both, including the top picks themselves
- **query_seismic_trace_data**: Find seismic trace data by bounding box, country, basin, source or name
- **query_seismic_datasets**: Resolve dataset IDs to their file locations

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

**Server** — `OSDU_BASE_URL` and `OSDU_PARTITION_ID` are required; the server exits at startup
without them.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_BASE_URL` | Yes | — | Base URL of the OSDU platform, e.g. `https://osdu.contoso.com` |
| `OSDU_PARTITION_ID` | Yes | — | Data partition ID, e.g. `opendes` |

**Authentication** — see [Authentication](#authentication).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_GRANT_TYPE` | Yes | — | Must be `authorization_code` |
| `OSDU_AUTH_CLIENT_ID` | Yes | — | Public client app registration ID |
| `OSDU_AUTH_DISCOVERY_URL` | Yes | — | Authority URL, e.g. `https://login.microsoftonline.com/<tenant-id>` |
| `OSDU_AUTH_SCOPE` | Yes | — | OSDU resource scope, e.g. `<osdu-app-id>/.default` |

Settings that configure *this server* rather than the connection (the write and delete gates,
the log level) keep the `OSDU_MCP_` prefix.

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
