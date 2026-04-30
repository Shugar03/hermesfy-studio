"""Tool: hermesfy_save_workflow — serialize workflow to JSON file."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from hermesfy.tools.workflows import get_workflow

DEFAULT_SAVE_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"
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


def save_workflow(workflow_id: str, filename: str | None = None) -> str:
    """Save a workflow to a JSON file.

    Args:
        workflow_id: The stored workflow ID to save.
        filename: Optional output file path. Must be within the workflow
                  directory. If not provided, auto-generates from workflow
                  name in ~/.hermes/hermesfy/workflows/.

    Returns:
        JSON string with file path, or error.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        return json.dumps({"error": {"code": "NODE_NOT_FOUND", "message": f"Workflow '{workflow_id}' not found"}})

    DEFAULT_SAVE_DIR.mkdir(parents=True, exist_ok=True)

    # Determine file path with sandbox validation
    if filename:
        try:
            filepath = _validate_safe_path(filename, DEFAULT_SAVE_DIR)
        except ValueError as exc:
            return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": str(exc)}})
    else:
        # Sanitize auto-generated name (only allow safe chars)
        safe_name = re.sub(r"[^\w\-]", "_", workflow.name.lower())
        filepath = DEFAULT_SAVE_DIR / f"{safe_name}.json"

    # Create parent dir if needed (already validated within base_dir)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Serialize
    data = {
        "id": workflow.id,
        "name": workflow.name,
        "nodes": [
            {"id": n.id, "type": n.type.value, "config": n.config, "position": list(n.position)}
            for n in workflow.nodes
        ],
        "edges": [{"source": e.source, "target": e.target} for e in workflow.edges],
    }

    serialized = json.dumps(data, indent=2)
    if len(serialized) > MAX_FILE_SIZE:
        return json.dumps({"error": {"code": "INVALID_WORKFLOW", "message": "Workflow data exceeds max file size"}})

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(serialized)

    # Set secure permissions (owner read/write only)
    try:
        os.chmod(filepath, 0o600)
    except OSError:
        pass  # Best-effort on platforms that don't support chmod

    return json.dumps({"file": str(filepath)})
