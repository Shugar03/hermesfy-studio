"""In-memory workflow store — module-level dict with helper functions."""

from __future__ import annotations

from typing import Optional

from hermesfy.dag.graph import Workflow

# Module-level workflow store
workflows: dict[str, Workflow] = {}


def add_workflow(workflow: Workflow) -> None:
    """Store a workflow in memory."""
    workflows[workflow.id] = workflow


def get_workflow(workflow_id: str) -> Optional[Workflow]:
    """Retrieve a workflow by ID, or None if not found."""
    return workflows.get(workflow_id)


def delete_workflow(workflow_id: str) -> None:
    """Remove a workflow from the store."""
    workflows.pop(workflow_id, None)


def list_workflows() -> list[Workflow]:
    """Return all stored workflows."""
    return list(workflows.values())
