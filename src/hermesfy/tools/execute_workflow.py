"""Tool: hermesfy_execute_workflow — execute a workflow's DAG and return results."""

import asyncio
import json

from hermesfy.dag.executor import execute
from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import get_workflow, set_workflow_states

# Try to use GenmediaProvider, but fall back gracefully if not possible
try:
    from hermesfy.providers.genmedia import GenmediaProvider, PROVIDER_AUTH, PROVIDER_ERROR
except ImportError:
    GenmediaProvider = None

# Legacy FalProvider fallback (will be removed after migration)
try:
    from hermesfy.providers.fal import FalProvider
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

    # Use GenmediaProvider if genmedia CLI is installed, fall back to FalProvider, then mock
    provider = None
    provider_error = None

    if GenmediaProvider:
        try:
            provider = GenmediaProvider()
        except RuntimeError as e:
            provider_error = str(e)

    if provider is None and FalProvider:
        try:
            provider = FalProvider()
        except RuntimeError as e:
            if provider_error:
                provider_error += " | " + str(e)
            else:
                provider_error = str(e)

    if provider is None:
        # No provider available — use mock for dry-run
        class MockProvider:
            async def generate(self, node_type: str, config: dict) -> dict:
                return {"mock": True, "node_type": node_type,
                        "image_url": "https://example.com/mock.png"}
        provider = MockProvider()

    # Run the executor in a dedicated thread with its own event loop.
    # This works in both sync and async contexts without deadlocks.
    events = []
    async_error: Exception | None = None

    async def _run():
        async for event in execute(workflow, provider):
            events.append(event)

    def _thread_target():
        nonlocal async_error
        try:
            asyncio.run(_run())
        except Exception as exc:
            async_error = exc
    import threading
    thread = threading.Thread(target=_thread_target)
    thread.start()
    thread.join(timeout=300)

    if async_error:
        return json.dumps({"error": {"code": PROVIDER_ERROR, "message": str(async_error)}})

    # Extract node states and errors from emitted events
    node_states: dict[str, str] = {}
    node_errors: dict[str, str] = {}
    for event in events:
        if event.event_type == "node_error":
            node_errors[event.node_id] = event.data.get("error", "unknown error") if event.data else "unknown error"
        elif event.event_type == "workflow_done" and event.data:
            ns = event.data.get("node_states", {})
            node_states = {k: v.value if hasattr(v, 'value') else str(v) for k, v in ns.items()}

    canvas = render_minimal_canvas(workflow, node_states=node_states, node_errors=node_errors)

    # Serialize events for persistence
    serialized_events = []
    for event in events:
        serialized_events.append({
            "event_type": event.event_type,
            "node_id": event.node_id,
            "data": event.data,
        })

    # Persist states so workflow_status can access them later
    set_workflow_states(workflow_id, node_states, node_errors, serialized_events)

    result = {"canvas": canvas, "events_count": len(events)}
    if node_errors:
        result["node_errors"] = node_errors
    return json.dumps(result)
