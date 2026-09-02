"""Search OSDU Instance for wells based on various criteria (geographic bounding boxes, country, basin, field)."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...shared.clients import BoundingBox, SearchClient
from ...shared.exceptions import handle_osdu_exceptions
from ._models import OsduData
from ._query import normalize_record_id, quoted
from ._reference import (
    FIELD,
    geo_context_clause,
    resolve_geo_context_filters,
    resolve_reference_filter,
    unresolved_result,
)

#: Wellbores read per request. OSDU caps a single search page at 1000.
_WELLBORE_PAGE = 1000

#: Wellbores read in total while resolving a filter. A search matching more than
#: this cannot be answered from what was read, so the tool refuses rather than
#: answering from part of it.
_WELLBORE_MAX_RECORDS = 5000

#: IDs spliced into one query clause. Past this the query string itself is the
#: problem, and what the caller needs is a narrower search, not a larger request.
_ID_FILTER_LIMIT = 1000


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


class WellboreRefFields(OsduData):
    """The one field the wellbore resolution step reads.

    Resolution may page through thousands of wellbores, and all it needs from
    each is the well it hangs off - so it asks for nothing else.
    """

    well_id: str | None = Field(default=None, alias="WellID")


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


class Curve(BaseModel):
    """One curve inside a WellLog's Curves list."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    curve_id: str | None = Field(default=None, alias="CurveID")
    mnemonic: str | None = Field(default=None, alias="Mnemonic")
    top_depth: float | None = Field(default=None, alias="TopDepth")
    base_depth: float | None = Field(default=None, alias="BaseDepth")
    depth_unit: str | None = Field(default=None, alias="DepthUnit")
    log_curve_type_id: str | None = Field(default=None, alias="LogCurveTypeID")


class WellLogFields(WellboreChildFields):
    """The fields query_well_logs reads off a WellLog record.

    The whole `Curves` array is asked for and trimmed to the declared curve
    fields here, rather than requesting each sub-field as its own dotted path.
    """

    curves: list[Curve] = Field(default_factory=list, alias="Curves")


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


async def _search_wellbores(
    *,
    well_ids: list[str] | None = None,
    field_ids: list[str] | None = None,
) -> list[tuple[str, str | None]]:
    """Page through the wellbores matching the given filters.

    Returns each match as `(wellbore id, well id)`. The filters are ANDed, so
    passing both narrows to the wellbores of those wells that are also in that
    field.

    `FieldID` is recorded on the wellbore and nowhere else in the hierarchy -
    not on the well above it, not on the work-product-components below it - so
    this search is the only place a field filter can be applied. Both the well
    search and the wellbore-child searches resolve theirs through it.
    """
    # Internal helper - not decorated, so the caller's handle_osdu_exceptions wraps once.
    # TODO: Consider adding arguments for technical_assurance_type_id, schema versions (other?)

    clauses: list[str] = []
    if well_ids:
        ids = " OR ".join(quoted(normalize_record_id(i)) for i in well_ids)
        clauses.append(f"data.WellID: ({ids})")
    if field_ids:
        clauses.append(geo_context_clause(FIELD, field_ids))
    if not clauses:
        raise ValueError("A wellbore search needs well IDs, a field, or both.")

    query = " AND ".join(clauses)
    wellbores: list[tuple[str, str | None]] = []
    read = 0
    total = 0
    async with SearchClient() as client:
        while read < _WELLBORE_MAX_RECORDS:
            response = await client.search_query(
                query=query,
                kind="osdu:wks:master-data--Wellbore:*",
                limit=_WELLBORE_PAGE,
                offset=read,
                returned_fields=WellboreRefFields.returned_fields(),
            )
            results = response.get("results", [])
            read += len(results)
            wellbores.extend(
                (
                    result["id"],
                    WellboreRefFields.model_validate(result.get("data", {})).well_id,
                )
                for result in results
                if result.get("id")
            )
            total = response.get("totalCount", read)
            # A short page is the last page, whatever the reported total says.
            if len(results) < _WELLBORE_PAGE or read >= total:
                break
        else:
            # Everything below would be resolved from an arbitrary prefix of the
            # wellbores. Say so rather than return a quietly partial answer.
            raise ValueError(
                f"Too many wellbores match the search: {total}. Limit is "
                f"{_WELLBORE_MAX_RECORDS}. Narrow the search and try again."
            )

    return wellbores


def _id_filter(path: str, ids: list[str], what: str) -> str:
    """Build a clause matching `path` against a list of record ids, or refuse to."""
    if len(ids) > _ID_FILTER_LIMIT:
        raise ValueError(
            f"Too many {what} to filter on: {len(ids)}. Limit is "
            f"{_ID_FILTER_LIMIT}. Narrow the search and try again."
        )
    return f"{path}: (" + " OR ".join(quoted(i) for i in ids) + ")"


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

    # Country and basin are recorded on the well itself; a field is not. It is
    # resolved through the wellbores in it, which name the wells to return.
    filters = await resolve_geo_context_filters(country, basin)
    if filters.unresolved:
        return unresolved_result("wells", *filters.unresolved)
    clauses, reports = filters.clauses, filters.reports

    if field:
        resolved = await resolve_reference_filter(FIELD, field)
        if resolved.unresolved:
            return unresolved_result("wells", *resolved.unresolved)
        reports.update(resolved.reports)

        wellbores = await _search_wellbores(field_ids=resolved.ids)
        well_ids = list(
            dict.fromkeys(
                normalize_record_id(well_id) for _, well_id in wellbores if well_id
            )
        )
        # A field whose wellbores name no wells has no wells to return, and an
        # empty id clause would match everything.
        if not well_ids:
            return {"wells": [], "totalCount": 0, **reports}
        clauses.append(_id_filter("id", well_ids, "wells in the field"))

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
        **reports,
    }


async def _query_wellbore_children(
    kind: str,
    well_ids: list[str] | None = None,
    field: str | None = None,
    limit: int = 250,
    model: type[OsduData] = WellboreChildFields,
) -> dict[str, Any]:
    """Search for work-product-components attached to a set of wellbores.

    Internal helper shared by the trajectory, well log and marker set tools.
    Both filters resolve to wellbores first: the components carry no field
    reference of their own, so a field can only narrow which wellbores are read.
    """
    if not well_ids and not field:
        raise ValueError("Provide well_ids, a field, or both.")

    field_ids: list[str] = []
    reports: dict[str, Any] = {}
    if field:
        resolved = await resolve_reference_filter(FIELD, field)
        if resolved.unresolved:
            return unresolved_result("results", *resolved.unresolved)
        field_ids, reports = resolved.ids, resolved.reports

    wellbores = await _search_wellbores(well_ids=well_ids, field_ids=field_ids)
    # Filters that select no wellbores select no components either. That is an
    # empty result, not a failure - and `reports` is what says why it is empty.
    if not wellbores:
        return {"results": [], "totalCount": 0, **reports}

    query = _id_filter(
        "data.WellboreID", [wellbore_id for wellbore_id, _ in wellbores], "wellbores"
    )

    async with SearchClient() as client:
        response = await client.search_query(
            query=query,
            kind=kind,
            limit=limit,
            returned_fields=model.returned_fields(),
        )

    return {
        "results": _project(response, model),
        "totalCount": response.get("totalCount", 0),
        **reports,
    }


@handle_osdu_exceptions
async def query_well_trajectories(
    well_ids: list[str] | None = None,
    field: str | None = None,
) -> dict[str, Any]:
    """Search the OSDU instance for trajectories, based on a list of well IDs or a field.

    Args:
        well_ids (list[str] | None): Well record ids whose wellbores to read.
        field (str | None): A field name or record id. Selects the wellbores
            recorded in that field; given with `well_ids` it narrows to the
            wellbores that are both.

    At least one of `well_ids` and `field` is required.
    """

    return await _query_wellbore_children(
        kind="osdu:wks:work-product-component--WellboreTrajectory:*",
        well_ids=well_ids,
        field=field,
    )


@handle_osdu_exceptions
async def query_well_logs(
    well_ids: list[str] | None = None,
    field: str | None = None,
) -> dict[str, Any]:
    """Search the OSDU instance for well logs, based on a list of well IDs or a field.

    Args:
        well_ids (list[str] | None): Well record ids whose wellbores to read.
        field (str | None): A field name or record id. Selects the wellbores
            recorded in that field; given with `well_ids` it narrows to the
            wellbores that are both.

    At least one of `well_ids` and `field` is required.

    Each log comes back with its `curves` list - the curves it holds, with id,
    mnemonic, top and base depth, depth unit and curve type - so no follow-up
    record read is needed to see what was logged. Curves are not filtered on:
    mnemonics vary too much between sources for that to be reliable, so the
    tool returns what is there and leaves the choosing to the caller.
    """

    return await _query_wellbore_children(
        kind="osdu:wks:work-product-component--WellLog:*",
        well_ids=well_ids,
        field=field,
        model=WellLogFields,
    )


@handle_osdu_exceptions
async def query_well_marker_sets(
    well_ids: list[str] | None = None,
    field: str | None = None,
) -> dict[str, Any]:
    """Search the OSDU instance for marker sets (well top picks), based on a list of well IDs or a field.

    Args:
        well_ids (list[str] | None): Well record ids whose wellbores to read.
        field (str | None): A field name or record id. Selects the wellbores
            recorded in that field; given with `well_ids` it narrows to the
            wellbores that are both.

    At least one of `well_ids` and `field` is required.

    Each marker set comes back with its `markers` list - the picks themselves,
    with name, measured depth, type, observation number and interpreter - so no
    follow-up record read is needed to see the tops.
    """

    return await _query_wellbore_children(
        kind="osdu:wks:work-product-component--WellboreMarkerSet:*",
        well_ids=well_ids,
        field=field,
        model=MarkerSetFields,
    )
