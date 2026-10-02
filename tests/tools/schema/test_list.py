"""Tests for schema_list tool."""

import os
import re
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.schema.list import schema_list
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_schema_list_success():
    """Test successful retrieval of schemas."""
    mock_response = {
        "schemas": [
            {
                "id": "osdu:wks:wellbore:1.0.0",
                "authority": "osdu",
                "source": "wks",
                "entityType": "wellbore",
                "version": "1.0.0",
                "status": "PUBLISHED",
                "scope": "INTERNAL",
                "createdBy": "user@example.com",
                "dateCreated": "2025-01-15T10:30:00Z",
            },
            {
                "id": "osdu:wks:welllog:2.0.0",
                "authority": "osdu",
                "source": "wks",
                "entityType": "welllog",
                "version": "2.0.0",
                "status": "PUBLISHED",
                "scope": "INTERNAL",
                "createdBy": "user@example.com",
                "dateCreated": "2025-02-20T14:45:00Z",
            },
        ],
        "totalCount": 2,
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/schema-service/v1/schema?limit=10",
                    payload=mock_response,
                )

                result = await schema_list()

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["schemas"]) == 2
        assert result["partition"] == "opendes"
        assert result["totalCount"] == 2

        # Check schema details
        assert result["schemas"][0]["id"] == "osdu:wks:wellbore:1.0.0"
        assert result["schemas"][1]["id"] == "osdu:wks:welllog:2.0.0"


@pytest.mark.asyncio
async def test_schema_list_with_filters():
    """Test retrieval of schemas with filtering."""
    mock_response = {
        "schemas": [
            {
                "id": "osdu:wks:wellbore:1.0.0",
                "authority": "osdu",
                "source": "wks",
                "entityType": "wellbore",
                "version": "1.0.0",
                "status": "PUBLISHED",
                "scope": "INTERNAL",
                "createdBy": "user@example.com",
                "dateCreated": "2025-01-15T10:30:00Z",
            }
        ],
        "totalCount": 1,
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    re.compile(
                        r"https://test\.osdu\.com/api/schema-service/v1/schema\?(?=.*authority=osdu)(?=.*entityType=wellbore)(?=.*limit=10)(?=.*source=wks).*"
                    ),
                    payload=mock_response,
                )

                result = await schema_list(
                    authority="osdu", source="wks", entity="wellbore"
                )

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["schemas"]) == 1
        assert result["schemas"][0]["authority"] == "osdu"
        assert result["schemas"][0]["source"] == "wks"
        assert result["schemas"][0]["entityType"] == "wellbore"


@pytest.mark.asyncio
async def test_schema_list_empty():
    """Test when no schemas exist or match filters."""
    mock_response = {"schemas": [], "totalCount": 0}

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    re.compile(
                        r"https://test\.osdu\.com/api/schema-service/v1/schema\?(?=.*authority=unknown)(?=.*limit=10).*"
                    ),
                    payload=mock_response,
                )

                result = await schema_list(authority="unknown")

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["schemas"]) == 0
        assert result["totalCount"] == 0
