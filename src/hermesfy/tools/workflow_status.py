"""Tool: hermesfy_workflow_status — get current canvas for a workflow."""

import json

from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import get_workflow, get_workflow_states

def workflow_status(workflow_id: str) -> str:
    """Return the current text canvas for a workflow.

    Args:
        workflow_id: The stored workflow ID.

    Returns:
        JSON string with canvas, or error.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        return json.dumps({"error": {"code": "NODE_NOT_FOUND", "message": f"Workflow '{workflow_id}' not found"}})

    node_states, node_errors = get_workflow_states(workflow_id)
    canvas = render_minimal_canvas(workflow, node_states=node_states or None, node_errors=node_errors or None)
    return json.dumps({"canvas": canvas})
