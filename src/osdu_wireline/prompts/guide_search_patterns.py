"""Search patterns guidance prompt."""

from .prompt_types import Prompt


async def guide_search_patterns() -> list[Prompt]:
    """Provide search pattern guidance for OSDU operations.

    Returns:
        List[Message]: Search pattern guidance content
    """
    content = """# OSDU Search Patterns Guide

## Available Search Tools

Search is exposed as typed, domain-specific tools. Each one targets a single
OSDU kind and returns a fixed, documented set of fields - there is no generic
query tool, so you do not compose Elasticsearch syntax by hand.

### Wells
- **query_wells**: Find wells by bounding box, country, basin, field or source
- **query_well_trajectories**: Trajectories for a list of well IDs, a field, or both
- **query_well_logs**: Well logs for a list of well IDs, a field, or both
- **query_well_marker_sets**: Marker sets for a list of well IDs, a field, or both, with the top picks themselves

### Seismic
- **query_seismic_trace_data**: Find seismic trace data by bounding box, country, basin, field, source or name
- **query_seismic_datasets**: Resolve dataset IDs to their file locations

## Quick Start Examples

### Find Wells by Area
```python
query_wells(
    bounding_box={
        "min_latitude": 29.0, "max_latitude": 31.0,
        "min_longitude": -95.0, "max_longitude": -93.0,
    },
    limit=25,
)
```

### Find Wells by Geopolitical Context
`country`, `basin` and `field` take the name, not the ID - the tool resolves it
against the instance, matching case, aliases, and partial names. Pass a record
ID instead when you already hold one.
```python
query_wells(country="United States")
query_wells(basin="Gulf of Mexico", source="Public")
query_wells(country="Norway", field="Sleipner")
query_wells(basin="opendes:master-data--Basin:GulfOfMexico:")
```

`country` and `basin` are recorded on the well itself. `field` is not - it is
recorded on the wellbore, so the tool resolves it by finding the wellbores in
that field and returning the wells they hang off. This is transparent, but it
means a field filter costs an extra search and cannot be combined with a very
large result set.

A name matching more than one record is handled two ways, and `resolved_country`,
`resolved_basin` or `resolved_field` tells you which.

**Five candidates or fewer: all of them are searched**, and the results are the
union. The candidates come back alongside real results so you can see what was
covered - do not re-run the search per candidate, it has already been done.
```python
query_wells(field="Sleipner")
{"wells": [...], "totalCount": 42,
 "resolved_field": {"status": "ambiguous", "input": "Sleipner",
                    "candidates": [{"name": "Sleipner Ost", "id": "opendes:..."},
                                   {"name": "Sleipner Vest", "id": "opendes:..."}],
                    "candidate_count": 2}}
```

**More than five, or no match at all: nothing is searched.** The candidates come
back with an empty result - retry with one of them, or with a longer name.
```python
{"wells": [], "totalCount": 0,
 "resolved_field": {"status": "not_found", "input": "Atlantis",
                    "candidates": ["Sleipner Ost", "Gudrun"],
                    "candidate_count": 2}}
```

Read `totalCount` to tell the two apart: an ambiguous name that was searched has
results, one that was not is empty.

### Find Seismic Trace Data by Name
`query_seismic_trace_data` resolves `country`, `basin` and `field` the same way.
```python
query_seismic_trace_data(name="AzureDisc", limit=10)
query_seismic_trace_data(basin="Gulf of Mexico", source="Public")
```

## Multi-Step Workflows

The domain tools are designed to be chained: the IDs one tool returns are the
input to the next.

### Wells to Logs
```python
# Step 1: Find wells in an area of interest
wells = query_wells(country="United States")

# Step 2: Fetch the logs hanging off those wells
# (wellbore resolution happens inside the tool)
query_well_logs(well_ids=[well["id"] for well in wells["wells"]])
```

### A Whole Field in One Call
The wellbore-child tools take `field` directly, so there is no need to fetch
the wells first. Give both to narrow to the wellbores that are in the field
*and* hang off those wells.
```python
query_well_marker_sets(field="Sleipner Ost")
query_well_logs(field="Sleipner Ost", well_ids=["opendes:master-data--Well:123"])
```

### Seismic Trace Data to Files
```python
# Step 1: Find the trace data
trace = query_seismic_trace_data(name="AzureDisc")

# Step 2: Resolve its Datasets references to concrete file locations
query_seismic_datasets(
    dataset_ids=[d for t in trace["trace_data"] for d in t["datasets"]]
)
```

## Response Shapes

Every tool returns a `totalCount` plus a named list of projected records. Each
record carries its `id` alongside the snake_case fields that tool declares:

- `query_wells` -> `{"wells": [...], "totalCount": int}`
- `query_well_logs` / `query_well_trajectories` -> `{"results": [...], "totalCount": int}`
- `query_well_marker_sets` -> `{"results": [...], "totalCount": int}`, where each
  result also carries `markers`: a list of `{marker_name, marker_measured_depth,
  marker_type_id, observation_number, interpreter_name}`
- `query_seismic_trace_data` -> `{"trace_data": [...], "totalCount": int}`
- `query_seismic_datasets` -> `{"datasets": [...], "totalCount": int}`

Fields a tool does not declare are not requested from OSDU and will not appear.

## Performance Tips

- Narrow with a bounding box or a geopolitical filter before raising `limit`
- Pass whole ID lists to the wellbore-child tools rather than calling per well
- `limit` is capped at 1000 by every tool
- Prefer chaining tools over broad scans - each one already targets a single kind

## Common Fields

- `id` - Record identifier, and the input to the chained tools
- `facility_name` - Well name (`data.FacilityName`)
- `name` - Record name (`data.Name`)
- `source` - Originating system (`data.Source`)
- `geo_contexts` - Basin and geopolitical references (`data.GeoContexts`)
- `spatial_location` / `spatial_area` - WGS84 geometry
- `markers` - The picks on a marker set (`data.Markers`), depths in metres
"""

    return [{"role": "user", "content": content}]
