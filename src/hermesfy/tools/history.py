"""Tool: hermesfy_history — query and manage the image generation history gallery."""

import json

from hermesfy.history import query_history, get_history_stats, clear_history

__all__ = ["history_tool"]


def history_tool(
    action: str = "list",
    limit: int = 20,
    offset: int = 0,
    model: str = "",
    pattern: str = "",
    tag: str = "",
    min_score: int = 0,
) -> str:
    """Query, inspect, or clear the image generation history.

    Args:
        action: 'list' (paginated gallery), 'stats' (summary), 'clear' (wipe history).
        limit: Max entries to return (default 20).
        offset: Pagination offset.
        model: Filter by model name.
        pattern: Filter by pattern.
        tag: Filter by tag.
        min_score: Filter by minimum QA score.

    Returns:
        JSON string with history entries or stats.
    """
    if action == "list":
        min_s = min_score if min_score > 0 else None
        entries = query_history(
            limit=limit,
            offset=offset,
            model=model,
            pattern=pattern,
            tag=tag,
            min_score=min_s,
        )
        return json.dumps({
            "entries": entries,
            "count": len(entries),
            "offset": offset,
            "limit": limit,
        }, indent=2)

    elif action == "stats":
        stats = get_history_stats()
        return json.dumps(stats, indent=2)

    elif action == "clear":
        removed = clear_history()
        return json.dumps({"status": "cleared", "removed": removed})

    else:
        return json.dumps({"error": f"Unknown action '{action}'. Use: list, stats, clear"})
