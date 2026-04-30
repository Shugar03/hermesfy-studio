"""Text-based DAG visualization with emoji state indicators."""

from hermesfy.dag.graph import Workflow, NodeType


# State emoji mapping
STATE_EMOJI = {
    "pending": "○",
    "running": "⏳",
    "completed": "✅",
    "failed": "❌",
    "retrying": "🔄",
    "quality_exhausted": "💀",
}

# Node type short labels
TYPE_LABEL = {
    NodeType.TEXT_PROMPT.value: "TEXT",
    NodeType.IMAGE_GEN.value: "GEN",
    NodeType.IMG2IMG.value: "IMG2IMG",
    NodeType.UPSCALE.value: "UPSCALE",
    NodeType.SEED.value: "SEED",
}


def render_canvas(workflow: Workflow, node_states: dict | None = None, node_errors: dict | None = None) -> str:
    """Render a text-based DAG visualization.

    Args:
        workflow: The workflow to render.
        node_states: Optional dict of node_id → state string (pending, running, completed, etc.).
        node_errors: Optional dict of node_id → error message for failed nodes.

    Returns:
        A multi-line string representing the canvas.
    """
    if node_states is None:
        node_states = {}
    if node_errors is None:
        node_errors = {}

    lines: list[str] = []
    lines.append(f"📋 Workflow: {workflow.name} ({workflow.id})")
    lines.append("═" * 50)

    node_map = {n.id: n for n in workflow.nodes}

    if workflow.edges:
        # Render with edges
        # Use Kahn's sort for ordering
        from hermesfy.dag.executor import _topological_sort
        try:
            order = _topological_sort(workflow)
        except ValueError:
            order = [n.id for n in workflow.nodes]

        rendered = set()
        for node_id in order:
            _render_node_block(lines, node_map, node_id, node_states, node_errors, rendered)

        # Render any remaining unvisited nodes (disconnected)
        for node_id in node_map:
            if node_id not in rendered:
                _render_node_block(lines, node_map, node_id, node_states, node_errors, rendered)
    else:
        # No edges — render each node separately
        for node in workflow.nodes:
            state = node_states.get(node.id, "pending")
            emoji = STATE_EMOJI.get(state, "○")
            type_label = TYPE_LABEL.get(node.type.value, node.type.value)
            config_summary = _config_summary(node.config)
            line = f"  {emoji} [{type_label}] {node.id} — {config_summary}"
            # Add error details for failed/exhausted nodes
            if state in ("failed", "quality_exhausted") and node.id in node_errors:
                error = node_errors[node.id]
                error_short = error[:60] + "..." if len(error) > 60 else error
                line += f"  ⚠️ {error_short}"
            lines.append(line)

    lines.append("═" * 50)

    # Status summary
    n = len(workflow.nodes)
    completed = sum(1 for s in node_states.values() if s == "completed")
    lines.append(f"Progress: {completed}/{n} completed")

    return "\n".join(lines)


def _render_node_block(
    lines: list[str],
    node_map: dict,
    node_id: str,
    node_states: dict,
    node_errors: dict,
    rendered: set,
) -> None:
    """Render a single node line on the canvas."""
    node = node_map.get(node_id)
    if node is None:
        return

    state = node_states.get(node_id, "pending")
    emoji = STATE_EMOJI.get(state, "○")
    type_label = TYPE_LABEL.get(node.type.value, node.type.value)
    config_summary = _config_summary(node.config)

    line = f"  {emoji} [{type_label}] {node_id} — {config_summary}"

    # Add error details for failed/exhausted nodes
    if state in ("failed", "quality_exhausted") and node_id in node_errors:
        error = node_errors[node_id]
        error_short = error[:60] + "..." if len(error) > 60 else error
        line += f"  ⚠️ {error_short}"

    lines.append(line)
    rendered.add(node_id)


def _config_summary(config: dict) -> str:
    """Create a brief human-readable summary of node config."""
    parts = []
    if "prompt" in config:
        p = str(config["prompt"])
        parts.append(f'prompt="{p[:30]}{"..." if len(p) > 30 else ""}"')
    if "model" in config:
        parts.append(f"model={config['model']}")
    if "image_url" in config:
        u = str(config["image_url"])
        parts.append(f"image_url={u[:20]}...")
    if "seed" in config:
        parts.append(f"seed={config['seed']}")
    if "width" in config or "height" in config:
        w = config.get("width", "")
        h = config.get("height", "")
        parts.append(f"{w}×{h}")
    return ", ".join(parts) if parts else "(no config)"


# Backward-compatible alias used by tools
render_minimal_canvas = render_canvas
