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
from osdu_wireline.shared.env import setting_names
from osdu_wireline.tools.search import (
    query_seismic_datasets,
    query_seismic_trace_data,
    query_well_logs,
    query_well_marker_sets,
    query_well_trajectories,
    query_wells,
)
from osdu_wireline.tools.search._reference import (
    BASIN,
    COUNTRY,
    FIELD,
    clear_reference_cache,
)
from osdu_wireline.tools.search.query_seismic import (
    SeismicDatasetFields,
    SeismicTraceDataFields,
)
from osdu_wireline.tools.search.query_wells import (
    MarkerSetFields,
    WellboreChildFields,
    WellboreRefFields,
    WellFields,
)
from tests.conftest import AZURE_CREDENTIAL

GULF_OF_MEXICO = BoundingBox(
    min_latitude=25.0,
    max_latitude=30.0,
    min_longitude=-95.0,
    max_longitude=-90.0,
)

SEARCH_URL = "https://test.osdu.com/api/search/v2/query"

WELLBORE_KIND = "osdu:wks:master-data--Wellbore:*"


def wellbores(*well_ids: str, total: int | None = None) -> dict:
    """A wellbore search response: one wellbore hanging off each well id."""
    return {
        "results": [
            {
                "id": f"opendes:master-data--Wellbore:wb{index}",
                "data": {"WellID": well_id},
            }
            for index, well_id in enumerate(well_ids)
        ],
        "totalCount": len(well_ids) if total is None else total,
    }


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
        # Reference lookups are memoised for the life of the process, so a
        # test's countries or basins must not answer an earlier test's.
        clear_reference_cache()
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
async def test_query_well_marker_sets_returns_the_picks_themselves():
    """A marker set comes back with its markers, not just a record id."""
    wellbores = {
        "results": [{"id": "opendes:master-data--Wellbore:490250953400", "data": {}}],
        "totalCount": 1,
    }
    marker_sets = {
        "results": [
            {
                "id": "opendes:work-product-component--WellboreMarkerSet:490250953400",
                "data": {
                    "WellboreID": "opendes:master-data--Wellbore:490250953400:",
                    "Markers": [
                        {
                            "MarkerMeasuredDepth": 822.9630480000001,
                            "MarkerName": "F2WC",
                        },
                        {"MarkerMeasuredDepth": 693.35904, "MarkerName": "F1WC"},
                    ],
                },
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(wellbores, marker_sets) as search:
        result = await query_well_marker_sets(
            well_ids=["opendes:master-data--Well:490250953400"]
        )

    marker_set = result["results"][0]
    assert marker_set["wellbore_id"] == "opendes:master-data--Wellbore:490250953400:"
    assert marker_set["markers"] == [
        {
            "marker_name": "F2WC",
            "marker_measured_depth": 822.9630480000001,
            "marker_type_id": None,
            "observation_number": None,
            "interpreter_name": None,
        },
        {
            "marker_name": "F1WC",
            "marker_measured_depth": 693.35904,
            "marker_type_id": None,
            "observation_number": None,
            "interpreter_name": None,
        },
    ]

    # The marker set asks for its own fields - the shared child projection would
    # not have requested the picks at all.
    assert search.requests[1]["returnedFields"] == MarkerSetFields.returned_fields()
    assert "data.Markers" in search.requests[1]["returnedFields"]


@pytest.mark.asyncio
async def test_marker_fields_the_model_does_not_declare_are_dropped():
    """A pick carries only the fields MarkerSetFields declares."""
    wellbores = {
        "results": [{"id": "opendes:master-data--Wellbore:w1", "data": {}}],
        "totalCount": 1,
    }
    marker_sets = {
        "results": [
            {
                "id": "opendes:work-product-component--WellboreMarkerSet:m1",
                "data": {
                    "Markers": [
                        {
                            "MarkerName": "B1",
                            "MarkerMeasuredDepth": 767.4711599999999,
                            "MarkerTypeID": "opendes:reference-data--MarkerType:Fault:",
                            "ObservationNumber": 1,
                            "InterpreterName": "A. Geologist",
                            "SurfaceDipAngle": 3.5,
                        }
                    ]
                },
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(wellbores, marker_sets):
        result = await query_well_marker_sets(well_ids=["opendes:master-data--Well:1"])

    marker = result["results"][0]["markers"][0]
    assert marker == {
        "marker_name": "B1",
        "marker_measured_depth": 767.4711599999999,
        "marker_type_id": "opendes:reference-data--MarkerType:Fault:",
        "observation_number": 1,
        "interpreter_name": "A. Geologist",
    }
    assert "SurfaceDipAngle" not in marker
    assert "surface_dip_angle" not in marker


@pytest.mark.asyncio
async def test_the_other_wellbore_child_tools_keep_the_shared_projection():
    """Only marker sets ask for markers - logs and trajectories are unchanged."""
    assert WellboreChildFields.returned_fields() == [
        "id",
        "data.Name",
        "data.WellboreID",
        "data.TechnicalAssurances",
    ]
    assert MarkerSetFields.returned_fields() == [
        *WellboreChildFields.returned_fields(),
        "data.Markers",
    ]


@pytest.mark.asyncio
async def test_query_well_logs_is_empty_when_there_are_no_wellbores():
    """Filters selecting no wellbores select no logs - an empty result, not an error."""
    with MockSearch({"results": [], "totalCount": 0}) as search:
        result = await query_well_logs(well_ids=["opendes:master-data--Well:123"])

    # The wellbore search was the only request - nothing to look up logs against.
    assert len(search.requests) == 1
    assert result == {"results": [], "totalCount": 0}


@pytest.mark.asyncio
async def test_an_empty_child_result_still_reports_what_the_field_resolved_to():
    """The report is what explains an empty result - it survives having no wellbores."""
    with MockSearch(SLEIPNER_FIELDS, {"results": [], "totalCount": 0}) as search:
        result = await query_well_logs(field="SLEIPNER")

    # The lookup and the wellbore search; no components to look for after that.
    assert len(search.requests) == 2
    assert result["results"] == []
    assert result["totalCount"] == 0
    assert result["resolved_field"]["status"] == "ambiguous"


@pytest.mark.asyncio
async def test_a_child_tool_takes_a_field_instead_of_well_ids():
    """A field selects the wellbores directly - no well IDs needed to get there."""
    found = wellbores("opendes:master-data--Well:1")
    marker_sets = {
        "results": [
            {
                "id": "opendes:work-product-component--WellboreMarkerSet:m1",
                "data": {"Markers": [{"MarkerName": "B1"}]},
            }
        ],
        "totalCount": 1,
    }

    with MockSearch(FIELDS, found, marker_sets) as search:
        result = await query_well_marker_sets(field="D15a-A")

    assert result["results"][0]["markers"][0]["marker_name"] == "B1"
    assert len(search.requests) == 3

    # The field narrows the wellbores; no well IDs were given, so none are asked for.
    wellbore_search = search.requests[1]
    assert wellbore_search["kind"] == WELLBORE_KIND
    assert wellbore_search["query"] == (
        'nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:D15a-A"))'
    )
    assert "data.WellID" not in wellbore_search["query"]

    # The components carry no field of their own, so they are found by wellbore.
    assert search.requests[2]["query"] == (
        'data.WellboreID: ("opendes:master-data--Wellbore:wb0")'
    )


@pytest.mark.asyncio
async def test_well_ids_and_a_field_narrow_to_the_wellbores_that_are_both():
    """Given both, the wellbore search ANDs them rather than picking one."""
    found = wellbores("opendes:master-data--Well:1")

    with MockSearch(FIELDS, found, {"results": [], "totalCount": 0}) as search:
        await query_well_logs(well_ids=["opendes:master-data--Well:1"], field="D15a-A")

    assert search.requests[1]["query"] == (
        'data.WellID: ("opendes:master-data--Well:1") AND '
        'nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:D15a-A"))'
    )


@pytest.mark.asyncio
async def test_a_child_tool_given_neither_filter_is_an_error():
    """An unfiltered child search would return an arbitrary slice of the instance."""
    with pytest.raises(McpError):
        await query_well_trajectories()


@pytest.mark.asyncio
async def test_a_child_tool_merges_a_short_candidate_list_too():
    """The child tools resolve a field through the same merge the well search does."""
    found = wellbores("opendes:master-data--Well:1")

    with MockSearch(SLEIPNER_FIELDS, found, {"results": [], "totalCount": 0}) as search:
        result = await query_well_logs(field="SLEIPNER")

    assert search.requests[1]["query"] == (
        'nested(data.GeoContexts, (FieldID:("opendes:master-data--Field:Sleipner_Ost"'
        ' OR "opendes:master-data--Field:Sleipner_Vest"'
        ' OR "opendes:master-data--Field:Sleipner_Alpha_North")))'
    )
    assert result["resolved_field"]["status"] == "ambiguous"


@pytest.mark.asyncio
async def test_a_child_tool_reports_an_unresolved_field_instead_of_searching():
    """An unusable field is handed back the way query_wells hands one back."""
    with MockSearch(FIELDS) as search:
        result = await query_well_marker_sets(field="Ekofisk")

    # The lookup was the only request - no wellbores, no marker sets.
    assert len(search.requests) == 1
    assert result["results"] == []
    assert result["totalCount"] == 0
    assert result["resolved_field"]["status"] == "not_found"


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
    assert MarkerSetFields.spatial_field() is None


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
        await query_well_logs(well_ids=["opendes:well:1", "opendes:well:2"])

    assert (
        search.requests[0]["query"]
        == 'data.WellID: ("opendes:well:1" OR "opendes:well:2")'
    )


# --- Reference (country and basin) resolution -----------------------------------------------------
#
# Resolution is exercised through the tool: the first search is the reference
# lookup, the second (when the name resolves) is the well query itself.

COUNTRIES = {
    "results": [
        {
            "data": {"GeoPoliticalEntityName": "Australia"},
            "id": "opendes:master-data--GeoPoliticalEntity:38fb7c60",
        },
        {
            "data": {
                "NameAliases": [
                    {"AliasName": "NO"},
                    {"AliasName": "NOR"},
                    {"AliasName": "578"},
                ],
                "GeoPoliticalEntityName": "Norway",
            },
            "id": "opendes:master-data--GeoPoliticalEntity:Norway",
        },
        {
            "data": {"GeoPoliticalEntityName": "BRASIL"},
            "id": "opendes:master-data--GeoPoliticalEntity:58305ab9",
        },
        {
            "data": {"GeoPoliticalEntityName": "UNKNOWN"},
            "id": "opendes:master-data--GeoPoliticalEntity:199dc51d",
        },
        {
            "data": {"GeoPoliticalEntityName": "United Kingdom"},
            "id": "opendes:master-data--GeoPoliticalEntity:2afc9d6f",
        },
        {
            "data": {"GeoPoliticalEntityName": "United States"},
            "id": "opendes:master-data--GeoPoliticalEntity:UnitedStates_Country",
        },
        {
            "data": {"GeoPoliticalEntityName": "Netherlands"},
            "id": "opendes:master-data--GeoPoliticalEntity:Netherlands_Country",
        },
    ],
    "aggregations": [],
    "phraseSuggestions": [],
    "totalCount": 7,
}

NO_WELLS = {"results": [], "totalCount": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("given", "expected_id"),
    [
        # An exact name, however the caller cased it.
        ("Norway", "opendes:master-data--GeoPoliticalEntity:Norway"),
        ("norway", "opendes:master-data--GeoPoliticalEntity:Norway"),
        ("brasil", "opendes:master-data--GeoPoliticalEntity:58305ab9"),
        # An alias, which OSDU stores nested under NameAliases.
        ("NOR", "opendes:master-data--GeoPoliticalEntity:Norway"),
        ("no", "opendes:master-data--GeoPoliticalEntity:Norway"),
        ("578", "opendes:master-data--GeoPoliticalEntity:Norway"),
        # Only the normalizing pass survives stray whitespace or punctuation.
        ("  united   kingdom  ", "opendes:master-data--GeoPoliticalEntity:2afc9d6f"),
        (
            "United States.",
            "opendes:master-data--GeoPoliticalEntity:UnitedStates_Country",
        ),
    ],
)
async def test_query_wells_resolves_country_name_to_id(given: str, expected_id: str):
    """A country name, an alias, or a loosely typed variant resolves to a record id."""
    with MockSearch(COUNTRIES, NO_WELLS) as search:
        result = await query_wells(country=given)

    # The resolved id - not the caller's text - is what filters the wells.
    assert len(search.requests) == 2
    assert search.requests[1]["query"] == (
        f'nested(data.GeoContexts, (GeoPoliticalEntityID:"{expected_id}"))'
    )
    assert result == {"wells": [], "totalCount": 0}


@pytest.mark.asyncio
async def test_query_wells_prefers_an_exact_name_over_another_countrys_alias():
    """Matching runs name-first, so an exact name beats an alias someone else claims."""
    countries = {
        "results": [
            {
                "data": {"GeoPoliticalEntityName": "Norway"},
                "id": "opendes:master-data--GeoPoliticalEntity:Norway",
            },
            {
                "data": {
                    "GeoPoliticalEntityName": "Nordic Union",
                    "NameAliases": [{"AliasName": "Norway"}],
                },
                "id": "opendes:master-data--GeoPoliticalEntity:Nordic",
            },
        ],
        "totalCount": 2,
    }

    with MockSearch(countries, NO_WELLS) as search:
        await query_wells(country="Norway")

    assert (
        "opendes:master-data--GeoPoliticalEntity:Norway" in search.requests[1]["query"]
    )


@pytest.mark.asyncio
async def test_query_wells_reports_an_unknown_country_instead_of_searching():
    """An unmatched name returns the candidate list rather than querying wells."""
    with MockSearch(COUNTRIES) as search:
        result = await query_wells(country="Atlantis")

    # The country lookup was the only request - no wells were searched for.
    assert len(search.requests) == 1
    assert result["wells"] == []
    assert result["totalCount"] == 0
    resolved = result["resolved_country"]
    assert resolved["status"] == "not_found"
    assert resolved["input"] == "Atlantis"
    assert "Norway" in resolved["candidates"]
    assert len(resolved["candidates"]) == 7


@pytest.mark.asyncio
async def test_a_short_candidate_list_is_searched_rather_than_handed_back():
    """Two records sharing a name are searched together, and reported as both.

    A caller given the pair just runs both and merges, so the search does that
    itself - the candidates still come back, so the caller can see what it
    covered.
    """
    countries = {
        "results": [
            {
                "data": {"GeoPoliticalEntityName": "Norway"},
                "id": "opendes:master-data--GeoPoliticalEntity:Norway",
            },
            {
                "data": {"GeoPoliticalEntityName": "norway"},
                "id": "opendes:master-data--GeoPoliticalEntity:duplicate",
            },
        ],
        "totalCount": 2,
    }
    wells = {
        "results": [{"id": "opendes:master-data--Well:1", "data": {}}],
        "totalCount": 1,
    }

    with MockSearch(countries, wells) as search:
        result = await query_wells(country="Norway")

    # Both ids in one clause, and the wells actually came back.
    assert len(search.requests) == 2
    assert search.requests[1]["query"] == (
        "nested(data.GeoContexts, (GeoPoliticalEntityID:"
        '("opendes:master-data--GeoPoliticalEntity:Norway" OR '
        '"opendes:master-data--GeoPoliticalEntity:duplicate")))'
    )
    assert result["totalCount"] == 1
    assert len(result["wells"]) == 1

    resolved = result["resolved_country"]
    assert resolved["status"] == "ambiguous"
    assert resolved["input"] == "Norway"
    assert [c["id"] for c in resolved["candidates"]] == [
        "opendes:master-data--GeoPoliticalEntity:Norway",
        "opendes:master-data--GeoPoliticalEntity:duplicate",
    ]


@pytest.mark.asyncio
async def test_a_long_candidate_list_is_still_handed_back_unsearched():
    """Past the merge threshold the union is no longer a search anyone meant."""
    countries = {
        "results": [
            {
                "data": {"GeoPoliticalEntityName": f"Norway {index}"},
                "id": f"opendes:master-data--GeoPoliticalEntity:{index}",
            }
            for index in range(6)
        ],
        "totalCount": 6,
    }

    with MockSearch(countries) as search:
        result = await query_wells(country="Norway")

    # The lookup was the only request - no wells were searched for.
    assert len(search.requests) == 1
    assert result["wells"] == []
    assert result["totalCount"] == 0
    assert result["resolved_country"]["status"] == "ambiguous"
    assert result["resolved_country"]["candidate_count"] == 6


@pytest.mark.asyncio
async def test_query_wells_skips_country_records_without_a_name():
    """A GeoPoliticalEntity with no name is dropped, not offered as a candidate."""
    countries = {
        "results": [
            {"data": {}, "id": "opendes:master-data--GeoPoliticalEntity:nameless"},
            {
                "data": {"GeoPoliticalEntityName": "Norway"},
                "id": "opendes:master-data--GeoPoliticalEntity:Norway",
            },
        ],
        "totalCount": 2,
    }

    with MockSearch(countries):
        result = await query_wells(country="Atlantis")

    assert result["resolved_country"]["candidates"] == ["Norway"]


@pytest.mark.asyncio
async def test_query_wells_combines_a_resolved_country_with_the_other_filters():
    """The country clause is ANDed with the tool's other filters."""
    with MockSearch(COUNTRIES, NO_WELLS) as search:
        await query_wells(
            country="Norway",
            basin="opendes:master-data--Basin:GulfOfMexico",
            source="Public",
        )

    assert search.requests[1]["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:Norway")) AND '
        'nested(data.GeoContexts, (BasinID:"opendes:master-data--Basin:GulfOfMexico")) '
        "AND "
        'data.Source:"Public"'
    )


@pytest.mark.asyncio
async def test_query_wells_requires_a_data_partition_to_resolve_a_country():
    """Without a partition there is no country type to look up, so the tool errors."""
    with MockSearch(COUNTRIES):
        with patch.dict(os.environ):
            for name in setting_names("OSDU_DATA_PARTITION"):
                os.environ.pop(name, None)
            with pytest.raises(McpError):
                await query_wells(country="Norway")


@pytest.mark.asyncio
async def test_query_wells_looks_the_countries_up_once_per_partition():
    """The country list is reference data, so a second search reuses it."""
    with MockSearch(COUNTRIES, NO_WELLS, NO_WELLS) as search:
        await query_wells(country="Norway")
        await query_wells(country="Australia")

    # One lookup, then a well query per call - the second call skips the lookup.
    assert len(search.requests) == 3
    assert "GeoPoliticalEntityTypeID" in search.requests[0]["query"]
    assert all("GeoContexts" in request["query"] for request in search.requests[1:])


@pytest.mark.asyncio
async def test_query_wells_takes_a_country_record_id_as_given():
    """A caller holding the id already needs no lookup - versioned form included."""
    with MockSearch(NO_WELLS, NO_WELLS) as search:
        await query_wells(country="opendes:master-data--GeoPoliticalEntity:Norway")
        # OSDU writes references with an empty trailing version segment.
        await query_wells(country="opendes:master-data--GeoPoliticalEntity:Norway:")

    assert len(search.requests) == 2
    expected = (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:Norway"))'
    )
    assert [request["query"] for request in search.requests] == [expected, expected]


@pytest.mark.asyncio
async def test_query_wells_looks_country_records_up_by_their_reference_type():
    """The lookup asks for country entities, and for the fields matching needs."""
    with MockSearch(COUNTRIES, NO_WELLS) as search:
        await query_wells(country="Norway")

    lookup = search.requests[0]
    assert lookup["kind"] == COUNTRY.kind
    assert lookup["query"] == (
        'data.GeoPoliticalEntityTypeID:"opendes:reference-data'
        '--GeoPoliticalEntityType:Country"'
    )
    assert lookup["returnedFields"] == COUNTRY.returned_fields


BASINS = {
    "results": [
        {
            "data": {"BasinName": "Powder River"},
            "id": "opendes:master-data--Basin:Powder_River_Basin",
        },
        {
            "data": {"BasinName": "Illinois"},
            "id": "opendes:master-data--Basin:Illinois_Basin",
        },
        {
            "data": {"BasinName": "NorthSeaBasin"},
            "id": "opendes:master-data--Basin:NorthSeaBasin",
        },
        {
            "data": {"BasinName": "Santos Basin Test"},
            "id": "opendes:master-data--Basin:test-map-basin-001",
        },
        {
            "data": {"BasinName": "UNKNOWN"},
            "id": "opendes:master-data--Basin:1522b609",
        },
    ],
    "aggregations": [],
    "phraseSuggestions": [],
    "totalCount": 5,
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("given", "expected_id"),
    [
        ("Powder River", "opendes:master-data--Basin:Powder_River_Basin"),
        ("illinois", "opendes:master-data--Basin:Illinois_Basin"),
        ("santos basin test", "opendes:master-data--Basin:test-map-basin-001"),
        # Normalizing collapses the spacing, but not a name run together.
        ("  Santos   Basin Test.", "opendes:master-data--Basin:test-map-basin-001"),
    ],
)
async def test_query_wells_resolves_basin_name_to_id(given: str, expected_id: str):
    """A basin name resolves through the same matchers a country name does."""
    with MockSearch(BASINS, NO_WELLS) as search:
        await query_wells(basin=given)

    assert len(search.requests) == 2
    assert search.requests[1]["query"] == (
        f'nested(data.GeoContexts, (BasinID:"{expected_id}"))'
    )


@pytest.mark.asyncio
async def test_query_wells_looks_basins_up_by_kind_alone():
    """A Basin kind holds only basins, so the lookup needs no type filter."""
    with MockSearch(BASINS, NO_WELLS) as search:
        await query_wells(basin="Illinois")

    lookup = search.requests[0]
    assert lookup["kind"] == BASIN.kind
    assert lookup["query"] == ""
    # Basins carry no aliases, so none are asked for.
    assert lookup["returnedFields"] == ["id", "data.BasinName"]
    assert BASIN.returned_fields == ["id", "data.BasinName"]


@pytest.mark.asyncio
async def test_query_wells_reports_an_unknown_basin_under_its_own_key():
    """An unmatched basin is reported like an unmatched country, keyed by entity."""
    with MockSearch(BASINS) as search:
        result = await query_wells(basin="Atlantis")

    assert len(search.requests) == 1
    assert result["resolved_basin"]["status"] == "not_found"
    assert "Powder River" in result["resolved_basin"]["candidates"]
    assert "resolved_country" not in result


@pytest.mark.asyncio
async def test_query_wells_resolves_country_and_basin_names_together():
    """Both names resolve, each against its own kind, before the wells are searched."""
    with MockSearch(COUNTRIES, BASINS, NO_WELLS) as search:
        await query_wells(country="NOR", basin="Illinois")

    assert len(search.requests) == 3
    assert search.requests[0]["kind"] == COUNTRY.kind
    assert search.requests[1]["kind"] == BASIN.kind
    assert search.requests[2]["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:Norway")) AND '
        'nested(data.GeoContexts, (BasinID:"opendes:master-data--Basin:Illinois_Basin"))'
    )


@pytest.mark.asyncio
async def test_query_wells_does_not_look_up_a_basin_it_will_not_use():
    """An unresolved country short-circuits: the basin is never looked up."""
    with MockSearch(COUNTRIES) as search:
        result = await query_wells(country="Atlantis", basin="Illinois")

    assert len(search.requests) == 1
    assert result["resolved_country"]["status"] == "not_found"


@pytest.mark.asyncio
async def test_reference_lookups_are_cached_separately():
    """Countries and basins share a cache, so one must not answer for the other."""
    with MockSearch(COUNTRIES, BASINS, NO_WELLS, NO_WELLS) as search:
        await query_wells(country="Norway", basin="Illinois")
        await query_wells(country="Australia", basin="NorthSeaBasin")

    # Two lookups and two well queries - the second call reuses both lookups.
    assert len(search.requests) == 4
    assert search.requests[3]["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:38fb7c60")) AND '
        'nested(data.GeoContexts, (BasinID:"opendes:master-data--Basin:NorthSeaBasin"))'
    )


FIELDS = {
    "results": [
        {
            "data": {"FieldName": "D15a-A"},
            "id": "opendes:master-data--Field:D15a-A",
        },
        {
            "data": {"FieldName": "K15-FJ"},
            "id": "opendes:master-data--Field:K15-FJ",
        },
        {
            "data": {"FieldName": "P12-SW"},
            "id": "opendes:master-data--Field:P12-SW",
        },
    ],
    "aggregations": [],
    "phraseSuggestions": [],
    "totalCount": 3,
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("given", "expected_id"),
    [
        ("D15a-A", "opendes:master-data--Field:D15a-A"),
        ("k15-fj", "opendes:master-data--Field:K15-FJ"),
        # Normalizing drops the hyphen without leaving a space behind, so the
        # run-together spelling matches - "P12 SW" would not.
        ("p12sw", "opendes:master-data--Field:P12-SW"),
    ],
)
async def test_query_wells_resolves_field_name_to_id(given: str, expected_id: str):
    """A field name resolves through the same matchers a country or basin does."""
    found = wellbores("opendes:master-data--Well:1")
    with MockSearch(FIELDS, found, NO_WELLS) as search:
        await query_wells(field=given)

    # Lookup, then the wellbores in the field, then the wells they hang off.
    assert len(search.requests) == 3
    assert search.requests[0]["kind"] == FIELD.kind
    assert search.requests[0]["query"] == ""
    assert search.requests[0]["returnedFields"] == ["id", "data.FieldName"]
    assert search.requests[1]["kind"] == WELLBORE_KIND
    assert search.requests[1]["query"] == (
        f'nested(data.GeoContexts, (FieldID:"{expected_id}"))'
    )


@pytest.mark.asyncio
async def test_query_wells_filters_wells_by_the_wellbores_in_the_field():
    """FieldID is recorded on the wellbore, so the Well query cannot carry it.

    The regression this guards: a `nested(data.GeoContexts, (FieldID:...))`
    clause on master-data--Well matches nothing and returns zero wells with
    nothing to explain them.
    """
    found = wellbores(
        "opendes:master-data--Well:1",
        "opendes:master-data--Well:2",
    )

    with MockSearch(FIELDS, found, NO_WELLS) as search:
        await query_wells(
            field="D15a-A",
            country="opendes:master-data--GeoPoliticalEntity:Norway",
        )

    wellbore_search, well_search = search.requests[1], search.requests[2]

    # The field is applied to the wellbores...
    assert wellbore_search["kind"] == WELLBORE_KIND
    assert wellbore_search["query"] == (
        'nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:D15a-A"))'
    )
    # ...and only their WellID is read back, not a whole wellbore.
    assert wellbore_search["returnedFields"] == WellboreRefFields.returned_fields()
    assert wellbore_search["returnedFields"] == ["id", "data.WellID"]

    # ...and reaches the wells as an id filter, ANDed with the well-level country.
    assert "master-data--Well" in well_search["kind"]
    assert well_search["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:Norway")) AND '
        'id: ("opendes:master-data--Well:1" OR "opendes:master-data--Well:2")'
    )
    assert "FieldID" not in well_search["query"]


@pytest.mark.asyncio
async def test_wells_named_by_more_than_one_wellbore_are_filtered_on_once():
    """A well with several wellbores in the field is still one id in the clause."""
    same_well = wellbores(
        "opendes:master-data--Well:1",
        # OSDU writes the reference with an empty trailing version segment, so
        # the two spellings have to normalise to one id before deduplication.
        "opendes:master-data--Well:1:",
        "opendes:master-data--Well:2",
    )

    with MockSearch(FIELDS, same_well, NO_WELLS) as search:
        await query_wells(field="D15a-A")

    assert search.requests[2]["query"] == (
        'id: ("opendes:master-data--Well:1" OR "opendes:master-data--Well:2")'
    )


@pytest.mark.asyncio
async def test_a_field_with_no_wellbores_returns_no_wells_rather_than_all_of_them():
    """An empty id filter would match everything, so the wells are never queried."""
    with MockSearch(FIELDS, {"results": [], "totalCount": 0}) as search:
        result = await query_wells(field="D15a-A")

    assert result == {"wells": [], "totalCount": 0}
    assert len(search.requests) == 2


@pytest.mark.asyncio
async def test_the_wellbores_in_a_field_are_read_past_the_first_page():
    """A full page means there may be more, so the wellbore search keeps reading."""
    first_page = wellbores(
        # Many wellbores, far fewer wells - a well can have several in a field.
        *[f"opendes:master-data--Well:{index % 500:04d}" for index in range(1000)],
        total=1002,
    )
    second_page = wellbores(
        "opendes:master-data--Well:0500",
        "opendes:master-data--Well:0501",
        total=1002,
    )

    with MockSearch(FIELDS, first_page, second_page, NO_WELLS) as search:
        await query_wells(field="D15a-A")

    assert len(search.requests) == 4
    assert search.requests[1]["offset"] == 0
    assert search.requests[2]["offset"] == 1000
    assert "opendes:master-data--Well:0501" in search.requests[3]["query"]


@pytest.mark.asyncio
async def test_a_field_with_more_wellbores_than_can_be_read_is_refused():
    """Answering from an arbitrary prefix of the wellbores is not an answer."""
    page = wellbores(
        *[f"opendes:master-data--Well:{index:05d}" for index in range(1000)],
        total=9000,
    )

    with MockSearch(FIELDS, page, page, page, page, page) as search:
        with pytest.raises(McpError):
            await query_wells(field="D15a-A")

    # Five pages read, then the refusal - the wells were never queried.
    assert len(search.requests) == 6
    assert all(request["kind"] == WELLBORE_KIND for request in search.requests[1:])


@pytest.mark.asyncio
async def test_query_wells_reports_an_unknown_field_under_its_own_key():
    """An unmatched field is reported with the fields the instance does hold."""
    with MockSearch(FIELDS) as search:
        result = await query_wells(field="Ekofisk")

    assert len(search.requests) == 1
    assert result["resolved_field"]["status"] == "not_found"
    assert result["resolved_field"]["candidates"] == ["D15a-A", "K15-FJ", "P12-SW"]


@pytest.mark.asyncio
async def test_query_wells_combines_every_reference_filter():
    """Country, basin and field each resolve, then AND together with source."""
    found = wellbores("opendes:master-data--Well:1")
    with MockSearch(COUNTRIES, BASINS, FIELDS, found, NO_WELLS) as search:
        await query_wells(
            country="Netherlands",
            basin="Illinois",
            field="D15a-A",
            source="Public",
        )

    # Three lookups, the wellbores in the field, then the wells.
    assert len(search.requests) == 5
    assert search.requests[4]["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:Netherlands_Country")) AND '
        'nested(data.GeoContexts, (BasinID:"opendes:master-data--Basin:Illinois_Basin"))'
        ' AND id: ("opendes:master-data--Well:1")'
        ' AND data.Source:"Public"'
    )


@pytest.mark.asyncio
async def test_query_wells_takes_a_field_record_id_as_given():
    """An id the caller already holds skips the lookup, as for the other filters."""
    found = wellbores("opendes:master-data--Well:1")
    with MockSearch(found, NO_WELLS) as search:
        await query_wells(field="opendes:master-data--Field:D15a-A")

    # No lookup - straight to the wellbores in the field, then the wells.
    assert len(search.requests) == 2
    assert search.requests[0]["kind"] == WELLBORE_KIND
    assert search.requests[0]["query"] == (
        'nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:D15a-A"))'
    )
    assert search.requests[1]["query"] == 'id: ("opendes:master-data--Well:1")'


SLEIPNER_FIELDS = {
    "results": [
        {
            "data": {"FieldName": "Sleipner Ost"},
            "id": "opendes:master-data--Field:Sleipner_Ost",
        },
        {
            "data": {"FieldName": "Sleipner Vest"},
            "id": "opendes:master-data--Field:Sleipner_Vest",
        },
        {
            "data": {"FieldName": "Sleipner Alpha North"},
            "id": "opendes:master-data--Field:Sleipner_Alpha_North",
        },
        {
            "data": {"FieldName": "Gudrun"},
            "id": "opendes:master-data--Field:Gudrun",
        },
    ],
    "totalCount": 4,
}


@pytest.mark.asyncio
async def test_query_wells_searches_the_records_containing_an_unmatched_name():
    """A name matching no record exactly searches the records containing it."""
    found = wellbores("opendes:master-data--Well:1")

    with MockSearch(SLEIPNER_FIELDS, found, NO_WELLS) as search:
        result = await query_wells(field="SLEIPNER")

    # The three near misses go to the wellbore search as one clause.
    assert len(search.requests) == 3
    assert search.requests[1]["kind"] == WELLBORE_KIND
    assert search.requests[1]["query"] == (
        'nested(data.GeoContexts, (FieldID:("opendes:master-data--Field:Sleipner_Ost"'
        ' OR "opendes:master-data--Field:Sleipner_Vest"'
        ' OR "opendes:master-data--Field:Sleipner_Alpha_North")))'
    )

    resolved = result["resolved_field"]
    assert resolved["status"] == "ambiguous"
    # The near misses, with the ids needed to narrow - not every field held.
    assert [candidate["name"] for candidate in resolved["candidates"]] == [
        "Sleipner Ost",
        "Sleipner Vest",
        "Sleipner Alpha North",
    ]
    assert "Gudrun" not in str(resolved["candidates"])


@pytest.mark.asyncio
async def test_query_wells_resolves_a_name_only_one_record_contains():
    """Containment narrowing to a single record resolves, like any other matcher."""
    with MockSearch(SLEIPNER_FIELDS, NO_WELLS) as search:
        await query_wells(field="Alpha North")

    # The resolved id reaches the wellbore search, which is where a field lives.
    assert search.requests[1]["kind"] == WELLBORE_KIND
    assert search.requests[1]["query"] == (
        'nested(data.GeoContexts, (FieldID:"opendes:master-data'
        '--Field:Sleipner_Alpha_North"))'
    )


@pytest.mark.asyncio
async def test_query_wells_prefers_a_whole_name_over_the_records_containing_it():
    """An exact name still wins outright, even when other records contain it."""
    fields = {
        "results": [
            {
                "data": {"FieldName": "Sleipner"},
                "id": "opendes:master-data--Field:Sleipner",
            },
            {
                "data": {"FieldName": "Sleipner Ost"},
                "id": "opendes:master-data--Field:Sleipner_Ost",
            },
        ],
        "totalCount": 2,
    }

    with MockSearch(fields, NO_WELLS) as search:
        await query_wells(field="sleipner")

    assert search.requests[1]["kind"] == WELLBORE_KIND
    assert search.requests[1]["query"] == (
        'nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:Sleipner"))'
    )


@pytest.mark.asyncio
async def test_query_wells_falls_back_to_every_candidate_when_none_contain_the_name():
    """With nothing to narrow to, the full list is still what the caller needs."""
    with MockSearch(SLEIPNER_FIELDS) as search:
        result = await query_wells(field="Ekofisk")

    assert len(search.requests) == 1
    resolved = result["resolved_field"]
    assert resolved["status"] == "not_found"
    assert resolved["candidates"] == [
        "Sleipner Ost",
        "Sleipner Vest",
        "Sleipner Alpha North",
        "Gudrun",
    ]


@pytest.mark.asyncio
async def test_query_wells_does_not_narrow_on_a_two_character_name():
    """Too short to be meaningful containment - "os" is inside half the instance."""
    with MockSearch(SLEIPNER_FIELDS):
        result = await query_wells(field="os")

    assert result["resolved_field"]["status"] == "not_found"
    assert len(result["resolved_field"]["candidates"]) == 4


@pytest.mark.asyncio
async def test_country_containment_matches_aliases_too():
    """Containment reads aliases as well as names, as the earlier matchers do."""
    countries = {
        "results": [
            {
                "data": {
                    "GeoPoliticalEntityName": "Norway",
                    "NameAliases": [{"AliasName": "Kingdom of Norway"}],
                },
                "id": "opendes:master-data--GeoPoliticalEntity:Norway",
            },
        ],
        "totalCount": 1,
    }

    with MockSearch(countries, NO_WELLS) as search:
        await query_wells(country="Kingdom of")

    assert (
        "opendes:master-data--GeoPoliticalEntity:Norway" in search.requests[1]["query"]
    )


@pytest.mark.asyncio
async def test_query_wells_rejects_a_record_id_of_the_wrong_entity():
    """A Field id passed as the basin is a mistake, not a shortcut past the lookup."""
    with MockSearch(BASINS) as search:
        result = await query_wells(basin="opendes:master-data--Field:D15a-A")

    # Without the entity check this would have filtered BasinID by a Field id
    # and returned zero wells with nothing to explain them.
    assert len(search.requests) == 1
    assert search.requests[0]["kind"] == BASIN.kind
    assert result["resolved_basin"]["status"] == "not_found"


@pytest.mark.asyncio
async def test_an_empty_lookup_is_not_cached():
    """An empty reference set is a misconfigured instance, not an answer to keep."""
    with MockSearch({"results": [], "totalCount": 0}, BASINS, NO_WELLS) as search:
        first = await query_wells(basin="Illinois")
        await query_wells(basin="Illinois")

    # The second call looked again rather than reusing the empty first result.
    assert first["resolved_basin"]["candidates"] == []
    assert len(search.requests) == 3
    assert search.requests[2]["query"] == (
        'nested(data.GeoContexts, (BasinID:"opendes:master-data--Basin:Illinois_Basin"))'
    )


@pytest.mark.asyncio
async def test_candidates_are_capped_but_counted():
    """An unmatched name returns a sample of the instance's records, not all of them."""
    fields = {
        "results": [
            {
                "data": {"FieldName": f"Field {index:03d}"},
                "id": f"opendes:master-data--Field:{index:03d}",
            }
            for index in range(120)
        ],
        "totalCount": 120,
    }

    with MockSearch(fields) as search:
        unmatched = await query_wells(field="Ekofisk")
    with MockSearch(fields) as search:
        matched = await query_wells(field="Field 0")

    assert len(unmatched["resolved_field"]["candidates"]) == 25
    assert unmatched["resolved_field"]["candidate_count"] == 120
    # The same cap applies to a name that is merely too broad to resolve.
    assert matched["resolved_field"]["status"] == "ambiguous"
    assert len(matched["resolved_field"]["candidates"]) == 25
    assert matched["resolved_field"]["candidate_count"] == 100
    assert search.requests[0]["limit"] == 1000


@pytest.mark.asyncio
async def test_a_reference_set_larger_than_one_page_is_read_through():
    """A full page means there may be more, so the lookup keeps reading."""
    first_page = {
        "results": [
            {
                "data": {"FieldName": f"Field {index:04d}"},
                "id": f"opendes:master-data--Field:{index:04d}",
            }
            for index in range(1000)
        ],
        "totalCount": 1002,
    }
    second_page = {
        "results": [
            {
                "data": {"FieldName": "Ekofisk"},
                "id": "opendes:master-data--Field:Ekofisk",
            },
            {
                "data": {"FieldName": "Gudrun"},
                "id": "opendes:master-data--Field:Gudrun",
            },
        ],
        "totalCount": 1002,
    }

    with MockSearch(first_page, second_page, NO_WELLS) as search:
        await query_wells(field="Ekofisk")

    # A name on the second page resolves because the first page did not end the
    # lookup - and the second page is asked for from where the first stopped.
    assert len(search.requests) == 3
    assert search.requests[0]["offset"] == 0
    assert search.requests[1]["offset"] == 1000
    assert search.requests[2]["kind"] == WELLBORE_KIND
    assert search.requests[2]["query"] == (
        'nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:Ekofisk"))'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "given",
    ["Guinea-Bissau", "Guinea Bissau", "guineabissau", "GUINEA BISSAU"],
)
async def test_a_hyphen_matches_however_the_caller_spells_it(given: str):
    """A punctuated name matches whether it is typed run together or spaced."""
    countries = {
        "results": [
            {
                "data": {"GeoPoliticalEntityName": "Guinea-Bissau"},
                "id": "opendes:master-data--GeoPoliticalEntity:GuineaBissau",
            },
        ],
        "totalCount": 1,
    }

    with MockSearch(countries, NO_WELLS) as search:
        await query_wells(country=given)

    assert search.requests[1]["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:GuineaBissau"))'
    )


NO_TRACE_DATA = {"results": [], "totalCount": 0}


@pytest.mark.asyncio
async def test_query_seismic_trace_data_resolves_the_same_reference_names():
    """Seismic takes names through the same lookups wells does, on its own kind."""
    with MockSearch(COUNTRIES, BASINS, FIELDS, NO_TRACE_DATA) as search:
        result = await query_seismic_trace_data(
            country="NOR", basin="Illinois", field="D15a-A", name="AzureDisc"
        )

    assert result == {"trace_data": [], "totalCount": 0}
    assert len(search.requests) == 4
    assert [request["kind"] for request in search.requests[:3]] == [
        COUNTRY.kind,
        BASIN.kind,
        FIELD.kind,
    ]
    assert search.requests[3]["query"] == (
        'nested(data.GeoContexts, (GeoPoliticalEntityID:"opendes:master-data'
        '--GeoPoliticalEntity:Norway")) AND '
        'nested(data.GeoContexts, (BasinID:"opendes:master-data--Basin:Illinois_Basin"))'
        ' AND nested(data.GeoContexts, (FieldID:"opendes:master-data--Field:D15a-A"))'
        " AND data.Name:(*AzureDisc*)"
    )


@pytest.mark.asyncio
async def test_query_seismic_trace_data_reports_an_unresolved_name_under_its_own_key():
    """An unusable filter reports back keyed by entity, with no trace data."""
    with MockSearch(BASINS) as search:
        result = await query_seismic_trace_data(basin="Atlantis")

    assert len(search.requests) == 1
    assert result["trace_data"] == []
    assert result["totalCount"] == 0
    assert result["resolved_basin"]["status"] == "not_found"


@pytest.mark.asyncio
async def test_reference_lookups_are_shared_between_the_search_tools():
    """One tool's lookup warms the cache the other reads - they are the same data."""
    with MockSearch(BASINS, NO_WELLS, NO_TRACE_DATA) as search:
        await query_wells(basin="Illinois")
        await query_seismic_trace_data(basin="Illinois")

    # One basin lookup, then a query per tool.
    assert len(search.requests) == 3
    assert search.requests[0]["kind"] == BASIN.kind
    assert "master-data--Well" in search.requests[1]["kind"]
    assert "SeismicTraceData" in search.requests[2]["kind"]
