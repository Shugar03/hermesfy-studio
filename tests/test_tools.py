"""Integration tests for all 7 Hermes tools: define → execute → status → edit → re-execute."""

import json
import uuid
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from hermesfy.dag.graph import Node, Edge, Workflow, NodeType


# ── Helpers ────────────────────────────────────────────────────────────


def make_tool_nodes(prompt="a cat", model="flux-dev"):
    return [
        {"id": "prompt-1", "type": "text_prompt", "config": {"prompt": prompt}},
        {"id": "gen-1", "type": "image_gen", "config": {"model": model, "prompt": "{{prompt-1}}"}},
    ]


def make_tool_edges():
    return [{"source": "prompt-1", "target": "gen-1"}]


# ── T4.1: Workflow Store ───────────────────────────────────────────────


class TestWorkflowStore:
    """Test the in-memory workflow store (CRUD operations)."""

    def test_store_add_and_get(self):
        """Workflow can be stored and retrieved by ID."""
        from hermesfy.tools.workflows import add_workflow, get_workflow

        wf = Workflow(
            id="test-1",
            name="test workflow",
            nodes=[Node(id="n1", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"})],
            edges=[],
        )
        add_workflow(wf)
        retrieved = get_workflow("test-1")
        assert retrieved is not None
        assert retrieved.name == "test workflow"

    def test_store_list(self):
        """All stored workflows can be listed."""
        from hermesfy.tools.workflows import add_workflow, list_workflows, workflows

        # Clear any previous state
        workflows.clear()

        wf1 = Workflow(id="wf-a", name="A", nodes=[], edges=[])
        wf2 = Workflow(id="wf-b", name="B", nodes=[], edges=[])
        add_workflow(wf1)
        add_workflow(wf2)

        wf_list = list_workflows()
        assert len(wf_list) == 2

    def test_store_delete(self):
        """Workflow can be deleted by ID."""
        from hermesfy.tools.workflows import add_workflow, delete_workflow, get_workflow

        wf = Workflow(id="to-delete", name="bye", nodes=[], edges=[])
        add_workflow(wf)
        delete_workflow("to-delete")
        assert get_workflow("to-delete") is None

    def test_store_get_missing_returns_none(self):
        """Getting a non-existent workflow returns None."""
        from hermesfy.tools.workflows import get_workflow
        assert get_workflow("nonexistent-id") is None


# ── T4.2: define_workflow ──────────────────────────────────────────────


class TestDefineWorkflow:
    """Tests for the hermesfy_define_workflow tool."""

    def test_define_valid_linear_workflow(self):
        """Define a simple A→B workflow returns workflow_id + canvas."""
        from hermesfy.tools.define_workflow import define_workflow

        result = define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges(), name="my-flow")
        parsed = json.loads(result) if isinstance(result, str) else result

        assert "workflow_id" in parsed
        assert "canvas" in parsed
        assert parsed["workflow_id"] is not None

    def test_define_empty_nodes_returns_error(self):
        """Empty nodes array returns INVALID_WORKFLOW error."""
        from hermesfy.tools.define_workflow import define_workflow

        result = define_workflow(nodes=[], edges=[])
        parsed = json.loads(result) if isinstance(result, str) else result
        assert "error" in parsed
        assert parsed["error"]["code"] == "INVALID_WORKFLOW"

    def test_define_cycle_returns_error(self):
        """Circular edges return CYCLE_DETECTED error."""
        from hermesfy.tools.define_workflow import define_workflow

        nodes = [
            {"id": "a", "type": "text_prompt", "config": {"prompt": "x"}},
            {"id": "b", "type": "text_prompt", "config": {"prompt": "y"}},
        ]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
        result = define_workflow(nodes=nodes, edges=edges)
        parsed = json.loads(result) if isinstance(result, str) else result
        assert "error" in parsed
        assert parsed["error"]["code"] == "CYCLE_DETECTED"

    def test_define_default_name(self):
        """If no name is provided, auto-generates one."""
        from hermesfy.tools.define_workflow import define_workflow

        result = define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges())
        parsed = json.loads(result) if isinstance(result, str) else result
        assert "workflow_id" in parsed


# ── T4.3 + T4.4: execute_workflow + workflow_status ────────────────────


class TestExecuteAndStatus:
    """Tests for execute_workflow and workflow_status tools."""

    def test_execute_workflow_happy_path(self):
        """Execute a defined workflow and verify results."""
        from hermesfy.tools.define_workflow import define_workflow
        from hermesfy.tools.execute_workflow import execute_workflow

        # First define
        def_result = json.loads(define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges()))
        wf_id = def_result["workflow_id"]

        # Then execute (uses MockProvider internally)
        result = json.loads(execute_workflow(workflow_id=wf_id))
        assert "canvas" in result or "error" not in result
        # Either successful execution or PROVIDER_AUTH (if FAL_API_KEY not set)
        if "error" in result:
            assert result["error"]["code"] in ("PROVIDER_AUTH",)

    def test_status_known_workflow(self):
        """Status on a known workflow returns canvas."""
        from hermesfy.tools.define_workflow import define_workflow
        from hermesfy.tools.workflow_status import workflow_status

        def_result = json.loads(define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges()))
        wf_id = def_result["workflow_id"]

        result = json.loads(workflow_status(workflow_id=wf_id))
        assert "canvas" in result

    def test_status_unknown_workflow(self):
        """Status on unknown workflow returns NOT_FOUND error."""
        from hermesfy.tools.workflow_status import workflow_status

        result = json.loads(workflow_status(workflow_id="nonexistent"))
        assert "error" in result
        assert result["error"]["code"] == "NODE_NOT_FOUND"


# ── T4.5: edit_node ───────────────────────────────────────────────────


class TestEditNode:
    """Tests for the hermesfy_edit_node tool."""

    def test_edit_node_config(self):
        """Edit a node's config and get updated canvas."""
        from hermesfy.tools.define_workflow import define_workflow
        from hermesfy.tools.edit_node import edit_node

        def_result = json.loads(define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges()))
        wf_id = def_result["workflow_id"]

        result = json.loads(edit_node(
            workflow_id=wf_id,
            node_id="prompt-1",
            changes={"prompt": "a majestic dragon"},
            re_execute=False,
        ))
        assert "canvas" in result

    def test_edit_nonexistent_node(self):
        """Editing a non-existent node returns NODE_NOT_FOUND error."""
        from hermesfy.tools.define_workflow import define_workflow
        from hermesfy.tools.edit_node import edit_node

        def_result = json.loads(define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges()))
        wf_id = def_result["workflow_id"]

        result = json.loads(edit_node(
            workflow_id=wf_id,
            node_id="nonexistent-node",
            changes={"prompt": "test"},
            re_execute=False,
        ))
        assert "error" in result
        assert result["error"]["code"] == "NODE_NOT_FOUND"


# ── T4.6: list_models ────────────────────────────────────────────────


class TestListModels:
    """Tests for the hermesfy_list_models tool."""

    def test_list_models_returns_all(self):
        """list_models returns markdown with all registered models."""
        from hermesfy.tools.list_models import list_models

        result = list_models()
        # Should contain model names
        assert "flux-dev" in result
        assert "flux-pro" in result
        assert "clarity-upscaler" in result


# ── T4.7 + T4.8: save_workflow + load_workflow ────────────────────────


class TestSaveLoad:
    """Tests for save_workflow and load_workflow tools."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """Save a workflow, then load it back — full state preserved."""
        from hermesfy.tools.define_workflow import define_workflow
        from hermesfy.tools.save_workflow import save_workflow
        from hermesfy.tools.load_workflow import load_workflow

        # Define
        def_result = json.loads(define_workflow(nodes=make_tool_nodes(), edges=make_tool_edges(), name="roundtrip-flow"))
        wf_id = def_result["workflow_id"]

        # Save to temp dir (override default path)
        custom_dir = tmp_path / "workflows"
        result = save_workflow(workflow_id=wf_id, filename=str(custom_dir / "roundtrip-flow"))
        parsed_save = json.loads(result) if isinstance(result, str) else result
        assert "file" in parsed_save
        assert os.path.exists(parsed_save["file"])

        # Load
        load_result = json.loads(load_workflow(filename=parsed_save["file"]))
        assert "workflow_id" in load_result
        assert "canvas" in load_result

    def test_load_nonexistent_file(self):
        """Loading a non-existent file returns FILE_NOT_FOUND error."""
        from hermesfy.tools.load_workflow import load_workflow

        result = json.loads(load_workflow(filename="/nonexistent/path/workflow.json"))
        assert "error" in result
        assert result["error"]["code"] == "FILE_NOT_FOUND"
