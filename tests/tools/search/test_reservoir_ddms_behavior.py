"""Behavior-driven tests for the Reservoir DDMS tools following ADR-010."""

import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from mcp.shared.exceptions import McpError

from osdu_wireline.shared.clients import ReservoirDDMSClient
from osdu_wireline.shared.exceptions import OSMCPAPIError, OSMCPValidationError
from osdu_wireline.tools.search import (
    query_available_dataspaces,
    query_dataspace_files,
)
from tests.conftest import OSDU_TEST_ENV

BASE = "https://test.osdu.com/api/reservoir-ddms/v2"
DATASPACES_URL = f"{BASE}/dataspaces"

# The dataspace id carries a slash, which must survive as %2F rather than
# splitting into extra path segments.
DATASPACE = "carl/volve_horizons"
RESOURCES_URL = f"{BASE}/dataspaces/carl%2Fvolve_horizons/resources/all"
RESOURCES_PATTERN = re.compile(r".*/dataspaces/[^/]+/resources/all$")


def dataspace_uris(*ids: str) -> list[dict[str, Any]]:
    """A /dataspaces response: one entry per dataspace id, in OSDU's uri form."""
    return [{"uri": f"eml:///dataspace('{id_}')"} for id_ in ids]


@contextmanager
def mock_ddms() -> Generator[aioresponses]:
    """Serve the Reservoir DDMS endpoints with USER_TOKEN auth."""
    with patch.dict(os.environ, OSDU_TEST_ENV), aioresponses() as mocked:
        yield mocked


@pytest.mark.asyncio
async def test_available_dataspaces_reports_ids_not_uris():
    """The tool reports the dataspace ids parsed out of the eml:// uris."""
    with mock_ddms() as mocked:
        mocked.get(DATASPACES_URL, payload=dataspace_uris("carl/volve", "demo"))
        result = await query_available_dataspaces()

    assert result == {"dataspaces": ["carl/volve", "demo"], "totalCount": 2}


@pytest.mark.asyncio
async def test_available_dataspaces_filters_on_a_partial_name():
    """name_pattern is a substring match, case-insensitively."""
    with mock_ddms() as mocked:
        mocked.get(DATASPACES_URL, payload=dataspace_uris("carl/volve", "demo"))
        result = await query_available_dataspaces(name_pattern="VOLVE")

    assert result == {"dataspaces": ["carl/volve"], "totalCount": 1}


@pytest.mark.asyncio
async def test_a_null_uri_does_not_break_the_dataspace_listing():
    """An entry whose uri is JSON null is skipped, not a TypeError."""
    payload = [{"uri": None}, {}, *dataspace_uris("demo")]
    with mock_ddms() as mocked:
        mocked.get(DATASPACES_URL, payload=payload)
        result = await query_available_dataspaces()

    assert result == {"dataspaces": ["demo"], "totalCount": 1}


@pytest.mark.asyncio
async def test_an_unexpected_listing_payload_is_reported_not_raised():
    """A dict where a list was expected yields an empty, flagged result."""
    with mock_ddms() as mocked:
        mocked.get(DATASPACES_URL, payload={"unexpected": True})
        result = await query_available_dataspaces()

    assert result["dataspaces"] == []
    assert result["error"]


@pytest.mark.asyncio
async def test_dataspace_files_returns_uri_and_name_for_each_resource():
    """Each resource is projected down to the two fields the tool declares."""
    payload = [
        {"uri": "eml:///resource(1)", "name": "Hugin", "extra": "dropped"},
        {"uri": "eml:///resource(2)", "name": "Skagerrak"},
    ]
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, payload=payload)
        result = await query_dataspace_files(DATASPACE)

    assert result == {
        "items": [
            {"uri": "eml:///resource(1)", "name": "Hugin"},
            {"uri": "eml:///resource(2)", "name": "Skagerrak"},
        ],
        "totalCount": 2,
    }


@pytest.mark.asyncio
async def test_dataspace_files_filters_on_uri_or_name():
    """item_pattern matches either field, and totalCount counts what came back."""
    payload = [
        {"uri": "eml:///resource(hugin-1)", "name": "First"},
        {"uri": "eml:///resource(2)", "name": "Hugin Second"},
        {"uri": "eml:///resource(3)", "name": "Skagerrak"},
    ]
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, payload=payload)
        result = await query_dataspace_files(DATASPACE, item_pattern="hugin")

    assert [i["name"] for i in result["items"]] == ["First", "Hugin Second"]
    assert result["totalCount"] == 2


@pytest.mark.asyncio
async def test_a_null_name_does_not_break_the_file_filter():
    """A resource with a JSON null name is still filterable on its uri."""
    payload = [{"uri": "eml:///resource(hugin-1)", "name": None}, {"uri": None}]
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, payload=payload)
        result = await query_dataspace_files(DATASPACE, item_pattern="hugin")

    assert result["items"] == [{"uri": "eml:///resource(hugin-1)", "name": ""}]


@pytest.mark.asyncio
async def test_a_dataspace_id_with_a_slash_stays_one_path_segment():
    """The id is percent-encoded, so the service sees one segment, not two."""
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, payload=[])
        await query_dataspace_files(DATASPACE)

        requested = [str(url) for _, url in (mocked.requests or {})]

    assert requested == [RESOURCES_URL]


@pytest.mark.asyncio
async def test_an_unknown_dataspace_is_reported_as_a_bad_argument():
    """A 404 for a dataspace the partition does not list is user error (400)."""
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, status=404, body="not found")
        mocked.get(DATASPACES_URL, payload=dataspace_uris("someone_else/data"))

        with pytest.raises(McpError) as excinfo:
            await query_dataspace_files(DATASPACE)

    assert excinfo.value.error.code == 400
    assert DATASPACE in str(excinfo.value)
    assert "someone_else/data" in str(excinfo.value)


@pytest.mark.asyncio
async def test_a_404_for_a_dataspace_that_exists_is_not_disguised_as_user_error():
    """The route being wrong must stay an API error, not become a bad argument."""
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, status=404, body="no such route")
        mocked.get(DATASPACES_URL, payload=dataspace_uris(DATASPACE))

        with pytest.raises(OSMCPAPIError) as excinfo:
            async with ReservoirDDMSClient() as client:
                await client.search_dataspace(DATASPACE)

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_a_dataspace_listing_that_fails_leaves_the_original_error_intact():
    """When the check itself cannot run, the caller still sees the real 404."""
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, status=404, body="not found")
        mocked.get(DATASPACES_URL, status=500, body="boom")

        with pytest.raises(OSMCPAPIError) as excinfo:
            async with ReservoirDDMSClient() as client:
                await client.search_dataspace(DATASPACE)

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_a_missing_dataspaces_route_surfaces_instead_of_reading_as_empty():
    """/dataspaces is a collection endpoint, so a 404 there is a real failure."""
    with mock_ddms() as mocked:
        mocked.get(DATASPACES_URL, status=404, body="not found")

        with pytest.raises(OSMCPAPIError) as excinfo:
            async with ReservoirDDMSClient() as client:
                await client.list_dataspaces()

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_the_client_raises_a_validation_error_the_tool_can_map():
    """The client-side error type is what handle_osdu_exceptions maps to 400."""
    with mock_ddms() as mocked:
        mocked.get(RESOURCES_PATTERN, status=404, body="not found")
        mocked.get(DATASPACES_URL, payload=dataspace_uris("demo"))

        with pytest.raises(OSMCPValidationError):
            async with ReservoirDDMSClient() as client:
                await client.search_dataspace(DATASPACE)
