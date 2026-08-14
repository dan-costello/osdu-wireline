"""Tests for the SchemaId helper in the schema client module."""

import pytest

from osdu_wireline.shared.clients.schema_client import SchemaId
from osdu_wireline.shared.exceptions import OSMCPValidationError


def test_str_formats_id():
    """Test that SchemaId formats to authority:source:entity:major.minor.patch."""
    schema_id = SchemaId(
        authority="lab", source="test", entity="testSchema", major=1, minor=2, patch=3
    )
    assert str(schema_id) == "lab:test:testSchema:1.2.3"


def test_version_property():
    """Test that version returns major.minor.patch."""
    schema_id = SchemaId(
        authority="lab", source="test", entity="testSchema", major=1, minor=2, patch=3
    )
    assert schema_id.version == "1.2.3"


def test_to_schema_identity():
    """Test that to_schema_identity builds the OSDU API shape."""
    schema_id = SchemaId(
        authority="lab", source="test", entity="testSchema", major=1, minor=0, patch=0
    )
    assert schema_id.to_schema_identity() == {
        "authority": "lab",
        "source": "test",
        "entityType": "testSchema",
        "schemaVersionMajor": 1,
        "schemaVersionMinor": 0,
        "schemaVersionPatch": 0,
        "id": "lab:test:testSchema:1.0.0",
    }


def test_parse_round_trips_str():
    """Test that parsing a formatted ID recovers the original components."""
    parsed = SchemaId.parse("osdu:wks:AbstractAccessControlList:1.0.0")
    assert parsed.authority == "osdu"
    assert parsed.source == "wks"
    assert parsed.entity == "AbstractAccessControlList"
    assert parsed.major == 1
    assert parsed.minor == 0
    assert parsed.patch == 0
    assert str(parsed) == "osdu:wks:AbstractAccessControlList:1.0.0"


@pytest.mark.parametrize(
    "bad_id",
    [
        "lab:test:testSchema",  # missing version segment
        "lab:test:1.0.0",  # only 3 colon-separated parts
        "lab:test:testSchema:1.0.0:extra",  # too many parts
        "lab:test:testSchema:1.0",  # version missing patch
        "lab:test:testSchema:1.0.0.0",  # version has too many parts
        "lab:test:testSchema:x.0.0",  # non-numeric version component
        "",  # empty string
    ],
)
def test_parse_raises_on_malformed_id(bad_id):
    """Test that parse raises OSMCPValidationError on malformed input."""
    with pytest.raises(OSMCPValidationError):
        SchemaId.parse(bad_id)
