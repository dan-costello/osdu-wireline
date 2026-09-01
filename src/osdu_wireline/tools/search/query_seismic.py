"""Search OSDU Instance for seismic trace data and the datasets backing it."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...shared.clients import BoundingBox, SearchClient
from ...shared.exceptions import handle_osdu_exceptions
from ._models import OsduData
from ._query import normalize_record_id, quoted, wildcard_contains


class SeismicTraceDataFields(OsduData):
    """The fields query_seismic_trace_data reads off a SeismicTraceData record."""

    spatial_field_name: ClassVar[str | None] = "spatial_area"

    artefacts: Any = Field(default=None, alias="Artefacts")
    datasets: list[str] = Field(default_factory=list, alias="Datasets")
    geo_contexts: Any = Field(default=None, alias="GeoContexts")
    name: str | None = Field(default=None, alias="Name")
    seismic_domain_type_id: str | None = Field(
        default=None, alias="SeismicDomainTypeID"
    )
    source: str | None = Field(default=None, alias="Source")
    spatial_area: Any = Field(default=None, alias="SpatialArea.Wgs84Coordinates")


class FileSourceInfo(BaseModel):
    """One file inside a seismic dataset's FileSourceInfos list."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    file_source: str | None = Field(default=None, alias="FileSource")
    name: str | None = Field(default=None, alias="Name")
    file_size: int | None = Field(default=None, alias="FileSize")
    domain: str | None = Field(default=None, alias="Domain")


class SeismicDatasetFields(OsduData):
    """The fields query_seismic_datasets reads off a FileCollection record."""

    collection_path: str | None = Field(
        default=None, alias="DatasetProperties.FileCollectionPath"
    )
    file_source_infos: list[FileSourceInfo] = Field(
        default_factory=list, alias="DatasetProperties.FileSourceInfos"
    )

    def resolved_files(self, record_id: str | None) -> list[dict[str, Any]]:
        """Yield each file with its FileSource resolved against the collection path."""

        files: list[dict[str, Any]] = []
        for info in self.file_source_infos:
            if not info.file_source:
                continue

            file_source = info.file_source
            if self.collection_path and not file_source.startswith(
                self.collection_path
            ):
                file_source = (
                    self.collection_path.rstrip("/") + "/" + file_source.lstrip("/")
                )

            files.append(
                {
                    "id": record_id,
                    "file_source": file_source,
                    "name": info.name,
                    "file_size": info.file_size,
                    "domain": info.domain,
                }
            )

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
            f"nested(data.GeoContexts, (GeoPoliticalEntityID:{quoted(country_id)}))"
        )
    if basin_id:
        clauses.append(f"nested(data.GeoContexts, (BasinID:{quoted(basin_id)}))")
    if source:
        clauses.append(f"data.Source:{quoted(source)}")
    if name:
        # Unquoted: a quoted value is a phrase, in which * is a literal asterisk.
        clauses.append(f"data.Name:({wildcard_contains(name)})")

    query = " AND ".join(clauses) if clauses else ""

    async with SearchClient() as client:
        response = await client.search_query(
            query=query,
            kind="osdu:wks:work-product-component--SeismicTraceData:*",
            limit=min(1000, limit),
            offset=offset,
            bounding_box=bounding_box,
            spatial_field=SeismicTraceDataFields.spatial_field(),
            returned_fields=SeismicTraceDataFields.returned_fields(),
        )

    results = [
        {
            "id": result.get("id"),
            **SeismicTraceDataFields.model_validate(
                result.get("data", {})
            ).model_dump(),
        }
        for result in response.get("results", [])
    ]
    return {"trace_data": results, "totalCount": response.get("totalCount", 0)}


@handle_osdu_exceptions
async def query_seismic_datasets(
    dataset_ids: list[str],
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the OSDU instance for seismic datasets, based on a list of dataset IDs."""

    if not dataset_ids:
        raise ValueError("dataset_ids must contain at least one dataset ID")

    ids = [normalize_record_id(i) for i in dataset_ids]
    query = "id:(" + " OR ".join(quoted(i) for i in ids) + ")"
    async with SearchClient() as client:
        response = await client.search_query(
            query=query,
            kind=[
                "osdu:wks:dataset--FileCollection.Bluware.OpenVDS:*",
                "osdu:wks:dataset--FileCollection.SEGY:*",
            ],
            limit=min(1000, max(limit, len(ids))),
            offset=offset,
            returned_fields=SeismicDatasetFields.returned_fields(),
        )

    datasets = [
        file
        for result in response.get("results", [])
        for file in SeismicDatasetFields.model_validate(
            result.get("data", {})
        ).resolved_files(result.get("id"))
    ]
    return {"datasets": datasets, "totalCount": response.get("totalCount", 0)}
