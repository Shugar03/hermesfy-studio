"""Tool: hermesfy_execute_workflow — execute a workflow's DAG and return results."""

import asyncio
import json

from hermesfy.dag.executor import execute
from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import get_workflow

# Try to use FalProvider, but fall back gracefully if not possible
try:
    from hermesfy.providers.fal import FalProvider, PROVIDER_AUTH, PROVIDER_ERROR
except ImportError:
    FalProvider = None


def execute_workflow(workflow_id: str, quality_config: dict | None = None) -> str:
    """Execute a workflow and return the final canvas with results.

    Args:
        workflow_id: The stored workflow ID to execute.
        quality_config: Optional quality gate config (not used in sync version).

    Returns:
        JSON string with canvas, or error.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        return json.dumps({"error": {"code": "NODE_NOT_FOUND", "message": f"Workflow '{workflow_id}' not found"}})

    # Use FalProvider if FAL_API_KEY is set, otherwise use a mock
    try:
        provider = FalProvider()
    except RuntimeError:
        # No FAL_API_KEY — use mock provider for dry-run
        class MockProvider:
            async def generate(self, node_type: str, config: dict) -> dict:
                return {"mock": True, "node_type": node_type, "image_url": "https://example.com/mock.png"}
        provider = MockProvider()

    # Run the executor (sync wrapper around async)
    events = []
    try:
        async def _run():
            async for event in execute(workflow, provider):
                events.append(event)

        try:
            loop = asyncio.get_running_loop()
            # Already in async context — cannot use asyncio.run()
            # In sync context, use asyncio.run()
            return json.dumps({"error": {"code": "PROVIDER_ERROR", "message": "execute_workflow must be called from sync context"}})
        except RuntimeError:
            # No running loop — use asyncio.run()
            asyncio.run(_run())
    except Exception as exc:
        return json.dumps({"error": {"code": PROVIDER_ERROR, "message": str(exc)}})

    canvas = render_minimal_canvas(workflow)
    return json.dumps({"canvas": canvas, "events_count": len(events)})
