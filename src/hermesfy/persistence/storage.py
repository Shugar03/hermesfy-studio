"""JSON persistence — save and load workflows to/from disk."""

import json
import os
from datetime import datetime
from pathlib import Path

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow

DEFAULT_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"


def save_workflow(workflow: Workflow, directory: Path | None = None) -> Path:
    """Save a workflow to a JSON file.

    Args:
        workflow: The Workflow to persist.
        directory: Optional directory. Defaults to ~/.hermes/hermesfy/workflows/.

    Returns:
        Path to the saved file.
    """
    target_dir = directory or DEFAULT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Auto-generate filename from workflow name
    safe_name = workflow.name.lower().replace(" ", "_").replace("-", "_")
    filename = target_dir / f"{safe_name}.json"

    data = {
        "id": workflow.id,
        "name": workflow.name,
        "nodes": [
            {"id": n.id, "type": n.type.value, "config": n.config, "position": list(n.position)}
            for n in workflow.nodes
        ],
        "edges": [{"source": e.source, "target": e.target} for e in workflow.edges],
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return filename


def load_workflow(filepath: Path) -> Workflow:
    """Load a workflow from a JSON file.

    Args:
        filepath: Path to the JSON file.

    Returns:
        The reconstructed Workflow.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the JSON is invalid.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Workflow file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = [
        Node(
            id=n["id"],
            type=NodeType(n["type"]),
            config=n.get("config", {}),
            position=tuple(n.get("position", (0, 0))),
        )
        for n in data.get("nodes", [])
    ]
    edges = [Edge(source=e["source"], target=e["target"]) for e in data.get("edges", [])]

    return Workflow(
        id=data.get("id", ""),
        name=data.get("name", "unnamed"),
        nodes=nodes,
        edges=edges,
    )
