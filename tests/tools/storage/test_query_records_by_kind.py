"""Tests for storage query records by kind operation."""

import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.storage.query_records_by_kind import (
    storage_query_records_by_kind,
)
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_storage_query_records_by_kind_success():
    """Test successful query of records by kind."""
    mock_response = {
        "cursor": "next-page-cursor",
        "results": ["test:record:123", "test:record:456", "test:record:789"],
    }

    with patch.dict(
        os.environ,
        {
            "OSDU_BASE_URL": "https://test.osdu.com",
            "OSDU_PARTITION_ID": "test-partition",
        },
    ):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/storage/v2/query/records?kind=test%3Atest%3Atest%3A1.0.0&limit=10",
                    payload=mock_response,
                )

                result = await storage_query_records_by_kind(
                    kind="test:test:test:1.0.0", limit=10
                )

                assert result["success"] is True
                assert result["cursor"] == "next-page-cursor"
                assert result["results"] == mock_response["results"]
                assert result["count"] == 3
                assert result["partition"] == "test-partition"


@pytest.mark.asyncio
async def test_storage_query_records_by_kind_with_cursor():
    """Test query with pagination cursor."""
    mock_response = {"cursor": "another-cursor", "results": ["test:record:999"]}

    with patch.dict(
        os.environ,
        {
            "OSDU_BASE_URL": "https://test.osdu.com",
            "OSDU_PARTITION_ID": "test-partition",
        },
    ):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/storage/v2/query/records?kind=test%3Atest%3Atest%3A1.0.0&limit=5&cursor=previous-cursor",
                    payload=mock_response,
                )

                result = await storage_query_records_by_kind(
                    kind="test:test:test:1.0.0", limit=5, cursor="previous-cursor"
                )

                assert result["success"] is True
                assert result["cursor"] == "another-cursor"
                assert result["count"] == 1
