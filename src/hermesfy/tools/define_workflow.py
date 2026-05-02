"""Tool: hermesfy_define_workflow — create and store a new workflow from JSON nodes/edges."""

import json
import logging
logger = logging.getLogger(__name__)

import uuid

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow, validate_workflow
from hermesfy.dag.graph import CYCLE_DETECTED, INVALID_WORKFLOW, NODE_NOT_FOUND
from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import add_workflow

DEFINE_WORKFLOW_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": [e.value for e in NodeType]},
                    "config": {"type": "object"},
                },
                "required": ["id", "type", "config"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["source", "target"],
            },
        },
        "name": {"type": "string"},
    },
    "required": ["nodes", "edges"],
}


def define_workflow(nodes: list[dict], edges: list[dict], name: str | None = None) -> str:
    """Define a workflow from nodes and edges, store it, return workflow_id + canvas.
    logger.info("[hermesfy:define_workflow] Called")

    Args:
        nodes: List of node dicts with id, type, config.
        edges: List of edge dicts with source, target.
        name: Optional human-readable name.

    Returns:
        JSON string with workflow_id and canvas, or error.
    """
    # Build Node objects
    try:
        workflow_nodes = []
        for n in nodes:
            node_type = NodeType(n["type"])
            workflow_nodes.append(
                Node(id=n["id"], type=node_type, config=n.get("config", {}))
            )
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": {"code": INVALID_WORKFLOW, "message": str(exc)}})

    # Build Edge objects
    workflow_edges = [Edge(source=e["source"], target=e["target"]) for e in edges]

    # Generate workflow
    workflow_name = name or f"workflow-{uuid.uuid4().hex[:8]}"
    workflow = Workflow(
        id=str(uuid.uuid4()),
        name=workflow_name,
        nodes=workflow_nodes,
        edges=workflow_edges,
    )

    # Validate
    try:
        validate_workflow(workflow)
    except ValueError as exc:
        msg = str(exc)
        if CYCLE_DETECTED in msg:
            return json.dumps({"error": {"code": CYCLE_DETECTED, "message": msg}})
        if NODE_NOT_FOUND in msg:
            return json.dumps({"error": {"code": NODE_NOT_FOUND, "message": msg}})
        return json.dumps({"error": {"code": INVALID_WORKFLOW, "message": msg}})

    # Store
    add_workflow(workflow)

    # Render canvas
    canvas = render_minimal_canvas(workflow)

    return json.dumps({"workflow_id": workflow.id, "canvas": canvas})
