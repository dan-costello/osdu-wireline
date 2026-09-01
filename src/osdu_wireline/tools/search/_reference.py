"""Resolve a reference entity's name to the record id a query filters on.

Wells and seismic are filtered by the id of the country, basin or field they
hang off, but callers think in names. Names are entered loosely - a different
case, an ISO code, a stray comma - so resolution runs a series of increasingly
forgiving matchers and stops at the first that hits, which keeps an exact name
from being beaten by another record's alias.

An unmatched or ambiguous name is returned to the caller as a result rather than
raised: the candidate list is what lets the next attempt succeed. The last
matcher is deliberately loose, so a name that matches nothing exactly usually
comes back as a handful of records that contain it rather than as a sample of
every record the instance holds.

Countries, basins and fields differ only in which kind holds them, which field
carries their name, whether they carry aliases, and how a record points at them
- so each is a `ReferenceLookup` value over one set of helpers rather than an
implementation of its own.
"""

import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from ...shared.clients import SearchClient
from ...shared.env import require_setting
from ._query import is_record_id, normalize_record_id, quoted

logger = logging.getLogger(__name__)

#: Records read per request. OSDU caps a single search page at 1000.
_LOOKUP_PAGE = 1000

#: Records read in total. An instance holding more reference records than this
#: is one where name resolution was never the right tool, so the lookup stops
#: rather than paging through all of it on every cold cache.
_LOOKUP_MAX_RECORDS = 5000

#: Candidates handed back with an unresolved name. Enough to choose from, or to
#: see the shape of, without returning an instance's reference data as a
#: failure message.
_MAX_CANDIDATES = 25

#: Below this an input is too short for containment to mean anything: two
#: characters are a substring of half the instance.
_MIN_SUBSTRING_LENGTH = 3

#: Aliases hang off any master-data record under the same nested field.
_ALIAS_FIELD = "data.NameAliases.AliasName"


@dataclass(frozen=True)
class ReferenceLookup:
    """How to find one kind of reference entity, and how a record points at it."""

    #: Names the entity in results and in the key a tool reports it under.
    label: str
    #: The kind holding the entity's own records.
    kind: str
    #: The field on those records carrying the name callers type.
    name_field: str
    #: The field inside `data.GeoContexts` that references the entity.
    context_field: str
    #: Whether the entity's records carry NameAliases worth matching on.
    has_aliases: bool = False
    #: Narrows the kind to a subset of it, given the data partition. Kinds that
    #: hold exactly one entity - a Basin holds only basins - need no filter.
    type_filter: Callable[[str], str] | None = field(default=None, compare=False)

    @property
    def returned_fields(self) -> list[str]:
        """The fields matching reads: the id to return, the name and aliases to match."""
        fields = ["id", f"data.{self.name_field}"]
        if self.has_aliases:
            fields.append(_ALIAS_FIELD)
        return fields

    @property
    def entity_type(self) -> str:
        """The entity-type segment an id of this kind carries: `master-data--Basin`."""
        return self.kind.split(":")[2]


#: A country is one of several entities sharing the GeoPoliticalEntity kind, so
#: it is the one lookup that has to narrow the kind by type.
COUNTRY = ReferenceLookup(
    label="country",
    kind="osdu:wks:master-data--GeoPoliticalEntity:*",
    name_field="GeoPoliticalEntityName",
    context_field="GeoPoliticalEntityID",
    has_aliases=True,
    type_filter=lambda partition: (
        "data.GeoPoliticalEntityTypeID:"
        f'"{partition}:reference-data--GeoPoliticalEntityType:Country"'
    ),
)

BASIN = ReferenceLookup(
    label="basin",
    kind="osdu:wks:master-data--Basin:*",
    name_field="BasinName",
    context_field="BasinID",
)

FIELD = ReferenceLookup(
    label="field",
    kind="osdu:wks:master-data--Field:*",
    name_field="FieldName",
    context_field="FieldID",
)


class ReferenceRecord(BaseModel):
    """A reference entity, reduced to what name matching needs."""

    name: str
    id: str
    aliases: list[str] = []


class Candidate(BaseModel):
    name: str
    id: str
    well_count: int | None = None


class Resolved(BaseModel):
    status: Literal["resolved"] = "resolved"
    id: str
    matched: str
    input: str


class NotFound(BaseModel):
    status: Literal["not_found"] = "not_found"
    input: str
    #: A sample, not the whole set - `candidate_count` says how many there are.
    candidates: list[str]
    candidate_count: int = 0


class Ambiguous(BaseModel):
    status: Literal["ambiguous"] = "ambiguous"
    input: str
    candidates: list[Candidate]
    candidate_count: int = 0


#: Records per (data partition, lookup), memoised for the life of the process.
#
# What countries, basins or fields an instance holds is reference data: it is
# read on most searches and changes on the order of never, so each set is
# fetched once. The memo is a plain dict rather than a lock-guarded one because
# an asyncio lock built at import time binds to the first event loop that takes
# it; two callers racing here cost one redundant read of an idempotent query,
# which is cheaper than that failure mode.
_RECORDS: dict[tuple[str, str], list[ReferenceRecord]] = {}


def clear_reference_cache() -> None:
    """Drop the memoised records.

    The cache outlives any one call, so a test that mocks a different set of
    records - or an operator who has just loaded new ones - needs a way to
    invalidate it.
    """
    _RECORDS.clear()


def _as_record(
    lookup: ReferenceLookup, result: dict[str, Any]
) -> ReferenceRecord | None:
    """Read one search hit, or None if it has no name or id to match on."""
    data = result.get("data") or {}
    name = data.get(lookup.name_field)
    record_id = result.get("id")
    if not name or not record_id:
        return None

    aliases = data.get("NameAliases") or [] if lookup.has_aliases else []
    return ReferenceRecord(
        name=name,
        id=record_id,
        aliases=[alias.get("AliasName") for alias in aliases if alias.get("AliasName")],
    )


async def available_records(lookup: ReferenceLookup) -> list[ReferenceRecord]:
    """List the entities this OSDU instance knows about, fetching them once."""
    data_partition = require_setting("OSDU_DATA_PARTITION")
    cached = _RECORDS.get((data_partition, lookup.label))
    if cached is not None:
        return cached

    records: list[ReferenceRecord] = []
    read = 0
    async with SearchClient() as client:
        while read < _LOOKUP_MAX_RECORDS:
            response = await client.search_query(
                query=lookup.type_filter(data_partition) if lookup.type_filter else "",
                kind=lookup.kind,
                limit=_LOOKUP_PAGE,
                offset=read,
                returned_fields=lookup.returned_fields,
            )
            results = response.get("results", [])
            read += len(results)
            records.extend(
                record
                for record in (_as_record(lookup, result) for result in results)
                if record is not None
            )
            total = response.get("totalCount", 0)
            # A short page is the last page, whatever the reported total says.
            if len(results) < _LOOKUP_PAGE or read >= total:
                break
        else:
            # A name past the cap resolves as not_found, which looks like any
            # other miss - so leave the reason somewhere it can be found.
            logger.warning(
                "Read %d of %s %s records; names beyond that will not resolve",
                read,
                total,
                lookup.label,
            )

    # An empty result is far likelier to be a partition that has not been
    # loaded, or an ACL hiding the kind, than an instance genuinely holding no
    # countries - and caching that would fail every later lookup for the life of
    # the process. Leave the cache cold so the next call can still find them.
    if records:
        _RECORDS[(data_partition, lookup.label)] = records
    return records


def _normal_forms(value: str) -> list[str]:
    """Reduce a name to the spellings it is likely to be typed as.

    Punctuation is dropped two ways, because either can be what the caller
    meant: `Sleipner-Ost` is written both `SleipnerOst` and `Sleipner Ost`, and
    two values match if they agree on any one spelling.
    """
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")

    forms: list[str] = []
    for replacement in ("", " "):
        form = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", replacement, value)).strip()
        if form not in forms:
            forms.append(form)
    return forms


def _exact_ci_name(record: ReferenceRecord, name: str) -> bool:
    """Match the record's name, case-insensitively."""
    return record.name.lower() == name.lower()


def _alias_ci(record: ReferenceRecord, name: str) -> bool:
    """Match any of the record's aliases, case-insensitively."""
    return any(alias.lower() == name.lower() for alias in record.aliases)


def _normalized_name_or_alias(record: ReferenceRecord, name: str) -> bool:
    """Match the name or an alias once both are normalized."""
    forms = set(_normal_forms(name))
    return any(
        forms & set(_normal_forms(candidate))
        for candidate in (record.name, *record.aliases)
    )


def _contained_in_name_or_alias(record: ReferenceRecord, name: str) -> bool:
    """Match a record whose name or alias contains the normalized input.

    A caller naming a field or basin rarely reproduces the qualifier attached to
    it - `Sleipner` for `Sleipner Ost`, `Powder River` for `Powder River Basin`.
    Containment runs one way only: what the caller typed has to appear in the
    record, not the reverse, so a record with a very short name cannot match
    every input that happens to mention it.
    """
    forms = [form for form in _normal_forms(name) if len(form) >= _MIN_SUBSTRING_LENGTH]
    return any(
        form in candidate_form
        for form in forms
        for candidate in (record.name, *record.aliases)
        for candidate_form in _normal_forms(candidate)
    )


#: Matchers in order of decreasing precision. The first to hit wins.
_MATCHERS: list[Callable[[ReferenceRecord, str], bool]] = [
    _exact_ci_name,
    _alias_ci,
    _normalized_name_or_alias,
    _contained_in_name_or_alias,
]


def is_lookup_record_id(lookup: ReferenceLookup, value: str) -> bool:
    """Report whether a value is an id of the entity this lookup resolves.

    An id of some other entity is not a shortcut, it is a mistake worth
    catching: filtering `BasinID` by a Field id returns no wells and no reason,
    where treating it as an unresolved name at least returns the basins.
    """
    if not is_record_id(value):
        return False
    return normalize_record_id(value).split(":")[1] == lookup.entity_type


async def resolve_reference_id(
    lookup: ReferenceLookup, name: str
) -> Ambiguous | NotFound | Resolved:
    """Resolve a name - or an id the caller already holds - to a record id."""
    if is_lookup_record_id(lookup, name):
        record_id = normalize_record_id(name)
        return Resolved(id=record_id, matched=record_id, input=name)

    records = await available_records(lookup)

    hits: list[ReferenceRecord] = []
    for matcher in _MATCHERS:
        hits = [record for record in records if matcher(record, name)]
        if hits:
            break

    if len(hits) == 1:
        return Resolved(id=hits[0].id, matched=hits[0].name, input=name)
    if not hits:
        return NotFound(
            input=name,
            candidates=[record.name for record in records[:_MAX_CANDIDATES]],
            candidate_count=len(records),
        )
    return Ambiguous(
        input=name,
        candidates=[
            Candidate(name=record.name, id=record.id)
            for record in hits[:_MAX_CANDIDATES]
        ],
        candidate_count=len(hits),
    )


async def resolve_country_id(country_name: str) -> Ambiguous | NotFound | Resolved:
    """Resolve a country name, alias, or record id to a GeoPoliticalEntity id."""
    return await resolve_reference_id(COUNTRY, country_name)


async def resolve_basin_id(basin_name: str) -> Ambiguous | NotFound | Resolved:
    """Resolve a basin name or record id to a Basin record id."""
    return await resolve_reference_id(BASIN, basin_name)


async def resolve_field_id(field_name: str) -> Ambiguous | NotFound | Resolved:
    """Resolve a field name or record id to a Field record id."""
    return await resolve_reference_id(FIELD, field_name)


def geo_context_clause(lookup: ReferenceLookup, record_id: str) -> str:
    """Build the nested GeoContexts clause matching records against `record_id`."""
    return f"nested(data.GeoContexts, ({lookup.context_field}:{quoted(record_id)}))"


async def resolve_geo_context_filters(
    country: str | None = None,
    basin: str | None = None,
    field: str | None = None,
) -> tuple[list[str], tuple[ReferenceLookup, Ambiguous | NotFound] | None]:
    """Turn the names a caller gave into GeoContexts clauses.

    Returns the clauses, and the first name that did not resolve - a tool has
    nothing to search for once one filter is unusable, so it reports that name
    back instead of returning wells or traces the caller did not ask for.
    """
    clauses: list[str] = []
    for lookup, given in ((COUNTRY, country), (BASIN, basin), (FIELD, field)):
        if not given:
            continue
        resolved = await resolve_reference_id(lookup, given)
        if not isinstance(resolved, Resolved):
            return clauses, (lookup, resolved)
        clauses.append(geo_context_clause(lookup, resolved.id))
    return clauses, None


def unresolved_result(
    results_key: str, lookup: ReferenceLookup, resolved: Ambiguous | NotFound
) -> dict[str, Any]:
    """Report a name the caller has to disambiguate, in place of search results."""
    return {
        results_key: [],
        "totalCount": 0,
        f"resolved_{lookup.label}": resolved.model_dump(),
    }
