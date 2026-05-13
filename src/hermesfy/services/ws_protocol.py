"""WebSocket protocol envelope, event type enumeration, and serialization.

The WS protocol layer wraps every :class:`DomainEvent` inside a
:class:`WSEventEnvelope` that carries routing metadata (session, workflow,
turn, run) and a monotonic sequence number so clients can detect gaps and
request replay via the ``after_seq`` query parameter.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hermesfy.services.event_bus import DomainEvent


# ── Event type enumeration ────────────────────────────────────────────────────

class EventType(str, Enum):
    """Well-known WebSocket event types for Hermesfy V5.

    Every event sent over the WebSocket MUST use one of these types so that
    the frontend can route payloads to the correct React component / store.
    """

    # Connection lifecycle
    CONNECTED = "connected"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

    # Chat
    CHAT_TEXT_DELTA = "chat.text_delta"
    CHAT_THINKING_DELTA = "chat.thinking_delta"
    CHAT_ACTION = "chat.action"
    CHAT_DONE = "chat.done"

    # DAG
    DAG_SNAPSHOT = "dag.snapshot"
    DAG_PATCH = "dag.patch"
    DAG_CONFLICT = "dag.conflict"

    # Execution
    EXECUTION_STARTED = "execution.started"
    EXECUTION_NODE_STARTED = "execution.node.started"
    EXECUTION_NODE_PROGRESS = "execution.node.progress"
    EXECUTION_NODE_COMPLETED = "execution.node.completed"
    EXECUTION_NODE_FAILED = "execution.node.failed"
    EXECUTION_COMPLETED = "execution.completed"

    # Approvals
    APPROVAL_REQUEST = "approval.request"
    APPROVAL_RESOLVED = "approval.resolved"

    # Artifacts & Learning
    ARTIFACT_CREATED = "artifact.created"
    LEARNING_SAVED = "learning.saved"


# ── WS envelope ────────────────────────────────────────────────────────────────

class WSEventEnvelope(BaseModel):
    """Standard envelope for every frame sent over the Hermesfy V5 WebSocket.

    This matches the TypeScript type defined in the SDD:

    .. code-block:: typescript

        type WSEventEnvelope<T> = {
            id: string;
            version: 1;
            type: string;
            seq: number;
            timestamp: string;
            sessionId?: string;
            workflowId?: string;
            turnId?: string;
            runId?: string;
            payload: T;
        };

    Attributes:
        id: Unique event identifier.
        version: Envelope schema version (always 1 for V5).
        type: Dot-separated event type — see :class:`EventType`.
        seq: Monotonic sequence number (per-topic, client-side ordering).
        timestamp: ISO-8601 UTC timestamp.
        session_id: Optional chat session identifier.
        workflow_id: Optional workflow identifier.
        turn_id: Optional chat turn identifier.
        run_id: Optional execution run identifier.
        payload: The event payload (arbitrary JSON-serializable data).
    """

    model_config = ConfigDict(
        frozen=False,
        populate_by_name=True,
        json_schema_serialization_defaults_required=True,
    )

    id: str
    version: int = 1
    type: str
    seq: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    workflow_id: Optional[str] = Field(default=None, alias="workflowId")
    turn_id: Optional[str] = Field(default=None, alias="turnId")
    run_id: Optional[str] = Field(default=None, alias="runId")
    payload: Any = None

    def to_json(self) -> str:
        """Serialize the envelope to a JSON string.

        Uses ``alias`` field names (camelCase) to match the frontend contract.
        """
        return self.model_dump_json(by_alias=True, exclude_none=True)

    @classmethod
    def from_json(cls, data: str | bytes) -> WSEventEnvelope:
        """Deserialize a JSON string into a :class:`WSEventEnvelope`.

        Raises:
            ValidationError: If the JSON is malformed or missing required fields.
        """
        raw: dict[str, Any] = json.loads(data) if isinstance(data, (str, bytes)) else {}
        return cls.model_validate(raw)


# ── Factory helpers ────────────────────────────────────────────────────────────

def create_envelope(
    domain_event: DomainEvent,
    *,
    seq: Optional[int] = None,
) -> WSEventEnvelope:
    """Create a :class:`WSEventEnvelope` from a :class:`DomainEvent`.

    The envelope inherits all routing fields (session_id, workflow_id,
    turn_id, run_id) and the event id / type / timestamp from the domain
    event.  The *seq* field may be overridden (e.g. when the EventBus
    stamps a per-topic sequence number).
    """
    return WSEventEnvelope(
        id=domain_event.id,
        type=domain_event.type,
        seq=seq if seq is not None else domain_event.seq,
        timestamp=domain_event.timestamp,
        session_id=domain_event.session_id,
        workflow_id=domain_event.workflow_id,
        turn_id=domain_event.turn_id,
        run_id=domain_event.run_id,
        payload=domain_event.payload,
    )


def parse_envelope(data: str | bytes) -> WSEventEnvelope:
    """Parse a raw JSON frame into a :class:`WSEventEnvelope` and validate.

    This is the entry-point used by WebSocket route handlers.  It validates
    that ``type`` is a known :class:`EventType` value.

    Raises:
        ValidationError: If the JSON is malformed or missing required fields.
        ValueError: If the event type is not a recognized :class:`EventType`.
    """
    envelope = WSEventEnvelope.from_json(data)

    # Validate the event type against the well-known set
    try:
        EventType(envelope.type)
    except ValueError:
        raise ValueError(
            f"Unknown event type {envelope.type!r}. Must be one of "
            f"{[e.value for e in EventType]}"
        ) from None

    return envelope


def build_connected_envelope(
    last_seq: int,
    *,
    session_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> WSEventEnvelope:
    """Build the ``connected`` envelope sent on successful WS handshake.

    Clients use ``lastSeq`` to request replay from ``lastSeq + 1`` via the
    ``after_seq`` query parameter on reconnect.
    """
    return WSEventEnvelope(
        id=f"evt_connected_{int(datetime.now(timezone.utc).timestamp())}",
        type=EventType.CONNECTED.value,
        seq=0,  # special — not a topic sequence
        payload={"lastSeq": last_seq},
        session_id=session_id,
        workflow_id=workflow_id,
    )


def build_heartbeat_envelope(
    *,
    session_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> WSEventEnvelope:
    """Build a ``heartbeat`` envelope for keep-alive pings."""
    return WSEventEnvelope(
        id=f"evt_hb_{int(datetime.now(timezone.utc).timestamp())}",
        type=EventType.HEARTBEAT.value,
        payload={"ts": datetime.now(timezone.utc).isoformat()},
        session_id=session_id,
        workflow_id=workflow_id,
    )


def build_error_envelope(
    message: str,
    *,
    code: str = "INTERNAL_ERROR",
    details: Any = None,
    session_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> WSEventEnvelope:
    """Build an ``error`` envelope for protocol- or application-level errors."""
    return WSEventEnvelope(
        id=f"evt_err_{int(datetime.now(timezone.utc).timestamp())}",
        type=EventType.ERROR.value,
        payload={
            "code": code,
            "message": message,
            "details": details,
        },
        session_id=session_id,
        workflow_id=workflow_id,
    )
