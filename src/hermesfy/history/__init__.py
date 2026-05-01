"""Image generation history — persistent log of generated images with metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HISTORY_DIR = Path.home() / ".hermes" / "hermesfy" / "history"
_HISTORY_FILE = _HISTORY_DIR / "history.jsonl"


def _ensure_dir() -> None:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def record_generation(
    image_url: str,
    workflow_id: str = "",
    workflow_name: str = "",
    prompt: str = "",
    model: str = "",
    pattern: str = "",
    qa_score: int | None = None,
    node_type: str = "",
    width: int = 0,
    height: int = 0,
    seed: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Record a generated image to the history log.

    Returns:
        The recorded entry dict.
    """
    _ensure_dir()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "image_url": image_url,
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "prompt": prompt,
        "model": model,
        "pattern": pattern,
        "qa_score": qa_score,
        "node_type": node_type,
        "width": width,
        "height": height,
        "seed": seed,
        "tags": tags or [],
    }

    with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def query_history(
    limit: int = 20,
    offset: int = 0,
    model: str = "",
    pattern: str = "",
    tag: str = "",
    min_score: int | None = None,
) -> list[dict]:
    """Query the history log with optional filters.

    Returns:
        List of history entries, newest first.
    """
    if not _HISTORY_FILE.exists():
        return []

    entries = []
    with open(_HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Apply filters
            if model and entry.get("model", "") != model:
                continue
            if pattern and entry.get("pattern", "") != pattern:
                continue
            if tag and tag not in entry.get("tags", []):
                continue
            if min_score is not None and (entry.get("qa_score") or 0) < min_score:
                continue

            entries.append(entry)

    # Sort newest first
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    # Apply pagination
    return entries[offset: offset + limit]


def get_history_stats() -> dict:
    """Get summary statistics of the history."""
    if not _HISTORY_FILE.exists():
        return {"total": 0}

    entries = []
    with open(_HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        return {"total": 0}

    models = {}
    patterns = {}
    scores = []
    for e in entries:
        m = e.get("model", "unknown")
        models[m] = models.get(m, 0) + 1
        p = e.get("pattern", "unknown")
        patterns[p] = patterns.get(p, 0) + 1
        if e.get("qa_score") is not None:
            scores.append(e["qa_score"])

    return {
        "total": len(entries),
        "by_model": models,
        "by_pattern": patterns,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "first": entries[-1].get("timestamp"),
        "last": entries[0].get("timestamp"),
    }


def clear_history() -> int:
    """Clear the history log. Returns number of entries removed."""
    if not _HISTORY_FILE.exists():
        return 0
    count = sum(1 for _ in open(_HISTORY_FILE, encoding="utf-8") if _.strip())
    _HISTORY_FILE.unlink()
    return count
