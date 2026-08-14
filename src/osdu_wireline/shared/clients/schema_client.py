"""OSDU Schema service client."""

from typing import Any

from ..env import get_env_bool
from ..exceptions import OSMCPAPIError, OSMCPValidationError
from ..osdu_client import OsduClient
from ..service_urls import OSMCPService


class SchemaId:
    """Parsed OSDU schema identifier (authority:source:entity:major.minor.patch)."""

    def __init__(
        self,
        authority: str,
        source: str,
        entity: str,
        major: int,
        minor: int,
        patch: int,
    ):
        self.authority = authority
        self.source = source
        self.entity = entity
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def parse(cls, id_str: str) -> "SchemaId":
        """Parse a schema ID string into its components.

        Args:
            id_str: Schema ID (format: authority:source:entity:major.minor.patch)

        Returns:
            Parsed SchemaId

        Raises:
            OSMCPValidationError: If id_str is not a well-formed schema ID
        """
        parts = id_str.split(":")
        if len(parts) != 4:
            raise OSMCPValidationError(
                f"Invalid schema ID '{id_str}': expected format "
                "authority:source:entity:major.minor.patch"
            )
        authority, source, entity, version = parts
        version_parts = version.split(".")
        if len(version_parts) != 3 or not all(part.isdigit() for part in version_parts):
            raise OSMCPValidationError(
                f"Invalid schema ID '{id_str}': version '{version}' must be "
                "major.minor.patch"
            )
        major, minor, patch = (int(part) for part in version_parts)
        return cls(authority, source, entity, major, minor, patch)

    @property
    def version(self) -> str:
        """Version string (major.minor.patch)."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def __str__(self) -> str:
        return f"{self.authority}:{self.source}:{self.entity}:{self.version}"

    def to_schema_identity(self) -> dict[str, Any]:
        """Build the OSDU API 'schemaIdentity' representation."""
        return {
            "authority": self.authority,
            "source": self.source,
            "entityType": self.entity,
            "schemaVersionMajor": self.major,
            "schemaVersionMinor": self.minor,
            "schemaVersionPatch": self.patch,
            "id": str(self),
        }


class SchemaClient(OsduClient):
    """Client for OSDU Schema service operations."""

    service = OSMCPService.SCHEMA

    async def list_schemas(
        self,
        authority: str | None = None,
        source: str | None = None,
        entity: str | None = None,
        status: str | None = "PUBLISHED",
        scope: str | None = None,
        latest_version: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List schemas with optional filtering.

        Args:
            authority: Filter by authority
            source: Filter by source
            entity: Filter by entity type (maps to entityType in API)
            status: Schema status (DEVELOPMENT, PUBLISHED, OBSOLETE)
            scope: Schema scope (INTERNAL, SHARED)
            latest_version: Only return latest versions
            limit: Maximum number of results (max 1000)
            offset: Pagination offset

        Returns:
            List of schemas matching the criteria with the format:
            {
                "schemaInfos": [...],
                "totalCount": 123,
                "count": 10,
                "offset": 0
            }
        """
        # Initialize parameters list
        params = []

        # Add pagination parameters
        params.append(
            f"limit={min(limit, 1000)}"
        )  # API limit is 100, but we'll enforce 1000

        if offset > 0:
            params.append(f"offset={offset}")

        # Add filter parameters
        if authority:
            params.append(f"authority={authority}")
        if source:
            params.append(f"source={source}")
        if entity:
            params.append(f"entityType={entity}")
        if status:
            params.append(f"status={status}")
        if scope:
            params.append(f"scope={scope}")
        if latest_version:
            params.append("latestVersion=true")

        # Build query string
        query_string = "&".join(params)

        # Make API request
        return await self.get(f"/schema?{query_string}")

    async def get_schema(self, schema_id: str) -> dict[str, Any]:
        """Get schema by ID.

        Args:
            schema_id: Schema ID (format: authority:source:entity:major.minor.patch)

        Returns:
            Schema details
        """
        return await self.get(f"/schema/{schema_id}")

    async def search_schemas(
        self,
        query: str | None = None,
        filter_criteria: dict[str, list[str]] | None = None,
        latest_version: bool = False,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search schemas with complex filtering.

        Note: This implementation uses the list_schemas endpoint with additional
        filtering since OSDU Schema API doesn't have a dedicated search endpoint.
        Client-side filtering is applied for more advanced search capabilities.

        Args:
            query: Free text search query
            filter_criteria: Structured filter criteria
            latest_version: Only return latest versions
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Search results matching the criteria containing schemaInfos
        """
        # Extract basic filters from the filter criteria if available
        authority = None
        source = None
        entity = None
        status = None
        scope = None

        if filter_criteria:
            # Extract simple filters for server-side filtering
            if "authority" in filter_criteria and isinstance(
                filter_criteria["authority"], str
            ):
                authority = filter_criteria["authority"]
            if "source" in filter_criteria and isinstance(
                filter_criteria["source"], str
            ):
                source = filter_criteria["source"]
            if "entity" in filter_criteria and isinstance(
                filter_criteria["entity"], str
            ):
                entity = filter_criteria["entity"]
            if "status" in filter_criteria and isinstance(
                filter_criteria["status"], str
            ):
                status = filter_criteria["status"]
            if "scope" in filter_criteria and isinstance(filter_criteria["scope"], str):
                scope = filter_criteria["scope"]

        # Use the list_schemas endpoint which is available in the API
        return await self.list_schemas(
            authority=authority,
            source=source,
            entity=entity,
            status=status,
            scope=scope,
            latest_version=latest_version,
            limit=limit,
            offset=offset,
        )

    async def create_schema(
        self,
        authority: str,
        source: str,
        entity: str,
        major_version: int,
        minor_version: int,
        patch_version: int,
        schema: dict[str, Any],
        status: str = "DEVELOPMENT",
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new schema.

        Args:
            authority: Schema authority
            source: Schema source
            entity: Schema entity type
            major_version: Major version number
            minor_version: Minor version number
            patch_version: Patch version number
            schema: JSON Schema definition
            status: Schema status (default: DEVELOPMENT)
            description: Schema description

        Returns:
            Created schema

        Raises:
            OSMCPAPIError: If write mode is disabled
        """
        # Check write protection
        if not get_env_bool("OSDU_MCP_ENABLE_WRITE_MODE"):
            raise OSMCPAPIError(
                "Write operations are disabled. Set OSDU_MCP_ENABLE_WRITE_MODE=true to enable.",
                status_code=403,
            )

        # Build request body
        schema_id = SchemaId(
            authority, source, entity, major_version, minor_version, patch_version
        )
        body = {
            "schemaInfo": {
                "schemaIdentity": schema_id.to_schema_identity(),
                "status": status,
            },
            "schema": schema,
        }

        # Add description to schema if provided
        if description and "title" not in schema:
            schema["title"] = description

        if description and "description" not in schema:
            schema["description"] = description

        return await self.post("/schema", json=body)

    async def update_schema(
        self, id: str, schema: dict[str, Any], status: str | None = None
    ) -> dict[str, Any]:
        """Update an existing schema in DEVELOPMENT status.

        Args:
            id: Schema ID to update
            schema: New schema definition
            status: New schema status (can transition from DEVELOPMENT to PUBLISHED)

        Returns:
            Updated schema

        Raises:
            OSMCPAPIError: If write mode is disabled
        """
        # Check write protection
        if not get_env_bool("OSDU_MCP_ENABLE_WRITE_MODE"):
            raise OSMCPAPIError(
                "Write operations are disabled. Set OSDU_MCP_ENABLE_WRITE_MODE=true to enable.",
                status_code=403,
            )

        # Get existing schema to extract identity details
        existing_schema = await self.get_schema(id)

        # Extract schema info from existing schema
        schema_info = existing_schema.get("schemaInfo", {})
        schema_identity = schema_info.get("schemaIdentity", {})

        # Build request body
        body = {"schemaInfo": {"schemaIdentity": schema_identity}, "schema": schema}

        # Update status if provided
        if status:
            body["schemaInfo"]["status"] = status

        return await self.put("/schema", json=body)
