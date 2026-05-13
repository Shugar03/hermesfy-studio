"""Approval service — manages approval requests for cost, VRH, and risky actions.

Handles the approval lifecycle: pending → approved/rejected/stale.
Integrates with EventBus for realtime notifications.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from hermesfy.api.schemas import (
    Approval,
    ApprovalStatus,
    RunStatus,
)
from hermesfy.api.settings import Settings
from hermesfy.services.event_bus import EventBus, DomainEvent
from hermesfy.storage.repositories import (
    ApprovalRepository,
    ExecutionRunRepository,
)

logger = logging.getLogger("hermesfy.approval_service")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalService:
    """Manages approval lifecycle and integrates with run execution."""

    def __init__(
        self,
        settings: Settings,
        event_bus: EventBus,
        approval_repo: Optional[ApprovalRepository] = None,
        run_repo: Optional[ExecutionRunRepository] = None,
    ):
        self.settings = settings
        self.event_bus = event_bus
        self.approval_repo = approval_repo or ApprovalRepository(settings)
        self.run_repo = run_repo or ExecutionRunRepository(settings)

    async def request_approval(
        self,
        workflow_id: str,
        workflow_version: int,
        title: str,
        description: str,
        run_id: Optional[str] = None,
        cost_breakdown: Optional[dict] = None,
        risk_level: str = "low",
        session_id: Optional[str] = None,
    ) -> Approval:
        """Create an approval request and publish it via EventBus."""
        approval = Approval(
            run_id=run_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            status=ApprovalStatus.PENDING,
            title=title,
            description=description,
            cost_breakdown=cost_breakdown,
            risk_level=risk_level,
            session_id=session_id,
        )
        await self.approval_repo.create(approval)

        await self.event_bus.publish(DomainEvent(
            type="approval.request",
            workflow_id=workflow_id,
            run_id=run_id,
            session_id=session_id,
            payload=approval.model_dump(),
        ))

        return approval

    async def approve(self, approval_id: str) -> tuple[bool, str]:
        """Approve an approval. If tied to a run, transitions the run to queued."""
        approval = await self.approval_repo.get(approval_id)
        if approval is None:
            return False, f"Approval {approval_id} not found"

        if approval.status != ApprovalStatus.PENDING:
            return False, f"Approval already {approval.status.value}"

        # Verify workflow hasn't changed since approval was created
        if approval.run_id:
            run = await self.run_repo.get(approval.run_id)
            if run and run.workflow_version != approval.workflow_version:
                # Mark old approval as stale
                await self.approval_repo.resolve(approval_id, ApprovalStatus.STALE.value)
                return False, "Workflow version changed — approval is stale"

        ok = await self.approval_repo.resolve(approval_id, ApprovalStatus.APPROVED.value)
        if not ok:
            return False, "Failed to resolve approval"

        # Transition the associated run from awaiting_approval to queued
        if approval.run_id:
            await self.run_repo.update_status(approval.run_id, RunStatus.QUEUED.value)

        await self.event_bus.publish(DomainEvent(
            type="approval.resolved",
            workflow_id=approval.workflow_id,
            run_id=approval.run_id,
            session_id=approval.session_id,
            payload={"approval_id": approval_id, "status": "approved"},
        ))

        return True, "Approved"

    async def reject(self, approval_id: str) -> tuple[bool, str]:
        """Reject an approval. Cancels the associated run if any."""
        approval = await self.approval_repo.get(approval_id)
        if approval is None:
            return False, f"Approval {approval_id} not found"

        if approval.status != ApprovalStatus.PENDING:
            return False, f"Approval already {approval.status.value}"

        ok = await self.approval_repo.resolve(approval_id, ApprovalStatus.REJECTED.value)
        if not ok:
            return False, "Failed to resolve approval"

        # Cancel the associated run
        if approval.run_id:
            await self.run_repo.update_status(approval.run_id, RunStatus.CANCELLED.value,
                                              finished_at=_utcnow())

        await self.event_bus.publish(DomainEvent(
            type="approval.resolved",
            workflow_id=approval.workflow_id,
            run_id=approval.run_id,
            session_id=approval.session_id,
            payload={"approval_id": approval_id, "status": "rejected"},
        ))

        return True, "Rejected"

    async def modify_approval(
        self, approval_id: str, modified_params: Optional[dict] = None
    ) -> tuple[bool, str]:
        """Modify an approval (e.g., reduce budget, change model)."""
        approval = await self.approval_repo.get(approval_id)
        if approval is None:
            return False, f"Approval {approval_id} not found"

        if approval.status != ApprovalStatus.PENDING:
            return False, f"Approval already {approval.status.value}"

        ok = await self.approval_repo.resolve(approval_id, ApprovalStatus.MODIFIED.value)
        if not ok:
            return False, "Failed to resolve approval"

        await self.event_bus.publish(DomainEvent(
            type="approval.resolved",
            workflow_id=approval.workflow_id,
            run_id=approval.run_id,
            session_id=approval.session_id,
            payload={"approval_id": approval_id, "status": "modified", "params": modified_params},
        ))

        return True, "Modified"

    async def get_approval(self, approval_id: str) -> Optional[Approval]:
        return await self.approval_repo.get(approval_id)

    async def check_workflow_version(self, approval_id: str) -> bool:
        """Check if the workflow version still matches. Returns True if valid."""
        approval = await self.approval_repo.get(approval_id)
        if approval is None or approval.run_id is None:
            return True

        run = await self.run_repo.get(approval.run_id)
        if run is None:
            return True

        return run.workflow_version == approval.workflow_version
