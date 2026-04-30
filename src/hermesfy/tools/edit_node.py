"""Tool: hermesfy_edit_node — modify a node's config with optional re-execution."""

import json

from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import get_workflow


def edit_node(workflow_id: str, node_id: str, changes: dict, re_execute: bool = False) -> str:
    """Edit a node's configuration in-place and optionally re-execute downstream.

    Args:
        workflow_id: The stored workflow ID.
        node_id: The node to edit.
        changes: Dict of config keys to update.
        re_execute: If True, re-execute from this node downstream (not yet implemented).

    Returns:
        JSON string with updated canvas, or error.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        return json.dumps({"error": {"code": "NODE_NOT_FOUND", "message": f"Workflow '{workflow_id}' not found"}})

    # Find the node
    target_node = None
    for node in workflow.nodes:
        if node.id == node_id:
            target_node = node
            break

    if target_node is None:
        return json.dumps({"error": {"code": "NODE_NOT_FOUND", "message": f"Node '{node_id}' not found"}})

    # Apply changes
    target_node.config.update(changes)

    canvas = render_minimal_canvas(workflow)
    return json.dumps({"canvas": canvas, "re_execute": re_execute})
