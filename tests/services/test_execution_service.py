"""Tests for ExecutionService run lifecycle."""

import pytest
from hermesfy.api.settings import Settings
from hermesfy.api.schemas import RunStatus
from hermesfy.services.event_bus import EventBus
from hermesfy.services.execution_service import ExecutionService


@pytest.fixture
def settings():
    return Settings(data_dir="/tmp/hermesfy_test_exec", default_budget_usd=0.10)


@pytest.fixture
def event_bus():
    return EventBus(ring_size=32, max_queue=16)


@pytest.fixture
def service(settings, event_bus):
    return ExecutionService(settings, event_bus)


@pytest.mark.asyncio
async def test_create_run_queued(service):
    """Create a run with cost under budget gets status QUEUED."""
    run = await service.create_run(
        workflow_id="wf_test1",
        workflow_version=1,
        budget_limit_usd=0.10,
        estimated_cost_usd=0.05,
    )
    assert run.id.startswith("run_")
    assert run.status == RunStatus.QUEUED
    assert run.workflow_id == "wf_test1"
    assert run.workflow_version == 1
    assert run.budget_limit_usd == 0.10
    assert run.estimated_cost_usd == 0.05


@pytest.mark.asyncio
async def test_create_run_awaiting_approval(service):
    """Create a run with cost exceeding budget gets AWAITING_APPROVAL."""
    run = await service.create_run(
        workflow_id="wf_test2",
        workflow_version=1,
        budget_limit_usd=0.05,
        estimated_cost_usd=0.12,
    )
    assert run.status == RunStatus.AWAITING_APPROVAL


@pytest.mark.asyncio
async def test_get_run(service):
    """Can retrieve a run after creation."""
    created = await service.create_run("wf_test3", 1)
    retrieved = await service.get_run(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id


@pytest.mark.asyncio
async def test_start_run(service):
    """A queued run can be started."""
    run = await service.create_run("wf_test4", 1)
    ok = await service.start_run(run.id)
    assert ok is True
    updated = await service.get_run(run.id)
    assert updated.status == RunStatus.RUNNING


@pytest.mark.asyncio
async def test_start_awaiting_approval_blocked(service):
    """A run awaiting approval cannot be started directly."""
    run = await service.create_run("wf_test5", 1, budget_limit_usd=0.05, estimated_cost_usd=0.15)
    ok = await service.start_run(run.id)
    assert ok is False


@pytest.mark.asyncio
async def test_complete_run(service):
    """A run can be completed."""
    run = await service.create_run("wf_test6", 1)
    await service.start_run(run.id)
    ok = await service.complete_run(run.id, actual_cost_usd=0.03)
    assert ok is True
    updated = await service.get_run(run.id)
    assert updated.status == RunStatus.SUCCEEDED
    assert updated.actual_cost_usd == 0.03


@pytest.mark.asyncio
async def test_fail_run(service):
    """A run can be marked as failed."""
    run = await service.create_run("wf_test7", 1)
    ok = await service.fail_run(run.id, error="provider timeout")
    assert ok is True
    updated = await service.get_run(run.id)
    assert updated.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_cancel_run(service):
    """A queued run can be cancelled."""
    run = await service.create_run("wf_test8", 1)
    ok = await service.cancel_run(run.id)
    assert ok is True
    updated = await service.get_run(run.id)
    assert updated.status == RunStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_nonexistent_run(service):
    """Cancelling a non-existent run returns False."""
    ok = await service.cancel_run("run_nonexistent")
    assert ok is False


@pytest.mark.asyncio
async def test_node_events_emit(service):
    """Node event methods don't crash."""
    await service.emit_node_started("run_1", "node_1", "wf_1")
    await service.emit_node_completed("run_1", "node_1", "wf_1", duration_ms=1500, cost_usd=0.01)
    await service.emit_node_failed("run_1", "node_2", "wf_1", error="timeout")
    await service.emit_node_progress("run_1", "node_3", "wf_1", phase="generating")
    # No assertion needed — if it doesn't crash, it works
