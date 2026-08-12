"""Tests for the health check tool."""

import os
import time
from urllib.parse import urljoin

import jwt
import pytest
from aioresponses import aioresponses

from osdu_mcp_server.shared.service_urls import OSMCPService, get_service_info_endpoint
from osdu_mcp_server.tools.health_check import health_check

SERVER_URL = "https://test.osdu.com"


def _info_url(service: OSMCPService) -> str:
    """Full URL of a service's info endpoint."""
    return urljoin(SERVER_URL, get_service_info_endpoint(service))


def _mock_all_services(mocked: aioresponses, payload=None, skip=None):
    """Register a healthy info response for every OSDU service."""
    for service in OSMCPService:
        if skip is not None and service is skip:
            continue
        mocked.get(_info_url(service), payload=payload or {"version": "1.0.0"})


@pytest.mark.asyncio
async def test_health_check_success(osdu_env):
    """Test successful health check reports connectivity and services."""
    with aioresponses() as mocked:
        _mock_all_services(mocked)

        result = await health_check()

        assert result["connectivity"] == "success"
        assert result["server_url"] == SERVER_URL
        assert result["data_partition"] == "opendes"
        assert result["authentication"]["status"] == "valid"
        assert "services" in result
        assert "timestamp" in result


@pytest.mark.asyncio
async def test_health_check_auth_failure(monkeypatch):
    """Test health check reports invalid authentication for a bad token."""
    expired_token = jwt.encode(
        {"sub": "test-user", "exp": int(time.time()) - 3600},
        "test-secret",
        algorithm="HS256",
    )
    monkeypatch.setitem(os.environ, "OSDU_MCP_SERVER_URL", SERVER_URL)
    monkeypatch.setitem(os.environ, "OSDU_MCP_SERVER_DATA_PARTITION", "opendes")
    monkeypatch.setitem(os.environ, "OSDU_MCP_USER_TOKEN", expired_token)

    with aioresponses() as mocked:
        _mock_all_services(mocked)

        result = await health_check(include_services=False)

        assert result["authentication"]["status"] == "invalid"


@pytest.mark.asyncio
async def test_health_check_service_unhealthy(osdu_env):
    """Test health check flags a service that returns an error."""
    with aioresponses() as mocked:
        _mock_all_services(mocked, skip=OSMCPService.STORAGE)
        mocked.get(
            _info_url(OSMCPService.STORAGE), status=503, body="Service unavailable"
        )

        result = await health_check()

        assert result["services"]["storage"].startswith("unhealthy")
        assert result["services"]["search"] == "healthy"
        assert result["services"]["legal"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_without_services(osdu_env):
    """Test health check without checking services."""
    result = await health_check(include_services=False)

    assert "services" not in result
    assert result["connectivity"] == "success"


@pytest.mark.asyncio
async def test_health_check_with_version_info(osdu_env):
    """Test health check with version information."""
    with aioresponses() as mocked:
        _mock_all_services(mocked)

        result = await health_check(include_version_info=True)

        assert "services" in result
        assert "version_info" in result["services"]
