"""WebSocket endpoints for real-time chat and DAG synchronization.

/ws/chat/{session_id}   — streaming chat messages and agent thinking
/ws/dag/{workflow_id}   — live canvas updates, node/edge changes, execution progress

P1 stubs: accept connections, echo back, support after_seq reconnect hint.
Full event bus and replay are wired in P2.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import hmac

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from hermesfy.api.deps import get_settings
from hermesfy.api.schemas import WSEventEnvelope

logger = logging.getLogger("hermesfy.api.ws")

router = APIRouter(tags=["websocket"])

# In-memory sequence counters per topic (P1 stub; P2 replaces with EventBus)
_seq_counters: dict[str, int] = {}


async def _enforce_ws_auth(websocket: WebSocket) -> bool:
    """Enforce WS auth when HERMESFY_AUTH_TOKEN is configured."""
    settings = get_settings()
    if not settings.auth_token:
        return True

    token = websocket.query_params.get("token")
    if token and hmac.compare_digest(token, settings.auth_token):
        return True

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        hdr_token = auth_header.removeprefix("Bearer ").strip()
        if hmac.compare_digest(hdr_token, settings.auth_token):
            return True

    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
    return False


def _next_seq(topic: str) -> int:
    """Return the next sequence number for a topic."""
    current = _seq_counters.get(topic, 0)
    _seq_counters[topic] = current + 1
    return current + 1


def _make_envelope(
    event_type: str,
    topic: str,
    payload: dict | None = None,
    **kwargs,
) -> WSEventEnvelope:
    """Build a WSEventEnvelope with incrementing seq for the topic."""
    seq = _next_seq(topic)
    return WSEventEnvelope(
        type=event_type,
        seq=seq,
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload=payload,
        **kwargs,
    )


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    after_seq: int | None = Query(default=None, alias="after_seq"),
) -> None:
    """WebSocket for real-time chat streaming.

    Accept?after_seq=N to replay events after that sequence number.
    """
    if not await _enforce_ws_auth(websocket):
        return
    await websocket.accept()
    topic = f"chat:{session_id}"
    logger.info("WS chat connected: session=%s after_seq=%s", session_id, after_seq)

    # Send connected event with last sequence info
    current_seq = _seq_counters.get(topic, 0)
    await websocket.send_json(
        _make_envelope(
            "connected",
            topic,
            payload={"last_seq": current_seq, "session_id": session_id},
            session_id=session_id,
        ).model_dump(mode="json")
    )

    try:
        while True:
            data = await websocket.receive_text()

            # Parse incoming message
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    _make_envelope(
                        "error",
                        topic,
                        payload={"error": "Invalid JSON", "raw": data[:200]},
                        session_id=session_id,
                    ).model_dump(mode="json")
                )
                continue

            # P1 stub: echo back with text_delta event
            msg_type = msg.get("type", "echo")
            await websocket.send_json(
                _make_envelope(
                    f"chat.{msg_type}",
                    topic,
                    payload=msg,
                    session_id=session_id,
                ).model_dump(mode="json")
            )

    except WebSocketDisconnect:
        logger.info("WS chat disconnected: session=%s", session_id)


@router.websocket("/ws/dag/{workflow_id}")
async def dag_websocket(
    websocket: WebSocket,
    workflow_id: str,
    after_seq: int | None = Query(default=None, alias="after_seq"),
) -> None:
    """WebSocket for live DAG canvas updates and execution progress.

    Accept?after_seq=N to replay events after that sequence number.
    """
    if not await _enforce_ws_auth(websocket):
        return
    await websocket.accept()
    topic = f"dag:{workflow_id}"
    logger.info("WS DAG connected: workflow=%s after_seq=%s", workflow_id, after_seq)

    # Send connected event
    current_seq = _seq_counters.get(topic, 0)
    await websocket.send_json(
        _make_envelope(
            "connected",
            topic,
            payload={"last_seq": current_seq, "workflow_id": workflow_id},
            workflow_id=workflow_id,
        ).model_dump(mode="json")
    )

    try:
        while True:
            data = await websocket.receive_text()

            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    _make_envelope(
                        "error",
                        topic,
                        payload={"error": "Invalid JSON", "raw": data[:200]},
                        workflow_id=workflow_id,
                    ).model_dump(mode="json")
                )
                continue

            msg_type = msg.get("type", "echo")
            await websocket.send_json(
                _make_envelope(
                    f"dag.{msg_type}",
                    topic,
                    payload=msg,
                    workflow_id=workflow_id,
                ).model_dump(mode="json")
            )

    except WebSocketDisconnect:
        logger.info("WS DAG disconnected: workflow=%s", workflow_id)
