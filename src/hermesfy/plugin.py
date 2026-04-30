"""Hermes plugin registration — entry point for hermesfy-studio."""

import os

from hermesfy.providers.registry import get_models


def register(ctx) -> None:
    """Register all 7 tools with the Hermes agent context.

    Args:
        ctx: Hermes plugin registration context (provides tool registration API).
    """
    # Verify FAL_API_KEY on startup
    fal_key = os.environ.get("FAL_API_KEY")
    if not fal_key:
        print("[hermesfy] Warning: FAL_API_KEY not set — provider will use mock mode")

    # Register tools
    from hermesfy.tools.define_workflow import define_workflow, DEFINE_WORKFLOW_SCHEMA
    from hermesfy.tools.execute_workflow import execute_workflow
    from hermesfy.tools.workflow_status import workflow_status
    from hermesfy.tools.edit_node import edit_node
    from hermesfy.tools.list_models import list_models
    from hermesfy.tools.save_workflow import save_workflow
    from hermesfy.tools.load_workflow import load_workflow

    execute_schema = {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "quality_config": {"type": "object"},
        },
        "required": ["workflow_id"],
    }

    ctx.register_tool(
        name="hermesfy_define_workflow",
        description="Define a new image generation workflow from nodes and edges",
        schema=DEFINE_WORKFLOW_SCHEMA,
        handler=define_workflow,
    )
    ctx.register_tool(
        name="hermesfy_execute_workflow",
        description="Execute a workflow's DAG and return the generated images",
        schema=execute_schema,
        handler=execute_workflow,
    )
    ctx.register_tool(
        name="hermesfy_workflow_status",
        description="Get the current status canvas for a workflow",
        schema={
            "type": "object",
            "properties": {"workflow_id": {"type": "string"}},
            "required": ["workflow_id"],
        },
        handler=workflow_status,
    )
    ctx.register_tool(
        name="hermesfy_edit_node",
        description="Edit a node's configuration with optional re-execution",
        schema={
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "node_id": {"type": "string"},
                "changes": {"type": "object"},
                "re_execute": {"type": "boolean"},
            },
            "required": ["workflow_id", "node_id", "changes"],
        },
        handler=edit_node,
    )
    ctx.register_tool(
        name="hermesfy_list_models",
        description="List all available Fal.ai models with descriptions and capabilities",
        schema={"type": "object", "properties": {}},
        handler=list_models,
    )
    ctx.register_tool(
        name="hermesfy_save_workflow",
        description="Save a workflow to a JSON file",
        schema={
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "filename": {"type": "string"},
            },
            "required": ["workflow_id"],
        },
        handler=save_workflow,
    )
    ctx.register_tool(
        name="hermesfy_load_workflow",
        description="Load a workflow from a JSON file",
        schema={
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
        handler=load_workflow,
    )
