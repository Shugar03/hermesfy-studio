"""HTML Canvas Renderer — visual node-based workflow display with thumbnails.

V6: Generates self-contained HTML with:
  - Real image thumbnails for REFERENCE_IMAGE nodes
  - Color-coded nodes by type (dark theme, Higgsfield-inspired)
  - SVG curved connections between nodes
  - Automatic layout via topological sort (layered graph)
  - State indicators (✅ ⏳ ❌ ○)

Usage:
    from hermesfy.rendering.canvas_html import render_canvas_html
    html = render_canvas_html(workflow, node_states, node_errors)
    # → self-contained HTML string, ready to save or display
"""

from __future__ import annotations

from hermesfy.dag.graph import Workflow, NodeType

# ── Node Type Colors (dark theme) ──────────────────────────────────────

NODE_STYLE = {
    "reference_image": {
        "bg": "#0d2137", "border": "#4fc3f7", "header_bg": "#153450",
        "label": "🖼️ REF", "icon": "🖼️",
    },
    "text_prompt": {
        "bg": "#1f0d2e", "border": "#ce93d8", "header_bg": "#2a1540",
        "label": "📝 TXT", "icon": "📝",
    },
    "image_gen": {
        "bg": "#0d1f0d", "border": "#66bb6a", "header_bg": "#153015",
        "label": "🎨 GEN", "icon": "🎨",
    },
    "img2img": {
        "bg": "#1f1f0d", "border": "#fff176", "header_bg": "#303015",
        "label": "🔄 I2I", "icon": "🔄",
    },
    "upscale": {
        "bg": "#0d1f2e", "border": "#42a5f5", "header_bg": "#153045",
        "label": "⬆️ UP", "icon": "⬆️",
    },
    "inpaint": {
        "bg": "#2e0d0d", "border": "#ef5350", "header_bg": "#401515",
        "label": "🖌️ INP", "icon": "🖌️",
    },
    "outpaint": {
        "bg": "#2e1f0d", "border": "#ff7043", "header_bg": "#402a15",
        "label": "⏏️ OUT", "icon": "⏏️",
    },
    "ip_adapter": {
        "bg": "#1f0d2e", "border": "#ab47bc", "header_bg": "#2a1540",
        "label": "🧠 IP", "icon": "🧠",
    },
    "remove_bg": {
        "bg": "#0d2e2e", "border": "#4db6ac", "header_bg": "#154040",
        "label": "✂️ BG", "icon": "✂️",
    },
    "face_restore": {
        "bg": "#2e0d1f", "border": "#ec407a", "header_bg": "#40152a",
        "label": "👤 FACE", "icon": "👤",
    },
    "seed": {
        "bg": "#1a1a1a", "border": "#9e9e9e", "header_bg": "#2a2a2a",
        "label": "🌱 SEED", "icon": "🌱",
    },
}

_DEFAULT_STYLE = {
    "bg": "#1a1a2e", "border": "#7986cb", "header_bg": "#252545",
    "label": "⬡ NODE", "icon": "⬡",
}

# State colors
STATE_COLORS = {
    "pending": "#9e9e9e",
    "running": "#42a5f5",
    "completed": "#66bb6a",
    "failed": "#ef5350",
    "retrying": "#ff7043",
}


# ── Layout Engine ──────────────────────────────────────────────────────

def _compute_layout(workflow: Workflow) -> dict[str, dict]:
    """Compute node positions using layered topological layout.

    Returns:
        Dict of node_id → {"x": int, "y": int, "layer": int, "pos_in_layer": int}
    """
    from hermesfy.dag.executor import _topological_sort

    try:
        order = _topological_sort(workflow)
    except ValueError:
        order = [n.id for n in workflow.nodes]

    node_map = {n.id: n for n in workflow.nodes}

    # Build dependency graph (who depends on whom)
    deps: dict[str, set[str]] = {n.id: set() for n in workflow.nodes}
    for edge in workflow.edges:
        deps[edge.target].add(edge.source)

    # Assign layers: layer = max(dependency_layer) + 1, inputs get layer 0
    layers: dict[str, int] = {}
    for node_id in order:
        if not deps[node_id]:
            layers[node_id] = 0
        else:
            layers[node_id] = max(layers.get(dep, 0) for dep in deps[node_id]) + 1

    # Count nodes per layer
    layer_counts: dict[int, int] = {}
    for node_id in order:
        layer = layers[node_id]
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    # Assign positions within each layer (centered vertically)
    layer_positions: dict[int, int] = {}
    positions: dict[str, dict] = {}

    NODE_WIDTH = 240
    NODE_HEIGHT = 180
    H_GAP = 300
    V_GAP = 200

    for node_id in order:
        layer = layers[node_id]
        pos_in_layer = layer_positions.get(layer, 0)
        layer_positions[layer] = pos_in_layer + 1

        total_in_layer = layer_counts[layer]
        # Center vertically
        y_offset = (total_in_layer - 1) * V_GAP / 2
        y = 60 + pos_in_layer * V_GAP - y_offset

        x = 40 + layer * H_GAP

        positions[node_id] = {
            "x": int(x),
            "y": int(y),
            "layer": layer,
            "pos_in_layer": pos_in_layer,
        }

    return positions


# ── HTML Generator ─────────────────────────────────────────────────────

def render_canvas_html(
    workflow: Workflow,
    node_states: dict | None = None,
    node_errors: dict | None = None,
    title: str = "Hermesfy Studio",
) -> str:
    """Render a visual HTML canvas with real image thumbnails and SVG connections.

    Args:
        workflow: The workflow to render.
        node_states: Optional dict of node_id → state string.
        node_errors: Optional dict of node_id → error message.
        title: Page title.

    Returns:
        Complete self-contained HTML string.
    """
    node_states = node_states or {}
    node_errors = node_errors or {}

    positions = _compute_layout(workflow)
    node_map = {n.id: n for n in workflow.nodes}

    # Calculate canvas size
    max_x = max((p["x"] for p in positions.values()), default=0) + 280
    max_y = max((p["y"] for p in positions.values()), default=0) + 200
    canvas_width = max(max_x, 800)
    canvas_height = max(max_y, 600)

    # ── Build HTML parts ────────────────────────────────────────────────

    # SVG connections
    svg_connections = _render_connections(workflow, positions)

    # Node divs
    node_divs = []
    for node_id, pos in positions.items():
        node = node_map.get(node_id)
        if node is None:
            continue
        state = node_states.get(node_id, "pending")
        error = node_errors.get(node_id, "")
        node_html = _render_node(node, state, error, pos)
        node_divs.append(node_html)

    # ── Assemble full HTML ──────────────────────────────────────────────

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow: auto;
    min-height: 100vh;
}}
.canvas-container {{
    position: relative;
    width: {canvas_width}px;
    height: {canvas_height}px;
    margin: 0 auto;
}}
.connections-svg {{
    position: absolute;
    top: 0; left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
}}
.connections-svg path {{
    stroke-width: 2;
    fill: none;
    stroke-linecap: round;
    opacity: 0.6;
}}
.node {{
    position: absolute;
    width: 240px;
    border-radius: 10px;
    border: 2px solid #30363d;
    overflow: hidden;
    z-index: 2;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    transition: box-shadow 0.2s;
}}
.node:hover {{
    box-shadow: 0 6px 28px rgba(0,0,0,0.6);
}}
.node-header {{
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.node-body {{
    padding: 10px;
    font-size: 12px;
    min-height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.node-body img {{
    max-width: 100%;
    max-height: 120px;
    border-radius: 6px;
    object-fit: cover;
}}
.node-body .prompt-text {{
    color: #8b949e;
    font-size: 11px;
    line-height: 1.4;
    word-break: break-word;
    text-align: center;
}}
.node-body .model-name {{
    color: #58a6ff;
    font-size: 12px;
    font-weight: 600;
}}
.node-body .seed-value {{
    color: #d2a8ff;
    font-size: 18px;
    font-weight: 700;
}}
.node-footer {{
    padding: 6px 12px;
    font-size: 10px;
    border-top: 1px solid rgba(255,255,255,0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.node-footer .state-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
}}
.node-footer .error-msg {{
    color: #ef5350;
    font-size: 10px;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.status-bar {{
    background: #161b22;
    border-bottom: 1px solid #21262d;
    padding: 12px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
}}
.status-bar .workflow-name {{
    font-weight: 700;
    color: #f0f6fc;
}}
.status-bar .stats {{
    color: #8b949e;
    font-size: 12px;
}}
.status-bar .stats span {{
    margin-left: 16px;
}}
</style>
</head>
<body>
<div class="status-bar">
    <span class="workflow-name">📋 {workflow.name}</span>
    <span class="stats">
        <span>🆔 {workflow.id}</span>
        <span>📦 {len(workflow.nodes)} nodes</span>
        <span>🔗 {len(workflow.edges)} edges</span>
    </span>
</div>
<div class="canvas-container">
    <svg class="connections-svg" viewBox="0 0 {canvas_width} {canvas_height}">
        {svg_connections}
    </svg>
    {''.join(node_divs)}
</div>
</body>
</html>"""
    return html


# ── Node Rendering ─────────────────────────────────────────────────────

def _render_node(node, state: str, error: str, pos: dict) -> str:
    """Render a single node as an HTML div."""
    ntype = node.type.value
    style = NODE_STYLE.get(ntype, _DEFAULT_STYLE)
    config = node.config if hasattr(node, 'config') else {}

    state_color = STATE_COLORS.get(state, "#9e9e9e")
    state_emoji = {
        "pending": "○", "running": "⏳", "completed": "✅",
        "failed": "❌", "retrying": "🔄",
    }.get(state, "○")

    # ── Header ──
    header = (
        f'<div class="node-header" style="background:{style["header_bg"]}; '
        f'color:{style["border"]};">'
        f'<span>{style["label"]}</span>'
        f'<span style="color:#8b949e;font-weight:400;">{node.id}</span>'
        f'</div>'
    )

    # ── Body ──
    body = _render_node_body(node, style, config)

    # ── Footer ──
    footer_parts = [
        f'<span class="state-dot" style="background:{state_color};" '
        f'title="{state}"></span> {state_emoji} {state}',
    ]
    if error:
        footer_parts.append(f'<span class="error-msg" title="{error}">⚠️ {error[:50]}</span>')

    footer = (
        f'<div class="node-footer">'
        + ''.join(footer_parts)
        + '</div>'
    )

    return (
        f'<div class="node" style="left:{pos["x"]}px;top:{pos["y"]}px;'
        f'background:{style["bg"]};border-color:{style["border"]};">'
        f'{header}{body}{footer}'
        f'</div>'
    )


def _render_node_body(node, style: dict, config: dict) -> str:
    """Render the body content of a node based on its type."""
    ntype = node.type.value

    if ntype == "reference_image":
        url = config.get("image_url", "")
        label = config.get("label", "")
        role = config.get("reference_role", "")
        role_badge = f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{role}</div>' if role else ""
        return (
            f'<div class="node-body">'
            f'<div style="text-align:center;">'
            f'<img src="{url}" alt="{label or "reference"}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'block\';" />'
            f'<div style="display:none;color:#8b949e;font-size:11px;">🖼️ Image not available</div>'
            f'{"".join(role_badge)}'
            f'</div>'
            f'</div>'
        )

    elif ntype == "text_prompt":
        prompt = config.get("prompt", "")[:120]
        return (
            f'<div class="node-body">'
            f'<div class="prompt-text">"{prompt}{"..." if len(config.get("prompt", "")) > 120 else ""}"</div>'
            f'</div>'
        )

    elif ntype == "seed":
        seed = config.get("seed", "—")
        return (
            f'<div class="node-body">'
            f'<div class="seed-value">🌱 {seed}</div>'
            f'</div>'
        )

    elif ntype in ("image_gen", "img2img", "upscale", "inpaint", "outpaint",
                    "ip_adapter", "remove_bg", "face_restore"):
        model = config.get("model", "auto")
        width = config.get("width", "")
        height = config.get("height", "")
        resolution = f"{width}×{height}" if width and height else ""
        parts = []
        parts.append(f'<div class="model-name">{model}</div>')
        if resolution:
            parts.append(f'<div style="color:#8b949e;font-size:11px;margin-top:4px;">{resolution}</div>')
        return (
            f'<div class="node-body">'
            f'<div style="text-align:center;">'
            + "".join(parts) +
            f'</div>'
            f'</div>'
        )

    else:
        return (
            f'<div class="node-body">'
            f'<div style="color:#8b949e;font-size:11px;">{ntype}</div>'
            f'</div>'
        )


# ── SVG Connections ────────────────────────────────────────────────────

def _render_connections(workflow: Workflow, positions: dict) -> str:
    """Render all edges as SVG curved paths."""
    paths = []

    for edge in workflow.edges:
        src_pos = positions.get(edge.source)
        tgt_pos = positions.get(edge.target)
        if not src_pos or not tgt_pos:
            continue

        # Source: right-center of source node
        x1 = src_pos["x"] + 240  # node width
        y1 = src_pos["y"] + 90   # half node height (approx)

        # Target: left-center of target node
        x2 = tgt_pos["x"]
        y2 = tgt_pos["y"] + 90

        # Control points for cubic Bézier curve
        dx = abs(x2 - x1) * 0.5
        cx1 = x1 + dx
        cy1 = y1
        cx2 = x2 - dx
        cy2 = y2

        # Get color from source node type
        src_node = next((n for n in workflow.nodes if n.id == edge.source), None)
        stroke_color = "#4fc3f7"  # default
        if src_node:
            style = NODE_STYLE.get(src_node.type.value, _DEFAULT_STYLE)
            stroke_color = style["border"]

        path = (
            f'<path d="M {x1},{y1} C {cx1},{cy1} {cx2},{cy2} {x2},{y2}" '
            f'stroke="{stroke_color}" />'
        )
        paths.append(path)

    return "\n".join(paths)
