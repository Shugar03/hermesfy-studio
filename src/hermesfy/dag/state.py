"""Node state machine: NodeState enum, NodeRun dataclass, transition validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


INVALID_TRANSITION = "INVALID_TRANSITION"


class NodeState(str, Enum):
    """The lifecycle state of a DAG node execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    QUALITY_EXHAUSTED = "quality_exhausted"

    def is_terminal(self) -> bool:
        """Return True if this is a terminal state (no further transitions)."""
        return self in (NodeState.COMPLETED, NodeState.QUALITY_EXHAUSTED)

    def is_active(self) -> bool:
        """Return True if the node is actively executing."""
        return self in (NodeState.RUNNING, NodeState.RETRYING)


# Valid state transitions.
# Key: current state → set of allowed next states.
_VALID_TRANSITIONS: dict[NodeState, set[NodeState]] = {
    NodeState.PENDING: {NodeState.PENDING, NodeState.RUNNING},
    NodeState.RUNNING: {NodeState.RUNNING, NodeState.COMPLETED, NodeState.FAILED},
    NodeState.FAILED: {NodeState.FAILED, NodeState.RETRYING},
    NodeState.RETRYING: {NodeState.RETRYING, NodeState.RUNNING, NodeState.QUALITY_EXHAUSTED},
    NodeState.COMPLETED: {NodeState.COMPLETED},
    NodeState.QUALITY_EXHAUSTED: {NodeState.QUALITY_EXHAUSTED},
}


@dataclass
class NodeRun:
    """Records a single execution attempt of a node.

    Attributes:
        attempt: The attempt number (0-based for initial, 1+ for retries).
        state: The resulting state after this attempt.
        output: Optional output data produced by the node.
        error: Optional error message if the attempt failed.
        timestamp: When this run record was created (UTC).
    """

    attempt: int
    state: NodeState
    output: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NodeEvent:
    """An event emitted during workflow execution.

    Attributes:
        node_id: The node this event pertains to.
        event_type: Type of event (node_start, node_complete, node_error, etc.).
        data: Optional payload (e.g., resolved config, output, error message).
    """

    node_id: str
    event_type: str
    data: Any = None


def validate_transition(from_state: NodeState, to_state: NodeState) -> None:
    """Validate that a state transition is allowed.

    Args:
        from_state: The current node state.
        to_state: The proposed next node state.

    Raises:
        ValueError: If the transition is not allowed, with INVALID_TRANSITION prefix.
    """
    allowed = _VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise ValueError(
            f"{INVALID_TRANSITION}: Cannot transition from '{from_state.value}' "
            f"to '{to_state.value}'"
        )
