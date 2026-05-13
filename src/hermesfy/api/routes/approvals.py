"""Approval routes.

POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
POST /api/approvals/{approval_id}/modify
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends

from hermesfy.api.deps import get_db, require_auth
from hermesfy.api.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from hermesfy.api.schemas import (
    Approval,
    ApprovalAction,
    ApprovalStatus,
)

logger = logging.getLogger("hermesfy.api.approvals")

router = APIRouter(prefix="/approvals", tags=["approvals"], dependencies=[Depends(require_auth)])


def _resolve_approval(
    action: str, approval_row: dict, comment: str | None, modified_params: dict | None,
) -> Approval:
    """Build an Approval model with the resolved state."""
    now = datetime.now(timezone.utc)
    if action == "approve":
        status = ApprovalStatus.APPROVED
    elif action == "reject":
        status = ApprovalStatus.REJECTED
    else:
        status = ApprovalStatus.MODIFIED
    return Approval(
        id=approval_row["id"],
        run_id=approval_row.get("run_id"),
        workflow_id=approval_row["workflow_id"],
        workflow_version=approval_row["workflow_version"],
        status=status,
        title=approval_row.get("title", "Approval Required"),
        description=approval_row.get("description", ""),
        cost_breakdown=None,
        risk_level=approval_row.get("risk_level", "low"),
        created_at=datetime.fromisoformat(approval_row["created_at"]),
        resolved_at=now,
        session_id=approval_row.get("session_id"),
    )


@router.post("/{approval_id}/approve", response_model=Approval)
async def approve(
    approval_id: str,
    body: ApprovalAction = ApprovalAction(action="approve"),
    db: aiosqlite.Connection = Depends(get_db),
) -> Approval:
    """Approve a pending approval request."""
    return await _handle_approval_action(approval_id, "approve", body.comment, body.modified_params, db)


@router.post("/{approval_id}/reject", response_model=Approval)
async def reject(
    approval_id: str,
    body: ApprovalAction = ApprovalAction(action="reject"),
    db: aiosqlite.Connection = Depends(get_db),
) -> Approval:
    """Reject a pending approval request."""
    return await _handle_approval_action(approval_id, "reject", body.comment, body.modified_params, db)


@router.post("/{approval_id}/modify", response_model=Approval)
async def modify(
    approval_id: str,
    body: ApprovalAction,
    db: aiosqlite.Connection = Depends(get_db),
) -> Approval:
    """Modify and approve an approval request with changed parameters."""
    if not body.modified_params:
        raise ValidationError("modified_params required for modify action")
    return await _handle_approval_action(approval_id, "modify", body.comment, body.modified_params, db)


async def _handle_approval_action(
    approval_id: str,
    action: str,
    comment: str | None,
    modified_params: dict | None,
    db: aiosqlite.Connection,
) -> Approval:
    """Shared logic for approve/reject/modify."""
    cursor = await db.execute(
        "SELECT * FROM approvals WHERE id = ?", (approval_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("Approval", approval_id)

    rowd = dict(row)

    if rowd["status"] != ApprovalStatus.PENDING.value:
        raise ConflictError(
            f"Approval '{approval_id}' is already {rowd['status']}",
        )

    # Check for stale approval (workflow version changed)
    # Fetch current workflow version
    wf_cursor = await db.execute(
        "SELECT version FROM workflows WHERE id = ?", (rowd["workflow_id"],)
    )
    wf_row = await wf_cursor.fetchone()
    if wf_row is not None:
        current_wf_version = dict(wf_row)["version"]
        if current_wf_version != rowd["workflow_version"]:
            await db.execute(
                "UPDATE approvals SET status = ?, resolved_at = ? WHERE id = ?",
                (ApprovalStatus.STALE.value, datetime.now(timezone.utc).isoformat(), approval_id),
            )
            await db.commit()
            raise ConflictError(
                f"Approval is stale: workflow version changed from {rowd['workflow_version']} to {current_wf_version}",
                {"code": "STALE_APPROVAL", "expected_version": rowd["workflow_version"], "current_version": current_wf_version},
            )

    now = datetime.now(timezone.utc)
    if action == "approve":
        new_status = ApprovalStatus.APPROVED
    elif action == "reject":
        new_status = ApprovalStatus.REJECTED
    else:
        new_status = ApprovalStatus.MODIFIED

    await db.execute(
        "UPDATE approvals SET status = ?, resolved_at = ? WHERE id = ?",
        (new_status.value, now.isoformat(), approval_id),
    )
    await db.commit()

    approval = _resolve_approval(action, rowd, comment, modified_params)
    logger.info("Resolved approval %s → %s", approval_id, new_status.value)
    return approval
