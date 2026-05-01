"""In-memory workflow store with automatic JSON persistence.

Workflows are stored in memory for fast access AND automatically saved
to disk (~/.hermes/hermesfy/workflows/) on every mutation.
On startup, existing workflows are loaded from disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from hermesfy.dag.graph import Workflow

# Default persistence directory
_PERSIST_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"

# Module-level workflow store
workflows: dict[str, Workflow] = {}

# Execution state store: workflow_id → {"node_states": {...}, "node_errors": {...}, "events": [...]}
_workflow_states: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Auto-persistence helpers
# ---------------------------------------------------------------------------

def _persist_workflow(workflow: Workflow) -> None:
    """Save a single workflow to disk as JSON."""
    _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = workflow.name.lower().replace(" ", "_").replace("-", "_")
    filepath = _PERSIST_DIR / f"{safe_name}.json"

    data = {
        "id": workflow.id,
        "name": workflow.name,
        "nodes": [
            {"id": n.id, "type": n.type.value, "config": n.config, "position": list(n.position)}
            for n in workflow.nodes
        ],
        "edges": [{"source": e.source, "target": e.target} for e in workflow.edges],
    }

    # Include execution states if available
    if workflow.id in _workflow_states:
        data["execution"] = _workflow_states[workflow.id]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _remove_persisted(workflow_id: str) -> None:
    """Remove a persisted workflow file by ID."""
    if not _PERSIST_DIR.exists():
        return
    for fp in _PERSIST_DIR.glob("*.json"):
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("id") == workflow_id:
                fp.unlink()
                return
        except (json.JSONDecodeError, OSError):
            continue


def load_persisted_workflows() -> int:
    """Load all persisted workflows from disk into memory.

    Returns:
        Number of workflows loaded.
    """
    if not _PERSIST_DIR.exists():
        return 0

    count = 0
    for fp in _PERSIST_DIR.glob("*.json"):
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)

            from hermesfy.dag.graph import Edge, Node, NodeType

            nodes = [
                Node(
                    id=n["id"],
                    type=NodeType(n["type"]),
                    config=n.get("config", {}),
                    position=tuple(n.get("position", (0, 0))),
                )
                for n in data.get("nodes", [])
            ]
            edges = [Edge(source=e["source"], target=e["target"]) for e in data.get("edges", [])]

            wf = Workflow(
                id=data.get("id", ""),
                name=data.get("name", "unnamed"),
                nodes=nodes,
                edges=edges,
            )
            workflows[wf.id] = wf

            # Restore execution states if present
            execution = data.get("execution")
            if execution:
                _workflow_states[wf.id] = execution

            count += 1
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            continue

    return count


# ---------------------------------------------------------------------------
# Public API (auto-persists on mutation)
# ---------------------------------------------------------------------------

def add_workflow(workflow: Workflow) -> None:
    """Store a workflow in memory and persist to disk."""
    workflows[workflow.id] = workflow
    _persist_workflow(workflow)


def get_workflow(workflow_id: str) -> Optional[Workflow]:
    """Retrieve a workflow by ID, or None if not found."""
    return workflows.get(workflow_id)


def delete_workflow(workflow_id: str) -> None:
    """Remove a workflow from memory and disk."""
    workflows.pop(workflow_id, None)
    _workflow_states.pop(workflow_id, None)
    _remove_persisted(workflow_id)


def list_workflows() -> list[Workflow]:
    """Return all stored workflows."""
    return list(workflows.values())


def set_workflow_states(
    workflow_id: str,
    node_states: dict[str, str],
    node_errors: dict[str, str],
    events: list[dict] | None = None,
) -> None:
    """Store execution states and events, then persist the updated workflow."""
    _workflow_states[workflow_id] = {
        "node_states": node_states,
        "node_errors": node_errors,
        "events": events or [],
    }
    # Re-persist the workflow with updated states
    wf = workflows.get(workflow_id)
    if wf is not None:
        _persist_workflow(wf)


def get_workflow_states(workflow_id: str) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    """Retrieve execution states for a workflow. Returns (node_states, node_errors, events)."""
    entry = _workflow_states.get(workflow_id, {})
    return (
        entry.get("node_states", {}),
        entry.get("node_errors", {}),
        entry.get("events", []),
    )
