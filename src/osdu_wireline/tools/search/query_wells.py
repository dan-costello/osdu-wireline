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
    # Validate parameters

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

    if limit > 1000:
        limit = 1000

    # Consider adding an optional argument for kind to allow different well schema versions to be searched.
    kind = "*:wks:master-data--Well:*"

    async with SearchClient() as client:
        return await client.search_query(
            query=query,
            kind=kind,
            limit=limit,
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


@handle_osdu_exceptions
async def query_wellbores(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for wellbores, based on a list of well IDs. The Well ids are retreived using the query_wells function. This is not to be called directly, but by query_trajectories and other tools."""

    # TODO: Consider adding arguments for field_id, technical_assurance_type_id, schema versions (other?)

    query = f'data.WellID: ("${('" OR "').join(well_ids)}")'
    kind = "*:wks:master-data--Wellbore:*"

    async with SearchClient() as client:
        res = await client.search_query(
            query=query,
            kind=kind,
            limit=250,
            returnedFields=[
                "id",
                "id",
                "data.FacilityName",
                "data.GeoContexts",
                "data.WellID",
                "data.TechnicalAssurances",
            ],
        )

        if res.get("success") and len(res.get("results", [])) > 0:
            # return list of wellbore IDs
            wellbore_ids = [result["id"] for result in res["results"]]
            return {"success": True, "wellbore_ids": wellbore_ids}
    raise ValueError("No wellbores found for the provided well IDs.")


@handle_osdu_exceptions
async def query_well_trajectories(
    well_ids: list[str],
) -> dict[str, Any]:
    """Search the OSDU instance for trajectories, based on a list of well IDs."""

    # TODO: Consider adding arguments for technical_assurance_type_id, schema versions (other?)

    wellbore_ids_result = await query_wellbores(well_ids)
    wellbore_ids = wellbore_ids_result.get("wellbore_ids", [])

    if not wellbore_ids:
        raise ValueError("No wellbores found for the provided well IDs.")

    async with SearchClient() as client:
        return await client.search_query(
            query=f'data.WellboreID: ("${('" OR "').join(wellbore_ids)}")',
            kind="*:wks:work-product-component--WellboreTrajectory:*",
            limit=250,
            returnedFields=[
                "id",
                "data.Name",
                "data.WellboreID",
                "data.TechnicalAssurances",
            ],
        )
