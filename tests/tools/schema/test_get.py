"""Tests for schema_get tool."""

import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.schema.get import schema_get
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_schema_get_success():
    """Test successful retrieval of schema by ID."""
    mock_response = {
        "id": "osdu:wks:wellbore:1.0.0",
        "schemaInfo": {
            "schemaIdentity": {
                "authority": "osdu",
                "source": "wks",
                "entityType": "wellbore",
                "schemaVersionMajor": 1,
                "schemaVersionMinor": 0,
                "schemaVersionPatch": 0,
                "id": "osdu:wks:wellbore:1.0.0",
            },
            "createdBy": "user@example.com",
            "dateCreated": "2025-01-15T10:30:00Z",
            "status": "PUBLISHED",
            "scope": "INTERNAL",
        },
        "schema": {
            "$id": "https://schema.osdu.opengroup.org/json/wks/wellbore.1.0.0.json",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Wellbore",
            "description": "Wellbore schema definition",
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Wellbore name"}},
            "required": ["name"],
        },
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/schema-service/v1/schema/osdu:wks:wellbore:1.0.0",
                    payload=mock_response,
                )

                result = await schema_get(id="osdu:wks:wellbore:1.0.0")

        assert result["success"] is True
        assert result["id"] == "osdu:wks:wellbore:1.0.0"
        assert result["partition"] == "opendes"
        assert "schemaInfo" in result
        assert "schema" in result

        # Check schema details
        assert result["schemaInfo"]["schemaIdentity"]["authority"] == "osdu"
        assert result["schemaInfo"]["schemaIdentity"]["source"] == "wks"
        assert result["schemaInfo"]["schemaIdentity"]["entityType"] == "wellbore"
        assert result["schema"]["title"] == "Wellbore"
