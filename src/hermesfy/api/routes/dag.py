"""DAG (workflow) CRUD routes with version conflict detection.

GET    /api/dag/{workflow_id}          — read workflow
PATCH  /api/dag/{workflow_id}          — update with expected_version
POST   /api/dag/{workflow_id}/nodes     — add node
PATCH  /api/dag/{workflow_id}/nodes/{node_id} — update node
DELETE /api/dag/{workflow_id}/nodes/{node_id} — remove node
POST   /api/dag/{workflow_id}/edges     — add edge
DELETE /api/dag/{workflow_id}/edges/{edge_id} — remove edge
POST   /api/dag                        — create new workflow
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, Query

from hermesfy.api.deps import get_db, require_auth
from hermesfy.api.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    VersionConflictError,
)
from hermesfy.api.schemas import (
    EdgeV2,
    NodeV2,
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowV2,
)

logger = logging.getLogger("hermesfy.api.dag")

router = APIRouter(prefix="/dag", tags=["dag"], dependencies=[Depends(require_auth)])

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _fetch_workflow(db: aiosqlite.Connection, workflow_id: str) -> dict:
    """Fetch a raw workflow row from DB. Raises NotFoundError if missing."""
    cursor = await db.execute(
        "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("Workflow", workflow_id)
    return dict(row)


async def _fetch_nodes(db: aiosqlite.Connection, workflow_id: str) -> list[NodeV2]:
    """Fetch all nodes for a workflow."""
    cursor = await db.execute(
        "SELECT * FROM nodes WHERE workflow_id = ? ORDER BY rowid", (workflow_id,)
    )
    nodes: list[NodeV2] = []
    async for row in cursor:
        rowd = dict(row)
        position = {"x": rowd.get("position_x", 0.0), "y": rowd.get("position_y", 0.0)}
        ui = json.loads(rowd.get("ui", "{}")) if rowd.get("ui") else {}
        config = json.loads(rowd.get("config_data", "{}")) if rowd.get("config_data") else {}
        nodes.append(NodeV2(
            id=rowd["id"],
            type=rowd["type"],
            config=config,
            position={"x": float(position["x"]), "y": float(position["y"])},
            ui=ui,
            disabled=bool(rowd.get("disabled", False)),
        ))
    return nodes


async def _fetch_edges(db: aiosqlite.Connection, workflow_id: str) -> list[EdgeV2]:
    """Fetch all edges for a workflow."""
    cursor = await db.execute(
        "SELECT * FROM edges WHERE workflow_id = ? ORDER BY rowid", (workflow_id,)
    )
    edges: list[EdgeV2] = []
    async for row in cursor:
        rowd = dict(row)
        edges.append(EdgeV2(
            id=rowd["id"],
            source=rowd["source"],
            target=rowd["target"],
            source_port=rowd.get("source_port"),
            target_port=rowd.get("target_port"),
            kind=rowd.get("kind", "data"),
        ))
    return edges


async def _assemble_workflow(db: aiosqlite.Connection, workflow_id: str) -> WorkflowV2:
    """Fetch a full WorkflowV2 from DB (row + nodes + edges)."""
    row = await _fetch_workflow(db, workflow_id)
    nodes = await _fetch_nodes(db, workflow_id)
    edges = await _fetch_edges(db, workflow_id)
    return WorkflowV2(
        id=row["id"],
        name=row["name"],
        version=row["version"],
        nodes=nodes,
        edges=edges,
        metadata=json.loads(row.get("metadata", "{}")) if row.get("metadata") else {},
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(timezone.utc),
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.now(timezone.utc),
        session_id=row.get("session_id"),
    )


async def _bump_version(db: aiosqlite.Connection, workflow_id: str, new_version: int) -> None:
    """Update the workflow version and updated_at timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE workflows SET version = ?, updated_at = ? WHERE id = ?",
        (new_version, now, workflow_id),
    )


async def _sync_nodes(db: aiosqlite.Connection, workflow_id: str, nodes: list[NodeV2]) -> None:
    """Replace all nodes for a workflow with the given list."""
    await db.execute("DELETE FROM nodes WHERE workflow_id = ?", (workflow_id,))
    for node in nodes:
        await db.execute(
            """INSERT INTO nodes (id, workflow_id, type, config_data, position_x, position_y,
               ui, disabled, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node.id, workflow_id, node.type,
                json.dumps(node.config),
                node.position.x, node.position.y,
                json.dumps(node.ui) if node.ui else "{}",
                int(node.disabled), node.schema_version,
            ),
        )


async def _sync_edges(db: aiosqlite.Connection, workflow_id: str, edges: list[EdgeV2]) -> None:
    """Replace all edges for a workflow with the given list."""
    await db.execute("DELETE FROM edges WHERE workflow_id = ?", (workflow_id,))
    for edge in edges:
        await db.execute(
            """INSERT INTO edges (id, workflow_id, source, target, source_port, target_port, kind)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                edge.id, workflow_id, edge.source, edge.target,
                edge.source_port, edge.target_port, edge.kind.value,
            ),
        )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=WorkflowV2, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> WorkflowV2:
    """Create a new workflow."""
    wf = WorkflowV2(
        name=body.name,
        nodes=body.nodes,
        edges=body.edges,
        session_id=body.session_id,
        version=1,
    )
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO workflows (id, name, version, metadata, created_at, updated_at, session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (wf.id, wf.name, wf.version, json.dumps(wf.metadata), now, now, wf.session_id),
    )
    await _sync_nodes(db, wf.id, wf.nodes)
    await _sync_edges(db, wf.id, wf.edges)
    await db.commit()
    logger.info("Created workflow %s (v1)", wf.id)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowV2)
async def get_workflow(
    workflow_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> WorkflowV2:
    """Read a workflow by ID."""
    return await _assemble_workflow(db, workflow_id)


@router.patch("/{workflow_id}", response_model=WorkflowV2)
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    db: aiosqlite.Connection = Depends(get_db),
) -> WorkflowV2:
    """Update a workflow with optimistic concurrency via expected_version.

    Returns 409 VERSION_CONFLICT if the workflow version doesn't match.
    """
    row = await _fetch_workflow(db, workflow_id)
    current_version = row["version"]

    if body.expected_version != current_version:
        raise VersionConflictError(body.expected_version, current_version)

    new_version = current_version + 1

    if body.name is not None:
        await db.execute(
            "UPDATE workflows SET name = ? WHERE id = ?", (body.name, workflow_id)
        )
    if body.nodes is not None:
        await _sync_nodes(db, workflow_id, body.nodes)
    if body.edges is not None:
        await _sync_edges(db, workflow_id, body.edges)
    if body.metadata is not None:
        existing_meta = json.loads(row.get("metadata", "{}")) if row.get("metadata") else {}
        existing_meta.update(body.metadata)
        await db.execute(
            "UPDATE workflows SET metadata = ? WHERE id = ?",
            (json.dumps(existing_meta), workflow_id),
        )

    await _bump_version(db, workflow_id, new_version)
    await db.commit()
    logger.info("Updated workflow %s (v%d → v%d)", workflow_id, current_version, new_version)
    return await _assemble_workflow(db, workflow_id)


@router.post("/{workflow_id}/nodes", response_model=NodeV2, status_code=201)
async def add_node(
    workflow_id: str,
    node: NodeV2,
    db: aiosqlite.Connection = Depends(get_db),
) -> NodeV2:
    """Add a node to an existing workflow (bumps version)."""
    row = await _fetch_workflow(db, workflow_id)
    new_version = row["version"] + 1

    # Check for duplicate node ID
    cursor = await db.execute(
        "SELECT id FROM nodes WHERE workflow_id = ? AND id = ?", (workflow_id, node.id)
    )
    if await cursor.fetchone() is not None:
        raise ConflictError(f"Node '{node.id}' already exists in workflow '{workflow_id}'")

    await db.execute(
        """INSERT INTO nodes (id, workflow_id, type, config_data, position_x, position_y,
           ui, disabled, schema_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            node.id, workflow_id, node.type,
            json.dumps(node.config),
            node.position.x, node.position.y,
            json.dumps(node.ui) if node.ui else "{}",
            int(node.disabled), node.schema_version,
        ),
    )
    await _bump_version(db, workflow_id, new_version)
    await db.commit()
    logger.info("Added node %s to workflow %s (v%d)", node.id, workflow_id, new_version)
    return node


@router.patch("/{workflow_id}/nodes/{node_id}", response_model=NodeV2)
async def update_node(
    workflow_id: str,
    node_id: str,
    node: NodeV2,
    db: aiosqlite.Connection = Depends(get_db),
) -> NodeV2:
    """Update an existing node (bumps version)."""
    row = await _fetch_workflow(db, workflow_id)
    new_version = row["version"] + 1

    # Verify node exists
    cursor = await db.execute(
        "SELECT id FROM nodes WHERE workflow_id = ? AND id = ?", (workflow_id, node_id)
    )
    if await cursor.fetchone() is None:
        raise NotFoundError("Node", node_id)

    await db.execute(
        """UPDATE nodes SET type = ?, config_data = ?, position_x = ?, position_y = ?,
           ui = ?, disabled = ?, schema_version = ?
           WHERE workflow_id = ? AND id = ?""",
        (
            node.type, json.dumps(node.config),
            node.position.x, node.position.y,
            json.dumps(node.ui) if node.ui else "{}",
            int(node.disabled), node.schema_version,
            workflow_id, node_id,
        ),
    )
    await _bump_version(db, workflow_id, new_version)
    await db.commit()
    logger.info("Updated node %s in workflow %s (v%d)", node_id, workflow_id, new_version)
    return node


@router.delete("/{workflow_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    workflow_id: str,
    node_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> None:
    """Delete a node (bumps version, also removes connected edges)."""
    row = await _fetch_workflow(db, workflow_id)
    new_version = row["version"] + 1

    # Verify node exists
    cursor = await db.execute(
        "SELECT id FROM nodes WHERE workflow_id = ? AND id = ?", (workflow_id, node_id)
    )
    if await cursor.fetchone() is None:
        raise NotFoundError("Node", node_id)

    await db.execute("DELETE FROM nodes WHERE workflow_id = ? AND id = ?", (workflow_id, node_id))
    # Also remove edges that reference this node
    await db.execute(
        "DELETE FROM edges WHERE workflow_id = ? AND (source = ? OR target = ?)",
        (workflow_id, node_id, node_id),
    )
    await _bump_version(db, workflow_id, new_version)
    await db.commit()
    logger.info("Deleted node %s from workflow %s (v%d)", node_id, workflow_id, new_version)


@router.post("/{workflow_id}/edges", response_model=EdgeV2, status_code=201)
async def add_edge(
    workflow_id: str,
    edge: EdgeV2,
    db: aiosqlite.Connection = Depends(get_db),
) -> EdgeV2:
    """Add an edge to an existing workflow (bumps version)."""
    row = await _fetch_workflow(db, workflow_id)
    new_version = row["version"] + 1

    # Check for duplicate edge ID
    cursor = await db.execute(
        "SELECT id FROM edges WHERE workflow_id = ? AND id = ?", (workflow_id, edge.id)
    )
    if await cursor.fetchone() is not None:
        raise ConflictError(f"Edge '{edge.id}' already exists in workflow '{workflow_id}'")

    await db.execute(
        """INSERT INTO edges (id, workflow_id, source, target, source_port, target_port, kind)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            edge.id, workflow_id, edge.source, edge.target,
            edge.source_port, edge.target_port, edge.kind.value,
        ),
    )
    await _bump_version(db, workflow_id, new_version)
    await db.commit()
    logger.info("Added edge %s to workflow %s (v%d)", edge.id, workflow_id, new_version)
    return edge


@router.delete("/{workflow_id}/edges/{edge_id}", status_code=204)
async def delete_edge(
    workflow_id: str,
    edge_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> None:
    """Delete an edge (bumps version)."""
    row = await _fetch_workflow(db, workflow_id)
    new_version = row["version"] + 1

    cursor = await db.execute(
        "SELECT id FROM edges WHERE workflow_id = ? AND id = ?", (workflow_id, edge_id)
    )
    if await cursor.fetchone() is None:
        raise NotFoundError("Edge", edge_id)

    await db.execute("DELETE FROM edges WHERE workflow_id = ? AND id = ?", (workflow_id, edge_id))
    await _bump_version(db, workflow_id, new_version)
    await db.commit()
    logger.info("Deleted edge %s from workflow %s (v%d)", edge_id, workflow_id, new_version)
