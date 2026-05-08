"""Tool: hermesfy_execute_workflow — execute a workflow's DAG and return results.

V5: VRHGate integration — blocks execution if workflow has visual references
     but VRH preview has not been shown and approved by the user.
"""

import asyncio
import json

from hermesfy.dag.executor import execute
from hermesfy.rendering.canvas import render_minimal_canvas
from hermesfy.tools.workflows import get_workflow, set_workflow_states
from hermesfy.vrh_gate import VRHGate, VRHBlocked, gate as vrh_gate

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

    # ── V5: VRH Gate — detect visual references and require preview ──────
    reference_count = _count_references(workflow)
    has_references = reference_count > 0

    if has_references:
        # Auto-register if not already tracked
        state = vrh_gate.get_state(workflow_id)
        if state is None:
            vrh_gate.require_preview(
                workflow_id,
                reference_count=reference_count,
                has_references=True,
            )

        try:
            vrh_gate.check(workflow_id)
        except VRHBlocked as e:
            return json.dumps({
                "error": {
                    "code": "VRH_GATE_BLOCKED",
                    "message": str(e),
                    "detail": {
                        "workflow_id": workflow_id,
                        "reference_count": reference_count,
                        "required_action": "Run VRH FASE 1 (VisualAnalyzer) + FASE 2 (Preview) first. "
                                          "Load skill 'hermesfy-vrh-workflow' for the full pipeline.",
                    }
                }
            })

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


# ── V5: Reference detection for VRH Gate ─────────────────────────────────

def _count_references(workflow) -> int:
    """Count how many reference images a workflow uses.

    Scans all node configs for image_url, reference_images, image_urls,
    and mask_url fields. Used by VRHGate to determine if preview is required.

    Args:
        workflow: Workflow object with nodes.

    Returns:
        Number of distinct reference images detected.
    """
    ref_urls: set = set()

    for node in workflow.nodes:
        config = node.config if hasattr(node, 'config') else {}

        # Single image URL
        for key in ('image_url', 'mask_url', 'reference_url'):
            url = config.get(key, '')
            if url and isinstance(url, str) and url.startswith(('http', 'file', '/')):
                ref_urls.add(url)

        # Multiple image URLs (list)
        for key in ('image_urls', 'reference_images', 'reference_urls'):
            urls = config.get(key, [])
            if isinstance(urls, list):
                for url in urls:
                    if isinstance(url, str) and url.startswith(('http', 'file', '/')):
                        ref_urls.add(url)
                    elif isinstance(url, dict):
                        img_url = url.get('url', url.get('image_url', ''))
                        if img_url and isinstance(img_url, str):
                            ref_urls.add(img_url)

    return len(ref_urls)
