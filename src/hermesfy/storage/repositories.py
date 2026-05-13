"""Repository classes for Hermesfy V5 SQLite persistence.

Each repository provides async CRUD operations for its entity.
Uses aiosqlite and a shared connection or connection factory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from hermesfy.api.settings import Settings
from hermesfy.api.schemas import (
    WorkflowV2,
    NodeV2,
    EdgeV2,
    ChatSession,
    ChatTurn,
    ExecutionRun,
    Approval,
)
from hermesfy.storage.db import ensure_schema

logger = logging.getLogger("hermesfy.storage.repositories")

# ID generators
import uuid as _uuid

def _uid(prefix: str) -> str:
    return f"{prefix}_{_uuid.uuid4().hex[:12]}"

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# WorkflowRepository
# ═══════════════════════════════════════════════════════════════════

class WorkflowRepository:
    """CRUD for WorkflowV2, including nodes, edges, and version history."""

    def __init__(self, settings: Settings):
        import aiosqlite
        self.db_path = settings.resolved_db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _connect(self) -> "aiosqlite.Connection":
        import aiosqlite
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Workflows ──────────────────────────────────────────────────

    async def create(self, workflow: WorkflowV2, session_id: Optional[str] = None) -> WorkflowV2:
        """Create a new workflow with its nodes and edges."""
        async with await self._connect() as db:
            now = _utcnow()
            await db.execute(
                "INSERT INTO workflows (id, name, version, metadata, created_at, updated_at, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (workflow.id, workflow.name, workflow.version or 1,
                 json.dumps(workflow.metadata or {}), now, now, session_id),
            )
            for node in workflow.nodes:
                await db.execute(
                    "INSERT INTO nodes (id, workflow_id, type, config_data, position_x, position_y, ui, disabled, schema_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (node.id, workflow.id, node.type, json.dumps(node.config),
                     node.position.get("x", 0), node.position.get("y", 0),
                     json.dumps(node.ui or {}), 1 if node.disabled else 0, node.schema_version),
                )
            for edge in workflow.edges:
                await db.execute(
                    "INSERT INTO edges (id, workflow_id, source, target, source_port, target_port, kind) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (edge.id, workflow.id, edge.source, edge.target,
                     edge.source_port, edge.target_port, edge.kind),
                )
            # Save initial version snapshot
            await db.execute(
                "INSERT INTO workflow_versions (workflow_id, version, snapshot, created_at) "
                "VALUES (?, ?, ?, ?)",
                (workflow.id, 1, workflow.model_dump_json(), now),
            )
            await db.commit()
        return workflow

    async def get(self, workflow_id: str) -> Optional[WorkflowV2]:
        """Retrieve a full workflow with nodes and edges."""
        async with await self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
            row = await cursor.fetchone()
            if row is None:
                return None

            nodes_cursor = await db.execute("SELECT * FROM nodes WHERE workflow_id = ?", (workflow_id,))
            nodes = []
            async for nr in nodes_cursor:
                nodes.append(NodeV2(
                    id=nr["id"],
                    type=nr["type"],
                    config=json.loads(nr["config_data"]),
                    position={"x": nr["position_x"], "y": nr["position_y"]},
                    ui=json.loads(nr["ui"]),
                    disabled=bool(nr["disabled"]),
                    schema_version=nr["schema_version"],
                ))

            edges_cursor = await db.execute("SELECT * FROM edges WHERE workflow_id = ?", (workflow_id,))
            edges = []
            async for er in edges_cursor:
                edges.append(EdgeV2(
                    id=er["id"],
                    source=er["source"],
                    target=er["target"],
                    source_port=er["source_port"],
                    target_port=er["target_port"],
                    kind=er["kind"],
                ))

            return WorkflowV2(
                id=row["id"],
                name=row["name"],
                version=row["version"],
                metadata=json.loads(row["metadata"]),
                nodes=nodes,
                edges=edges,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    async def update(self, workflow_id: str, expected_version: int, patch_data: dict) -> tuple[Optional[WorkflowV2], str | None]:
        """Update a workflow with optimistic concurrency control.

        Args:
            workflow_id: The workflow to update.
            expected_version: The version the caller expects. If it doesn't match, returns (None, error).
            patch_data: Dict with optional keys: name, metadata, nodes (full replace), edges (full replace).

        Returns:
            Tuple of (updated WorkflowV2 | None, error message | None).
        """
        current = await self.get(workflow_id)
        if current is None:
            return None, f"Workflow '{workflow_id}' not found"

        if current.version != expected_version:
            return None, f"Version conflict: expected {expected_version}, actual {current.version}"

        async with await self._connect() as db:
            now = _utcnow()
            new_version = current.version + 1

            if "name" in patch_data:
                await db.execute("UPDATE workflows SET name = ?, updated_at = ? WHERE id = ?",
                                 (patch_data["name"], now, workflow_id))
                current.name = patch_data["name"]
            if "metadata" in patch_data:
                await db.execute("UPDATE workflows SET metadata = ?, updated_at = ? WHERE id = ?",
                                 (json.dumps(patch_data["metadata"]), now, workflow_id))
                current.metadata = patch_data["metadata"]

            await db.execute("UPDATE workflows SET version = ?, updated_at = ? WHERE id = ?",
                             (new_version, now, workflow_id))
            current.version = new_version
            current.updated_at = now

            # Full replace of nodes if provided
            if "nodes" in patch_data:
                await db.execute("DELETE FROM nodes WHERE workflow_id = ?", (workflow_id,))
                for node in patch_data["nodes"]:
                    n = node if isinstance(node, NodeV2) else NodeV2(**node) if isinstance(node, dict) else node
                    await db.execute(
                        "INSERT INTO nodes (id, workflow_id, type, config_data, position_x, position_y, ui, disabled, schema_version) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (n.id, workflow_id, n.type, json.dumps(n.config if isinstance(n, NodeV2) else n.get("config", {})),
                         (n.position.get("x",0) if isinstance(n, NodeV2) else n.get("position",{}).get("x",0)),
                         (n.position.get("y",0) if isinstance(n, NodeV2) else n.get("position",{}).get("y",0)),
                         json.dumps(n.ui if isinstance(n, NodeV2) else n.get("ui",{})),
                         1 if (n.disabled if isinstance(n, NodeV2) else n.get("disabled")) else 0,
                         n.schema_version if isinstance(n, NodeV2) else n.get("schema_version", 1)),
                    )
                current.nodes = [NodeV2(**n) if isinstance(n, dict) else n for n in patch_data["nodes"]]

            if "edges" in patch_data:
                await db.execute("DELETE FROM edges WHERE workflow_id = ?", (workflow_id,))
                for edge in patch_data["edges"]:
                    e = edge if isinstance(edge, EdgeV2) else EdgeV2(**edge) if isinstance(edge, dict) else edge
                    await db.execute(
                        "INSERT INTO edges (id, workflow_id, source, target, source_port, target_port, kind) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (e.id, workflow_id, e.source, e.target, e.source_port, e.target_port, e.kind),
                    )
                current.edges = [EdgeV2(**e) if isinstance(e, dict) else e for e in patch_data["edges"]]

            # Save version snapshot
            snapshot = current.model_dump_json()
            await db.execute(
                "INSERT INTO workflow_versions (workflow_id, version, snapshot, created_at) "
                "VALUES (?, ?, ?, ?)",
                (workflow_id, new_version, snapshot, now),
            )
            await db.commit()

        return await self.get(workflow_id), None

    async def delete(self, workflow_id: str) -> bool:
        """Delete a workflow and all related records (cascaded). Returns True if deleted."""
        async with await self._connect() as db:
            cursor = await db.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def list_all(self) -> list[WorkflowV2]:
        """List all workflows (without full node/edge data for efficiency)."""
        async with await self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT id FROM workflows ORDER BY updated_at DESC")
            ids = [row["id"] async for row in cursor]
        result = []
        for wid in ids:
            wf = await self.get(wid)
            if wf:
                result.append(wf)
        return result


# ═══════════════════════════════════════════════════════════════════
# ChatSessionRepository
# ═══════════════════════════════════════════════════════════════════

class ChatSessionRepository:
    def __init__(self, settings: Settings):
        self.db_path = settings.resolved_db_path

    async def create(self, session: ChatSession) -> ChatSession:
        import aiosqlite
        now = _utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute(
                "INSERT INTO chat_sessions (id, workflow_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session.id, session.workflow_id, session.title, now, now),
            )
            await db.commit()
        session.created_at = now
        session.updated_at = now
        return session

    async def get(self, session_id: str) -> Optional[ChatSession]:
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return ChatSession(
                id=row["id"],
                workflow_id=row["workflow_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )


# ═══════════════════════════════════════════════════════════════════
# ChatTurnRepository
# ═══════════════════════════════════════════════════════════════════

class ChatTurnRepository:
    def __init__(self, settings: Settings):
        self.db_path = settings.resolved_db_path

    async def create(self, turn: ChatTurn) -> ChatTurn:
        import aiosqlite
        now = _utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute(
                "INSERT INTO chat_turns (id, session_id, user_message, agent_response, status, actions, cost_usd, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (turn.id, turn.session_id, turn.user_message, turn.agent_response,
                 turn.status, json.dumps(turn.actions or []), turn.cost_usd, now),
            )
            await db.commit()
        turn.created_at = now
        return turn

    async def get(self, turn_id: str) -> Optional[ChatTurn]:
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM chat_turns WHERE id = ?", (turn_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return ChatTurn(
                id=row["id"],
                session_id=row["session_id"],
                user_message=row["user_message"],
                agent_response=row["agent_response"],
                status=row["status"],
                actions=json.loads(row["actions"]),
                cost_usd=row["cost_usd"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )


# ═══════════════════════════════════════════════════════════════════
# ExecutionRunRepository
# ═══════════════════════════════════════════════════════════════════

class ExecutionRunRepository:
    def __init__(self, settings: Settings, auto_ensure: bool = True):
        import aiosqlite
        self.db_path = settings.resolved_db_path
        self._auto_ensure = auto_ensure

    async def _ensure(self) -> None:
        """Ensure the execution_runs table exists."""
        import aiosqlite
        if self._auto_ensure:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA foreign_keys=ON")
                # Minimal ensure for execution_runs
                await db.execute("""CREATE TABLE IF NOT EXISTS execution_runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workflow_version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    budget_limit_usd REAL NOT NULL DEFAULT 0.07,
                    estimated_cost_usd REAL,
                    actual_cost_usd REAL,
                    started_at TEXT,
                    finished_at TEXT,
                    session_id TEXT
                )""")
                await db.commit()

    async def create(self, run: ExecutionRun) -> ExecutionRun:
        import aiosqlite
        await self._ensure()
        now = _utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute(
                "INSERT INTO execution_runs (id, workflow_id, workflow_version, status, budget_limit_usd, "
                "estimated_cost_usd, actual_cost_usd, started_at, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run.id, run.workflow_id, run.workflow_version, run.status,
                 run.budget_limit_usd, run.estimated_cost_usd, run.actual_cost_usd,
                 now, run.session_id),
            )
            await db.commit()
        run.started_at = now
        return run

    async def get(self, run_id: str) -> Optional[ExecutionRun]:
        import aiosqlite
        await self._ensure()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM execution_runs WHERE id = ?", (run_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return ExecutionRun(
                id=row["id"],
                workflow_id=row["workflow_id"],
                workflow_version=row["workflow_version"],
                status=row["status"],
                budget_limit_usd=row["budget_limit_usd"],
                estimated_cost_usd=row["estimated_cost_usd"],
                actual_cost_usd=row["actual_cost_usd"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                session_id=row["session_id"],
            )

    async def update_status(self, run_id: str, status: str,
                            started_at: Optional[str] = None,
                            finished_at: Optional[str] = None,
                            actual_cost_usd: Optional[float] = None) -> bool:
        import aiosqlite
        await self._ensure()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            cursor = await db.execute(
                """UPDATE execution_runs
                   SET status = ?,
                       started_at = COALESCE(?, started_at),
                       finished_at = COALESCE(?, finished_at),
                       actual_cost_usd = COALESCE(?, actual_cost_usd)
                   WHERE id = ?""",
                (status, started_at, finished_at, actual_cost_usd, run_id),
            )
            await db.commit()
            return cursor.rowcount > 0


# ═══════════════════════════════════════════════════════════════════
# ApprovalRepository
# ═══════════════════════════════════════════════════════════════════

class ApprovalRepository:
    def __init__(self, settings: Settings, auto_ensure: bool = True):
        self.db_path = settings.resolved_db_path
        self._auto_ensure = auto_ensure

    async def _ensure(self) -> None:
        """Ensure the approvals table exists."""
        import aiosqlite
        if self._auto_ensure:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA foreign_keys=ON")
                await db.execute("""CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT,
                    workflow_id TEXT NOT NULL,
                    workflow_version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    title TEXT NOT NULL DEFAULT 'Approval Required',
                    description TEXT NOT NULL DEFAULT '',
                    cost_breakdown TEXT,
                    risk_level TEXT NOT NULL DEFAULT 'low',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    session_id TEXT
                )""")
                await db.commit()

    async def create(self, approval: Approval) -> Approval:
        import aiosqlite
        await self._ensure()
        now = _utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute(
                "INSERT INTO approvals (id, run_id, workflow_id, workflow_version, status, title, "
                "description, cost_breakdown, risk_level, created_at, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (approval.id, approval.run_id, approval.workflow_id, approval.workflow_version,
                 approval.status, approval.title, approval.description,
                 json.dumps(approval.cost_breakdown) if approval.cost_breakdown else None,
                 approval.risk_level, now, approval.session_id),
            )
            await db.commit()
        approval.created_at = now
        return approval

    async def get(self, approval_id: str) -> Optional[Approval]:
        import aiosqlite
        await self._ensure()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            cb = row["cost_breakdown"]
            return Approval(
                id=row["id"],
                run_id=row["run_id"],
                workflow_id=row["workflow_id"],
                workflow_version=row["workflow_version"],
                status=row["status"],
                title=row["title"],
                description=row["description"],
                cost_breakdown=json.loads(cb) if cb else None,
                risk_level=row["risk_level"],
                created_at=row["created_at"],
                resolved_at=row["resolved_at"],
                session_id=row["session_id"],
            )

    async def resolve(self, approval_id: str, status: str) -> bool:
        import aiosqlite
        await self._ensure()
        now = _utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            cursor = await db.execute(
                "UPDATE approvals SET status = ?, resolved_at = ? WHERE id = ?",
                (status, now, approval_id),
            )
            await db.commit()
            return cursor.rowcount > 0
