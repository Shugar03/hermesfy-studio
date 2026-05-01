"""Tool: hermesfy_list_templates — browse and inspect workflow templates."""

import json

from hermesfy.templates import list_templates, get_template, template_to_json

__all__ = ["list_templates_tool"]


def list_templates_tool(action: str = "list", template_key: str = "", description: str = "") -> str:
    """Browse, inspect, or export workflow templates.

    Args:
        action: 'list' (all templates), 'inspect' (one template details), 'export' (JSON for define_workflow).
        template_key: Template key for inspect/export (e.g., 'product_studio').
        description: Description to inject into {description} placeholders (for export).

    Returns:
        JSON string with template info or export data.
    """
    if action == "list":
        templates = list_templates()
        return json.dumps({"templates": templates, "count": len(templates)}, indent=2)

    elif action == "inspect":
        tmpl = get_template(template_key)
        if tmpl is None:
            return json.dumps({"error": f"Template '{template_key}' not found"})
        return json.dumps({
            "key": tmpl["_key"],
            "name": tmpl["name"],
            "description": tmpl.get("description", ""),
            "category": tmpl.get("category", ""),
            "nodes": tmpl.get("nodes", []),
            "edges": tmpl.get("edges", []),
        }, indent=2)

    elif action == "export":
        data = template_to_json(template_key, description)
        if data is None:
            return json.dumps({"error": f"Template '{template_key}' not found"})
        return json.dumps(data, indent=2)

    else:
        return json.dumps({"error": f"Unknown action '{action}'. Use: list, inspect, export"})
