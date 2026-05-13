"""WorkflowService: CRUD, versioning, and validation for DAG workflows.

Provides a service layer over the in-memory workflow store with:
  - Create / Read / Update / Delete
  - Automatic version tracking (semver-like major.minor.patch)
  - Validation via the DAG graph engine
  - Import/export to JSON
  - Session-scoped workflow registry
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermesfy.dag.graph import (
    Edge,
    Node,
    NodeType,
    Workflow,
    validate_workflow,
)
from hermesfy.tools.workflows import (
    add_workflow,
    delete_workflow,
    get_workflow,
    list_workflows,
    get_workflow_states,
    set_workflow_states,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_PERSIST_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"

# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class WorkflowVersion:
    """Immutable version snapshot of a workflow."""

    version: str  # e.g. "1.0.0"
    workflow_id: str
    timestamp: str
    snapshot: dict  # Full serialized workflow at this version

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp,
            "snapshot": self.snapshot,
        }


@dataclass
class WorkflowMetadata:
    """Rich metadata for a workflow, separate from the DAG structure."""

    workflow_id: str
    name: str
    session_id: str = "default"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0.0"
    versions: list[WorkflowVersion] = field(default_factory=list)
    status: str = "draft"  # draft | running | completed | failed

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "session_id": self.session_id,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "versions": [v.to_dict() for v in self.versions],
            "status": self.status,
        }


# ── Service ──────────────────────────────────────────────────────────────────


class WorkflowServiceError(Exception):
    """Base exception for WorkflowService errors."""


class WorkflowNotFoundError(WorkflowServiceError):
    """Raised when a workflow ID is not found."""


class WorkflowValidationError(WorkflowServiceError):
    """Raised when a workflow fails validation."""


class WorkflowService:
    """Service for managing DAG workflows with versioning and validation.

    Features:
        - CRUD operations backed by the in-memory + disk store
        - Semantic versioning on every update
        - Full workflow validation before persistence
        - Session-scoped workflow queries
        - Import/export to JSON files
    """

    def __init__(self, persist_dir: Path | None = None):
        self._persist_dir = persist_dir or DEFAULT_PERSIST_DIR
        # In-memory metadata store: workflow_id → WorkflowMetadata
        self._metadata: dict[str, WorkflowMetadata] = {}

    # ── CRUD ─────────────────────────────────────────────────────────────

    def create(
        self,
        name: str,
        nodes: list[dict],
        edges: list[dict],
        session_id: str = "default",
        description: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        """Create a new workflow from node/edge dicts.

        Args:
            name: Human-readable workflow name.
            nodes: List of node dicts with id, type, config, position.
            edges: List of edge dicts with source, target.
            session_id: Session scope identifier.
            description: Optional description.
            tags: Optional tags.

        Returns:
            Dict with workflow_id, name, version, and serialized workflow.

        Raises:
            WorkflowValidationError: If the workflow structure is invalid.
        """
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        # Build nodes
        node_objects: list[Node] = []
        for n in nodes:
            try:
                ntype = NodeType(n["type"])
            except (KeyError, ValueError) as e:
                raise WorkflowValidationError(
                    f"Invalid node type for node '{n.get('id', '?')}': {e}"
                )
            node_objects.append(
                Node(
                    id=n["id"],
                    type=ntype,
                    config=n.get("config", {}),
                    position=tuple(n.get("position", (0, 0))),
                )
            )

        # Build edges
        edge_objects: list[Edge] = []
        for e in edges:
            edge_objects.append(Edge(source=e["source"], target=e["target"]))

        # Build workflow
        workflow = Workflow(
            id=workflow_id,
            name=name,
            nodes=node_objects,
            edges=edge_objects,
        )

        # Validate
        try:
            validate_workflow(workflow)
        except ValueError as e:
            raise WorkflowValidationError(str(e))

        # Persist
        add_workflow(workflow)

        # Create metadata
        metadata = WorkflowMetadata(
            workflow_id=workflow_id,
            name=name,
            session_id=session_id,
            description=description,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            version="1.0.0",
            versions=[
                WorkflowVersion(
                    version="1.0.0",
                    workflow_id=workflow_id,
                    timestamp=now,
                    snapshot=self._serialize_workflow(workflow),
                )
            ],
            status="draft",
        )
        self._metadata[workflow_id] = metadata

        logger.info("Created workflow %s v%s (%d nodes, %d edges)",
                     workflow_id, metadata.version, len(nodes), len(edges))

        return {
            "workflow_id": workflow_id,
            "name": name,
            "version": metadata.version,
            "workflow": self._serialize_workflow(workflow),
            "metadata": metadata.to_dict(),
        }

    def get(self, workflow_id: str) -> dict:
        """Retrieve a workflow by ID.

        Returns:
            Dict with workflow serialization and metadata.

        Raises:
            WorkflowNotFoundError: If workflow ID not found.
        """
        workflow = get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")

        metadata = self._metadata.get(workflow_id)
        node_states, node_errors, events = get_workflow_states(workflow_id)

        result: dict[str, Any] = {
            "workflow_id": workflow.id,
            "name": workflow.name,
            "workflow": self._serialize_workflow(workflow),
        }

        if metadata:
            result["metadata"] = metadata.to_dict()

        if node_states:
            result["execution"] = {
                "node_states": node_states,
                "node_errors": node_errors,
                "events": events,
            }

        return result

    def update(
        self,
        workflow_id: str,
        nodes: list[dict] | None = None,
        edges: list[dict] | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Update an existing workflow, creating a new version.

        Args:
            workflow_id: The workflow to update.
            nodes: New nodes list (if None, keeps existing).
            edges: New edges list (if None, keeps existing).
            name: New name (if None, keeps existing).
            description: New description.
            tags: New tags.

        Returns:
            Dict with updated workflow info and new version.

        Raises:
            WorkflowNotFoundError: If workflow ID not found.
            WorkflowValidationError: If the updated workflow fails validation.
        """
        existing = get_workflow(workflow_id)
        if existing is None:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")

        metadata = self._metadata.get(workflow_id)
        now = datetime.now(timezone.utc).isoformat()

        # Build new nodes
        if nodes is not None:
            node_objects: list[Node] = []
            for n in nodes:
                try:
                    ntype = NodeType(n["type"])
                except (KeyError, ValueError) as e:
                    raise WorkflowValidationError(
                        f"Invalid node type for node '{n.get('id', '?')}': {e}"
                    )
                node_objects.append(
                    Node(
                        id=n["id"],
                        type=ntype,
                        config=n.get("config", {}),
                        position=tuple(n.get("position", (0, 0))),
                    )
                )
        else:
            node_objects = list(existing.nodes)

        # Build new edges
        if edges is not None:
            edge_objects = [Edge(source=e["source"], target=e["target"]) for e in edges]
        else:
            edge_objects = list(existing.edges)

        new_name = name if name is not None else existing.name
        workflow = Workflow(
            id=workflow_id,
            name=new_name,
            nodes=node_objects,
            edges=edge_objects,
        )

        # Validate
        try:
            validate_workflow(workflow)
        except ValueError as e:
            raise WorkflowValidationError(str(e))

        # Persist
        add_workflow(workflow)

        # Compute new version
        new_version = self._bump_version(metadata.version if metadata else "1.0.0")
        snapshot = self._serialize_workflow(workflow)

        # Update metadata
        if metadata:
            metadata.name = new_name
            if description is not None:
                metadata.description = description
            if tags is not None:
                metadata.tags = tags
            metadata.updated_at = now
            metadata.version = new_version
            metadata.versions.append(
                WorkflowVersion(
                    version=new_version,
                    workflow_id=workflow_id,
                    timestamp=now,
                    snapshot=snapshot,
                )
            )
        else:
            metadata = WorkflowMetadata(
                workflow_id=workflow_id,
                name=new_name,
                description=description or "",
                tags=tags or [],
                created_at=now,
                updated_at=now,
                version=new_version,
                versions=[
                    WorkflowVersion(
                        version=new_version,
                        workflow_id=workflow_id,
                        timestamp=now,
                        snapshot=snapshot,
                    )
                ],
                status="draft",
            )
        self._metadata[workflow_id] = metadata

        logger.info("Updated workflow %s → v%s", workflow_id, new_version)

        return {
            "workflow_id": workflow_id,
            "name": new_name,
            "version": new_version,
            "previous_version": metadata.versions[-2].version if len(metadata.versions) > 1 else None,
            "workflow": snapshot,
            "metadata": metadata.to_dict(),
        }

    def delete(self, workflow_id: str) -> dict:
        """Delete a workflow by ID.

        Raises:
            WorkflowNotFoundError: If workflow ID not found.
        """
        if get_workflow(workflow_id) is None:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")

        delete_workflow(workflow_id)
        self._metadata.pop(workflow_id, None)

        logger.info("Deleted workflow %s", workflow_id)
        return {"deleted": True, "workflow_id": workflow_id}

    def list_by_session(self, session_id: str | None = None) -> list[dict]:
        """List all workflows, optionally filtered by session_id.

        Returns:
            List of workflow summary dicts.
        """
        result = []
        for wf in list_workflows():
            metadata = self._metadata.get(wf.id)
            if session_id and metadata and metadata.session_id != session_id:
                continue
            result.append({
                "workflow_id": wf.id,
                "name": wf.name,
                "nodes": len(wf.nodes),
                "edges": len(wf.edges),
                "version": metadata.version if metadata else "1.0.0",
                "status": metadata.status if metadata else "draft",
                "session_id": metadata.session_id if metadata else "default",
                "updated_at": metadata.updated_at if metadata else "",
            })
        return result

    # ── Versioning ───────────────────────────────────────────────────────

    def list_versions(self, workflow_id: str) -> list[dict]:
        """List all versions for a workflow.

        Raises:
            WorkflowNotFoundError: If workflow ID not found.
        """
        metadata = self._metadata.get(workflow_id)
        if metadata is None:
            # Check if workflow exists in store but not in metadata
            if get_workflow(workflow_id) is None:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")
            return [{"version": "1.0.0", "workflow_id": workflow_id, "timestamp": ""}]

        return [v.to_dict() for v in metadata.versions]

    def get_version(self, workflow_id: str, version: str) -> dict:
        """Retrieve a specific version snapshot.

        Raises:
            WorkflowNotFoundError: If workflow or version not found.
        """
        metadata = self._metadata.get(workflow_id)
        if metadata is None:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")

        for v in metadata.versions:
            if v.version == version:
                return v.to_dict()

        raise WorkflowNotFoundError(
            f"Version '{version}' not found for workflow '{workflow_id}'"
        )

    def _bump_version(self, current: str) -> str:
        """Increment the minor version (e.g. 1.0.0 → 1.1.0)."""
        parts = current.split(".")
        if len(parts) != 3:
            return "1.0.0"
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{major}.{minor + 1}.0"

    # ── Serialization ────────────────────────────────────────────────────

    @staticmethod
    def _serialize_workflow(workflow: Workflow) -> dict:
        """Serialize a Workflow to a JSON-safe dict."""
        return {
            "id": workflow.id,
            "name": workflow.name,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type.value,
                    "config": n.config,
                    "position": list(n.position),
                }
                for n in workflow.nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target} for e in workflow.edges
            ],
        }

    # ── Validation ───────────────────────────────────────────────────────

    @staticmethod
    def validate_structure(nodes: list[dict], edges: list[dict]) -> dict:
        """Validate a workflow structure without persisting it.

        Returns:
            Dict with valid=True/False and any errors.

        Raises:
            WorkflowValidationError: If validation fails.
        """
        try:
            node_objects = []
            for n in nodes:
                ntype = NodeType(n["type"])
                node_objects.append(
                    Node(
                        id=n["id"],
                        type=ntype,
                        config=n.get("config", {}),
                        position=tuple(n.get("position", (0, 0))),
                    )
                )

            edge_objects = [Edge(source=e["source"], target=e["target"]) for e in edges]

            workflow = Workflow(
                id="__validate__",
                name="Validation Check",
                nodes=node_objects,
                edges=edge_objects,
            )
            validate_workflow(workflow)
            return {"valid": True, "errors": []}
        except (ValueError, KeyError) as e:
            return {"valid": False, "errors": [str(e)]}

    # ── Import / Export ──────────────────────────────────────────────────

    def export_to_file(self, workflow_id: str, filepath: Path | str) -> dict:
        """Export a workflow to a JSON file.

        Raises:
            WorkflowNotFoundError: If workflow ID not found.
        """
        workflow = get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found")

        data = self._serialize_workflow(workflow)
        metadata = self._metadata.get(workflow_id)
        if metadata:
            data["metadata"] = metadata.to_dict()

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info("Exported workflow %s to %s", workflow_id, filepath)
        return {"exported": True, "filepath": str(filepath), "workflow_id": workflow_id}

    def import_from_file(self, filepath: Path | str, session_id: str = "default") -> dict:
        """Import a workflow from a JSON file.

        Returns:
            Dict with the created workflow info.

        Raises:
            WorkflowValidationError: If the imported workflow is invalid.
        """
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        name = data.get("name", filepath.stem)
        description = data.get("metadata", {}).get("description", f"Imported from {filepath.name}")
        tags = data.get("metadata", {}).get("tags", [])

        return self.create(
            name=name,
            nodes=nodes,
            edges=edges,
            session_id=session_id,
            description=description,
            tags=tags,
        )

    # ── Session Management ───────────────────────────────────────────────

    def clear_session(self, session_id: str) -> dict:
        """Delete all workflows in a session."""
        deleted = []
        for wf in list_workflows():
            metadata = self._metadata.get(wf.id)
            if metadata and metadata.session_id == session_id:
                delete_workflow(wf.id)
                self._metadata.pop(wf.id, None)
                deleted.append(wf.id)

        logger.info("Cleared session %s: %d workflows deleted", session_id, len(deleted))
        return {"cleared": True, "session_id": session_id, "deleted_workflows": deleted, "count": len(deleted)}
