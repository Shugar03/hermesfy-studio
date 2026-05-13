"""Tests for Narrator fallback narration."""

import pytest
from hermesfy.services.narrator import Narrator


@pytest.fixture
def narrator():
    return Narrator()


@pytest.mark.asyncio
async def test_narrate_with_text_content(narrator):
    """When stdout has text content, it's returned as-is."""
    stdout = "Here is the generated image prompt."
    result = await narrator.narrate(stdout)
    assert "Here is the generated image prompt" in result


@pytest.mark.asyncio
async def test_narrate_empty_stdout(narrator):
    """When stdout has no text or actions, a default message is returned."""
    result = await narrator.narrate("", use_external=False)
    assert len(result) > 0
    assert "acciones visibles" in result.lower() or "acciones" in result.lower()


@pytest.mark.asyncio
async def test_narrate_with_actions_only(narrator):
    """When stdout has actions but no text, fallback narration is generated."""
    stdout = (
        "hermesfy create image_gen --workflow-id wf_1\n"
        "hermesfy connect node_a node_b --workflow-id wf_1\n"
    )
    result = await narrator.narrate(stdout, use_external=False)
    assert len(result) > 0
    # Should contain a summary, not the raw stdout
    assert "Resumen" in result or "acciones" in result.lower()


@pytest.mark.asyncio
async def test_narrate_passthrough(narrator):
    """narrate_passthrough returns text unchanged."""
    text = "Hello world"
    result = await narrator.narrate_passthrough(text)
    assert result == text


@pytest.mark.asyncio
async def test_narrate_passthrough_empty(narrator):
    """narrate_passthrough handles empty string."""
    result = await narrator.narrate_passthrough("")
    assert len(result) > 0  # should return a default message
