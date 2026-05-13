"""Tests for HermesVerboseParser stdout parsing."""

import pytest
from hermesfy.services.hermes_verbose_parser import (
    HermesVerboseParser,
    VerboseEvent,
)


@pytest.fixture
def parser():
    return HermesVerboseParser()


def test_parse_empty_line(parser):
    """Empty lines return None."""
    assert parser.parse_line("") is None
    assert parser.parse_line("   ") is None


def test_parse_text_line(parser):
    """Plain text lines are parsed as 'text' events."""
    ev = parser.parse_line("Hello, I will create a DAG for you.")
    assert ev is not None
    assert ev.event_type == "text"
    assert "Hello" in ev.data["content"]


def test_parse_tool_call(parser):
    """Lines with <tool_call> JSON are parsed correctly."""
    line = '<tool_call>{"name": "hermesfy_define_workflow", "args": {"nodes": []}}</tool_call>'
    ev = parser.parse_line(line)
    assert ev is not None
    assert ev.event_type == "tool_call"
    assert ev.data["tool_name"] == "hermesfy_define_workflow"


def test_parse_action_tap(parser):
    """Lines with hermesfy CLI commands are parsed as action events."""
    ev = parser.parse_line("hermesfy create image_gen --workflow-id wf_123")
    assert ev is not None
    assert ev.event_type == "action"
    assert ev.data["cli_command"] == "create"


def test_parse_learning_saved(parser):
    """LEARNING_SAVED lines are detected."""
    ev = parser.parse_line("LEARNING_SAVED: flux-schnell-num-steps-cap")
    assert ev is not None
    assert ev.event_type == "learning"
    assert ev.data["topic"] == "flux-schnell-num-steps-cap"


def test_parse_stream(parser):
    """parse_stream handles multi-line stdout."""
    stdout = (
        "Hello! I'll help you.\n"
        '<tool_call>{"name": "terminal", "args": {"command": "echo hi"}}</tool_call>\n'
        "Done! Created the node.\n"
    )
    events = parser.parse_stream(stdout)
    assert len(events) >= 3
    types = [e.event_type for e in events]
    assert "text" in types
    assert "tool_call" in types


def test_has_only_actions_true(parser):
    """Returns True when there are actions but no text."""
    events = [
        VerboseEvent(event_type="tool_call", data={"tool_name": "test"}),
        VerboseEvent(event_type="action", data={"cli_command": "create"}),
    ]
    assert parser.has_only_actions(events) is True


def test_has_only_actions_false(parser):
    """Returns False when there is text content."""
    events = [
        VerboseEvent(event_type="text", data={"content": "Hello"}),
        VerboseEvent(event_type="tool_call", data={"tool_name": "test"}),
    ]
    assert parser.has_only_actions(events) is False


def test_extract_actions_summary(parser):
    """Actions summary extracts human-readable strings."""
    events = [
        VerboseEvent(event_type="action", data={"full": "hermesfy create image_gen --workflow-id wf_1"}),
        VerboseEvent(event_type="tool_call", data={"tool_name": "hermesfy_execute_workflow"}),
    ]
    summary = parser.extract_actions_summary(events)
    assert len(summary) == 2
    assert any("create" in s for s in summary)
    assert any("hermesfy_execute_workflow" in s for s in summary)
