"""Tests for workflow resource registration and accessibility."""

import json

from osdu_wireline import resources as resources_module
from osdu_wireline.resources import (
    ResourceDir,
    _describe,
    get_workflow_resources,
)

# --- Discovery mechanics (hermetic: synthetic dirs, no real filenames) ---


def test_discovers_files_per_configured_directory(tmp_path, monkeypatch):
    """Each configured (directory, scheme, label) yields one resource per
    supported-extension file, skipping unsupported extensions and subdirs."""
    templates_dir = tmp_path / "templates"
    references_dir = tmp_path / "references"
    templates_dir.mkdir()
    references_dir.mkdir()

    (templates_dir / "a.json").write_text('{"_description": "desc a"}')
    (templates_dir / "ignored.txt").write_text("not a supported extension")
    (templates_dir / "subdir").mkdir()
    (references_dir / "b.md").write_text("# Title\n\nSome prose paragraph.\n")

    monkeypatch.setattr(
        resources_module,
        "RESOURCE_DIRS",
        [
            ResourceDir(templates_dir, "template", "Template"),
            ResourceDir(references_dir, "reference", "Reference"),
        ],
    )

    resources = get_workflow_resources()

    by_uri = {str(r.uri): r for r in resources}
    assert set(by_uri) == {"template://a.json", "reference://b.md"}

    template_resource = by_uri["template://a.json"]
    assert template_resource.name == "Template: a.json"
    assert template_resource.mime_type == "application/json"
    assert template_resource.path == templates_dir / "a.json"

    reference_resource = by_uri["reference://b.md"]
    assert reference_resource.name == "Reference: b.md"
    assert reference_resource.mime_type == "text/markdown"


def test_resource_uris_are_unique_across_schemes(tmp_path, monkeypatch):
    """Same-basename files in different configured dirs stay distinct via scheme."""
    templates_dir = tmp_path / "templates"
    references_dir = tmp_path / "references"
    templates_dir.mkdir()
    references_dir.mkdir()

    (templates_dir / "x.json").write_text("{}")
    (references_dir / "x.json").write_text("{}")

    monkeypatch.setattr(
        resources_module,
        "RESOURCE_DIRS",
        [
            ResourceDir(templates_dir, "template", "Template"),
            ResourceDir(references_dir, "reference", "Reference"),
        ],
    )

    resources = get_workflow_resources()
    uris = [str(r.uri) for r in resources]

    assert len(uris) == len(set(uris))
    assert set(uris) == {"template://x.json", "reference://x.json"}


# --- Description derivation (hermetic: calls _describe directly) ---


def test_describe_json_variants(tmp_path):
    """_describe pulls _description from JSON dicts, else returns None."""
    with_desc = tmp_path / "with_desc.json"
    with_desc.write_text('{"_description": "hello"}')
    assert _describe(with_desc, "json") == "hello"

    no_desc = tmp_path / "no_desc.json"
    no_desc.write_text('{"other": "field"}')
    assert _describe(no_desc, "json") is None

    non_string_desc = tmp_path / "non_string.json"
    non_string_desc.write_text('{"_description": 5}')
    assert _describe(non_string_desc, "json") is None

    non_dict = tmp_path / "non_dict.json"
    non_dict.write_text("[1, 2, 3]")
    assert _describe(non_dict, "json") is None

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not valid json")
    assert _describe(malformed, "json") is None

    missing = tmp_path / "does_not_exist.json"
    assert _describe(missing, "json") is None


def test_describe_markdown_variants(tmp_path):
    """_describe takes the first prose paragraph from markdown, else None."""
    with_paragraph = tmp_path / "with_paragraph.md"
    with_paragraph.write_text("# Title\n\nFirst line.\nSecond line.\n\nIgnored.\n")
    assert _describe(with_paragraph, "md") == "First line. Second line."

    only_headings = tmp_path / "only_headings.md"
    only_headings.write_text("# Title\n## Subtitle\n")
    assert _describe(only_headings, "md") is None

    empty = tmp_path / "empty.md"
    empty.write_text("")
    assert _describe(empty, "md") is None

    missing = tmp_path / "does_not_exist.md"
    assert _describe(missing, "md") is None


# --- Structural checks against the real repo directories (no hardcoded filenames) ---


def test_matches_actual_directory_contents():
    """get_workflow_resources() output matches an independent walk of the real
    RESOURCE_DIRS, catching drift without naming any specific file."""
    expected = set()
    for directory, scheme, _label in resources_module.RESOURCE_DIRS:
        for path in sorted(directory.glob("*")):
            if not path.is_file():
                continue
            ext = path.suffix.lstrip(".")
            if ext not in resources_module.MIME_TYPES:
                continue
            expected.add((f"{scheme}://{path.name}", path))

    resources = get_workflow_resources()
    actual = {(str(r.uri), r.path) for r in resources}

    assert actual == expected
    assert len(resources) == len(expected)


def test_resources_are_well_formed_for_registration():
    """Every real resource is well-formed enough for FastMCP.add_resource."""
    resources = get_workflow_resources()
    assert resources

    for resource in resources:
        assert resource.name
        assert resource.mime_type in ("application/json", "text/markdown")
        assert resource.path.exists(), f"Resource file does not exist: {resource.path}"
        assert resource.description is None or isinstance(resource.description, str)
        if resource.description is not None:
            assert resource.description.strip()

        if resource.mime_type == "application/json":
            with open(resource.path, encoding="utf-8") as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    raise AssertionError(
                        f"Resource file {resource.path} contains invalid JSON: {e}"
                    ) from e
        else:
            with open(resource.path, encoding="utf-8") as f:
                assert f.read().strip(), f"Resource file {resource.path} is empty"
