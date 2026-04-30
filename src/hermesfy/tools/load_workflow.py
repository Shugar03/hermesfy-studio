"""Tool: hermesfy_load_workflow — deserialize workflow from JSON file."""

import json
import uuid
from pathlib import Path

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow
from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import add_workflow


def load_workflow(filename: str) -> str:
    """Load a workflow from a JSON file and restore it to the in-memory store.

    Args:
        filename: Path to the JSON workflow file.

    Returns:
        JSON string with workflow_id and canvas, or error.
    """
    filepath = Path(filename)
    if not filepath.exists():
        return json.dumps({"error": {"code": "FILE_NOT_FOUND", "message": f"File '{filename}' not found"}})

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": str(exc)}})

    # Reconstruct Workflow
    try:
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
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": str(exc)}})

    workflow = Workflow(
        id=data.get("id", str(uuid.uuid4())),
        name=data.get("name", "loaded-workflow"),
        nodes=nodes,
        edges=edges,
    )

    add_workflow(workflow)
    canvas = render_minimal_canvas(workflow)

    return json.dumps({"workflow_id": workflow.id, "canvas": canvas})
