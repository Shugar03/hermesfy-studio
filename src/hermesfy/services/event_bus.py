"""Async EventBus with per-topic ring buffers for replay and bounded subscriber queues.

The EventBus is the central nervous system of Hermesfy V5. It decouples producers
from consumers, supports late-joining subscribers via replay, and never blocks
publishers due to slow consumers.

Topics follow the convention:
    chat:{session_id}
    dag:{workflow_id}
    run:{run_id}
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("hermesfy.event_bus")

# ── Domain Event ──────────────────────────────────────────────────────────────

class DomainEvent(BaseModel):
    """Base event for all Hermesfy V5 domain events.

    Every event flowing through the system carries a monotonically increasing
    sequence number per topic, enabling reconnect/replay via ``after_seq``.

    Attributes:
        id: Unique event identifier (UUID4).
        type: Dot-separated event type string, e.g. ``"chat.text_delta"``.
        version: Schema version of this event (default 1).
        seq: Monotonically increasing sequence number assigned by the bus.
        timestamp: UTC timestamp when the event was published.
        session_id: Optional chat session identifier.
        workflow_id: Optional workflow identifier.
        turn_id: Optional chat turn identifier.
        run_id: Optional execution run identifier.
        payload: Arbitrary event payload (dict, list, or primitive).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    version: int = 1
    seq: int = 0  # Assigned by the bus on publish
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    turn_id: Optional[str] = None
    run_id: Optional[str] = None
    payload: Any = None


# ── Subscriber ────────────────────────────────────────────────────────────────

class _Subscriber:
    """Internal subscriber handle wrapping a bounded asyncio.Queue."""

    __slots__ = ("queue", "topic")

    def __init__(self, topic: str, max_queue: int) -> None:
        self.topic = topic
        self.queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=max_queue)


# ── Event Bus ─────────────────────────────────────────────────────────────────

class EventBus:
    """Async event bus with ring-buffer replay and bounded subscriber queues.

    Publishers call :meth:`publish` and never block — if a subscriber's queue
    is full the event is silently dropped for that subscriber.  Subscribers
    call :meth:`subscribe` and receive an async iterator.  If ``after_seq`` is
    provided, the bus replays all events from its ring buffer whose sequence
    number is strictly greater.

    Parameters:
        ring_size: Maximum number of events retained per topic for replay.
            Defaults to 1024.
        max_queue: Maximum number of events buffered per subscriber before
            overflow events are dropped.  Defaults to 256.
    """

    def __init__(self, ring_size: int = 1024, max_queue: int = 256) -> None:
        self._ring_size = ring_size
        self._max_queue = max_queue

        # Per-topic: ring buffer (deque with maxlen) + list of subscribers
        self._rings: dict[str, deque[DomainEvent]] = defaultdict(
            lambda: deque(maxlen=ring_size)
        )
        self._subscribers: dict[str, list[_Subscriber]] = defaultdict(list)

        # Per-topic monotonically increasing sequence counter
        self._seq_counters: dict[str, int] = defaultdict(int)

        # Lock for thread-safe ring subscriber registration (though
        # all public methods are designed for single-event-loop use).
        self._lock = asyncio.Lock()

    # ── publish ───────────────────────────────────────────────────────────

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all subscribers of every matching topic.

        The event is stamped with a sequence number per topic and appended
        to each topic's ring buffer.  It is then offered to every subscriber
        queue; if a queue is full the event is silently dropped for that
        subscriber.

        *The caller never blocks* — queue ``put_nowait`` is used.
        """
        # Determine topics this event belongs to.  A single event may
        # broadcast to multiple topics (chat + dag + run).
        topics = self._event_topics(event)

        async with self._lock:
            for topic in topics:
                seq = self._next_seq(topic)

                # Stamp the event with this topic's sequence number.
                # We create a new instance because DomainEvent is frozen.
                stamped = event.model_copy(update={"seq": seq})

                # Ring buffer
                self._rings[topic].append(stamped)

                # Fan-out to subscribers
                for sub in list(self._subscribers.get(topic, [])):
                    try:
                        sub.queue.put_nowait(stamped)
                    except asyncio.QueueFull:
                        logger.debug(
                            "EventBus: subscriber queue full for topic=%r seq=%d",
                            topic,
                            seq,
                        )

    # ── subscribe ─────────────────────────────────────────────────────────

    def subscribe(
        self,
        topic: str,
        after_seq: Optional[int] = None,
    ) -> AsyncIterator[DomainEvent]:
        """Subscribe to a topic, returning an async iterator of events.

        The subscriber is registered **eagerly** so events published immediately
        after this call are captured.  If *after_seq* is provided the bus first
        replays every ring-buffer event whose ``seq`` is strictly greater.

        NOTE: This is a regular (non-async) method that returns an async
        generator.  Do **not** ``await`` the return value — iterate it
        with ``async for`` or ``anext()``.
        """
        # Validate topic format eagerly
        self._validate_topic(topic)

        # Register the subscriber eagerly so events aren't missed
        sub = _Subscriber(topic, self._max_queue)
        self._subscribers[topic].append(sub)

        # Capture replay events now (before any publish happens)
        replay_events: list[DomainEvent] = []
        if after_seq is not None:
            ring = self._rings[topic]
            start_idx = 0
            for i, evt in enumerate(ring):
                if evt.seq > after_seq:
                    start_idx = i
                    break
            else:
                start_idx = len(ring)
            replay_events = list(ring)[start_idx:]

        async def _generator() -> AsyncIterator[DomainEvent]:
            try:
                # Replay phase first
                for evt in replay_events:
                    yield evt

                # Live phase — read from subscriber queue
                while True:
                    event = await sub.queue.get()
                    yield event
            finally:
                # Unsubscribe on exit
                try:
                    self._subscribers[topic].remove(sub)
                except ValueError:
                    pass  # Already removed

        return _generator()

    # ── helpers ───────────────────────────────────────────────────────────

    def _event_topics(self, event: DomainEvent) -> list[str]:
        """Return the list of topics an event should be published to."""
        topics: list[str] = []
        if event.session_id:
            topics.append(f"chat:{event.session_id}")
        if event.workflow_id:
            topics.append(f"dag:{event.workflow_id}")
        if event.run_id:
            topics.append(f"run:{event.run_id}")
        return topics

    def _next_seq(self, topic: str) -> int:
        """Increment and return the next sequence number for *topic*."""
        self._seq_counters[topic] += 1
        return self._seq_counters[topic]

    @staticmethod
    def _validate_topic(topic: str) -> None:
        """Raise ValueError if *topic* does not follow the required format."""
        if not topic or ":" not in topic:
            raise ValueError(
                f"Invalid topic {topic!r}: must be in format 'prefix:id', "
                f"e.g. 'chat:sess_01', 'dag:wf_01', 'run:run_01'"
            )

    @property
    def ring_size(self) -> int:
        """Configured ring buffer size per topic."""
        return self._ring_size

    @property
    def max_queue(self) -> int:
        """Configured max subscriber queue size."""
        return self._max_queue
