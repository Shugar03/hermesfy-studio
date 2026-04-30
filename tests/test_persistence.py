"""Tests for workflow JSON save/load roundtrip, directory creation, auto-naming."""

import os
import tempfile
from pathlib import Path

import pytest

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow
from hermesfy.persistence.storage import save_workflow, load_workflow


class TestSaveWorkflow:
    """Tests for saving workflows to disk."""

    def test_save_creates_file(self, tmp_path):
        """Saving a workflow creates a JSON file."""
        wf = Workflow(
            id="wf-1",
            name="test-save",
            nodes=[Node(id="n1", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"})],
            edges=[],
        )
        filepath = save_workflow(wf, directory=tmp_path)
        assert filepath.exists()
        assert filepath.name == "test_save.json"  # sanitized name

    def test_save_auto_creates_directory(self, tmp_path):
        """Directory is auto-created if it doesn't exist."""
        nested_dir = tmp_path / "sub" / "dir"
        wf = Workflow(id="wf-2", name="auto-dir", nodes=[], edges=[])
        filepath = save_workflow(wf, directory=nested_dir)
        assert nested_dir.exists()
        assert filepath.exists()

    def test_save_sanitizes_filename(self):
        """Workflow name is sanitized for safe filename."""
        with tempfile.TemporaryDirectory() as d:
            wf = Workflow(
                id="wf-3",
                name="My Cool Workflow!",
                nodes=[Node(id="x", type=NodeType.SEED, config={"seed": 1})],
                edges=[],
            )
            filepath = save_workflow(wf, directory=Path(d))
            # Spaces become underscores, punctuation removed
            assert filepath.name.startswith("my_cool")

    def test_save_preserves_all_data(self, tmp_path):
        """All workflow data survives serialization roundtrip."""
        wf = Workflow(
            id="wf-4",
            name="roundtrip",
            nodes=[
                Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "dragon"}, position=(10, 20)),
                Node(id="b", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "width": 512}, position=(30, 40)),
            ],
            edges=[Edge(source="a", target="b")],
        )
        filepath = save_workflow(wf, directory=tmp_path)

        # Load it back
        restored = load_workflow(filepath)
        assert restored.id == "wf-4"
        assert restored.name == "roundtrip"
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1

        # Check node details
        restored_a = next(n for n in restored.nodes if n.id == "a")
        assert restored_a.type == NodeType.TEXT_PROMPT
        assert restored_a.config["prompt"] == "dragon"
        assert restored_a.position == (10, 20)

        restored_b = next(n for n in restored.nodes if n.id == "b")
        assert restored_b.config["model"] == "flux-dev"

        # Check edge
        assert restored.edges[0].source == "a"
        assert restored.edges[0].target == "b"

    def test_load_nonexistent_file_raises(self):
        """Loading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_workflow(Path("/nonexistent/path/workflow.json"))

    def test_save_default_directory(self):
        """Saving without directory uses ~/.hermes/hermesfy/workflows/."""
        wf = Workflow(
            id="wf-default",
            name="default-save-test",
            nodes=[Node(id="x", type=NodeType.SEED, config={"seed": 1})],
            edges=[],
        )
        filepath = save_workflow(wf)
        assert filepath.exists()
        # Clean up
        filepath.unlink()
