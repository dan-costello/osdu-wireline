"""Tests for storage write and delete operation protection.

Storage protections are enforced inside StorageClient, so these tests need a
configured environment (osdu_env) for the client to be constructed.
"""

import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from osdu_mcp_server.tools.storage.create_update_records import (
    storage_create_update_records,
)
from osdu_mcp_server.tools.storage.delete_record import storage_delete_record
from osdu_mcp_server.tools.storage.purge_record import storage_purge_record

VALID_RECORD = {
    "kind": "test:test:test:1.0.0",
    "acl": {"viewers": ["test"], "owners": ["test"]},
    "legal": {"legaltags": ["test"], "otherRelevantDataCountries": ["US"]},
    "data": {"test": "data"},
}


@pytest.mark.asyncio
async def test_storage_create_blocked_by_default(osdu_env):
    """Test storage create is blocked when write is disabled."""
    with patch.dict(os.environ, {}, clear=False):
        # Remove the env var if it exists
        os.environ.pop("OSDU_MCP_ENABLE_WRITE_MODE", None)

        with pytest.raises(
            Exception, match="Write operations are disabled"
        ) as exc_info:
            await storage_create_update_records([VALID_RECORD])

        assert "Write operations are disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_storage_delete_blocked_by_default(osdu_env):
    """Test storage delete is blocked when delete mode is disabled."""
    with patch.dict(os.environ, {}, clear=False):
        # Remove the env var if it exists
        os.environ.pop("OSDU_MCP_ENABLE_DELETE_MODE", None)

        with pytest.raises(
            Exception, match="Delete operations are disabled"
        ) as exc_info:
            await storage_delete_record("test:record:123")

        assert "Delete operations are disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_storage_purge_blocked_by_default(osdu_env):
    """Test storage purge is blocked when delete mode is disabled."""
    with patch.dict(os.environ, {}, clear=False):
        # Remove the env var if it exists
        os.environ.pop("OSDU_MCP_ENABLE_DELETE_MODE", None)

        with pytest.raises(
            Exception, match="Delete operations are disabled"
        ) as exc_info:
            await storage_purge_record("test:record:123", confirm=True)

        assert "Delete operations are disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_storage_purge_requires_confirmation(osdu_env):
    """Test storage purge requires explicit confirmation."""
    with patch.dict(os.environ, {"OSDU_MCP_ENABLE_DELETE_MODE": "true"}):
        with pytest.raises(
            Exception, match="requires explicit confirmation"
        ) as exc_info:
            # Without confirmation
            await storage_purge_record("test:record:123", confirm=False)

        assert "requires explicit confirmation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dual_protection_independence(osdu_env):
    """Test that write and delete protections are independent."""
    # Test write enabled but delete disabled
    with patch.dict(os.environ, {"OSDU_MCP_ENABLE_WRITE_MODE": "true"}, clear=False):
        os.environ.pop("OSDU_MCP_ENABLE_DELETE_MODE", None)

        with aioresponses() as mocked:
            mocked.put(
                "https://test.osdu.com/api/storage/v2/records",
                payload={
                    "recordCount": 1,
                    "recordIds": ["test:record:123"],
                    "recordIdVersions": ["1234567890"],
                },
            )

            # Create should work
            result = await storage_create_update_records([VALID_RECORD])
            assert result["success"] is True
            assert result["write_enabled"] is True

        # But delete should still fail
        with pytest.raises(
            Exception, match="Delete operations are disabled"
        ) as exc_info:
            await storage_delete_record("test:record:123")

        assert "Delete operations are disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_record_validation(osdu_env):
    """Test record validation for required fields."""
    with patch.dict(os.environ, {"OSDU_MCP_ENABLE_WRITE_MODE": "true"}):
        # Test missing required field
        invalid_record = {
            "kind": "test:test:test:1.0.0",
            "acl": {"viewers": ["test"], "owners": ["test"]},
            # Missing legal and data fields
        }

        with pytest.raises(Exception, match="Missing required field") as exc_info:
            await storage_create_update_records([invalid_record])

        assert "Missing required field" in str(exc_info.value)

        # Test invalid ACL
        invalid_acl_record = {
            "kind": "test:test:test:1.0.0",
            "acl": {"viewers": ["test"]},  # Missing owners
            "legal": {"legaltags": ["test"], "otherRelevantDataCountries": ["US"]},
            "data": {"test": "data"},
        }

        with pytest.raises(
            Exception, match="ACL must contain both 'viewers' and 'owners'"
        ) as exc_info:
            await storage_create_update_records([invalid_acl_record])

        assert "ACL must contain both 'viewers' and 'owners'" in str(exc_info.value)
