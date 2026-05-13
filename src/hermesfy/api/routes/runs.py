"""Execution run routes.

POST /api/dag/{workflow_id}/execute   — create run
GET  /api/runs/{run_id}              — get run status
POST /api/runs/{run_id}/cancel       — cancel run
POST /api/runs/{run_id}/retry        — retry failed run
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends

from hermesfy.api.deps import get_db, require_auth
from hermesfy.api.errors import NotFoundError, ValidationError
from hermesfy.api.schemas import (
    ExecutionRun,
    ExecutionRunCreate,
    RunStatus,
)

logger = logging.getLogger("hermesfy.api.runs")

router = APIRouter(tags=["runs"], dependencies=[Depends(require_auth)])


# ── Create run (via DAG route) ────────────────────────────────────────────────


@router.post("/dag/{workflow_id}/execute", response_model=ExecutionRun, status_code=202)
async def execute_workflow(
    workflow_id: str,
    body: ExecutionRunCreate = ExecutionRunCreate(),
    db: aiosqlite.Connection = Depends(get_db),
) -> ExecutionRun:
    """Queue a workflow for execution. Returns the run immediately.

    In P1 this is a stub — actual execution is wired in P5.
    """
    # Verify workflow exists
    cursor = await db.execute(
        "SELECT id, version FROM workflows WHERE id = ?", (workflow_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("Workflow", workflow_id)

    rowd = dict(row)
    version = rowd["version"]

    run = ExecutionRun(
        workflow_id=workflow_id,
        workflow_version=version,
        budget_limit_usd=body.budget_limit_usd,
        status=RunStatus.QUEUED,
    )
    await db.execute(
        """INSERT INTO execution_runs
           (id, workflow_id, workflow_version, status, budget_limit_usd,
            estimated_cost_usd, actual_cost_usd, started_at, finished_at, session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.id, run.workflow_id, run.workflow_version, run.status.value,
            run.budget_limit_usd, run.estimated_cost_usd, run.actual_cost_usd,
            run.started_at.isoformat() if run.started_at else None,
            run.finished_at.isoformat() if run.finished_at else None,
            run.session_id,
        ),
    )
    await db.commit()
    logger.info("Created run %s for workflow %s (v%d)", run.id, workflow_id, version)
    return run


# ── Read run ──────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}", response_model=ExecutionRun)
async def get_run(
    run_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> ExecutionRun:
    """Get the current status of an execution run."""
    cursor = await db.execute(
        "SELECT * FROM execution_runs WHERE id = ?", (run_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("ExecutionRun", run_id)

    rowd = dict(row)
    return ExecutionRun(
        id=rowd["id"],
        workflow_id=rowd["workflow_id"],
        workflow_version=rowd["workflow_version"],
        status=RunStatus(rowd["status"]),
        budget_limit_usd=rowd["budget_limit_usd"],
        estimated_cost_usd=rowd.get("estimated_cost_usd"),
        actual_cost_usd=rowd.get("actual_cost_usd"),
        started_at=datetime.fromisoformat(rowd["started_at"]) if rowd.get("started_at") else None,
        finished_at=datetime.fromisoformat(rowd["finished_at"]) if rowd.get("finished_at") else None,
        session_id=rowd.get("session_id"),
    )


# ── Cancel run ────────────────────────────────────────────────────────────────


@router.post("/runs/{run_id}/cancel", response_model=ExecutionRun)
async def cancel_run(
    run_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> ExecutionRun:
    """Cancel a queued or running execution."""
    cursor = await db.execute(
        "SELECT * FROM execution_runs WHERE id = ?", (run_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("ExecutionRun", run_id)

    rowd = dict(row)
    current_status = RunStatus(rowd["status"])

    if current_status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED):
        raise ValidationError(
            f"Cannot cancel run in status '{current_status.value}'",
        )

    now = datetime.now(timezone.utc)
    await db.execute(
        """UPDATE execution_runs SET status = ?, finished_at = ?
           WHERE id = ?""",
        (RunStatus.CANCELLED.value, now.isoformat(), run_id),
    )
    await db.commit()

    return ExecutionRun(
        id=rowd["id"],
        workflow_id=rowd["workflow_id"],
        workflow_version=rowd["workflow_version"],
        status=RunStatus.CANCELLED,
        budget_limit_usd=rowd["budget_limit_usd"],
        estimated_cost_usd=rowd.get("estimated_cost_usd"),
        actual_cost_usd=rowd.get("actual_cost_usd"),
        started_at=datetime.fromisoformat(rowd["started_at"]) if rowd.get("started_at") else None,
        finished_at=now,
        session_id=rowd.get("session_id"),
    )


# ── Retry run ─────────────────────────────────────────────────────────────────


@router.post("/runs/{run_id}/retry", response_model=ExecutionRun, status_code=202)
async def retry_run(
    run_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> ExecutionRun:
    """Retry a failed or cancelled run (creates a new run)."""
    cursor = await db.execute(
        "SELECT * FROM execution_runs WHERE id = ?", (run_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("ExecutionRun", run_id)

    rowd = dict(row)
    current_status = RunStatus(rowd["status"])

    if current_status not in (RunStatus.FAILED, RunStatus.CANCELLED):
        raise ValidationError(
            f"Cannot retry run in status '{current_status.value}'",
        )

    # Create a new run cloning the old one
    new_run = ExecutionRun(
        workflow_id=rowd["workflow_id"],
        workflow_version=rowd["workflow_version"],
        status=RunStatus.QUEUED,
        budget_limit_usd=rowd["budget_limit_usd"],
        session_id=rowd.get("session_id"),
    )
    await db.execute(
        """INSERT INTO execution_runs
           (id, workflow_id, workflow_version, status, budget_limit_usd,
            estimated_cost_usd, actual_cost_usd, started_at, finished_at, session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            new_run.id, new_run.workflow_id, new_run.workflow_version, new_run.status.value,
            new_run.budget_limit_usd, new_run.estimated_cost_usd, new_run.actual_cost_usd,
            new_run.started_at.isoformat() if new_run.started_at else None,
            new_run.finished_at.isoformat() if new_run.finished_at else None,
            new_run.session_id,
        ),
    )
    await db.commit()
    logger.info("Retried run %s → new run %s (workflow %s v%d)",
                run_id, new_run.id, new_run.workflow_id, new_run.workflow_version)
    return new_run
