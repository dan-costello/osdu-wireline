"""Tests for partition_list tool."""

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.partition.list import partition_list

PARTITIONS_URL = "https://test.osdu.com/api/partition/v1/partitions"


@pytest.mark.asyncio
async def test_partition_list_success(osdu_env):
    """Test successful partition listing."""
    with aioresponses() as mocked:
        mocked.get(PARTITIONS_URL, payload=["osdu", "tenant-a", "tenant-b"])

        result = await partition_list()

        assert result["success"] is True
        assert result["partitions"] == ["osdu", "tenant-a", "tenant-b"]
        assert result["count"] == 3


@pytest.mark.asyncio
async def test_partition_list_empty(osdu_env):
    """Test partition listing with no results."""
    with aioresponses() as mocked:
        mocked.get(PARTITIONS_URL, payload=[])

        result = await partition_list()

        assert result["success"] is True
        assert result["partitions"] == []
        assert result["count"] == 0


@pytest.mark.asyncio
async def test_partition_list_forbidden(osdu_env):
    """Test partition listing with insufficient permissions."""
    with aioresponses() as mocked:
        mocked.get(PARTITIONS_URL, status=403, body="Access denied")

        result = await partition_list()

        assert result["success"] is False
        assert result["partitions"] == []
        assert "Insufficient permissions" in result["error"]


@pytest.mark.asyncio
async def test_partition_list_with_detailed_metadata(osdu_env):
    """Test partition listing with detailed metadata."""
    with aioresponses() as mocked:
        mocked.get(PARTITIONS_URL, payload=["osdu", "tenant-a"])

        result = await partition_list(detailed=True)

        assert result["success"] is True
        assert result["partitions"] == ["osdu", "tenant-a"]
        assert result["count"] == 2
        assert "metadata" in result
        assert result["metadata"]["server_url"] == "https://test.osdu.com"
