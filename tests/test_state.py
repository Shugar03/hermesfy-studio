"""Unit tests for DAG state tracking: NodeState, NodeRun, transition validation."""

import pytest
from datetime import datetime
from hermesfy.dag.state import NodeState, NodeRun, validate_transition, INVALID_TRANSITION


class TestNodeState:
    """Tests for the NodeState enum."""

    def test_enum_values(self):
        """NodeState MUST contain all six states."""
        assert NodeState.PENDING.value == "pending"
        assert NodeState.RUNNING.value == "running"
        assert NodeState.COMPLETED.value == "completed"
        assert NodeState.FAILED.value == "failed"
        assert NodeState.RETRYING.value == "retrying"
        assert NodeState.QUALITY_EXHAUSTED.value == "quality_exhausted"

    def test_enum_from_string(self):
        """NodeState can be constructed from a string value."""
        assert NodeState("pending") == NodeState.PENDING
        assert NodeState("running") == NodeState.RUNNING
        assert NodeState("completed") == NodeState.COMPLETED
        assert NodeState("failed") == NodeState.FAILED
        assert NodeState("retrying") == NodeState.RETRYING
        assert NodeState("quality_exhausted") == NodeState.QUALITY_EXHAUSTED

    def test_invalid_state_raises(self):
        """Invalid state string raises ValueError."""
        with pytest.raises(ValueError):
            NodeState("invalid")

    def test_is_terminal(self):
        """States COMPLETED and QUALITY_EXHAUSTED are terminal."""
        assert NodeState.COMPLETED.is_terminal() is True
        assert NodeState.QUALITY_EXHAUSTED.is_terminal() is True

    def test_pending_is_not_terminal(self):
        """PENDING is not a terminal state."""
        assert NodeState.PENDING.is_terminal() is False

    def test_running_is_not_terminal(self):
        """RUNNING is not a terminal state."""
        assert NodeState.RUNNING.is_terminal() is False

    def test_failed_is_not_terminal(self):
        """FAILED is not terminal because it can lead to RETRYING."""
        assert NodeState.FAILED.is_terminal() is False

    def test_retrying_is_not_terminal(self):
        """RETRYING is not terminal because it transitions to RUNNING."""
        assert NodeState.RETRYING.is_terminal() is False

    def test_is_active(self):
        """States RUNNING and RETRYING are active."""
        assert NodeState.RUNNING.is_active() is True
        assert NodeState.RETRYING.is_active() is True

    def test_pending_is_not_active(self):
        """PENDING is not an active state."""
        assert NodeState.PENDING.is_active() is False

    def test_terminal_is_not_active(self):
        """Terminal states are not active."""
        assert NodeState.COMPLETED.is_active() is False
        assert NodeState.QUALITY_EXHAUSTED.is_active() is False


class TestNodeRun:
    """Tests for the NodeRun dataclass."""

    def test_node_run_creation(self):
        """NodeRun records the attempt, state, and timestamp."""
        ts = datetime.now()
        run = NodeRun(attempt=1, state=NodeState.PENDING, timestamp=ts)
        assert run.attempt == 1
        assert run.state == NodeState.PENDING
        assert run.timestamp == ts
        assert run.output is None
        assert run.error is None

    def test_node_run_with_output(self):
        """NodeRun can store output data."""
        run = NodeRun(
            attempt=1,
            state=NodeState.COMPLETED,
            output={"url": "https://example.com/image.png"},
            timestamp=datetime.now(),
        )
        assert run.output == {"url": "https://example.com/image.png"}
        assert run.error is None

    def test_node_run_with_error(self):
        """NodeRun can store error information."""
        run = NodeRun(
            attempt=1,
            state=NodeState.FAILED,
            error="Rate limit exceeded",
            timestamp=datetime.now(),
        )
        assert run.error == "Rate limit exceeded"
        assert run.output is None

    def test_node_run_default_timestamp(self):
        """NodeRun auto-generates a timestamp if not provided."""
        run = NodeRun(attempt=0, state=NodeState.PENDING)
        assert isinstance(run.timestamp, datetime)

    def test_node_run_equality(self):
        """Two NodeRuns with identical fields are equal."""
        ts = datetime(2026, 1, 15, 12, 0, 0)
        r1 = NodeRun(attempt=1, state=NodeState.COMPLETED, output={"a": 1}, timestamp=ts)
        r2 = NodeRun(attempt=1, state=NodeState.COMPLETED, output={"a": 1}, timestamp=ts)
        assert r1 == r2


class TestValidateTransition:
    """Tests for state transition validation."""

    # Valid transitions (from design doc):
    # PENDING → RUNNING
    # RUNNING → COMPLETED
    # RUNNING → FAILED
    # FAILED → RETRYING
    # RETRYING → RUNNING
    # RETRYING → QUALITY_EXHAUSTED

    def test_pending_to_running_valid(self):
        """PENDING → RUNNING is a valid transition."""
        validate_transition(NodeState.PENDING, NodeState.RUNNING)

    def test_running_to_completed_valid(self):
        """RUNNING → COMPLETED is a valid transition."""
        validate_transition(NodeState.RUNNING, NodeState.COMPLETED)

    def test_running_to_failed_valid(self):
        """RUNNING → FAILED is a valid transition."""
        validate_transition(NodeState.RUNNING, NodeState.FAILED)

    def test_failed_to_retrying_valid(self):
        """FAILED → RETRYING is a valid transition."""
        validate_transition(NodeState.FAILED, NodeState.RETRYING)

    def test_retrying_to_running_valid(self):
        """RETRYING → RUNNING is a valid transition."""
        validate_transition(NodeState.RETRYING, NodeState.RUNNING)

    def test_retrying_to_quality_exhausted_valid(self):
        """RETRYING → QUALITY_EXHAUSTED is a valid transition."""
        validate_transition(NodeState.RETRYING, NodeState.QUALITY_EXHAUSTED)

    def test_same_state_is_valid(self):
        """Transition to same state (no-op) is valid."""
        validate_transition(NodeState.PENDING, NodeState.PENDING)

    def test_pending_to_completed_invalid(self):
        """PENDING → COMPLETED is invalid (must go through RUNNING)."""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(NodeState.PENDING, NodeState.COMPLETED)
        assert INVALID_TRANSITION in str(exc_info.value)

    def test_completed_to_running_invalid(self):
        """COMPLETED → RUNNING is invalid (terminal state)."""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(NodeState.COMPLETED, NodeState.RUNNING)
        assert INVALID_TRANSITION in str(exc_info.value)

    def test_completed_to_failed_invalid(self):
        """COMPLETED → FAILED is invalid (terminal state)."""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(NodeState.COMPLETED, NodeState.FAILED)
        assert INVALID_TRANSITION in str(exc_info.value)

    def test_quality_exhausted_to_retrying_invalid(self):
        """QUALITY_EXHAUSTED → RETRYING is invalid (terminal state)."""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(NodeState.QUALITY_EXHAUSTED, NodeState.RETRYING)
        assert INVALID_TRANSITION in str(exc_info.value)

    def test_running_to_retrying_invalid(self):
        """RUNNING → RETRYING is invalid (must go through FAILED first)."""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(NodeState.RUNNING, NodeState.RETRYING)
        assert INVALID_TRANSITION in str(exc_info.value)
