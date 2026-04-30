"""Tool: hermesfy_load_workflow — deserialize workflow from JSON file."""

import json
import os
import re
import uuid
from pathlib import Path

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow
from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import add_workflow

DEFAULT_LOAD_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB max

# Only allow alphanumeric, underscore, hyphen, dot in user-provided paths
_SAFE_NAME_RE = re.compile(r"^[\w\-./\\]+$")


def _validate_safe_path(user_path: str, base_dir: Path) -> Path:
    """Validate and resolve a user-provided path within base_dir.

    Prevents path traversal attacks (../, absolute paths, etc.).

    Args:
        user_path: The filename/path provided by the user.
        base_dir: The trusted base directory.

    Returns:
        Resolved absolute path within base_dir.

    Raises:
        ValueError: If path escapes base_dir or contains malicious patterns.
    """
    if not _SAFE_NAME_RE.match(user_path):
        raise ValueError(f"Invalid characters in filename: {user_path}")

    base_dir = base_dir.resolve()
    filepath = (base_dir / user_path).resolve()

    if not str(filepath).startswith(str(base_dir)):
        raise ValueError(f"Path traversal blocked: {user_path}")

    return filepath


def load_workflow(filename: str) -> str:
    """Load a workflow from a JSON file and restore it to the in-memory store.

    Args:
        filename: Path within the workflow directory (path traversal blocked).

    Returns:
        JSON string with workflow_id and canvas, or error.
    """
    DEFAULT_LOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        filepath = _validate_safe_path(filename, DEFAULT_LOAD_DIR)
    except ValueError as exc:
        return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": str(exc)}})

    if not filepath.exists():
        return json.dumps({"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {filename}"}})

    # File size limit
    try:
        fsize = os.path.getsize(filepath)
        if fsize > MAX_FILE_SIZE:
            return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": f"File exceeds max size ({MAX_FILE_SIZE} bytes)"}})
    except OSError as exc:
        return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": str(exc)}})

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
