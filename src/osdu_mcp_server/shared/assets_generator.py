"""
Assets generator for dynamic MCP server capability documentation.

Generates comprehensive documentation content that reflects the current
server state and available capabilities.
"""


class AssetsGenerator:
    """Generate dynamic documentation for server capabilities."""

    def __init__(self):
        """Initialize the assets generator."""

    def generate_comprehensive_overview(self) -> str:
        """Generate complete server capabilities overview."""
        sections = [
            self._generate_header(),
            self._generate_server_overview(),
            self._generate_prompts_section(),
            self._generate_tools_section(),
            self._generate_configuration_section(),
            self._generate_workflows_section(),
            self._generate_tips_section(),
            self._generate_footer(),
        ]

        return "\n\n".join(sections)

    def _generate_header(self) -> str:
        """Generate header section."""
        return "# 🚀 OSDU MCP Server Assets"

    def _generate_server_overview(self) -> str:
        """Generate server overview section."""
        return """## 📊 Server Overview

**OSDU MCP Server** provides AI assistants with secure access to OSDU platform capabilities through the Model Context Protocol.

- **Purpose**: Bridge AI assistants to OSDU platform operations
- **Protocol**: Model Context Protocol (MCP) v1.0+
- **Authentication**: Azure DefaultAzureCredential with multiple fallback methods
- **Security**: Write and delete operations protected by default"""

    def _generate_prompts_section(self) -> str:
        """Generate prompts section."""
        return """## 📝 Prompts
Interactive conversation starters and guided workflows:

• **list_mcp_assets** () - Comprehensive overview of all server capabilities
• **guide_search_patterns** () - Search pattern guidance for OSDU operations
• **guide_record_lifecycle** () - Complete record lifecycle workflow from creation to cleanup"""

    def _generate_tools_section(self) -> str:
        """Generate tools documentation section."""
        return """## 🔧 Tools
OSDU platform integration and data management functions:

### Foundation
• **health_check** (include_services, include_auth, include_version_info) - Check OSDU platform connectivity and service health

### Partition Service
• **partition_list** (include_count, detailed) - List all accessible OSDU partitions
• **partition_get** (partition_id, include_sensitive, redact_sensitive_values) - Retrieve configuration for a specific partition
• **partition_create** (partition_id, properties, dry_run) - Create a new partition (write-protected)
• **partition_update** (partition_id, properties, dry_run) - Update partition properties (write-protected)
• **partition_delete** (partition_id, confirm, dry_run) - Delete a partition (delete-protected)

### Entitlements Service
• **entitlements_mine** () - Get groups for the current authenticated user

### Legal Service
• **legaltag_list** (valid_only) - List all legal tags in the current partition
• **legaltag_get** (name) - Retrieve a specific legal tag by name
• **legaltag_get_properties** () - Get allowed values for legal tag properties
• **legaltag_search** (query, valid_only, sort_by, sort_order, limit) - Search legal tags with filter conditions
• **legaltag_batch_retrieve** (names) - Retrieve multiple legal tags by name
• **legaltag_create** (name, description, country_of_origin, contract_id, security_classification, personal_data, export_classification, data_type, expiration_date, extension_properties) - Create a new legal tag (write-protected)
• **legaltag_update** (name, description, contract_id, expiration_date, extension_properties) - Update an existing legal tag (write-protected)
• **legaltag_delete** (name, confirm) - Delete a legal tag (delete-protected)

### Schema Service
• **schema_list** (authority, source, entity, status, scope, latest_version, limit, offset) - List schemas with optional filtering
• **schema_get** (id) - Retrieve complete schema by ID
• **schema_search** (text, search_in, version_pattern, filter, latest_version, limit, offset, include_content, sort_by, sort_order) - Advanced schema discovery with rich filtering and text search
• **schema_create** (authority, source, entity, major_version, minor_version, patch_version, schema, status, description) - Create a new schema (write-protected)
• **schema_update** (id, schema, status) - Update an existing schema (write-protected)

### Search Service
• **search_query** (query, kind, limit, offset) - Execute search queries using Elasticsearch syntax
• **search_by_id** (id, limit) - Find specific records by ID
• **search_by_kind** (kind, limit, offset) - Find all records of specific type

### Storage Service
• **storage_create_update_records** (records, skip_dupes) - Create or update records (write-protected)
• **storage_get_record** (id, attributes) - Get latest version of a record by ID
• **storage_get_record_version** (id, version, attributes) - Get specific version of a record
• **storage_list_record_versions** (id) - List all versions of a record
• **storage_query_records_by_kind** (kind, limit, cursor) - Get record IDs of a specific kind
• **storage_fetch_records** (records, attributes) - Retrieve multiple records at once
• **storage_delete_record** (id) - Logically delete a record (delete-protected)
• **storage_purge_record** (id, confirm) - Permanently delete a record (delete-protected)"""

    def _generate_configuration_section(self) -> str:
        """Generate configuration guidance section."""
        return """## ⚡ Configuration Quick Setup

### Required Environment Variables
```bash
# Core OSDU Configuration
export OSDU_MCP_SERVER_URL="https://your-osdu.com"
export OSDU_MCP_SERVER_DATA_PARTITION="your-partition"

# Authentication (required)
export AZURE_CLIENT_ID="your-client-id"
export AZURE_TENANT_ID="your-tenant-id"

# Optional: Service Principal authentication
export AZURE_CLIENT_SECRET="your-secret"

# Optional: Enable write operations (disabled by default)
export OSDU_MCP_ENABLE_WRITE_MODE="true"

# Optional: Enable delete operations (disabled by default)
export OSDU_MCP_ENABLE_DELETE_MODE="true"

# Optional: Enable logging (disabled by default)
export OSDU_MCP_LOGGING_ENABLED="true"
export OSDU_MCP_LOGGING_LEVEL="INFO"
```

### Authentication Methods
1. **Service Principal**: Provide AZURE_CLIENT_SECRET for automated environments
2. **Managed Identity**: Automatic in Azure-hosted environments (AKS, VM, App Service)
3. **Azure CLI**: Run `az login` for local development
4. **Developer CLI**: Run `azd login` as fallback for local development"""

    def _generate_workflows_section(self) -> str:
        """Generate workflow examples section."""
        return """## 🎯 Quick Start Workflows

### 1. Verify OSDU Connectivity
```
1. Use tool: health_check
   Arguments: include_services=true, include_auth=true
   Result: Comprehensive platform status and service availability
```

### 2. Explore Available Data
```
1. Check partitions: partition_list
   Result: Available data partitions you can access

2. Review legal tags: legaltag_list
   Result: Compliance tags available for data classification

3. Explore schemas: schema_list with scope="SHARED"
   Result: Standard OSDU data schemas available
```

### 3. Query Existing Data
```
1. Find record types: schema_list with authority="osdu"
   Result: Available OSDU standard record types

2. Query records: storage_query_records_by_kind
   Arguments: kind="osdu:wks:dataset--File.Generic:1.0.0"
   Result: Available dataset records

3. Get record details: storage_get_record
   Arguments: id="<record-id>"
   Result: Complete record information
```

### 4. Create New Data (Write Mode Required)
```
1. Enable write mode: Set OSDU_MCP_ENABLE_WRITE_MODE="true"

2. Validate schema: schema_get
   Arguments: id="osdu:wks:dataset--File.Generic:1.0.0"
   Result: Schema requirements for new records

3. Create legal tag: legaltag_create (if needed)
   Arguments: name, description, compliance properties

4. Create record: storage_create_update_records
   Arguments: records with proper ACL, legal, and data sections
```"""

    def _generate_tips_section(self) -> str:
        """Generate pro tips section."""
        return """## 💡 Pro Tips

### Security Best Practices
• **Protection by Default**: Write and delete operations are disabled by default for safety
• **Graduated Permissions**: Enable write mode separately from delete mode for enhanced control
• **Authentication Flexibility**: Supports Service Principal, Managed Identity, Azure CLI, and Developer CLI

### Performance Optimization
• **Selective Health Checks**: Use health_check parameters to avoid timeouts on large deployments
• **Batch Operations**: Use storage_fetch_records for multiple record operations
• **Connection Pooling**: HTTP client automatically pools connections for efficiency
• **Pagination**: Use limit/offset parameters for large result sets

### Common Patterns
• **Start with Health**: Always verify connectivity with health_check before other operations
• **Explore Before Create**: Use list/get operations to understand existing data before creating new records
• **Schema First**: Review schema requirements before creating records to ensure compliance
• **Legal Tag Validation**: Verify legal tags exist and are valid before using in records

### Troubleshooting
• **Authentication Issues**: Use health_check with include_auth=true to validate credentials
• **Permission Errors**: Check OSDU_MCP_ENABLE_WRITE_MODE and OSDU_MCP_ENABLE_DELETE_MODE settings
• **Service Unavailable**: Use health_check with include_services=true to identify specific service issues
• **Schema Validation**: Use schema_get to understand exact requirements for record creation"""

    def _generate_footer(self) -> str:
        """Generate footer section."""
        return """---

**🚀 Ready to explore OSDU data? Start with `health_check` to verify your connection!**

For more information, see the [OSDU MCP Server documentation](https://github.com/dan-costello/osdu-mcp-server)."""
