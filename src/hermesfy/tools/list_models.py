"""Tool: hermesfy_list_models — list all available models from the registry."""

from hermesfy.providers.registry import get_models


def list_models() -> str:
    """Return a formatted markdown list of all registered models.

    Returns:
        Markdown string with model names, descriptions, and supported node types.
    """
    models = get_models()

    lines = ["# Available Models\n"]
    for model in models:
        name = model["name"]
        desc = model["description"]
        node_types = ", ".join(model.get("supported_node_types", []))
        endpoint = model.get("endpoint", "n/a")
        lines.append(f"## {name}")
        lines.append(f"- **Description**: {desc}")
        lines.append(f"- **Endpoint**: `{endpoint}`")
        lines.append(f"- **Supported node types**: {node_types}")
        lines.append("")

    return "\n".join(lines)
