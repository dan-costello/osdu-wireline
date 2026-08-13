# Quick Start Workflows

Common OSDU Wireline workflows and operational tips. Tool signatures come from `tools/list`;
this document covers the order to call them in and why.

## 1. Verify OSDU Connectivity

```
1. Use tool: health_check
   Arguments: include_services=true, include_auth=true
   Result: Comprehensive platform status and service availability
```

## 2. Explore Available Data

```
1. Check partitions: partition_list
   Result: Available data partitions you can access

2. Review legal tags: legaltag_list
   Result: Compliance tags available for data classification

3. Explore schemas: schema_list with scope="SHARED"
   Result: Standard OSDU data schemas available
```

## 3. Query Existing Data

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

See `reference://search-query-patterns.json` for proven query patterns, or invoke the
`guide_search_patterns` prompt for Elasticsearch syntax guidance.

## 4. Create New Data (Write Mode Required)

```
1. Enable write mode: Set OSDU_MCP_ENABLE_WRITE_MODE="true"

2. Validate schema: schema_get
   Arguments: id="osdu:wks:dataset--File.Generic:1.0.0"
   Result: Schema requirements for new records

3. Create legal tag: legaltag_create (if needed)
   Arguments: name, description, compliance properties

4. Create record: storage_create_update_records
   Arguments: records with proper ACL, legal, and data sections
```

Working starting points: `template://legal-tag-template.json`,
`template://processing-parameter-record.json`, and `reference://acl-format-examples.json` for
per-environment ACL formats. The `guide_record_lifecycle` prompt walks the full
create-to-cleanup workflow in detail.

## Pro Tips

### Security Best Practices

- **Protection by default**: write and delete operations are disabled unless explicitly enabled
- **Graduated permissions**: `OSDU_MCP_ENABLE_WRITE_MODE` and `OSDU_MCP_ENABLE_DELETE_MODE` are
  separate gates, so creates and updates can be allowed while destructive operations stay closed
- **Authentication**: the provider is auto-detected from the environment; see the project README
  for the supported providers and their priority order

### Performance Optimization

- **Selective health checks**: use `health_check` parameters to avoid timeouts on large deployments
- **Batch operations**: use `storage_fetch_records` for multiple record retrievals
- **Connection pooling**: the HTTP client pools connections automatically
- **Pagination**: use limit/offset parameters for large result sets

### Common Patterns

- **Start with health**: verify connectivity with `health_check` before other operations
- **Explore before create**: use list/get operations to understand existing data first
- **Schema first**: review schema requirements before creating records to ensure compliance
- **Legal tag validation**: verify legal tags exist and are valid before using them in records

### Troubleshooting

- **Authentication issues**: `health_check` with `include_auth=true` validates credentials
- **Permission errors**: check `OSDU_MCP_ENABLE_WRITE_MODE` and `OSDU_MCP_ENABLE_DELETE_MODE`
- **Service unavailable**: `health_check` with `include_services=true` identifies the failing service
- **Schema validation**: `schema_get` gives the exact requirements for record creation
