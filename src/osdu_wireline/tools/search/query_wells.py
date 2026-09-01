"""Search OSDU Instance for wells based on various criteria (geographic bounding boxes, country_id, basin_id)."""

from typing import Any, ClassVar

from pydantic import Field

from ...shared.clients import BoundingBox, SearchClient
from ...shared.exceptions import handle_osdu_exceptions
from ._models import OsduData
from ._query import normalize_record_id, quoted


class WellFields(OsduData):
    """The fields query_wells reads off a master-data--Well record."""

    spatial_field_name: ClassVar[str | None] = "spatial_location"

    facility_name: str | None = Field(default=None, alias="FacilityName")
    spatial_location: Any = Field(
        default=None, alias="SpatialLocation.Wgs84Coordinates"
    )
    source: str | None = Field(default=None, alias="Source")
    geo_contexts: Any = Field(default=None, alias="GeoContexts")
    technical_assurances: Any = Field(default=None, alias="TechnicalAssurances")


class WellboreFields(OsduData):
    """The fields the wellbore lookup reads off a master-data--Wellbore record."""

    facility_name: str | None = Field(default=None, alias="FacilityName")
    geo_contexts: Any = Field(default=None, alias="GeoContexts")
    well_id: str | None = Field(default=None, alias="WellID")
    technical_assurances: Any = Field(default=None, alias="TechnicalAssurances")


class WellboreChildFields(OsduData):
    """The fields read off a work-product-component hanging off a wellbore."""

    name: str | None = Field(default=None, alias="Name")
    wellbore_id: str | None = Field(default=None, alias="WellboreID")
    technical_assurances: Any = Field(default=None, alias="TechnicalAssurances")


def _project(response: dict[str, Any], model: type[OsduData]) -> list[dict[str, Any]]:
    """Map an OSDU response onto the given model, keeping the record id."""
    return [
        {
            "id": result.get("id"),
            **model.model_validate(result.get("data", {})).model_dump(),
        }
        for result in response.get("results", [])
    ]


@handle_osdu_exceptions
async def query_wells(
    bounding_box: BoundingBox | None = None,
    country_id: str | None = None,
    basin_id: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the OSDU instance for wells, based on a number of criteria (geographic bounding boxes, country_id, basin_id)

    Args:
        bounding_box (BoundingBox | None): A geographic bounding box to filter wells by location.
        country_id (str | None): A country ID to filter wells by.
        basin_id (str | None): A basin ID to filter wells by.
        source (str | None): A source to filter wells by.
        limit (int): The maximum number of wells to return (default: 50).
        offset (int): The number of wells to skip before starting to collect the result set (default: 0).
    """

    clauses: list[str] = []
    if country_id:
        clauses.append(
            f"nested(data.GeoContexts, (GeoPoliticalEntityID:{quoted(country_id)}))"
        )
    if basin_id:
        clauses.append(f"nested(data.GeoContexts, (BasinID:{quoted(basin_id)}))")
    if source:
        clauses.append(f"data.Source:{quoted(source)}")

    query = " AND ".join(clauses) if clauses else ""

    async with SearchClient() as client:
        response = await client.search_query(
            query=query,
            kind="osdu:wks:master-data--Well:*",
            limit=min(1000, limit),
            offset=offset,
            bounding_box=bounding_box,
            spatial_field=WellFields.spatial_field(),
            returned_fields=WellFields.returned_fields(),
        )

    return {
        "wells": _project(response, WellFields),
        "totalCount": response.get("totalCount", 0),
    }


async def _resolve_wellbore_ids(well_ids: list[str]) -> list[str]:
    """Resolve a list of well IDs to their wellbore IDs."""

    # Internal helper - not decorated, so the caller's handle_osdu_exceptions wraps once.
    # TODO: Consider adding arguments for field_id, technical_assurance_type_id, schema versions (other?)

    async with SearchClient() as client:
        response = await client.search_query(
            query=f"data.WellID: ({' OR '.join(quoted(normalize_record_id(i)) for i in well_ids)})",
            kind="osdu:wks:master-data--Wellbore:*",
            limit=250,
            returned_fields=WellboreFields.returned_fields(),
        )

    wellbore_ids = [
        result["id"] for result in response.get("results", []) if result.get("id")
    ]
    if not wellbore_ids:
        raise ValueError("No wellbores found for the provided well IDs.")

    return wellbore_ids


async def _query_wellbore_children(
    well_ids: list[str],
    kind: str,
    limit: int = 250,
) -> dict[str, Any]:
    """Search for work-product-components attached to the wellbores of the given wells.

    Internal helper shared by the trajectory, well log and marker set tools.
    """
    # TODO: Consider adding arguments for technical_assurance_type_id, schema versions (other?)

    wellbore_ids = await _resolve_wellbore_ids(well_ids)

    async with SearchClient() as client:
        response = await client.search_query(
            query=f"data.WellboreID: ({' OR '.join(quoted(i) for i in wellbore_ids)})",
            kind=kind,
            limit=limit,
            returned_fields=WellboreChildFields.returned_fields(),
        )

    return {
        "results": _project(response, WellboreChildFields),
        "totalCount": response.get("totalCount", 0),
    }


@handle_osdu_exceptions
async def query_well_trajectories(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for trajectories, based on a list of well IDs."""

    return await _query_wellbore_children(
        well_ids, kind="osdu:wks:work-product-component--WellboreTrajectory:*"
    )


@handle_osdu_exceptions
async def query_well_logs(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for well logs, based on a list of well IDs."""

    return await _query_wellbore_children(
        well_ids, kind="osdu:wks:work-product-component--WellLog:*"
    )


@handle_osdu_exceptions
async def query_well_marker_sets(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for marker sets (well top picks), based on a list of well IDs."""

    return await _query_wellbore_children(
        well_ids, kind="osdu:wks:work-product-component--WellboreMarkerSet:*"
    )
