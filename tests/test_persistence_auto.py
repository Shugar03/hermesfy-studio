"""Tests for automatic workflow persistence."""

import json
import pytest
from pathlib import Path
from hermesfy.tools.workflows import (
    add_workflow,
    get_workflow,
    delete_workflow,
    list_workflows,
    set_workflow_states,
    get_workflow_states,
    load_persisted_workflows,
    _PERSIST_DIR,
    workflows,
    _workflow_states,
)
from hermesfy.dag.graph import Workflow, Node, Edge, NodeType


@pytest.fixture(autouse=True)
def clean_state():
    """Clear in-memory store and persisted files between tests."""
    workflows.clear()
    _workflow_states.clear()
    yield
    workflows.clear()
    _workflow_states.clear()


def _make_workflow(wf_id="wf-test", name="test workflow"):
    """Create a minimal test workflow."""
    return Workflow(
        id=wf_id,
        name=name,
        nodes=[
            Node(id="prompt", type=NodeType.TEXT_PROMPT, config={"prompt": "a jar"}),
            Node(id="gen", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"}),
        ],
        edges=[Edge(source="prompt", target="gen")],
    )


class TestAutoPersistence:
    def test_add_workflow_creates_json_file(self, tmp_path, monkeypatch):
        """Adding a workflow creates a JSON file on disk."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )
        wf = _make_workflow()
        add_workflow(wf)

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

        with open(files[0]) as f:
            data = json.load(f)
        assert data["id"] == "wf-test"
        assert data["name"] == "test workflow"
        assert len(data["nodes"]) == 2

    def test_delete_workflow_removes_file(self, tmp_path, monkeypatch):
        """Deleting a workflow removes its JSON file."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )
        wf = _make_workflow()
        add_workflow(wf)
        assert len(list(tmp_path.glob("*.json"))) == 1

        delete_workflow("wf-test")
        assert len(list(tmp_path.glob("*.json"))) == 0

    def test_set_workflow_states_persists_execution(self, tmp_path, monkeypatch):
        """Setting workflow states includes execution data in the JSON."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )
        wf = _make_workflow()
        add_workflow(wf)

        set_workflow_states(
            "wf-test",
            node_states={"prompt": "completed", "gen": "completed"},
            node_errors={},
            events=[{"event_type": "workflow_done"}],
        )

        files = list(tmp_path.glob("*.json"))
        with open(files[0]) as f:
            data = json.load(f)

        assert "execution" in data
        assert data["execution"]["node_states"]["gen"] == "completed"

    def test_load_persisted_workflows_restores_state(self, tmp_path, monkeypatch):
        """Loading from disk restores workflows into memory."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )

        # Create and persist
        wf = _make_workflow()
        add_workflow(wf)
        set_workflow_states(
            "wf-test",
            node_states={"prompt": "completed"},
            node_errors={},
        )

        # Clear memory
        workflows.clear()
        _workflow_states.clear()
        assert get_workflow("wf-test") is None

        # Load from disk
        count = load_persisted_workflows()
        assert count == 1

        restored = get_workflow("wf-test")
        assert restored is not None
        assert restored.name == "test workflow"
        assert len(restored.nodes) == 2

        states, errors, _ = get_workflow_states("wf-test")
        assert states["prompt"] == "completed"

    def test_load_handles_empty_directory(self, tmp_path, monkeypatch):
        """Loading from empty directory returns 0."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )
        assert load_persisted_workflows() == 0

    def test_load_handles_corrupted_json(self, tmp_path, monkeypatch):
        """Corrupted JSON files are skipped gracefully."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )
        (tmp_path / "bad.json").write_text("not valid json {{{")
        (tmp_path / "good.json").write_text(json.dumps({
            "id": "wf-ok", "name": "ok", "nodes": [], "edges": []
        }))

        count = load_persisted_workflows()
        assert count == 1
        assert get_workflow("wf-ok") is not None

    def test_persistence_preserves_node_configs(self, tmp_path, monkeypatch):
        """Node configs survive the persist/load cycle."""
        monkeypatch.setattr(
            "hermesfy.tools.workflows._PERSIST_DIR", tmp_path
        )
        wf = _make_workflow()
        wf.nodes[0].config["prompt"] = "luxury skincare jar on marble"
        add_workflow(wf)

        workflows.clear()
        load_persisted_workflows()

        restored = get_workflow("wf-test")
        assert restored.nodes[0].config["prompt"] == "luxury skincare jar on marble"
