"""Typed projections of OSDU records.

Each search tool declares a model whose field aliases are the OSDU property
paths it reads. The `returned_fields` classmethod derives the search API's
`returnedFields` list from those aliases, so the fields a tool asks for cannot
drift from the fields it actually consumes.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


def _flatten_into(source: dict[str, Any], prefix: str, target: dict[str, Any]) -> None:
    """Copy `source` into `target`, flattening nested dicts onto dotted keys."""
    for key, value in source.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            # Keep the container as well, so a model may alias either depth.
            target.setdefault(path, value)
            _flatten_into(value, f"{path}.", target)
        else:
            target[path] = value


class OsduData(BaseModel):
    """Base for the `data` block of an OSDU record.

    Depending on the property, OSDU returns a requested field either flattened
    onto a dotted key ("DatasetProperties.FileCollectionPath") or as nested
    objects. Both are normalised to the dotted form before validation, so a
    model only ever declares the dotted path.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # Names the field holding this kind's WGS84 geometry, for models whose kind
    # can be filtered by a bounding box. The path itself lives on that field's
    # alias, so it is never written twice.
    spatial_field_name: ClassVar[str | None] = None

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        flattened: dict[str, Any] = {}
        _flatten_into(value, "", flattened)
        return flattened

    @classmethod
    def returned_fields(cls) -> list[str]:
        """The `returnedFields` list needed to populate this model."""
        fields = [
            f"data.{field.alias or name}"
            for name, field in cls.model_fields.items()
            if not field.exclude
        ]
        return ["id", *fields]

    @classmethod
    def spatial_field(cls) -> str | None:
        """The `spatialFilter.field` path for this kind's geometry, if it has one."""
        if cls.spatial_field_name is None:
            return None

        # KeyError here means spatial_field_name names a field that does not
        # exist - fail loudly rather than filter on nothing.
        field = cls.model_fields[cls.spatial_field_name]
        return f"data.{field.alias or cls.spatial_field_name}"
