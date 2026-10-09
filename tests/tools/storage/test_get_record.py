"""Tests for storage get record operations."""

import os
import re
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.storage.get_record import storage_get_record
from osdu_wireline.tools.storage.get_record_version import storage_get_record_version
from osdu_wireline.tools.storage.list_record_versions import (
    storage_list_record_versions,
)
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_storage_get_record_success():
    """Test successful record retrieval."""
    mock_record = {
        "id": "test:record:123",
        "kind": "test:test:test:1.0.0",
        "version": 1234567890,
        "acl": {"viewers": ["test"], "owners": ["test"]},
        "legal": {"legaltags": ["test"], "otherRelevantDataCountries": ["US"]},
        "data": {"name": "Test Record", "value": 42},
        "createTime": "2023-01-01T00:00:00.000Z",
        "createUser": "test@example.com",
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/storage/v2/records/test:record:123",
                    payload=mock_record,
                )

                result = await storage_get_record("test:record:123")

                assert result["success"] is True
                assert result["record"]["id"] == "test:record:123"
                assert result["record"]["kind"] == "test:test:test:1.0.0"
                assert result["partition"] == "opendes"


@pytest.mark.asyncio
async def test_storage_get_record_with_attributes():
    """Test record retrieval with attribute filtering."""
    mock_record = {
        "id": "test:record:123",
        "kind": "test:test:test:1.0.0",
        "version": 1234567890,
        "data": {"name": "Test Record"},  # Only requested attribute
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                # Use pattern matching for URL with query parameters
                mocked.get(
                    url=re.compile(
                        r"https://test\.osdu\.com/api/storage/v2/records/test:record:123.*"
                    ),
                    payload=mock_record,
                )

                result = await storage_get_record(
                    "test:record:123", attributes=["data.name"]
                )

                assert result["success"] is True
                assert result["record"]["data"]["name"] == "Test Record"


@pytest.mark.asyncio
async def test_storage_get_record_version_success():
    """Test successful record version retrieval."""
    mock_record = {
        "id": "test:record:123",
        "kind": "test:test:test:1.0.0",
        "version": 1234567890,
        "data": {"name": "Test Record Version"},
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/storage/v2/records/test:record:123/1234567890",
                    payload=mock_record,
                )

                result = await storage_get_record_version("test:record:123", 1234567890)

                assert result["success"] is True
                assert result["record"]["version"] == 1234567890


@pytest.mark.asyncio
async def test_storage_list_record_versions_success():
    """Test successful record versions listing."""
    mock_versions = {
        "recordId": "test:record:123",
        "versions": [1234567890, 1234567891, 1234567892],
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/storage/v2/records/versions/test:record:123",
                    payload=mock_versions,
                )

                result = await storage_list_record_versions("test:record:123")

                assert result["success"] is True
                assert result["recordId"] == "test:record:123"
                assert result["count"] == 3
                assert len(result["versions"]) == 3
                assert 1234567890 in result["versions"]
