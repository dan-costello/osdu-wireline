"""Tests for entitlements_mine tool."""

import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.entitlements import entitlements_mine
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_entitlements_mine_success():
    """Test successful retrieval of user groups."""
    mock_response = {
        "groups": [
            {
                "name": "users",
                "email": "users@opendes.dataservices.energy",
                "description": "All users",
            },
            {
                "name": "users.datalake.viewers",
                "email": "users.datalake.viewers@opendes.dataservices.energy",
                "description": "Data Lake read access",
            },
        ]
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "test-partition",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                # Mock the actual API call
                mocked.get(
                    url="https://test.osdu.com/api/entitlements/v2/groups",
                    payload=mock_response,
                )

                result = await entitlements_mine()

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["groups"]) == 2
        assert result["groups"][0]["name"] == "users"
        assert result["groups"][1]["name"] == "users.datalake.viewers"

        # Test we return all fields from API
        assert "email" in result["groups"][0]
        assert "description" in result["groups"][0]


@pytest.mark.asyncio
async def test_entitlements_mine_empty():
    """Test when user has no groups."""
    mock_response = {"groups": []}

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "test-partition",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                # Mock the actual API call
                mocked.get(
                    url="https://test.osdu.com/api/entitlements/v2/groups",
                    payload=mock_response,
                )

                result = await entitlements_mine()

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["groups"]) == 0
        assert result["partition"] == "test-partition"
