"""Tests for WebSocket protocol envelope serialization and event type validation."""

import json

import pytest
from pydantic import ValidationError

from hermesfy.services.event_bus import DomainEvent
from hermesfy.services.ws_protocol import (
    EventType,
    WSEventEnvelope,
    build_connected_envelope,
    build_error_envelope,
    build_heartbeat_envelope,
    create_envelope,
    parse_envelope,
)


# ── WSEventEnvelope serialization ──────────────────────────────────────────────

def test_envelope_to_json_camelcase():
    """to_json() should use camelCase alias field names."""
    envelope = WSEventEnvelope(
        id="evt_001",
        type="chat.text_delta",
        seq=1,
        timestamp="2026-05-13T12:00:00Z",
        session_id="sess_01",
        workflow_id="wf_01",
        payload={"text": "Hello"},
    )

    raw = envelope.to_json()
    data = json.loads(raw)

    assert data["id"] == "evt_001"
    assert data["type"] == "chat.text_delta"
    assert data["seq"] == 1
    assert data["sessionId"] == "sess_01"
    assert data["workflowId"] == "wf_01"
    assert data["payload"] == {"text": "Hello"}
    # session_id / workflow_id should NOT appear (aliased to camelCase)
    assert "session_id" not in data
    assert "workflow_id" not in data


def test_envelope_from_json_camelcase():
    """from_json() should parse camelCase field names."""
    raw = json.dumps({
        "id": "evt_001",
        "version": 1,
        "type": "chat.text_delta",
        "seq": 5,
        "timestamp": "2026-05-13T12:00:00Z",
        "sessionId": "sess_01",
        "workflowId": "wf_01",
        "runId": "run_01",
        "payload": {"text": "Hello"},
    })

    envelope = WSEventEnvelope.from_json(raw)

    assert envelope.id == "evt_001"
    assert envelope.type == "chat.text_delta"
    assert envelope.seq == 5
    assert envelope.session_id == "sess_01"
    assert envelope.workflow_id == "wf_01"
    assert envelope.run_id == "run_01"
    assert envelope.payload == {"text": "Hello"}


def test_envelope_none_fields_excluded():
    """Fields with None should be excluded from JSON output."""
    envelope = WSEventEnvelope(
        id="evt_001",
        type="chat.text_delta",
        payload={"text": "Hello"},
    )

    raw = envelope.to_json()
    data = json.loads(raw)

    assert "sessionId" not in data
    assert "workflowId" not in data
    assert "runId" not in data
    assert "turnId" not in data


def test_envelope_default_values():
    """Envelope should have sensible defaults for version and timestamp."""
    envelope = WSEventEnvelope(id="evt_001", type="connected")
    assert envelope.version == 1
    assert envelope.timestamp
    assert envelope.seq == 0


# ── create_envelope ────────────────────────────────────────────────────────────

def test_create_envelope_from_domain_event():
    """create_envelope should copy all routing fields from DomainEvent."""
    domain = DomainEvent(
        type="execution.node.completed",
        session_id="sess_01",
        workflow_id="wf_01",
        run_id="run_01",
        payload={"node_id": "n1"},
    )

    envelope = create_envelope(domain)

    assert envelope.id == domain.id
    assert envelope.type == domain.type
    assert envelope.session_id == "sess_01"
    assert envelope.workflow_id == "wf_01"
    assert envelope.run_id == "run_01"
    assert envelope.payload == {"node_id": "n1"}
    assert envelope.seq == 0  # DomainEvent.seq is 0 by default


def test_create_envelope_override_seq():
    """create_envelope should allow overriding the seq number."""
    domain = DomainEvent(type="test.event")
    envelope = create_envelope(domain, seq=42)
    assert envelope.seq == 42


# ── parse_envelope ─────────────────────────────────────────────────────────────

def test_parse_envelope_valid_event_type():
    """parse_envelope should accept well-known event types."""
    raw = json.dumps({
        "id": "evt_001",
        "type": "chat.text_delta",
        "payload": {"text": "Hello"},
    })

    envelope = parse_envelope(raw)
    assert envelope.type == "chat.text_delta"


def test_parse_envelope_unknown_event_type():
    """parse_envelope should reject unknown event types."""
    raw = json.dumps({
        "id": "evt_001",
        "type": "unknown.weird.event",
        "payload": {},
    })

    with pytest.raises(ValueError, match="Unknown event type"):
        parse_envelope(raw)


def test_parse_envelope_missing_required_fields():
    """parse_envelope should reject missing required fields like id and type."""
    raw = json.dumps({"payload": {}})

    with pytest.raises(ValidationError):
        parse_envelope(raw)


def test_parse_envelope_from_bytes():
    """parse_envelope should handle bytes input."""
    raw = json.dumps({
        "id": "evt_001",
        "type": "connected",
        "payload": {},
    }).encode()

    envelope = parse_envelope(raw)
    assert envelope.type == "connected"


# ── Event type validation ──────────────────────────────────────────────────────

def test_event_type_enum_all_values():
    """All EventType values should be strings matching the SDD spec."""
    expected = {
        "connected",
        "heartbeat",
        "error",
        "chat.text_delta",
        "chat.thinking_delta",
        "chat.action",
        "chat.done",
        "dag.snapshot",
        "dag.patch",
        "dag.conflict",
        "execution.started",
        "execution.node.started",
        "execution.node.progress",
        "execution.node.completed",
        "execution.node.failed",
        "execution.completed",
        "approval.request",
        "approval.resolved",
        "artifact.created",
        "learning.saved",
    }
    actual = {e.value for e in EventType}
    assert actual == expected


def test_event_type_from_string():
    """EventType should be constructable from strings."""
    assert EventType("chat.text_delta") == EventType.CHAT_TEXT_DELTA
    assert EventType("execution.node.started") == EventType.EXECUTION_NODE_STARTED


def test_event_type_invalid_string():
    """EventType should raise ValueError for unknown strings."""
    with pytest.raises(ValueError):
        EventType("bogus.event")


# ── Builders ────────────────────────────────────────────────────────────────────

def test_build_connected_envelope():
    """build_connected_envelope should include lastSeq in payload."""
    envelope = build_connected_envelope(
        last_seq=42,
        session_id="sess_01",
        workflow_id="wf_01",
    )

    assert envelope.type == "connected"
    assert envelope.payload == {"lastSeq": 42}
    assert envelope.session_id == "sess_01"
    assert envelope.workflow_id == "wf_01"
    assert envelope.id.startswith("evt_connected_")


def test_build_heartbeat_envelope():
    """build_heartbeat_envelope should include a timestamp in payload."""
    envelope = build_heartbeat_envelope(session_id="sess_01")

    assert envelope.type == "heartbeat"
    assert "ts" in envelope.payload
    assert envelope.id.startswith("evt_hb_")
    assert envelope.session_id == "sess_01"


def test_build_error_envelope():
    """build_error_envelope should include code, message, and optional details."""
    envelope = build_error_envelope(
        message="Something went wrong",
        code="INVALID_DAG",
        details={"node": "n1", "reason": "missing input"},
        session_id="sess_01",
    )

    assert envelope.type == "error"
    assert envelope.payload["code"] == "INVALID_DAG"
    assert envelope.payload["message"] == "Something went wrong"
    assert envelope.payload["details"] == {"node": "n1", "reason": "missing input"}
    assert envelope.id.startswith("evt_err_")


def test_build_error_envelope_defaults():
    """build_error_envelope should default to INTERNAL_ERROR code."""
    envelope = build_error_envelope(message="Oops")
    assert envelope.payload["code"] == "INTERNAL_ERROR"
    assert envelope.payload["details"] is None


# ── Round-trip ─────────────────────────────────────────────────────────────────

def test_envelope_round_trip():
    """An envelope should survive to_json → from_json round-trip unchanged."""
    original = WSEventEnvelope(
        id="evt_001",
        type="dag.patch",
        seq=7,
        timestamp="2026-05-13T12:00:00Z",
        session_id="sess_01",
        workflow_id="wf_01",
        run_id="run_01",
        turn_id="turn_01",
        payload={"nodes": [{"id": "n1"}]},
    )

    # Serialize
    raw = original.to_json()
    # Deserialize
    restored = WSEventEnvelope.from_json(raw)

    assert restored.id == original.id
    assert restored.type == original.type
    assert restored.seq == original.seq
    assert restored.session_id == original.session_id
    assert restored.workflow_id == original.workflow_id
    assert restored.run_id == original.run_id
    assert restored.turn_id == original.turn_id
    assert restored.payload == original.payload


# ── DomainEvent → Envelope → JSON flow ─────────────────────────────────────────

def test_full_event_to_envelope_flow():
    """Simulate the full DomainEvent → WSEventEnvelope → JSON → parse flow."""
    # 1. Create a domain event (as the executor would)
    domain = DomainEvent(
        type="execution.node.completed",
        session_id="sess_01",
        workflow_id="wf_01",
        run_id="run_01",
        payload={"node_id": "gen-1", "output_url": "https://fal.ai/output.png"},
    )

    # 2. Wrap in envelope (as the WS handler would)
    envelope = create_envelope(domain, seq=15)

    # 3. Serialize to JSON for wire transfer
    raw = envelope.to_json()

    # 4. Parse on the receiving side (as the frontend or test would)
    parsed = parse_envelope(raw)

    assert parsed.id == domain.id
    assert parsed.type == "execution.node.completed"
    assert parsed.seq == 15
    assert parsed.session_id == "sess_01"
    assert parsed.workflow_id == "wf_01"
    assert parsed.run_id == "run_01"
    assert parsed.payload == {"node_id": "gen-1", "output_url": "https://fal.ai/output.png"}
