"""Search OSDU Instance for wells based on various criteria (geographic bounding boxes, country, basin, field)."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...shared.clients import BoundingBox, SearchClient
from ...shared.exceptions import handle_osdu_exceptions
from ._models import OsduData
from ._query import normalize_record_id, quoted
from ._reference import resolve_geo_context_filters, unresolved_result

#: Wellbores read when resolving a well's children. A well with more wellbores
#: than this cannot be resolved from a single page, so the tool refuses rather
#: than answering from part of it.
_WELLBORE_LIMIT = 250


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


class Marker(BaseModel):
    """One pick inside a WellboreMarkerSet's Markers list."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    marker_name: str | None = Field(default=None, alias="MarkerName")
    marker_measured_depth: float | None = Field(
        default=None, alias="MarkerMeasuredDepth"
    )
    marker_type_id: str | None = Field(default=None, alias="MarkerTypeID")
    observation_number: int | None = Field(default=None, alias="ObservationNumber")
    interpreter_name: str | None = Field(default=None, alias="InterpreterName")


class MarkerSetFields(WellboreChildFields):
    """The fields query_well_marker_sets reads off a WellboreMarkerSet record.

    The whole `Markers` array is asked for and trimmed to the declared pick
    fields here, rather than requesting each sub-field as its own dotted path.
    """

    markers: list[Marker] = Field(default_factory=list, alias="Markers")


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
    country: str | None = None,
    basin: str | None = None,
    field: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the OSDU instance for wells, based on a number of criteria (geographic bounding boxes, country, basin, field, source)

    Args:
        bounding_box (BoundingBox | None): A geographic bounding box to filter wells by location.
        country (str | None): A country name, alias, or record id to filter wells by.
        basin (str | None): A basin name or record id to filter wells by.
        field (str | None): A field name or record id to filter wells by.
        source (str | None): A source to filter wells by.
        limit (int): The maximum number of wells to return (default: 50).
        offset (int): The number of wells to skip before starting to collect the result set (default: 0).

    A name that matches no record, or more than one, is reported back under
    `resolved_country`, `resolved_basin` or `resolved_field` with the candidates
    to choose from, rather than being searched for as typed.
    """

    clauses, unresolved = await resolve_geo_context_filters(country, basin, field)
    if unresolved:
        return unresolved_result("wells", *unresolved)
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
            limit=_WELLBORE_LIMIT,
            returned_fields=WellboreFields.returned_fields(),
        )

    wellbore_ids = [
        result["id"] for result in response.get("results", []) if result.get("id")
    ]
    if not wellbore_ids:
        raise ValueError("No wellbores found for the provided well IDs.")

    # The search caps the page at _WELLBORE_LIMIT, so a larger total means the
    # children below would be resolved from an arbitrary subset of the
    # wellbores. Say so rather than return a quietly partial answer.
    total = response.get("totalCount", len(wellbore_ids))
    if total > _WELLBORE_LIMIT:
        raise ValueError(
            f"Too many wellbores found for the provided well IDs: {total}. "
            f"Limit is {_WELLBORE_LIMIT}. Narrow the well IDs and try again."
        )
    return wellbore_ids


async def _query_wellbore_children(
    well_ids: list[str],
    kind: str,
    limit: int = 250,
    model: type[OsduData] = WellboreChildFields,
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
            returned_fields=model.returned_fields(),
        )

    return {
        "results": _project(response, model),
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
    """Search the OSDU instance for marker sets (well top picks), based on a list of well IDs.

    Each marker set comes back with its `markers` list - the picks themselves,
    with name, measured depth, type, observation number and interpreter - so no
    follow-up record read is needed to see the tops.
    """

    return await _query_wellbore_children(
        well_ids,
        kind="osdu:wks:work-product-component--WellboreMarkerSet:*",
        model=MarkerSetFields,
    )
