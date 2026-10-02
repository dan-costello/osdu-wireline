"""Tests for schema write protection."""

import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_wireline.tools.schema.create import schema_create
from osdu_wireline.tools.schema.update import schema_update
from tests.conftest import static_token


@pytest.mark.asyncio
async def test_schema_create_write_protection():
    """Test write protection for schema_create."""

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
        "OSDU_MCP_ENABLE_WRITE_MODE": "false",  # Write protection enabled
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with pytest.raises(
                Exception, match="Schema write operations are disabled"
            ) as excinfo:
                await schema_create(
                    authority="test",
                    source="test",
                    entity="test",
                    major_version=1,
                    minor_version=0,
                    patch_version=0,
                    schema_definition={"type": "object"},
                )

            assert "Schema write operations are disabled" in str(excinfo.value)
            assert "OSDU_MCP_ENABLE_WRITE_MODE=true" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schema_update_write_protection():
    """Test write protection for schema_update."""

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
        "OSDU_MCP_ENABLE_WRITE_MODE": "false",  # Write protection enabled
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with pytest.raises(
                Exception, match="Schema write operations are disabled"
            ) as excinfo:
                await schema_update(
                    id="test:test:test:1.0.0", schema_definition={"type": "object"}
                )

            assert "Schema write operations are disabled" in str(excinfo.value)
            assert "OSDU_MCP_ENABLE_WRITE_MODE=true" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schema_create_write_enabled(sent_json):
    """Test successful schema creation with write mode enabled."""
    mock_response = {"id": "test:test:test:1.0.0", "status": "DEVELOPMENT"}

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
        "OSDU_MCP_ENABLE_WRITE_MODE": "true",  # Write protection disabled
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                mocked.post(
                    "https://test.osdu.com/api/schema-service/v1/schema",
                    payload=mock_response,
                )

                result = await schema_create(
                    authority="test",
                    source="test",
                    entity="test",
                    major_version=1,
                    minor_version=0,
                    patch_version=0,
                    schema_definition={"type": "object"},
                )

                # The request must carry the schema; an earlier bug sent an
                # empty body because the json= kwarg was overwritten with None.
                sent = sent_json(
                    mocked,
                    "POST",
                    "https://test.osdu.com/api/schema-service/v1/schema",
                )
                assert sent is not None
                assert sent["schema"]["type"] == "object"
                assert sent["schemaInfo"]["schemaIdentity"]["entityType"] == "test"

            assert result["success"] is True
            assert result["created"] is True
            assert result["id"] == "test:test:test:1.0.0"
            assert result["write_enabled"] is True


@pytest.mark.asyncio
async def test_schema_update_write_enabled(sent_json):
    """Test successful schema update with write mode enabled."""
    mock_get_response = {
        "id": "test:test:test:1.0.0",
        "schemaInfo": {
            "schemaIdentity": {
                "authority": "test",
                "source": "test",
                "entityType": "test",
                "schemaVersionMajor": 1,
                "schemaVersionMinor": 0,
                "schemaVersionPatch": 0,
                "id": "test:test:test:1.0.0",
            },
            "status": "DEVELOPMENT",
        },
    }

    mock_update_response = {"id": "test:test:test:1.0.0", "status": "DEVELOPMENT"}

    test_env = {
        "OSDU_BASE_URL": "https://test.osdu.com",
        "OSDU_PARTITION_ID": "opendes",
        "OSDU_MCP_ENABLE_WRITE_MODE": "true",  # Write protection disabled
    }

    with patch.dict(os.environ, test_env):
        with static_token():
            with aioresponses() as mocked:
                # Mock both raw URL and quoted URL to handle aioresponses URL normalization
                test_schema_url = "https://test.osdu.com/api/schema-service/v1/schema/test:test:test:1.0.0"
                mocked.get(test_schema_url, payload=mock_get_response)
                mocked.get(
                    "https://test.osdu.com/api/schema-service/v1/schema/test%3Atest%3Atest%3A1.0.0",
                    payload=mock_get_response,
                )
                mocked.put(
                    "https://test.osdu.com/api/schema-service/v1/schema",
                    payload=mock_update_response,
                )

                result = await schema_update(
                    id="test:test:test:1.0.0",
                    schema_definition={
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                )

                sent = sent_json(
                    mocked,
                    "PUT",
                    "https://test.osdu.com/api/schema-service/v1/schema",
                )
                assert sent is not None
                assert sent["schema"]["properties"] == {"name": {"type": "string"}}

            assert result["success"] is True
            assert result["updated"] is True
            assert result["id"] == "test:test:test:1.0.0"
            assert result["write_enabled"] is True
