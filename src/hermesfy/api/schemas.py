"""Pydantic v2 schemas for the Hermesfy V5 domain model.

Covers: NodeV2, EdgeV2, WorkflowV2, ChatSession, ChatTurn, ExecutionRun,
Approval, and WSEventEnvelope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ── ID helpers ────────────────────────────────────────────────────────────────


def _new_id(prefix: str) -> str:
    """Generate a short unique ID with a prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


# ── Enums ─────────────────────────────────────────────────────────────────────


class RunStatus(str, Enum):
    QUEUED = "queued"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    STALE = "stale"


class EdgeKind(str, Enum):
    DATA = "data"
    IMAGE = "image"
    MASK = "mask"
    CONTROL = "control"
    REFERENCE = "reference"


class TurnStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Position ──────────────────────────────────────────────────────────────────


class Position(BaseModel):
    """2D canvas position."""

    x: float = 0.0
    y: float = 0.0


# ── Node V2 ───────────────────────────────────────────────────────────────────


class NodeV2(BaseModel):
    """A node in a V2 workflow graph with port support."""

    id: str = Field(default_factory=lambda: _new_id("node"))
    type: str = Field(..., description="Node type: text_prompt, image_gen, etc.")
    config: dict[str, Any] = Field(default_factory=dict)
    position: Position = Field(default_factory=Position)
    ui: dict[str, Any] = Field(default_factory=dict)
    disabled: bool = False
    schema_version: int = 1

    @field_validator("type")
    @classmethod
    def type_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("node type must not be empty")
        return v.strip()


# ── Edge V2 ───────────────────────────────────────────────────────────────────


class EdgeV2(BaseModel):
    """A directed edge in a V2 workflow graph with port support."""

    id: str = Field(default_factory=lambda: _new_id("edge"))
    source: str
    target: str
    source_port: Optional[str] = None
    target_port: Optional[str] = None
    kind: EdgeKind = EdgeKind.DATA


# ── Workflow V2 ───────────────────────────────────────────────────────────────


class WorkflowV2(BaseModel):
    """A complete V2 workflow definition with versioning."""

    id: str = Field(default_factory=lambda: _new_id("wf"))
    name: str = "Untitled Workflow"
    version: int = 1
    nodes: list[NodeV2] = Field(default_factory=list)
    edges: list[EdgeV2] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None


class WorkflowCreate(BaseModel):
    """Payload for creating a new workflow."""

    name: str = "Untitled Workflow"
    nodes: list[NodeV2] = Field(default_factory=list)
    edges: list[EdgeV2] = Field(default_factory=list)
    session_id: Optional[str] = None


class WorkflowUpdate(BaseModel):
    """Payload for updating a workflow (partial update)."""

    expected_version: int
    name: Optional[str] = None
    nodes: Optional[list[NodeV2]] = None
    edges: Optional[list[EdgeV2]] = None
    metadata: Optional[dict[str, Any]] = None


# ── Chat Session ──────────────────────────────────────────────────────────────


class ChatSession(BaseModel):
    """A chat session tied to a workflow."""

    id: str = Field(default_factory=lambda: _new_id("sess"))
    workflow_id: Optional[str] = None
    title: str = "New Chat"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSessionCreate(BaseModel):
    """Payload for creating a chat session."""

    workflow_id: Optional[str] = None
    title: str = "New Chat"


# ── Chat Turn ─────────────────────────────────────────────────────────────────


class ChatTurn(BaseModel):
    """A single turn (user message + agent response) in a chat session."""

    id: str = Field(default_factory=lambda: _new_id("turn"))
    session_id: str
    user_message: str
    agent_response: Optional[str] = None
    status: TurnStatus = TurnStatus.PENDING
    actions: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class ChatTurnCreate(BaseModel):
    """Payload for creating a chat turn (sending a message)."""

    message: str = Field(..., min_length=1, description="User message to the agent")


# ── Execution Run ─────────────────────────────────────────────────────────────


class ExecutionRun(BaseModel):
    """An execution run of a workflow."""

    id: str = Field(default_factory=lambda: _new_id("run"))
    workflow_id: str
    workflow_version: int
    status: RunStatus = RunStatus.QUEUED
    budget_limit_usd: float = 0.07
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    session_id: Optional[str] = None


class ExecutionRunCreate(BaseModel):
    """Payload for creating an execution run."""

    budget_limit_usd: float = 0.07
    options: dict[str, Any] = Field(default_factory=dict)


# ── Approval ──────────────────────────────────────────────────────────────────


class Approval(BaseModel):
    """An approval request tied to a run or action."""

    id: str = Field(default_factory=lambda: _new_id("appr"))
    run_id: Optional[str] = None
    workflow_id: str
    workflow_version: int
    status: ApprovalStatus = ApprovalStatus.PENDING
    title: str = "Approval Required"
    description: str = ""
    cost_breakdown: Optional[dict[str, Any]] = None
    risk_level: str = "low"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    session_id: Optional[str] = None


class ApprovalAction(BaseModel):
    """Payload for resolving an approval."""

    action: str = Field(..., pattern="^(approve|reject|modify)$")
    comment: Optional[str] = None
    modified_params: Optional[dict[str, Any]] = None


# ── WebSocket Event Envelope ──────────────────────────────────────────────────


class WSEventEnvelope(BaseModel):
    """Standard envelope for all WebSocket messages."""

    id: str = Field(default_factory=lambda: _new_id("evt"))
    version: int = 1
    type: str = Field(..., description="Event type, e.g. chat.text_delta, dag.snapshot")
    seq: int = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    turn_id: Optional[str] = None
    run_id: Optional[str] = None
    payload: Any = None
