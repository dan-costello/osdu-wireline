"""Behavior-driven tests for search tools following ADR-010."""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from aioresponses import aioresponses
from azure.core.credentials import AccessToken
from mcp.shared.exceptions import McpError

from osdu_wireline.shared.clients import BoundingBox, SearchClient
from osdu_wireline.tools.search import (
    query_seismic_datasets,
    query_seismic_trace_data,
    query_well_logs,
    query_wells,
)
from osdu_wireline.tools.search.query_seismic import (
    SeismicDatasetFields,
    SeismicTraceDataFields,
)
from osdu_wireline.tools.search.query_wells import WellboreChildFields, WellFields
from tests.conftest import AZURE_CREDENTIAL

GULF_OF_MEXICO = BoundingBox(
    min_latitude=25.0,
    max_latitude=30.0,
    min_longitude=-95.0,
    max_longitude=-90.0,
)

SEARCH_URL = "https://test.osdu.com/api/search/v2/query"

TEST_ENV = {
    "OSDU_MCP_SERVER_URL": "https://test.osdu.com",
    "OSDU_MCP_SERVER_DATA_PARTITION": "opendes",
    "AZURE_CLIENT_ID": "test-client-id",
    "AZURE_TENANT_ID": "test-tenant-id",
    "AZURE_CLIENT_SECRET": "test-secret",
}


class MockSearch:
    """Mock the search endpoint and capture the payloads sent to it."""

    def __init__(self, *payloads: dict) -> None:
        self._payloads = payloads
        self.requests: list[dict] = []

    def __enter__(self) -> "MockSearch":
        token = AccessToken(
            token="fake-token",
            expires_on=int((datetime.now() + timedelta(hours=1)).timestamp()),
        )

        self._env = patch.dict(os.environ, TEST_ENV)
        self._env.start()

        self._cred = patch(AZURE_CREDENTIAL)
        credential_class = self._cred.start()
        credential = MagicMock()
        credential.get_token.return_value = token
        credential_class.return_value = credential

        self._mocked = aioresponses()
        self._mocked.start()
        for payload in self._payloads:
            self._mocked.post(SEARCH_URL, payload=payload)
        return self

    def __exit__(self, *exc: object) -> bool:
        for (_method, url), calls in self._mocked.requests.items():
            if str(url).endswith("/query"):
                for call in calls:
                    body = call.kwargs.get("json")
                    if body is None and isinstance(call.kwargs.get("data"), str):
                        body = json.loads(call.kwargs["data"])
                    self.requests.append(body or {})
        self._mocked.stop()
        self._cred.stop()
        self._env.stop()
        return False


@pytest.mark.asyncio
async def test_query_wells_projects_declared_fields():
    """query_wells returns the fields its model declares, keyed by record id."""
    response = {
        "results": [
            {
                "id": "opendes:master-data--Well:123",
                "kind": "osdu:wks:master-data--Well:1.0.0",
                "data": {
                    "FacilityName": "Test Well",
                    "Source": "Public",
                    "SpatialLocation.Wgs84Coordinates": {"type": "Point"},
                    # Not declared by WellFields - must not leak through.
                    "SpudDate": "2020-01-01",
                },
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(response) as search:
        result = await query_wells(source="Public")

    well = result["wells"][0]
    assert result["totalCount"] == 1
    assert well["id"] == "opendes:master-data--Well:123"
    assert well["facility_name"] == "Test Well"
    assert well["spatial_location"] == {"type": "Point"}
    assert "SpudDate" not in well
    assert "spud_date" not in well

    # The tool asks OSDU for exactly the fields its model declares.
    assert search.requests[0]["returnedFields"] == WellFields.returned_fields()
    assert search.requests[0]["query"] == 'data.Source:"Public"'


@pytest.mark.asyncio
async def test_query_wells_handles_no_results():
    """An empty OSDU response yields an empty projection, not an error."""
    with MockSearch({"results": [], "totalCount": 0}):
        result = await query_wells(source="Nonexistent")

    assert result == {"wells": [], "totalCount": 0}


@pytest.mark.asyncio
async def test_query_well_logs_resolves_wellbores_first():
    """The wellbore-child tools resolve well IDs to wellbore IDs, then query."""
    wellbores = {
        "results": [{"id": "opendes:master-data--Wellbore:w1", "data": {}}],
        "totalCount": 1,
    }
    logs = {
        "results": [
            {
                "id": "opendes:work-product-component--WellLog:l1",
                "data": {"Name": "GR", "WellboreID": "opendes:...--Wellbore:w1"},
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(wellbores, logs) as search:
        result = await query_well_logs(well_ids=["opendes:master-data--Well:123"])

    assert result["results"][0]["name"] == "GR"
    assert len(search.requests) == 2
    assert "data.WellID" in search.requests[0]["query"]
    assert "opendes:master-data--Wellbore:w1" in search.requests[1]["query"]
    assert search.requests[1]["returnedFields"] == WellboreChildFields.returned_fields()


@pytest.mark.asyncio
async def test_query_well_logs_errors_when_no_wellbores():
    """A well with no wellbores is an error, not a silent empty result."""
    with MockSearch({"results": [], "totalCount": 0}):
        with pytest.raises(McpError):
            await query_well_logs(well_ids=["opendes:master-data--Well:123"])


@pytest.mark.asyncio
async def test_query_seismic_trace_data_projects_declared_fields():
    """Seismic trace data is projected through its declared field model."""
    response = {
        "results": [
            {
                "id": "opendes:work-product-component--SeismicTraceData:s1",
                "data": {
                    "Name": "AzureDisc",
                    "Datasets": ["opendes:dataset--FileCollection.SEGY:d1"],
                    "SpatialArea.Wgs84Coordinates": {"type": "Polygon"},
                    "InlineMin": 1,
                    "InlineMax": 500,
                },
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(response) as search:
        result = await query_seismic_trace_data(name="AzureDisc")

    trace = result["trace_data"][0]
    assert trace["name"] == "AzureDisc"
    assert trace["spatial_area"] == {"type": "Polygon"}
    assert trace["inline_max"] == 500
    assert trace["datasets"] == ["opendes:dataset--FileCollection.SEGY:d1"]
    assert (
        search.requests[0]["returnedFields"] == SeismicTraceDataFields.returned_fields()
    )


@pytest.mark.asyncio
async def test_query_seismic_datasets_resolves_file_sources():
    """Dataset files come back with FileSource resolved against the collection path."""
    response = {
        "results": [
            {
                "id": "opendes:dataset--FileCollection.Bluware.OpenVDS:d1",
                "data": {
                    "DatasetProperties.FileCollectionPath": "sd://opendes/landmarkvds/",
                    "DatasetProperties.FileSourceInfos": [
                        {
                            "FileSource": "sd://opendes/landmarkvds/00Azure",
                            "Name": "00Azure",
                        }
                    ],
                },
            },
            {
                "id": "opendes:dataset--FileCollection.SEGY:d2",
                "data": {
                    "DatasetProperties.FileCollectionPath": "sd://opendes/segy",
                    "DatasetProperties.FileSourceInfos": [
                        {"FileSource": "/a.segy", "Name": "a"},
                        {"Name": "entry with no FileSource"},
                    ],
                },
            },
        ],
        "totalCount": 2,
    }

    with MockSearch(response) as search:
        result = await query_seismic_datasets(dataset_ids=["d1", "d2"])

    assert result["datasets"] == [
        {
            "id": "opendes:dataset--FileCollection.Bluware.OpenVDS:d1",
            "file_source": "sd://opendes/landmarkvds/00Azure",
            "name": "00Azure",
            "file_size": None,
            "domain": None,
        },
        {
            "id": "opendes:dataset--FileCollection.SEGY:d2",
            "file_source": "sd://opendes/segy/a.segy",
            "name": "a",
            "file_size": None,
            "domain": None,
        },
    ]
    assert (
        search.requests[0]["returnedFields"] == SeismicDatasetFields.returned_fields()
    )


@pytest.mark.asyncio
async def test_query_seismic_datasets_accepts_nested_properties():
    """OSDU may return properties nested rather than flattened onto dotted keys."""
    response = {
        "results": [
            {
                "id": "opendes:dataset--FileCollection.SEGY:d3",
                "data": {
                    "DatasetProperties": {
                        "FileCollectionPath": "sd://opendes/segy",
                        "FileSourceInfos": [{"FileSource": "/b.segy", "Name": "b"}],
                    }
                },
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(response):
        result = await query_seismic_datasets(dataset_ids=["d3"])

    assert result["datasets"][0]["file_source"] == "sd://opendes/segy/b.segy"


@pytest.mark.asyncio
async def test_query_seismic_datasets_requires_ids():
    """An empty ID list is rejected rather than sent as a malformed query."""
    with pytest.raises(McpError):
        await query_seismic_datasets(dataset_ids=[])


@pytest.mark.asyncio
async def test_dataset_ids_are_stripped_of_their_version_segment():
    """Trace records reference datasets in the version-qualified form.

    OSDU leaves the version empty when unpinned, so the reference arrives with a
    bare trailing colon. The index stores the unversioned id, and querying the
    qualified form matches nothing.
    """
    unversioned = (
        "opendes:dataset--FileCollection.Bluware.OpenVDS:"
        "c81d04ebe8984a39a61112be64856ed5"
    )

    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_seismic_datasets(dataset_ids=[f"{unversioned}:"])

    assert search.requests[0]["query"] == f'id:("{unversioned}")'


@pytest.mark.asyncio
async def test_pinned_versions_are_stripped_but_ids_are_left_intact():
    """A numeric version is dropped; anything else is left alone."""
    base = "opendes:dataset--FileCollection.SEGY:abc"

    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_seismic_datasets(dataset_ids=[f"{base}:1699999999999", base])

    assert search.requests[0]["query"] == f'id:("{base}" OR "{base}")'


@pytest.mark.asyncio
async def test_dataset_files_surface_size_and_domain():
    """FileSourceInfos already carries size and domain - do not discard them."""
    response = {
        "results": [
            {
                "id": "opendes:dataset--FileCollection.Bluware.OpenVDS:d1",
                "data": {
                    "DatasetProperties.FileCollectionPath": "sd://opendes/dgi/",
                    "DatasetProperties.FileSourceInfos": [
                        {
                            "FileSource": "sd://opendes/dgi/experiment.vds",
                            "Name": None,
                            "FileSize": 1923578118,
                            "Domain": "Time",
                        }
                    ],
                },
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(response):
        result = await query_seismic_datasets(dataset_ids=["d1"])

    assert result["datasets"][0] == {
        "id": "opendes:dataset--FileCollection.Bluware.OpenVDS:d1",
        "file_source": "sd://opendes/dgi/experiment.vds",
        "name": None,
        "file_size": 1923578118,
        "domain": "Time",
    }


@pytest.mark.asyncio
async def test_query_seismic_datasets_names_the_authority_literally():
    """A wildcard authority segment matches nothing on the index.

    Verified against a payload known to return a record: replacing 'osdu' with
    '*' in the kind is the difference between one result and zero.
    """
    record = (
        "opendes:dataset--FileCollection.Bluware.OpenVDS:"
        "c81d04ebe8984a39a61112be64856ed5"
    )

    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_seismic_datasets(dataset_ids=[record])

    assert search.requests[0]["kind"] == [
        "osdu:wks:dataset--FileCollection.Bluware.OpenVDS:*",
        "osdu:wks:dataset--FileCollection.SEGY:*",
    ]
    assert search.requests[0]["query"] == f'id:("{record}")'


# --- Spatial filtering -------------------------------------------------------


def test_spatial_field_is_derived_per_kind():
    """Each model resolves its own geometry path; kinds without one return None."""
    assert WellFields.spatial_field() == "data.SpatialLocation.Wgs84Coordinates"
    assert SeismicTraceDataFields.spatial_field() == "data.SpatialArea.Wgs84Coordinates"
    assert SeismicDatasetFields.spatial_field() is None
    assert WellboreChildFields.spatial_field() is None


@pytest.mark.asyncio
async def test_seismic_bounding_box_filters_on_spatial_area():
    """Seismic geometry lives at SpatialArea, not the well's SpatialLocation."""
    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_seismic_trace_data(bounding_box=GULF_OF_MEXICO)

    spatial_filter = search.requests[0]["spatialFilter"]
    assert spatial_filter["field"] == "data.SpatialArea.Wgs84Coordinates"
    assert spatial_filter["byBoundingBox"] == {
        "topLeft": {"lat": 30.0, "lon": -95.0},
        "bottomRight": {"lat": 25.0, "lon": -90.0},
    }


@pytest.mark.asyncio
async def test_wells_bounding_box_still_filters_on_spatial_location():
    """Regression guard: parameterising the field must not change well search."""
    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_wells(bounding_box=GULF_OF_MEXICO)

    assert (
        search.requests[0]["spatialFilter"]["field"]
        == "data.SpatialLocation.Wgs84Coordinates"
    )


@pytest.mark.asyncio
async def test_search_without_spatial_field_is_rejected():
    """A bounding box that cannot say what to filter on must fail loudly."""
    client = SearchClient.__new__(SearchClient)
    with pytest.raises(ValueError, match="spatial_field is required"):
        await client.search_query(
            kind="*:wks:master-data--Well:*",
            returned_fields=["id"],
            bounding_box=GULF_OF_MEXICO,
        )


# --- Query term escaping -----------------------------------------------------


@pytest.mark.asyncio
async def test_name_search_uses_an_unquoted_wildcard():
    """A quoted value is a phrase, so the wildcards must sit outside quotes."""
    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_seismic_trace_data(name="AzureDisc")

    assert search.requests[0]["query"] == "data.Name:(*AzureDisc*)"


@pytest.mark.asyncio
async def test_name_search_escapes_caller_wildcards_and_spaces():
    """The only wildcards in the query are the two the tool adds."""
    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_seismic_trace_data(name="Azure Disc*")

    query = search.requests[0]["query"]
    assert query == "data.Name:(*Azure\\ Disc\\**)"
    # Two unescaped wildcards: the leading and trailing ones.
    assert query.count("*") - query.count("\\*") == 2


@pytest.mark.asyncio
async def test_query_terms_cannot_break_out_of_their_quotes():
    """A term containing a quote is escaped rather than closing the phrase."""
    hostile = 'Public" OR data.Source:"'
    with MockSearch({"results": [], "totalCount": 0}) as search:
        await query_wells(source=hostile)

    query = search.requests[0]["query"]
    assert query == 'data.Source:"Public\\" OR data.Source:\\""'
    # Every quote is either a delimiter or escaped - none can terminate early.
    assert query.count('"') - query.count('\\"') == 2


@pytest.mark.asyncio
async def test_id_lists_are_quoted_per_id():
    """ID lists are built by quoting each ID, not by splicing a delimiter."""
    with MockSearch({"results": [], "totalCount": 0}) as search:
        with pytest.raises(McpError):
            await query_well_logs(well_ids=["opendes:well:1", "opendes:well:2"])

    assert (
        search.requests[0]["query"]
        == 'data.WellID: ("opendes:well:1" OR "opendes:well:2")'
    )
