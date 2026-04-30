"""Tool: hermesfy_save_workflow — serialize workflow to JSON file."""

import json
import os
from datetime import datetime
from pathlib import Path

from hermesfy.tools.workflows import get_workflow

DEFAULT_SAVE_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"


def save_workflow(workflow_id: str, filename: str | None = None) -> str:
    """Save a workflow to a JSON file.

    Args:
        workflow_id: The stored workflow ID to save.
        filename: Optional output file path. If not provided, auto-generates
                  from workflow name in ~/.hermes/hermesfy/workflows/.

    Returns:
        JSON string with file path, or error.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        return json.dumps({"error": {"code": "NODE_NOT_FOUND", "message": f"Workflow '{workflow_id}' not found"}})

    # Determine file path
    if filename:
        filepath = Path(filename)
    else:
        DEFAULT_SAVE_DIR.mkdir(parents=True, exist_ok=True)
        # Sanitize name
        safe_name = workflow.name.lower().replace(" ", "_").replace("-", "_")
        filepath = DEFAULT_SAVE_DIR / f"{safe_name}.json"

    # Create parent dir if needed
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

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return json.dumps({"file": str(filepath)})
