"""Search OSDU Instance for wells based on various criteria (geographic bounding boxes, country_id, basin_id)."""

from typing import Any

from ...shared.clients import BoundingBox, SearchClient
from ...shared.exceptions import handle_osdu_exceptions


@handle_osdu_exceptions
async def query_wells(
    bounding_box: BoundingBox | None = None,
    country_id: str | None = None,
    basin_id: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the OSDU instance for wells, based on a number of criteria (geographic bounding boxes, country_id, basin_id)"""

    clauses: list[str] = []
    if country_id:
        clauses.append(
            f'nested(data.GeoContexts, (GeoPoliticalEntityID:"{country_id}"))'
        )
    if basin_id:
        clauses.append(f'nested(data.GeoContexts, (BasinID:"{basin_id}"))')
    if source:
        clauses.append(f'data.Source:"{source}"')

    query = " AND ".join(clauses) if clauses else ""

    async with SearchClient() as client:
        return await client.search_query(
            query=query,
            kind="*:wks:master-data--Well:*",
            limit=min(1000, limit),
            offset=offset,
            bounding_box=bounding_box,
            returnedFields=[
                "id",
                "data.FacilityName",
                "data.SpatialLocation.Wgs84Coordinates",
                "data.Source",
                "data.GeoContexts",
                "data.TechnicalAssurances",
            ],
        )


# Default fields returned for work-product-components hanging off a wellbore.
_WELLBORE_CHILD_FIELDS = [
    "id",
    "data.Name",
    "data.WellboreID",
    "data.TechnicalAssurances",
]


async def _resolve_wellbore_ids(well_ids: list[str]) -> list[str]:
    """Resolve a list of well IDs to their wellbore IDs."""

    # Internal helper - not decorated, so the caller's handle_osdu_exceptions wraps once.
    # TODO: Consider adding arguments for field_id, technical_assurance_type_id, schema versions (other?)

    async with SearchClient() as client:
        res = await client.search_query(
            query=f'data.WellID: ("{('" OR "').join(well_ids)}")',
            kind="*:wks:master-data--Wellbore:*",
            limit=250,
            returnedFields=[
                "id",
                "data.FacilityName",
                "data.GeoContexts",
                "data.WellID",
                "data.TechnicalAssurances",
            ],
        )

    if res.get("success") and res.get("results"):
        return [result["id"] for result in res["results"]]

    raise ValueError("No wellbores found for the provided well IDs.")


async def _query_wellbore_children(
    well_ids: list[str],
    kind: str,
    returned_fields: list[str] | None = None,
    limit: int = 250,
) -> dict[str, Any]:
    """Search for work-product-components attached to the wellbores of the given wells.

    Internal helper shared by the trajectory, well log and marker set tools.
    """
    # TODO: Consider adding arguments for technical_assurance_type_id, schema versions (other?)

    wellbore_ids = await _resolve_wellbore_ids(well_ids)

    async with SearchClient() as client:
        return await client.search_query(
            query=f'data.WellboreID: ("{('" OR "').join(wellbore_ids)}")',
            kind=kind,
            limit=limit,
            returnedFields=returned_fields or _WELLBORE_CHILD_FIELDS,
        )


@handle_osdu_exceptions
async def query_well_trajectories(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for trajectories, based on a list of well IDs."""

    return await _query_wellbore_children(
        well_ids, kind="*:wks:work-product-component--WellboreTrajectory:*"
    )


@handle_osdu_exceptions
async def query_well_logs(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for well logs, based on a list of well IDs."""

    return await _query_wellbore_children(
        well_ids, kind="*:wks:work-product-component--WellLog:*"
    )


@handle_osdu_exceptions
async def query_well_marker_sets(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for marker sets (well top picks), based on a list of well IDs."""

    return await _query_wellbore_children(
        well_ids, kind="*:wks:work-product-component--WellboreMarkerSet:*"
    )
