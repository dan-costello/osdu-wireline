# OSDU MCP Server

[![CI](https://github.com/dan-costello/osdu-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/dan-costello/osdu-mcp-server/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%20|%203.13%20|%203.14-blue)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with ty](https://img.shields.io/badge/type%20checked-ty-261230.svg)](https://github.com/astral-sh/ty)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green)](https://modelcontextprotocol.io)

A Model Context Protocol (MCP) server that provides AI assistants with access to OSDU platform capabilities.

## TOC

1. [Purpose](#purpose)
2. [Configuration](#configuration)
   - [Connecting to MCP Clients](#connecting-to-mcp-clients)
3. [Authentication](#authentication)
   - [Authentication Priority](#authentication-priority)
   - [Authentication Methods](#authentication-methods)
4. [Usage](#usage)
    - [Prompts](#prompts)
    - [Tools](#tools)
5. [Write/Delete Protection](#writedelete-protection)
    - [Write Operations](#write-operations)
    - [Delete Operations](#delete-operations)
6. [Logging Configuration](#logging-configuration)

## Purpose

This server enables AI assistants to interact with OSDU platform services including search, data management, and schema operations through the MCP protocol.  

Forked from [OSDU MCP Server](https://github.com/danielscholl-osdu/osdu-mcp-server) to help me learn more about MCP and OSDU in general.

## Configuration

### Connecting to MCP Clients
This server currently uses stdio for communication with MCP clients. Below are examples of how to configure the server for different MCP clients:
 - [Claude Code](./docs/mcp-usage/claude_code.md)
 - [Claude Desktop](./docs/mcp-usage/claude_desktop.md)
 - [VS Code](./docs/mcp-usage/vs_code.md)

## Authentication

### Authentication Priority

The server automatically detects your authentication provider in this priority order:

1. **Manual Token** (highest priority) - `OSDU_MCP_USER_TOKEN`
2. **Azure** - `AZURE_CLIENT_ID` or `AZURE_TENANT_ID`
3. **AWS** (explicit) - `AWS_ACCESS_KEY_ID` or `AWS_PROFILE`
4. **GCP** (explicit) - `GOOGLE_APPLICATION_CREDENTIALS`
5. **AWS** (auto-discovery) - IAM roles, SSO
6. **GCP** (auto-discovery) - gcloud, metadata service

### Authentication Methods
 - [Azure](./docs/authentication/azure.md)
 - [AWS](./docs/authentication/aws.md)
 - [GCP](./docs/authentication/gcp.md)
 - [Manual OAuth Token](./docs/authentication/manual_oauth.md)  
 - [Domain Configuration (all providers)](./docs/authentication/domain.md)

## Usage

### Prompts
- **list_mcp_assets**: Comprehensive overview of all server capabilities with usage examples and quick start guidance
- **guide_search_patterns**: Search pattern guidance for OSDU operations with Elasticsearch syntax examples

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



## Write/Delete Protection

### Write Operations

Write operations (create, update) for any service are disabled by default, you must explicitly enable them:

```json
"env": {
  "OSDU_MCP_ENABLE_WRITE_MODE": "true"
}
```

### Delete Operations

Delete and purge operations are separately controlled and disabled by default:

```json
"env": {
  "OSDU_MCP_ENABLE_DELETE_MODE": "true"
}
```

This dual protection allows you to enable data creation and updates while maintaining strict control over destructive operations.

## Logging Configuration

The MCP server uses structured JSON logging. By default, logging is disabled due to verbosity. You can enable it by setting:

```json
"env": {
  "OSDU_MCP_LOGGING_ENABLED": "true",
  "OSDU_MCP_LOGGING_LEVEL": "INFO" 
}
```

Valid logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL



