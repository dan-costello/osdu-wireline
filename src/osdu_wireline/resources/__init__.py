"""MCP Resources for OSDU workflow templates and examples."""

import json
from collections import namedtuple
from pathlib import Path

from mcp.server.fastmcp.resources import FileResource
from pydantic import AnyUrl

ResourceDir = namedtuple("ResourceDir", ["directory", "scheme", "label"])

# Get the resources directory path
RESOURCES_DIR = Path(__file__).parent
RESOURCE_DIRS = [
    ResourceDir(RESOURCES_DIR / "templates", "template", "Template"),
    ResourceDir(RESOURCES_DIR / "references", "reference", "Reference"),
]


MIME_TYPES = {
    "json": "application/json",
    "md": "text/markdown",
}


def _describe(resource_file: Path, ext: str) -> str | None:
    """Build a resource description from what the file states itself.

    Returns:
        The file's own description, or None if it has none
    """
    if ext == "json":
        try:
            with open(resource_file, encoding="utf-8") as f:
                content = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(content, dict):
            return None

        description = content.get("_description")
        return description if isinstance(description, str) else None
    if ext == "md":
        try:
            text = resource_file.read_text(encoding="utf-8")
        except OSError:
            return None

        paragraph: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if not stripped:
                if paragraph:
                    break
                continue
            paragraph.append(stripped)

        return " ".join(paragraph) or None

    return None


def get_workflow_resources() -> list[FileResource]:
    """Get all MCP resources for OSDU workflow templates."""
    resources: list[FileResource] = []

    for directory, scheme, label in RESOURCE_DIRS:
        for resource_file in sorted(directory.glob("*")):
            if not resource_file.is_file():
                continue

            ext = resource_file.suffix.lstrip(".")
            mime_type = MIME_TYPES.get(ext)
            if mime_type is None:
                continue

            resources.append(
                FileResource(
                    uri=AnyUrl(f"{scheme}://{resource_file.name}"),
                    name=f"{label}: {resource_file.name}",
                    description=_describe(resource_file, ext),
                    mime_type=mime_type,
                    path=resource_file,
                )
            )

    return resources


__all__ = ["get_workflow_resources"]
