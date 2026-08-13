"""Tests for utility functions."""

from datetime import datetime

from freezegun import freeze_time

from osdu_wireline.shared.utils import get_timestamp


@freeze_time("2025-01-15 10:30:00")
def test_get_timestamp():
    """Test timestamp generation."""
    timestamp = get_timestamp()
    assert timestamp == "2025-01-15T10:30:00Z"
    # Verify it's a valid ISO format
    datetime.fromisoformat(timestamp)
