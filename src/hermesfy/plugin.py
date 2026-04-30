"""Hermes plugin registration — entry point for hermesfy-studio."""

import os
import logging
from pathlib import Path

from hermesfy.providers.registry import get_models

logger = logging.getLogger(__name__)


def _on_session_start(**kwargs) -> None:
    """Notify that Hermesfy Studio tools are ready."""
    logger.info(
        "[hermesfy] Hermesfy Studio active — DAG workflow engine for image generation via Fal.ai. "
        "7 tools available: define_workflow, execute_workflow, workflow_status, "
        "edit_node, list_models, save_workflow, load_workflow. "
        "Use skill 'hermesfy-guide' for full documentation."
    )


def register(ctx) -> None:
    """Register all 7 tools + skill + hook with the Hermes agent context."""

    # Register skill for context (loadable via skill system)
    skill_path = Path(__file__).parent / "skills" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            name="hermesfy-guide",
            path=skill_path,
            description="Hermesfy Studio: DAG workflow engine for AI image generation with Fal.ai — tools, node types, models, styles, and text canvas",
        )

    # On-session-start hook
    ctx.register_hook("on_session_start", _on_session_start)

    # Verify FAL_API_KEY on startup
    fal_key = os.environ.get("FAL_API_KEY")
    if not fal_key:
        logger.warning("[hermesfy] FAL_API_KEY not set — provider will use mock mode")

    # Register 7 tools
    from hermesfy.tools.define_workflow import define_workflow, DEFINE_WORKFLOW_SCHEMA
    from hermesfy.tools.execute_workflow import execute_workflow
    from hermesfy.tools.workflow_status import workflow_status
    from hermesfy.tools.edit_node import edit_node
    from hermesfy.tools.list_models import list_models
    from hermesfy.tools.save_workflow import save_workflow
    from hermesfy.tools.load_workflow import load_workflow

    TOOLSET = "hermesfy"

    ctx.register_tool(
        name="hermesfy_define_workflow",
        toolset=TOOLSET,
        description="Define a new image generation workflow from nodes and edges",
        schema=DEFINE_WORKFLOW_SCHEMA,
        handler=define_workflow,
    )
    ctx.register_tool(
        name="hermesfy_execute_workflow",
        toolset=TOOLSET,
        description="Execute a workflow's DAG via Fal.ai and return generated images",
        schema={
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "quality_config": {"type": "object"},
            },
            "required": ["workflow_id"],
        },
        handler=execute_workflow,
    )
    ctx.register_tool(
        name="hermesfy_workflow_status",
        toolset=TOOLSET,
        description="Show text canvas with node states (○ ⏳ ✅ ❌ 🔄 💀)",
        schema={
            "type": "object",
            "properties": {"workflow_id": {"type": "string"}},
            "required": ["workflow_id"],
        },
        handler=workflow_status,
    )
    ctx.register_tool(
        name="hermesfy_edit_node",
        toolset=TOOLSET,
        description="Edit a node's configuration and optionally re-execute",
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
        toolset=TOOLSET,
        description="List all available Fal.ai models (flux, upscale, etc.)",
        schema={"type": "object", "properties": {}},
        handler=list_models,
    )
    ctx.register_tool(
        name="hermesfy_save_workflow",
        toolset=TOOLSET,
        description="Save a workflow to a JSON file for later use",
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
        toolset=TOOLSET,
        description="Load a previously saved workflow from a JSON file",
        schema={
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
        handler=load_workflow,
    )

    logger.info(
        "[hermesfy] Registered 7 tools in toolset '%s', 1 skill (hermesfy-guide), "
        "1 hook (on_session_start). %d Fal.ai models available.",
        TOOLSET,
        len(get_models()),
    )
