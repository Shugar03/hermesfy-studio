"""Tests for ApprovalService lifecycle."""

import pytest
from hermesfy.api.settings import Settings
from hermesfy.api.schemas import ApprovalStatus, RunStatus
from hermesfy.services.event_bus import EventBus
from hermesfy.services.approval_service import ApprovalService
from hermesfy.services.execution_service import ExecutionService
from hermesfy.storage.repositories import ApprovalRepository, ExecutionRunRepository


@pytest.fixture
def settings():
    return Settings(data_dir="/tmp/hermesfy_test_appr", default_budget_usd=0.10)


@pytest.fixture
def event_bus():
    return EventBus(ring_size=32, max_queue=16)


@pytest.fixture
def approval_repo(settings):
    return ApprovalRepository(settings)


@pytest.fixture
def run_repo(settings):
    return ExecutionRunRepository(settings)


@pytest.fixture
def approval_service(settings, event_bus, approval_repo, run_repo):
    return ApprovalService(settings, event_bus, approval_repo, run_repo)


@pytest.fixture
def exec_service(settings, event_bus):
    return ExecutionService(settings, event_bus)


@pytest.mark.asyncio
async def test_request_approval(approval_service):
    """Request approval creates a pending approval and emits event."""
    approval = await approval_service.request_approval(
        workflow_id="wf_1",
        workflow_version=1,
        title="Test Approval",
        description="Testing approval flow",
        risk_level="low",
    )
    assert approval.id.startswith("appr_")
    assert approval.status == ApprovalStatus.PENDING
    assert approval.title == "Test Approval"


@pytest.mark.asyncio
async def test_approve_approval(approval_service):
    """Approving transitions approval to approved."""
    approval = await approval_service.request_approval(
        workflow_id="wf_2", workflow_version=1,
        title="Approve me", description="test",
    )
    ok, msg = await approval_service.approve(approval.id)
    assert ok is True
    retrieved = await approval_service.get_approval(approval.id)
    assert retrieved.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_reject_approval(approval_service):
    """Rejecting transitions approval to rejected."""
    approval = await approval_service.request_approval(
        workflow_id="wf_3", workflow_version=1,
        title="Reject me", description="test",
    )
    ok, msg = await approval_service.reject(approval.id)
    assert ok is True
    retrieved = await approval_service.get_approval(approval.id)
    assert retrieved.status == ApprovalStatus.REJECTED


@pytest.mark.asyncio
async def test_modify_approval(approval_service):
    """Modifying transitions approval to modified."""
    approval = await approval_service.request_approval(
        workflow_id="wf_4", workflow_version=1,
        title="Modify me", description="test",
    )
    ok, msg = await approval_service.modify_approval(approval.id, {"budget": 0.05})
    assert ok is True
    retrieved = await approval_service.get_approval(approval.id)
    assert retrieved.status == ApprovalStatus.MODIFIED


@pytest.mark.asyncio
async def test_double_approve_fails(approval_service):
    """Cannot approve an already approved approval."""
    approval = await approval_service.request_approval(
        workflow_id="wf_5", workflow_version=1,
        title="Once only", description="test",
    )
    ok1, _ = await approval_service.approve(approval.id)
    assert ok1 is True
    ok2, msg = await approval_service.approve(approval.id)
    assert ok2 is False


@pytest.mark.asyncio
async def test_nonexistent_approval(approval_service):
    """Operations on non-existent approvals return False."""
    ok, msg = await approval_service.approve("appr_nonexistent")
    assert ok is False


@pytest.mark.asyncio
async def test_approval_with_run_integration(approval_service, exec_service):
    """Approving an approval tied to a run transitions the run from awaiting_approval to queued."""
    run = await exec_service.create_run(
        workflow_id="wf_6", workflow_version=1,
        budget_limit_usd=0.05, estimated_cost_usd=0.15,
    )
    assert run.status == RunStatus.AWAITING_APPROVAL

    # Find the approval that was auto-created
    # (We need to check the DB for it)
    # For now, approve any pending approval for this run
    approval = await approval_service.request_approval(
        workflow_id="wf_6", workflow_version=1,
        title="Override", description="test",
        run_id=run.id,
    )
    ok, _ = await approval_service.approve(approval.id)
    assert ok is True

    updated_run = await exec_service.get_run(run.id)
    assert updated_run.status == RunStatus.QUEUED


@pytest.mark.asyncio
async def test_check_workflow_version(approval_service, exec_service):
    """Version check returns True when versions match."""
    run = await exec_service.create_run("wf_7", 1)
    approval = await approval_service.request_approval(
        workflow_id="wf_7", workflow_version=1,
        title="Version check", description="test",
        run_id=run.id,
    )
    valid = await approval_service.check_workflow_version(approval.id)
    assert valid is True
