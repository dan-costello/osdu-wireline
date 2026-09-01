"""Tests for guide_search_patterns prompt."""

import pytest

from osdu_wireline.prompts import guide_search_patterns
from osdu_wireline.tools import search as search_tools


@pytest.mark.asyncio
async def test_guide_search_patterns_returns_message_format():
    """Test that search patterns prompt returns correct Message format."""
    result = await guide_search_patterns()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert isinstance(result[0]["content"], str)
    assert len(result[0]["content"]) > 0


@pytest.mark.asyncio
async def test_guide_search_patterns_contains_key_sections():
    """Test that the prompt contains all expected content sections."""
    result = await guide_search_patterns()
    content = result[0]["content"]

    assert "Available Search Tools" in content
    assert "Quick Start Examples" in content
    assert "Multi-Step Workflows" in content
    assert "Response Shapes" in content
    assert "Performance Tips" in content


@pytest.mark.asyncio
async def test_guide_search_patterns_documents_every_registered_tool():
    """The prompt must describe each search tool the package actually exports."""
    result = await guide_search_patterns()
    content = result[0]["content"]

    for tool in search_tools.__all__:
        assert tool in content, f"{tool} is exported but undocumented in the prompt"


@pytest.mark.asyncio
async def test_guide_search_patterns_omits_removed_generic_tools():
    """The generic query tools were removed; the prompt must not advertise them."""
    result = await guide_search_patterns()
    content = result[0]["content"]

    assert "search_query(" not in content
    assert "search_by_id(" not in content
    assert "search_by_kind(" not in content


@pytest.mark.asyncio
async def test_guide_search_patterns_includes_domain_examples():
    """Test that the prompt includes runnable examples of the typed tools."""
    result = await guide_search_patterns()
    content = result[0]["content"]

    assert "bounding_box" in content
    # The reference filters take names, so the examples must call them by the
    # parameter names the tool actually exposes.
    assert 'query_wells(country="' in content
    assert 'basin="' in content
    assert 'field="' in content
    assert "country_id" not in content
    assert "basin_id" not in content
    assert "well_ids" in content
    assert "dataset_ids" in content


@pytest.mark.asyncio
async def test_guide_search_patterns_documents_response_shapes():
    """Test that the prompt states what each tool returns."""
    result = await guide_search_patterns()
    content = result[0]["content"]

    assert "totalCount" in content
    assert '"wells"' in content
    assert '"trace_data"' in content
    assert '"datasets"' in content


@pytest.mark.asyncio
async def test_guide_search_patterns_includes_workflows():
    """Test that the prompt includes multi-step workflow guidance."""
    result = await guide_search_patterns()
    content = result[0]["content"]

    assert "Wells to Logs" in content
    assert "Seismic Trace Data to Files" in content
    assert "limit=" in content
