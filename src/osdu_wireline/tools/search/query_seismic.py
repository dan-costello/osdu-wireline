"""Search OSDU Instance for seismic trace data and the datasets backing it."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...shared.clients import BoundingBox, SearchClient
from ...shared.exceptions import handle_osdu_exceptions


class FileSourceInfo(BaseModel):
    """One file inside a seismic dataset's FileSourceInfos list."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    file_source: str | None = Field(default=None, alias="FileSource")
    name: str | None = Field(default=None, alias="Name")
    file_size: int | None = Field(default=None, alias="FileSize")
    domain: str | None = Field(default=None, alias="Domain")


class SeismicDatasetData(BaseModel):
    """The `data` block of a dataset--FileCollection.* record.

    OSDU flattens nested properties into dotted keys when returnedFields is used,
    so the aliases here carry the dots rather than nesting further.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    collection_path: str | None = Field(
        default=None, alias="DatasetProperties.FileCollectionPath"
    )
    file_source_infos: list[FileSourceInfo] = Field(
        default_factory=list, alias="DatasetProperties.FileSourceInfos"
    )


class SeismicDataset(BaseModel):
    """A single search result for a seismic dataset."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = None
    data: SeismicDatasetData = Field(default_factory=SeismicDatasetData)

    def resolved_files(self) -> list[dict[str, Any]]:
        """Yield each file with its FileSource resolved against the collection path."""

        files: list[dict[str, Any]] = []
        for info in self.data.file_source_infos:
            if not info.file_source:
                continue

            file_source = info.file_source
            collection_path = self.data.collection_path
            if collection_path and not file_source.startswith(collection_path):
                file_source = (
                    collection_path.rstrip("/") + "/" + file_source.lstrip("/")
                )

            files.append({"id": self.id, "file_source": file_source, "name": info.name})

        return files


@handle_osdu_exceptions
async def query_seismic_trace_data(
    bounding_box: BoundingBox | None = None,
    country_id: str | None = None,
    basin_id: str | None = None,
    source: str | None = None,
    name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the OSDU instance for seismic trace data, based on a number of criteria (geographic bounding boxes, country_id, basin_id, name)"""

    clauses: list[str] = []
    if country_id:
        clauses.append(
            f'nested(data.GeoContexts, (GeoPoliticalEntityID:"{country_id}"))'
        )
    if basin_id:
        clauses.append(f'nested(data.GeoContexts, (BasinID:"{basin_id}"))')
    if source:
        clauses.append(f'data.Source:"{source}"')
    if name:
        clauses.append(f'data.Name:"*{name}*"')  # Use wildcard search for name

    query = " AND ".join(clauses) if clauses else ""

    async with SearchClient() as client:
        search_results = await client.search_query(
            query=query,
            kind="*:wks:work-product-component--SeismicTraceData:*",
            limit=min(1000, limit),
            offset=offset,
            bounding_box=bounding_box,
            returnedFields=["id", "data.Datasets", "data.Name", "data.Source"],
        )

        results = []
        for result in search_results.get("results", []):
            item = {
                "id": result.get("id"),
                "name": result.get("data", {}).get("Name"),
                "source": result.get("data", {}).get("Source"),
                "datasets": result.get("data", {}).get("Datasets", []),
            }
            results.append(item)
        return {"results": results, "total_count": search_results.get("total_count", 0)}


@handle_osdu_exceptions
async def query_seismic_datasets(
    dataset_ids: list[str],
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the OSDU instance for seismic datasets, based on a list of dataset IDs."""

    query = "id:(" + " OR ".join(f'"{dataset_id}"' for dataset_id in dataset_ids) + ")"
    async with SearchClient() as client:
        search_results = await client.search_query(
            query=query,
            kind=[
                "osdu:wks:dataset--FileCollection.Bluware.OpenVDS:*",
                "osdu:wks:dataset--FileCollection.SEGY:*",
            ],
            limit=min(1000, limit),
            offset=offset,
            returnedFields=[
                "id",
                "data.DatasetProperties.FileCollectionPath",
                "data.DatasetProperties.FileSourceInfos",
            ],
        )

    datasets = [
        file
        for result in search_results.get("results", [])
        for file in SeismicDataset.model_validate(result).resolved_files()
    ]
    return {"datasets": datasets}
