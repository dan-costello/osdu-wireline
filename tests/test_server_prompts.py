"""
Integration tests for server prompt registration.

Tests that prompts are properly registered with the MCP server.
"""

import pytest

from osdu_wireline.server import mcp


def test_prompts_available_in_main_package():
    """Test that the guide prompts are available in main package exports."""
    from osdu_wireline import guide_record_lifecycle, guide_search_patterns

    assert callable(guide_search_patterns)
    assert callable(guide_record_lifecycle)


@pytest.mark.asyncio
async def test_prompts_registered_with_server():
    """Test that exactly the expected prompts are registered with the server."""
    names = {prompt.name for prompt in await mcp.list_prompts()}

    assert names == {"guide_search_patterns", "guide_record_lifecycle"}


@pytest.mark.asyncio
async def test_prompt_execution_via_main_import():
    """Test that a prompt can be executed via main package import."""
    from osdu_wireline import guide_search_patterns

    result = await guide_search_patterns()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert len(result[0]["content"]) > 1000


def test_server_exposes_instructions():
    """Test that the server advertises usage instructions to clients."""
    assert mcp.instructions is not None
    assert "OSDU_MCP_ENABLE_WRITE_MODE" in mcp.instructions
