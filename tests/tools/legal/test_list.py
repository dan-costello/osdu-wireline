"""Tests for legaltag_list tool."""

import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.legal import legaltag_list
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_legaltag_list_success():
    """Test successful retrieval of legal tags."""
    mock_response = {
        "legalTags": [
            {
                "name": "opendes-Private-USA-EHC",
                "description": "Private data for USA with EHC compliance",
                "properties": {
                    "countryOfOrigin": ["US"],
                    "contractId": "A1234",
                    "expirationDate": "2028-12-31",
                    "securityClassification": "Private",
                    "personalData": "No Personal Data",
                    "exportClassification": "EAR99",
                },
            },
            {
                "name": "opendes-Public-Global-Data",
                "description": "Public global data",
                "properties": {
                    "countryOfOrigin": ["XX"],
                    "contractId": "B5678",
                    "securityClassification": "Public",
                    "personalData": "No Personal Data",
                    "exportClassification": "No License Required",
                },
            },
        ]
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/legal/v1/legaltags?valid=true",
                    payload=mock_response,
                )

                result = await legaltag_list(valid_only=True)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["legalTags"]) == 2
        assert result["partition"] == "opendes"

        # Check simplified names were added
        assert result["legalTags"][0]["simplifiedName"] == "Private-USA-EHC"
        assert result["legalTags"][1]["simplifiedName"] == "Public-Global-Data"


@pytest.mark.asyncio
async def test_legaltag_list_invalid_only():
    """Test retrieval of invalid legal tags only."""
    mock_response = {
        "legalTags": [
            {
                "name": "opendes-Expired-Contract",
                "description": "Expired contract data",
                "properties": {
                    "countryOfOrigin": ["US"],
                    "contractId": "EXP123",
                    "expirationDate": "2020-12-31",
                    "securityClassification": "Private",
                },
            }
        ]
    }

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/legal/v1/legaltags?valid=false",
                    payload=mock_response,
                )

                result = await legaltag_list(valid_only=False)

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["legalTags"]) == 1
        assert result["legalTags"][0]["simplifiedName"] == "Expired-Contract"


@pytest.mark.asyncio
async def test_legaltag_list_empty():
    """Test when no legal tags exist."""
    mock_response = {"legalTags": []}

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.get(
                    "https://test.osdu.com/api/legal/v1/legaltags?valid=true",
                    payload=mock_response,
                )

                result = await legaltag_list()

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["legalTags"]) == 0
