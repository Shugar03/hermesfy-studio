"""Chat session and turn routes.

POST /api/chat/sessions          — create session
POST /api/chat/sessions/{id}/messages — send message (creates turn)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends

from hermesfy.api.deps import get_db, require_auth
from hermesfy.api.errors import NotFoundError
from hermesfy.api.schemas import (
    ChatSession,
    ChatSessionCreate,
    ChatTurn,
    ChatTurnCreate,
    TurnStatus,
)

logger = logging.getLogger("hermesfy.api.chat")

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_auth)])


@router.post("/sessions", response_model=ChatSession, status_code=201)
async def create_session(
    body: ChatSessionCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> ChatSession:
    """Create a new chat session, optionally linked to a workflow."""
    session = ChatSession(
        workflow_id=body.workflow_id,
        title=body.title,
    )
    await db.execute(
        """INSERT INTO chat_sessions (id, workflow_id, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session.id, session.workflow_id, session.title,
         session.created_at.isoformat(), session.updated_at.isoformat()),
    )
    await db.commit()
    logger.info("Created chat session %s", session.id)
    return session


@router.post("/sessions/{session_id}/messages", response_model=ChatTurn, status_code=201)
async def send_message(
    session_id: str,
    body: ChatTurnCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> ChatTurn:
    """Send a message in a chat session, creating a new turn.

    In P1 this is a stub — the actual Hermes agent subprocess is wired in P4.
    """
    # Verify session exists
    cursor = await db.execute(
        "SELECT id FROM chat_sessions WHERE id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise NotFoundError("ChatSession", session_id)

    turn = ChatTurn(
        session_id=session_id,
        user_message=body.message,
        status=TurnStatus.COMPLETED,  # stub: immediate completion
        agent_response="[Hermes agent not yet wired — P4]",
    )
    await db.execute(
        """INSERT INTO chat_turns (id, session_id, user_message, agent_response,
           status, cost_usd, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            turn.id, turn.session_id, turn.user_message, turn.agent_response,
            turn.status.value, turn.cost_usd,
            turn.created_at.isoformat(), turn.completed_at.isoformat() if turn.completed_at else None,
        ),
    )
    await db.commit()
    logger.info("Created turn %s in session %s", turn.id, session_id)
    return turn
