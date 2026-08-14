"""Tool for advanced schema discovery with rich filtering and text search."""

import fnmatch
import logging

from ...shared.clients.schema_client import SchemaClient
from ...shared.exceptions import handle_osdu_exceptions

logger = logging.getLogger(__name__)

# Filter keys that map onto the schema identity and can be server-side filtered
_IDENTITY_FILTER_KEYS = ("authority", "source", "entity", "status", "scope")


@handle_osdu_exceptions
async def schema_search(
    # Text search parameters
    text: str | None = None,
    search_in: list[str] | None = None,
    # Version filtering
    version_pattern: str | None = None,
    # Rich filtering
    filter: dict[str, str | list[str]] | None = None,
    # Common parameters
    latest_version: bool = False,
    limit: int = 100,
    offset: int = 0,
    # Advanced options
    include_content: bool = False,
    sort_by: str = "dateCreated",
    sort_order: str = "DESC",
) -> dict:
    """Advanced schema discovery with rich filtering and text search.

    Args:
        text (str, optional): Text to search across schema content. Example: "pressure"
        search_in (List[str], optional): Fields to search in. Default: ["title", "description", "properties"]
        version_pattern (str, optional): Version with wildcard support. Examples: "1.1.0", "1.*.*"
        filter (Dict, optional): Key-value filter criteria. Keys include:
            - authority: Schema authority (str or List[str]). Example: "osdu" or ["osdu", "lab"]
            - source: Schema source (str or List[str]). Example: "wks"
            - entity: Entity type (str or List[str]). Example: "wellbore"
            - status: Schema status (str or List[str]). Example: "PUBLISHED" or ["PUBLISHED", "DEVELOPMENT"]
            - scope: Schema scope (str or List[str]). Example: "SHARED" or "INTERNAL"
        latest_version (bool, optional): Only return latest versions. Default: False
        limit (int, optional): Maximum results to return. Range: 1-1000. Default: 100
        offset (int, optional): Pagination offset. Default: 0
        include_content (bool, optional): Include full schema content. Default: False
        sort_by (str, optional): Field to sort by. Options: "dateCreated", "authority", "source", "entityType", "status", "scope", "id". Default: "dateCreated"
        sort_order (str, optional): Sort direction. Options: "ASC", "DESC". Default: "DESC"

    Returns:
        Dict: Search results containing:
            - success (bool): Operation success status
            - schemas (List[Dict]): Matching schemas
            - count (int): Number of returned schemas
            - totalCount (int): Total schemas in repository
            - offset (int): Current pagination offset
            - partition (str): Current data partition
            - filteredCount (int): Number of schemas after filtering
            - query (str): Original text query if provided

    Example Usage:
        # Find schemas with version 1.1.0
        schema_search(version_pattern="1.1.0")

        # Find schemas about pressure in SHARED scope
        schema_search(
            text="pressure",
            filter={"scope": "SHARED"}
        )

        # Find schemas from multiple authorities
        schema_search(
            filter={
                "authority": ["osdu", "lab"],
                "status": "PUBLISHED"
            }
        )

        # Find schemas with 1.1.* versions across all scopes
        schema_search(
            version_pattern="1.1.*",
            filter={"scope": ["SHARED", "INTERNAL"]},
            limit=200
        )
    """
    # Default search fields if not provided
    if search_in is None:
        search_in = ["title", "description", "properties"]

    # Initialize filter if not provided
    filter = filter or {}

    # Analyze what can be server-side filtered
    server_filters = _extract_server_filters(filter)

    async with SchemaClient() as client:
        # Get current partition
        partition = client.data_partition

        # Collect filters that need client-side processing
        # These include array filters and other advanced criteria
        client_filters = {
            key: value
            for key, value in filter.items()
            if (key in _IDENTITY_FILTER_KEYS and isinstance(value, list))
            or key not in _IDENTITY_FILTER_KEYS
        }

        # Apply server-side filtering through the API
        logger.info(f"Executing schema list with server filters: {server_filters}")
        api_limit = min(1000, limit * 2)  # Request more to account for client filtering

        try:
            # Make API request with server-side filters using search_schemas which internally redirects
            # to list_schemas with the appropriate parameters - this ensures forward compatibility
            # if a dedicated search endpoint is added in the future
            response, schemas = await _fetch_schemas(
                client, server_filters, latest_version, api_limit, offset
            )
            logger.info(f"Retrieved {len(schemas)} schemas from API response")

        except Exception as e:
            logger.exception("Error during schema search")
            return {
                "success": False,
                "error": f"Failed to retrieve schemas: {e!s}",
                "partition": partition,
            }

        total_count = response.get("totalCount", len(schemas))

        logger.info(
            f"Retrieved {len(schemas)} schemas from server, applying client-side filtering"
        )

        # Apply client-side filtering, text search, and content enrichment
        filtered_schemas = await _filter_and_enrich_schemas(
            schemas,
            client_filters,
            version_pattern,
            text,
            search_in,
            include_content,
            client,
        )

        # Apply sorting if needed
        if sort_by:
            filtered_schemas = _sort_schemas(filtered_schemas, sort_by, sort_order)

        # Apply pagination
        start_idx = 0
        end_idx = min(limit, len(filtered_schemas))
        paginated_schemas = filtered_schemas[start_idx:end_idx]

        # Build response
        logger.info(
            "Schema search completed successfully",
            extra={
                "requested": api_limit,
                "retrieved": len(schemas),
                "filtered": len(filtered_schemas),
                "returned": len(paginated_schemas),
            },
        )

        return {
            "success": True,
            "schemas": paginated_schemas,
            "count": len(paginated_schemas),
            "totalCount": total_count,  # Note: This is approximate due to client filtering
            "offset": offset,
            "partition": partition,
            "filteredCount": len(filtered_schemas),  # Additional info for transparency
            "query": text or None,  # Include search query for reference
        }


def _extract_server_filters(
    filter: dict[str, str | list[str]],
) -> dict[str, list[str]]:
    """Build server-side filter criteria from string-valued identity filter keys."""
    key_mapping = {
        "authority": "authority",
        "source": "source",
        "entity": "entityType",
        "status": "status",
        "scope": "scope",
    }
    server_filters: dict[str, list[str]] = {}
    for filter_key, api_key in key_mapping.items():
        value = filter.get(filter_key)
        if isinstance(value, str):
            server_filters[api_key] = [value]
    return server_filters


async def _fetch_schemas(
    client: SchemaClient,
    server_filters: dict[str, list[str]],
    latest_version: bool,
    api_limit: int,
    offset: int,
) -> tuple[dict, list[dict]]:
    """Call the API and extract the schema list from the response."""
    response = await client.search_schemas(
        filter_criteria=server_filters,
        latest_version=latest_version,
        limit=api_limit,
        offset=offset,
    )
    # Extract schemas from response - API returns "schemaInfos" but we map to "schemas" for consistency
    schemas = response.get("schemaInfos", [])
    if not schemas:
        # Fallback - though schemaInfos is the expected field name from the API
        schemas = response.get("schemas", [])
    return response, schemas


async def _filter_and_enrich_schemas(
    schemas: list[dict],
    client_filters: dict,
    version_pattern: str | None,
    text: str | None,
    search_in: list[str],
    include_content: bool,
    client: SchemaClient,
) -> list[dict]:
    """Apply client-side filtering, text search, and optional content enrichment."""
    filtered_schemas = []
    for schema in schemas:
        if not _matches_client_filters(schema, client_filters, version_pattern):
            continue

        # If text search is enabled, check if schema matches
        if text:
            matches = await _matches_text_search(
                schema, text, search_in, include_content, client
            )
            if not matches:
                continue

        # Add schema to filtered results
        filtered_schemas.append(schema)

        # Fetch full schema content if requested
        if include_content and "id" in schema.get("schemaIdentity", {}):
            schema_id = schema["schemaIdentity"]["id"]
            try:
                schema_content = await client.get_schema(schema_id)
                schema["schemaContent"] = schema_content.get("schema", {})
            except Exception as e:
                logger.warning(f"Failed to fetch schema content for {schema_id}: {e}")

    return filtered_schemas


def _matches_client_filters(
    schema: dict, filters: dict, version_pattern: str | None
) -> bool:
    """Apply client-side filters to a schema."""
    # Extract schema identity for easier access
    schema_identity = schema.get("schemaIdentity", {})

    # Check array-based filters
    for key, values in filters.items():
        if not isinstance(values, list):
            continue

        if (
            (key == "authority" and schema_identity.get("authority") not in values)
            or (key == "source" and schema_identity.get("source") not in values)
            or (key == "entity" and schema_identity.get("entityType") not in values)
            or (key == "status" and schema.get("status") not in values)
            or (key == "scope" and schema.get("scope") not in values)
        ):
            return False

    # Check version pattern if provided
    if version_pattern:
        major = schema_identity.get("schemaVersionMajor", 0)
        minor = schema_identity.get("schemaVersionMinor", 0)
        patch = schema_identity.get("schemaVersionPatch", 0)
        version_str = f"{major}.{minor}.{patch}"

        if not fnmatch.fnmatch(version_str, version_pattern):
            return False

    return True


def _matches_identity_fields(
    schema_identity: dict, search_fields: list[str], text_lower: str
) -> bool:
    """Check case-insensitive substring match against schema identity fields."""
    identity_field_map = {
        "id": "id",
        "authority": "authority",
        "source": "source",
        "entityType": "entityType",
    }
    for field_name, identity_key in identity_field_map.items():
        if (
            field_name in search_fields
            and text_lower in schema_identity.get(identity_key, "").lower()
        ):
            return True
    return False


async def _get_schema_content_for_search(
    schema: dict, include_content: bool, client: SchemaClient
) -> dict | None:
    """Resolve the full schema content to search, fetching it if necessary."""
    if include_content and "schemaContent" in schema:
        return schema["schemaContent"]

    schema_id = schema.get("schemaIdentity", {}).get("id")
    if not schema_id:
        return None

    try:
        schema_data = await client.get_schema(schema_id)
        return schema_data.get("schema", {})
    except Exception:
        return None


def _matches_content_fields(
    schema_content: dict, search_fields: list[str], text_lower: str
) -> bool:
    """Check case-insensitive substring match against schema content fields."""
    if (
        "title" in search_fields
        and text_lower in schema_content.get("title", "").lower()
    ):
        return True
    if (
        "description" in search_fields
        and text_lower in schema_content.get("description", "").lower()
    ):
        return True
    if "properties" in search_fields:
        properties = schema_content.get("properties", {})
        if _search_in_object(properties, text_lower):
            return True
    return False


async def _matches_text_search(
    schema: dict,
    text: str,
    search_fields: list[str],
    include_content: bool,
    client: SchemaClient,
) -> bool:
    """Check if schema matches text search criteria."""
    # Convert to lowercase for case-insensitive search
    text_lower = text.lower()
    schema_identity = schema.get("schemaIdentity", {})

    if _matches_identity_fields(schema_identity, search_fields, text_lower):
        return True

    # Need to fetch full schema if searching in content
    content_fields = ["title", "description", "properties", "content"]
    if not any(field in search_fields for field in content_fields):
        return False

    schema_content = await _get_schema_content_for_search(
        schema, include_content, client
    )
    if schema_content is None:
        return False

    return _matches_content_fields(schema_content, search_fields, text_lower)


def _search_in_object(obj: dict, text: str) -> bool:
    """Recursively search for text in a nested object."""
    if not isinstance(obj, dict):
        return False

    # Search in current object
    for key, value in obj.items():
        # Check if text is in key
        if text in key.lower():
            return True

        # Check if text is in string value
        if isinstance(value, str) and text in value.lower():
            return True

        # Recursively check nested objects
        if isinstance(value, dict):
            if _search_in_object(value, text):
                return True

        # Check in list elements
        elif isinstance(value, list):
            for item in value:
                if (isinstance(item, dict) and _search_in_object(item, text)) or (
                    isinstance(item, str) and text in item.lower()
                ):
                    return True

    return False


def _sort_schemas(schemas: list[dict], sort_by: str, sort_order: str) -> list[dict]:
    """Sort schemas by the specified field."""
    # Map sort_by values to actual schema keys
    sort_field_mapping = {
        "dateCreated": "dateCreated",
        "authority": ["schemaIdentity", "authority"],
        "source": ["schemaIdentity", "source"],
        "entityType": ["schemaIdentity", "entityType"],
        "status": "status",
        "scope": "scope",
        "id": ["schemaIdentity", "id"],
        "version": [
            "schemaIdentity",
            "schemaVersionMajor",
            "schemaVersionMinor",
            "schemaVersionPatch",
        ],
    }

    # Get actual field(s) to sort by
    sort_fields = sort_field_mapping.get(sort_by, sort_by)

    # Sort schemas
    def _get_sort_key(schema):
        if isinstance(sort_fields, list):
            # For nested fields, navigate through the object
            value = schema
            for field in sort_fields:
                if isinstance(value, dict) and field in value:
                    value = value[field]
                else:
                    # If field doesn't exist, use a default value
                    value = None
                    break
            return value
        # For direct fields
        return schema.get(sort_fields)

    # Sort with None values last
    return sorted(
        schemas,
        key=lambda s: (_get_sort_key(s) is None, _get_sort_key(s)),
        reverse=(sort_order.upper() == "DESC"),
    )
