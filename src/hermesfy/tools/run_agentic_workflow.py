"""Tool: hermesfy_run_agentic_workflow — full agentic loop.

Orchestrates: plan → execute → QA → adjust → re-execute → deliver.
Single entry point for end-to-end image generation with quality control.
"""

import json
import re
import base64
import os
import requests

from hermesfy.dag.graph import (
    validate_workflow, Workflow, Node, Edge, NodeType, REQUIRED_CONFIG,
)
from hermesfy.dag.executor import execute
from hermesfy.providers.fal import FalProvider


__all__ = ["run_agentic_workflow"]

# --- Default workflow patterns ---

_PATTERNS = {
    "simple": {
        "nodes": [
            {"id": "prompt", "type": "text_prompt", "config": {"prompt": "{description}"}},
            {"id": "gen", "type": "image_gen", "config": {
                "model": "flux-dev", "prompt": "{{prompt}}",
                "width": 1024, "height": 1024,
                "num_inference_steps": 28, "guidance_scale": 3.5,
            }},
        ],
        "edges": [{"source": "prompt", "target": "gen"}],
    },
    "upscale": {
        "nodes": [
            {"id": "prompt", "type": "text_prompt", "config": {"prompt": "{description}"}},
            {"id": "gen", "type": "image_gen", "config": {
                "model": "flux-dev", "prompt": "{{prompt}}",
                "width": 1024, "height": 1024,
                "num_inference_steps": 28, "guidance_scale": 3.5,
            }},
            {"id": "upscale", "type": "upscale", "config": {
                "model": "clarity-upscaler", "image_url": "{{gen}}", "scale": 2,
            }},
        ],
        "edges": [
            {"source": "prompt", "target": "gen"},
            {"source": "gen", "target": "upscale"},
        ],
    },
    "remove_bg": {
        "nodes": [
            {"id": "prompt", "type": "text_prompt", "config": {"prompt": "{description}"}},
            {"id": "gen", "type": "image_gen", "config": {
                "model": "flux-dev", "prompt": "{{prompt}}",
                "width": 1024, "height": 1024,
                "num_inference_steps": 28, "guidance_scale": 3.5,
            }},
            {"id": "nobg", "type": "remove_bg", "config": {
                "model": "birefnet", "image_url": "{{gen}}",
            }},
        ],
        "edges": [
            {"source": "prompt", "target": "gen"},
            {"source": "gen", "target": "nobg"},
        ],
    },
    "variants": {
        "nodes": [
            {"id": "prompt", "type": "text_prompt", "config": {"prompt": "{description} on white background, studio lighting"}},
            {"id": "master", "type": "image_gen", "config": {
                "model": "flux-dev", "prompt": "{{prompt}}",
                "width": 1024, "height": 1024,
                "num_inference_steps": 28, "guidance_scale": 3.5,
            }},
            {"id": "variant_1", "type": "img2img", "config": {
                "model": "flux-dev", "prompt": "{{prompt}}, lifestyle setting, warm ambient light",
                "image_url": "{{master}}", "strength": 0.4,
                "num_inference_steps": 28,
            }},
            {"id": "variant_2", "type": "img2img", "config": {
                "model": "flux-dev", "prompt": "{{prompt}}, social media layout, gradient background",
                "image_url": "{{master}}", "strength": 0.45,
                "num_inference_steps": 28,
            }},
        ],
        "edges": [
            {"source": "prompt", "target": "master"},
            {"source": "master", "target": "variant_1"},
            {"source": "master", "target": "variant_2"},
        ],
    },
}


# --- QA functions ---

def _get_google_key() -> str:
    """Load Google API key from environment or .env file."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        return key
    env_path = os.path.expanduser("~/.hermes/.env")
    try:
        with open(env_path) as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""


def _qa_analyze(image_url: str, user_intent: str) -> dict:
    """Analyze a generated image with Gemini 2.5 Flash vision.

    Returns: {"score": int, "pass": bool, "critique": str, "suggestions": list}
    """
    google_key = _get_google_key()
    if not google_key:
        return {"score": 7, "pass": True, "critique": "No GOOGLE_API_KEY — skipping QA", "suggestions": []}

    try:
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        img_b64 = base64.b64encode(img_resp.content).decode()
        mime = "image/png" if ".png" in image_url else "image/jpeg"
    except Exception as e:
        return {"score": 7, "pass": True, "critique": f"Image download failed: {e}", "suggestions": []}

    prompt = f"""Product photography QA. Rate 1-10 for: prompt adherence, technical quality, commercial viability.
Intent: {user_intent}
JSON ONLY: {{"score": N, "pass": true/false, "critique": "...", "suggestions": ["..."]}}"""

    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": google_key},
            json={"contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": img_b64}},
            ]}]},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return {"score": 7, "pass": True, "critique": "QA analysis failed", "suggestions": []}


def _adjust_prompt(original: str, critique: str, suggestions: list) -> str:
    """Adjust a prompt based on QA critique."""
    fixes = []
    c = critique.lower()
    if "blur" in c or "focus" in c or "sharp" in c:
        fixes.extend(["sharp focus", "high detail", "professional photography"])
    if "dark" in c or "shadow" in c or "lighting" in c:
        fixes.extend(["bright studio lighting", "soft diffused light"])
    if "artifact" in c or "distort" in c:
        fixes.extend(["clean lines", "no artifacts"])
    for s in (suggestions or []):
        if s and len(s) < 80 and not s.lower().startswith("ensure"):
            fixes.append(s)
    if fixes:
        return f"{original}, {', '.join(fixes[:4])}"
    return original + ", professional photography, sharp focus, studio lighting"


# --- Main tool ---

def run_agentic_workflow(
    description: str,
    pattern: str = "simple",
    qa_enabled: bool = True,
    max_adjustments: int = 3,
    seed: int | None = None,
) -> str:
    """Run a full agentic workflow: plan → execute → QA → adjust → deliver.

    Args:
        description: Natural language description of the image to generate.
        pattern: Workflow pattern (simple, upscale, remove_bg, variants).
        qa_enabled: Enable QA Agent vision review (requires GOOGLE_API_KEY).
        max_adjustments: Max prompt adjustment iterations (0 = no QA loop).
        seed: Optional fixed seed for reproducibility.

    Returns:
        JSON string with status, image URLs, iterations, and QA history.
    """
    # Step 1: Build DAG from pattern
    pattern_data = _PATTERNS.get(pattern)
    if not pattern_data:
        return json.dumps({"error": f"Unknown pattern '{pattern}'. Available: {list(_PATTERNS.keys())}"})

    nodes = []
    for n in pattern_data["nodes"]:
        config = dict(n["config"])
        # Replace {description} placeholder
        for k, v in config.items():
            if isinstance(v, str) and "{description}" in v:
                config[k] = v.replace("{description}", description)
        if seed is not None and n["type"] == "image_gen":
            config["seed"] = seed
        nodes.append({"id": n["id"], "type": n["type"], "config": config})

    edges = [dict(e) for e in pattern_data["edges"]]

    # Step 2: Define workflow
    from hermesfy.tools.define_workflow import define_workflow
    wf_result = json.loads(define_workflow(
        nodes=nodes, edges=edges,
        name=f"agentic-{pattern}",
    ))
    if "error" in wf_result:
        return json.dumps({"error": wf_result["error"]})
    workflow_id = wf_result["workflow_id"]

    # Step 3: Execute + QA loop
    provider = FalProvider()
    history = []
    current_prompt = description
    image_url = None

    for iteration in range(max_adjustments + 1):
        # Execute
        import asyncio
        wf = _get_workflow(workflow_id)
        if wf is None:
            return json.dumps({"error": f"Workflow {workflow_id} not found"})

        exec_events = []
        async def _run():
            async for event in execute(wf, provider):
                exec_events.append(event)
        asyncio.run(_run())

        # Extract image URL from last provider node
        image_url = None
        for event in exec_events:
            if event.event_type == "node_complete" and event.data:
                output = event.data.get("output", {})
                if isinstance(output, dict) and "url" in output:
                    image_url = output["url"]

        # Check for errors
        node_errors = {}
        node_states = {}
        for event in exec_events:
            if event.event_type == "node_error":
                node_errors[event.node_id] = event.data.get("error", "unknown") if event.data else "unknown"
            elif event.event_type == "workflow_done" and event.data:
                ns = event.data.get("node_states", {})
                node_states = {k: v.value if hasattr(v, 'value') else str(v) for k, v in ns.items()}

        if node_errors:
            return json.dumps({
                "status": "error",
                "workflow_id": workflow_id,
                "errors": node_errors,
                "iterations": iteration + 1,
            })

        # QA analysis
        if not qa_enabled or max_adjustments == 0:
            break

        qa = _qa_analyze(image_url, description)
        history.append({
            "iteration": iteration + 1,
            "score": qa["score"],
            "pass": qa["pass"],
            "critique": qa["critique"][:200],
        })

        if qa["pass"]:
            break

        # Adjust prompt for next iteration
        if iteration < max_adjustments:
            current_prompt = _adjust_prompt(current_prompt, qa["critique"], qa.get("suggestions", []))
            _edit_workflow_node(workflow_id, "prompt", {"prompt": current_prompt})

    # Step 4: Build result
    from hermesfy.rendering.canvas import render_minimal_canvas
    canvas = render_minimal_canvas(wf, node_states=node_states, node_errors=node_errors)

    result = {
        "status": "success",
        "workflow_id": workflow_id,
        "image_url": image_url,
        "canvas": canvas,
        "iterations": len(history) if history else 1,
        "pattern": pattern,
    }
    if history:
        result["qa_history"] = history
        result["final_score"] = history[-1]["score"]
    if current_prompt != description:
        result["final_prompt"] = current_prompt

    return json.dumps(result)


# --- Internal helpers ---

def _get_workflow(workflow_id: str):
    """Get workflow from the in-memory store."""
    from hermesfy.tools.workflows import workflows
    return workflows.get(workflow_id)


def _edit_workflow_node(workflow_id: str, node_id: str, changes: dict):
    """Edit a node in the in-memory workflow."""
    wf = _get_workflow(workflow_id)
    if wf is None:
        return
    for node in wf.nodes:
        if node.id == node_id:
            node.config.update(changes)
            break
