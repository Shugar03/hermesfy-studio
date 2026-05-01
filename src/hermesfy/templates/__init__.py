"""Workflow templates — pre-built pipelines for common use cases."""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Optional

from hermesfy.dag.graph import Edge, Node, NodeType, validate_workflow, Workflow

_TEMPLATES_DIR = Path(__file__).parent
_cache: dict[str, dict] | None = None


def _load_all() -> dict[str, dict]:
    """Load all YAML templates from the templates directory."""
    global _cache
    if _cache is not None:
        return _cache

    _cache = {}
    for fp in _TEMPLATES_DIR.glob("*.yaml"):
        try:
            with open(fp, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and "name" in data:
                key = fp.stem
                data["_key"] = key
                data["_file"] = fp.name
                _cache[key] = data
        except (yaml.YAMLError, OSError):
            continue
    return _cache


def list_templates() -> list[dict]:
    """List all available templates with metadata."""
    templates = _load_all()
    return [
        {
            "key": t["_key"],
            "name": t["name"],
            "description": t.get("description", ""),
            "category": t.get("category", "general"),
            "nodes": len(t.get("nodes", [])),
            "file": t["_file"],
        }
        for t in templates.values()
    ]


def get_template(key: str) -> Optional[dict]:
    """Get a template definition by key."""
    return _load_all().get(key)


def instantiate_template(key: str, description: str = "") -> Optional[Workflow]:
    """Create a Workflow instance from a template, with optional description replacement.

    Args:
        key: Template key (e.g., 'product_studio').
        description: Text to replace {description} placeholders in prompt nodes.

    Returns:
        A validated Workflow, or None if template not found.
    """
    tmpl = get_template(key)
    if tmpl is None:
        return None

    nodes = []
    for n in tmpl.get("nodes", []):
        config = dict(n.get("config", {}))
        # Replace {description} placeholder
        if description:
            for k, v in config.items():
                if isinstance(v, str) and "{description}" in v:
                    config[k] = v.replace("{description}", description)
        nodes.append(Node(
            id=n["id"],
            type=NodeType(n["type"]),
            config=config,
        ))

    edges = [Edge(source=e["source"], target=e["target"]) for e in tmpl.get("edges", [])]

    wf = Workflow(
        id="",
        name=tmpl["name"],
        nodes=nodes,
        edges=edges,
    )
    return wf


def template_to_json(key: str, description: str = "") -> dict | None:
    """Export a template as a JSON-serializable dict (for hermesfy_define_workflow)."""
    wf = instantiate_template(key, description)
    if wf is None:
        return None
    return {
        "name": wf.name,
        "nodes": [
            {"id": n.id, "type": n.type.value, "config": n.config}
            for n in wf.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target}
            for e in wf.edges
        ],
    }
