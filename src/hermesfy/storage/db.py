"""SQLite database initialization — WAL mode, schema creation, migration stub.

Creates all tables required by the V5 domain model if they don't exist.
Uses aiosqlite for async I/O compatibility with FastAPI.
"""

from __future__ import annotations

import logging

import aiosqlite

from hermesfy.api.settings import Settings

logger = logging.getLogger("hermesfy.storage.db")


SCHEMA_SQL = """
-- Workflows (V2 with versioning)
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Untitled Workflow',
    version INTEGER NOT NULL DEFAULT 1,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    session_id TEXT
);

-- Nodes within a workflow
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    type TEXT NOT NULL,
    config_data TEXT NOT NULL DEFAULT '{}',
    position_x REAL NOT NULL DEFAULT 0.0,
    position_y REAL NOT NULL DEFAULT 0.0,
    ui TEXT NOT NULL DEFAULT '{}',
    disabled INTEGER NOT NULL DEFAULT 0,
    schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (workflow_id, id),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Edges within a workflow (V2 with ports)
CREATE TABLE IF NOT EXISTS edges (
    id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    source_port TEXT,
    target_port TEXT,
    kind TEXT NOT NULL DEFAULT 'data',
    PRIMARY KEY (workflow_id, id),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Workflow version history (for audit/replay)
CREATE TABLE IF NOT EXISTS workflow_versions (
    workflow_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (workflow_id, version),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE SET NULL
);

-- Chat turns (messages in a session)
CREATE TABLE IF NOT EXISTS chat_turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    agent_response TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    actions TEXT NOT NULL DEFAULT '[]',
    cost_usd REAL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- Execution runs
CREATE TABLE IF NOT EXISTS execution_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_version INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    budget_limit_usd REAL NOT NULL DEFAULT 0.07,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    started_at TEXT,
    finished_at TEXT,
    session_id TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Execution events (for replay)
CREATE TABLE IF NOT EXISTS execution_events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    node_id TEXT,
    data TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES execution_runs(id) ON DELETE CASCADE
);

-- Artifacts (generated outputs)
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    workflow_id TEXT NOT NULL,
    node_id TEXT,
    artifact_type TEXT NOT NULL DEFAULT 'image',
    url TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES execution_runs(id) ON DELETE SET NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Approvals (cost, VRH, risky actions)
CREATE TABLE IF NOT EXISTS approvals (
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
    session_id TEXT,
    FOREIGN KEY (run_id) REFERENCES execution_runs(id) ON DELETE SET NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Learnings (persistent error patterns and fixes)
CREATE TABLE IF NOT EXISTS learnings (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL DEFAULT 'general',
    pattern TEXT NOT NULL,
    fix TEXT,
    severity TEXT NOT NULL DEFAULT 'info',
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_nodes_workflow ON nodes(workflow_id);
CREATE INDEX IF NOT EXISTS idx_edges_workflow ON edges(workflow_id);
CREATE INDEX IF NOT EXISTS idx_chat_turns_session ON chat_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_execution_runs_workflow ON execution_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_execution_events_run ON execution_events(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_workflow ON artifacts(workflow_id);
CREATE INDEX IF NOT EXISTS idx_approvals_workflow ON approvals(workflow_id);
CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_id);
"""


async def ensure_schema(settings: Settings) -> None:
    """Create the database and all tables if they don't exist.

    This is idempotent — safe to call on every startup.
    """
    db_path = settings.resolved_db_path
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    logger.info("DB schema ensured at %s", db_path)


async def check_db_readiness(settings: Settings) -> bool:
    """Check if the database is reachable and writable.

    Returns True if the DB is ready, False otherwise.
    """
    try:
        db_path = settings.resolved_db_path
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            # Try a write to confirm writable
            await db.execute(
                "CREATE TABLE IF NOT EXISTS _readiness_check (id INTEGER PRIMARY KEY)"
            )
            await db.execute("INSERT OR REPLACE INTO _readiness_check (id) VALUES (1)")
            await db.commit()
            return True
    except Exception:
        logger.exception("DB readiness check failed")
        return False
