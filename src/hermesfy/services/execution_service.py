"""Execution service — manages workflow execution runs with concurrency, cancellation,
cost tracking, and approval integration.

Orchestrates the full run lifecycle: queued → awaiting_approval → running → succeeded/failed/cancelled.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from hermesfy.api.schemas import (
    ExecutionRun,
    RunStatus,
    Approval,
    ApprovalStatus,
)
from hermesfy.api.settings import Settings
from hermesfy.services.event_bus import EventBus, DomainEvent
from hermesfy.storage.repositories import (
    ExecutionRunRepository,
    ApprovalRepository,
)

logger = logging.getLogger("hermesfy.execution_service")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionService:
    """Manages execution runs: creation, status transitions, cancellation, cost tracking."""

    def __init__(
        self,
        settings: Settings,
        event_bus: EventBus,
        run_repo: Optional[ExecutionRunRepository] = None,
        approval_repo: Optional[ApprovalRepository] = None,
    ):
        self.settings = settings
        self.event_bus = event_bus
        self.run_repo = run_repo or ExecutionRunRepository(settings)
        self.approval_repo = approval_repo or ApprovalRepository(settings)
        self._active_runs: dict[str, asyncio.Task] = {}

    # ── Run lifecycle ──────────────────────────────────────────────────────

    async def create_run(
        self,
        workflow_id: str,
        workflow_version: int,
        budget_limit_usd: Optional[float] = None,
        estimated_cost_usd: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> ExecutionRun:
        """Create a new execution run. If estimated cost exceeds budget, status is awaiting_approval."""
        budget = budget_limit_usd or self.settings.default_budget_usd

        status = RunStatus.QUEUED
        if estimated_cost_usd and estimated_cost_usd > budget:
            status = RunStatus.AWAITING_APPROVAL

        run = ExecutionRun(
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            status=status,
            budget_limit_usd=budget,
            estimated_cost_usd=estimated_cost_usd,
            session_id=session_id,
        )

        await self.run_repo.create(run)

        # If awaiting approval, create approval record
        if status == RunStatus.AWAITING_APPROVAL:
            approval = Approval(
                run_id=run.id,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                status=ApprovalStatus.PENDING,
                title=f"Approve run {run.id} (${estimated_cost_usd:.2f})",
                description=f"Estimated cost ${estimated_cost_usd:.2f} exceeds budget ${budget:.2f}",
                risk_level="medium" if estimated_cost_usd and estimated_cost_usd > budget * 2 else "low",
                session_id=session_id,
            )
            await self.approval_repo.create(approval)
            await self.event_bus.publish(DomainEvent(
                type="approval.request",
                workflow_id=workflow_id,
                run_id=run.id,
                payload=approval.model_dump(),
                session_id=session_id,
            ))

        await self.event_bus.publish(DomainEvent(
            type="execution.created",
            workflow_id=workflow_id,
            run_id=run.id,
            payload=run.model_dump(),
            session_id=session_id,
        ))

        return run

    async def get_run(self, run_id: str) -> Optional[ExecutionRun]:
        return await self.run_repo.get(run_id)

    async def start_run(self, run_id: str) -> bool:
        """Mark a run as running. Only works if status is queued or awaiting_approval with approved."""
        run = await self.run_repo.get(run_id)
        if run is None:
            return False
        if run.status not in (RunStatus.QUEUED,):
            return False

        # Check if approval is needed and resolved
        if run.status == RunStatus.AWAITING_APPROVAL:
            # Check if there's an approved approval for this run
            # For now, allow transition only if status was already changed by approval service
            return False

        ok = await self.run_repo.update_status(run_id, RunStatus.RUNNING.value, started_at=_utcnow())
        if ok:
            await self.event_bus.publish(DomainEvent(
                type="execution.started",
                workflow_id=run.workflow_id,
                run_id=run_id,
                payload={"run_id": run_id, "workflow_id": run.workflow_id},
                session_id=run.session_id,
            ))
        return ok

    async def complete_run(self, run_id: str, actual_cost_usd: Optional[float] = None) -> bool:
        """Mark a run as succeeded."""
        finished = _utcnow()
        ok = await self.run_repo.update_status(
            run_id, RunStatus.SUCCEEDED.value,
            finished_at=finished, actual_cost_usd=actual_cost_usd,
        )
        if ok:
            await self.event_bus.publish(DomainEvent(
                type="execution.completed",
                run_id=run_id,
                payload={"run_id": run_id, "status": "succeeded", "actual_cost_usd": actual_cost_usd},
            ))
        return ok

    async def fail_run(self, run_id: str, error: str = "") -> bool:
        """Mark a run as failed."""
        finished = _utcnow()
        ok = await self.run_repo.update_status(
            run_id, RunStatus.FAILED.value, finished_at=finished,
        )
        if ok:
            await self.event_bus.publish(DomainEvent(
                type="execution.failed",
                run_id=run_id,
                payload={"run_id": run_id, "error": error},
            ))
        return ok

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running or queued run."""
        run = await self.run_repo.get(run_id)
        if run is None:
            return False
        if run.status not in (RunStatus.QUEUED, RunStatus.AWAITING_APPROVAL, RunStatus.RUNNING):
            return False

        # Cancel any active subprocess task
        task = self._active_runs.pop(run_id, None)
        if task and not task.done():
            task.cancel()

        finished = _utcnow()
        ok = await self.run_repo.update_status(run_id, RunStatus.CANCELLED.value, finished_at=finished)
        if ok:
            await self.event_bus.publish(DomainEvent(
                type="execution.cancelled",
                run_id=run_id,
                payload={"run_id": run_id},
            ))
        return ok

    async def register_active_run(self, run_id: str, task: asyncio.Task) -> None:
        """Register a running task so it can be cancelled."""
        self._active_runs[run_id] = task

    # ── Node-level events ──────────────────────────────────────────────────

    async def emit_node_started(self, run_id: str, node_id: str, workflow_id: str) -> None:
        await self.event_bus.publish(DomainEvent(
            type="execution.node.started",
            run_id=run_id,
            workflow_id=workflow_id,
            payload={"node_id": node_id, "run_id": run_id},
        ))

    async def emit_node_completed(self, run_id: str, node_id: str, workflow_id: str,
                                  duration_ms: float = 0, cost_usd: float = 0) -> None:
        await self.event_bus.publish(DomainEvent(
            type="execution.node.completed",
            run_id=run_id,
            workflow_id=workflow_id,
            payload={"node_id": node_id, "run_id": run_id, "duration_ms": duration_ms, "cost_usd": cost_usd},
        ))

    async def emit_node_failed(self, run_id: str, node_id: str, workflow_id: str,
                               error: str = "") -> None:
        await self.event_bus.publish(DomainEvent(
            type="execution.node.failed",
            run_id=run_id,
            workflow_id=workflow_id,
            payload={"node_id": node_id, "run_id": run_id, "error": error},
        ))

    async def emit_node_progress(self, run_id: str, node_id: str, workflow_id: str,
                                 phase: str = "", message: str = "") -> None:
        await self.event_bus.publish(DomainEvent(
            type="execution.node.progress",
            run_id=run_id,
            workflow_id=workflow_id,
            payload={"node_id": node_id, "run_id": run_id, "phase": phase, "message": message},
        ))
