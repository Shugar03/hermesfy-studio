"""In-memory workflow store — module-level dict with helper functions."""

from __future__ import annotations

from typing import Optional
from hermesfy.dag.graph import Workflow

# Module-level workflow store
workflows: dict[str, Workflow] = {}

# Execution state store: workflow_id → {"node_states": {...}, "node_errors": {...}, "events": [...]}
_workflow_states: dict[str, dict] = {}


def add_workflow(workflow: Workflow) -> None:
    """Store a workflow in memory."""
    workflows[workflow.id] = workflow


def get_workflow(workflow_id: str) -> Optional[Workflow]:
    """Retrieve a workflow by ID, or None if not found."""
    return workflows.get(workflow_id)


def delete_workflow(workflow_id: str) -> None:
    """Remove a workflow from the store."""
    workflows.pop(workflow_id, None)
    _workflow_states.pop(workflow_id, None)


def list_workflows() -> list[Workflow]:
    """Return all stored workflows."""
    return list(workflows.values())


def set_workflow_states(
    workflow_id: str,
    node_states: dict[str, str],
    node_errors: dict[str, str],
    events: list[dict] | None = None,
) -> None:
    """Store execution states and events for a workflow after execution."""
    _workflow_states[workflow_id] = {
        "node_states": node_states,
        "node_errors": node_errors,
        "events": events or [],
    }


def get_workflow_states(workflow_id: str) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    """Retrieve execution states for a workflow. Returns (node_states, node_errors, events)."""
    entry = _workflow_states.get(workflow_id, {})
    return (
        entry.get("node_states", {}),
        entry.get("node_errors", {}),
        entry.get("events", []),
    )
