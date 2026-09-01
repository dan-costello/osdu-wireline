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
- **query_well_trajectories**: Trajectories for a list of well IDs
- **query_well_logs**: Well logs for a list of well IDs
- **query_well_marker_sets**: Marker sets (top picks) for a list of well IDs

### Seismic
- **query_seismic_trace_data**: Find seismic trace data by bounding box, country, basin, source or name
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

A name that matches nothing, or more than one record, comes back as
`resolved_country`, `resolved_basin` or `resolved_field` with the candidates to
choose between, and no wells - retry with one of them.
```python
{"wells": [], "totalCount": 0,
 "resolved_field": {"status": "ambiguous", "input": "Sleipner",
                    "candidates": [{"name": "Sleipner Ost", "id": "opendes:..."}],
                    "candidate_count": 1}}
```

### Find Seismic Trace Data by Name
```python
query_seismic_trace_data(name="AzureDisc", limit=10)
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
- `query_well_logs` / `query_well_trajectories` / `query_well_marker_sets` -> `{"results": [...], "totalCount": int}`
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
"""

    return [{"role": "user", "content": content}]
