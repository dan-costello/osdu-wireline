"""Tests for schema_search tool."""

import re

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.schema.search import schema_search

SCHEMA_LIST_URL = re.compile(r"^https://test\.osdu\.com/api/schema-service/v1/schema\?")
SCHEMA_GET_URL = (
    "https://test.osdu.com/api/schema-service/v1/schema/osdu:wks:TestSchema:1.0.0"
)

SCHEMA_INFO = {
    "schemaIdentity": {
        "authority": "osdu",
        "source": "wks",
        "entityType": "TestSchema",
        "schemaVersionMajor": 1,
        "schemaVersionMinor": 0,
        "schemaVersionPatch": 0,
        "id": "osdu:wks:TestSchema:1.0.0",
    },
    "status": "PUBLISHED",
    "scope": "SHARED",
}

LIST_RESPONSE = {
    "schemaInfos": [SCHEMA_INFO],
    "count": 1,
    "totalCount": 1,
    "offset": 0,
}


@pytest.mark.asyncio
async def test_schema_search_basic(osdu_env):
    """Test that schema_search handles API response correctly."""
    with aioresponses() as mocked:
        mocked.get(SCHEMA_LIST_URL, payload=LIST_RESPONSE)

        result = await schema_search()

        assert result["success"] is True
        assert len(result["schemas"]) == 1
        assert result["count"] == 1
        assert (
            result["schemas"][0]["schemaIdentity"]["id"] == "osdu:wks:TestSchema:1.0.0"
        )


@pytest.mark.asyncio
async def test_schema_search_with_text(osdu_env):
    """Test schema_search with text search capability."""
    schema_content = {
        "title": "Test Schema",
        "description": "This is a schema for testing",
        "properties": {
            "testField": {
                "type": "string",
                "description": "Test field with pressure measurements",
            }
        },
    }

    with aioresponses() as mocked:
        mocked.get(SCHEMA_LIST_URL, payload=LIST_RESPONSE)
        mocked.get(SCHEMA_GET_URL, payload={"schema": schema_content})

        # Text search fetches schema content to match against
        result = await schema_search(text="pressure")

        assert result["success"] is True
        assert len(result["schemas"]) == 1
        assert result["count"] == 1
        assert result["query"] == "pressure"
