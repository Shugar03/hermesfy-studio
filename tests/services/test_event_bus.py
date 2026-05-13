"""Tests for the async EventBus with ring-buffer replay and subscriber isolation."""

import asyncio
from typing import Optional

import pytest

from hermesfy.services.event_bus import DomainEvent, EventBus


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_event(
    event_type: str,
    *,
    session_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    run_id: Optional[str] = None,
    payload=None,
) -> DomainEvent:
    """Create a domain event with minimal fields."""
    return DomainEvent(
        type=event_type,
        session_id=session_id,
        workflow_id=workflow_id,
        run_id=run_id,
        payload=payload or {},
    )


async def collect(
    it,
    count: int,
    timeout: float = 2.0,
) -> list[DomainEvent]:
    """Collect *count* events from an async iterator with a timeout."""
    events: list[DomainEvent] = []
    # Yield to let the event loop process any pending publish tasks
    await asyncio.sleep(0.2)
    try:
        for _ in range(count):
            event = await asyncio.wait_for(it.__anext__(), timeout=timeout)
            events.append(event)
    except asyncio.TimeoutError:
        pass
    return events


# ── Basic pub/sub ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_reaches_single_subscriber():
    """A published event should be received by a subscriber on the same topic."""
    bus = EventBus()
    evt = make_event("chat.text_delta", session_id="sess_01")

    sub = bus.subscribe("chat:sess_01")  # NOT awaited — returns async generator
    await bus.publish(evt)

    received = await collect(sub, 1)
    assert len(received) == 1
    assert received[0].type == "chat.text_delta"
    assert received[0].session_id == "sess_01"


@pytest.mark.asyncio
async def test_publish_reaches_multiple_subscribers():
    """Multiple subscribers on the same topic should each receive the event."""
    bus = EventBus()
    evt = make_event("dag.patch", workflow_id="wf_01")

    sub1 = bus.subscribe("dag:wf_01")
    sub2 = bus.subscribe("dag:wf_01")

    await bus.publish(evt)

    r1 = await collect(sub1, 1)
    r2 = await collect(sub2, 1)

    assert len(r1) == 1
    assert len(r2) == 1
    assert r1[0].id == r2[0].id  # Same event ID


@pytest.mark.asyncio
async def test_subscriber_topic_isolation():
    """A subscriber on topic A should NOT receive events from topic B."""
    bus = EventBus()
    evt_a = make_event("chat.text_delta", session_id="sess_A")
    evt_b = make_event("chat.text_delta", session_id="sess_B")

    sub_a = bus.subscribe("chat:sess_A")
    sub_b = bus.subscribe("chat:sess_B")

    await bus.publish(evt_a)

    r_a = await collect(sub_a, 1)
    r_b = await collect(sub_b, 1, timeout=0.2)

    assert len(r_a) == 1
    assert r_a[0].session_id == "sess_A"
    assert len(r_b) == 0  # sess_B subscriber should not receive sess_A events


# ── Replay ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replay_after_seq():
    """A late subscriber with after_seq should receive missed events."""
    bus = EventBus(ring_size=100)

    # Publish 5 events
    for i in range(5):
        await bus.publish(make_event("chat.text_delta", session_id="sess_01", payload={"n": i}))

    # Now subscribe with after_seq pointing at seq 2
    sub = bus.subscribe("chat:sess_01", after_seq=2)
    replayed = await collect(sub, 3, timeout=0.3)

    assert len(replayed) == 3
    seqs = [e.seq for e in replayed]
    assert seqs == [3, 4, 5]


@pytest.mark.asyncio
async def test_replay_none_when_after_seq_covers_all():
    """If after_seq >= latest seq, no events should be replayed."""
    bus = EventBus(ring_size=100)

    await bus.publish(make_event("chat.text_delta", session_id="sess_01"))
    await bus.publish(make_event("chat.text_delta", session_id="sess_01"))

    sub = bus.subscribe("chat:sess_01", after_seq=5)
    replayed = await collect(sub, 1, timeout=0.3)

    assert len(replayed) == 0


@pytest.mark.asyncio
async def test_replay_no_after_seq_no_replay():
    """When after_seq is None, the subscriber gets only live events."""
    bus = EventBus(ring_size=100)

    await bus.publish(make_event("chat.text_delta", session_id="sess_01"))

    sub = bus.subscribe("chat:sess_01")  # No after_seq
    replayed = await collect(sub, 2, timeout=0.3)

    assert len(replayed) == 0  # No replay, no new events yet


# ── Sequence ordering ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sequence_numbers_are_monotonic():
    """Events on a topic should receive strictly increasing seq numbers."""
    bus = EventBus()

    sub = bus.subscribe("dag:wf_01")
    for i in range(10):
        await bus.publish(make_event("dag.patch", workflow_id="wf_01", payload={"n": i}))

    received = await collect(sub, 10)
    seqs = [e.seq for e in received]
    assert seqs == list(range(1, 11))


@pytest.mark.asyncio
async def test_sequence_numbers_per_topic_independent():
    """Sequence counters are independent per topic."""
    bus = EventBus()

    sub_a = bus.subscribe("chat:sess_A")
    sub_b = bus.subscribe("chat:sess_B")

    await bus.publish(make_event("chat.text_delta", session_id="sess_A"))
    await bus.publish(make_event("chat.text_delta", session_id="sess_B"))
    await bus.publish(make_event("chat.text_delta", session_id="sess_A"))

    r_a = await collect(sub_a, 2)
    r_b = await collect(sub_b, 1)

    assert [e.seq for e in r_a] == [1, 2]
    assert [e.seq for e in r_b] == [1]


# ── Ring buffer overflow ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ring_buffer_evicts_oldest():
    """When ring buffer is full, oldest events are evicted."""
    bus = EventBus(ring_size=5)

    # Publish 7 events
    for i in range(7):
        await bus.publish(make_event("chat.text_delta", session_id="sess_01", payload={"n": i}))

    # Subscribe requesting replay from seq 0 — should only get the last 5
    sub = bus.subscribe("chat:sess_01", after_seq=0)
    replayed = await collect(sub, 5, timeout=0.3)

    assert len(replayed) == 5
    seqs = [e.seq for e in replayed]
    assert seqs == [3, 4, 5, 6, 7]


# ── Subscriber overflow (non-blocking publish) ─────────────────────────────────

@pytest.mark.asyncio
async def test_publish_never_blocks_on_slow_subscriber():
    """Publishing should return immediately even if a subscriber queue is full."""
    bus = EventBus(max_queue=2)

    sub = bus.subscribe("chat:sess_01")
    # Don't drain the subscriber — fill it up
    for i in range(5):
        await bus.publish(make_event("chat.text_delta", session_id="sess_01", payload={"n": i}))

    # publish should NOT block or raise
    await bus.publish(make_event("chat.text_delta", session_id="sess_01", payload={"n": 99}))

    # The subscriber should have at most max_queue events
    received = await collect(sub, 10, timeout=0.3)
    assert len(received) <= 2  # max_queue=2, overflow drops


# ── Unsubscribe ────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_subscriber_unsubscribes_on_break():
        """When a subscriber breaks out of the iterator, it is removed."""
        bus = EventBus()

        sub = bus.subscribe("chat:sess_01")
        await bus.publish(make_event("chat.text_delta", session_id="sess_01"))

        # Break out after first event
        received = await collect(sub, 1)
        assert len(received) == 1

        # Close the generator to trigger unsubscribe (finally block)
        await sub.aclose()

        # The subscriber is removed — publish another event, no errors
        await bus.publish(make_event("chat.text_delta", session_id="sess_01", payload={"n": 2}))

        # Verify bus state: no lingering subscribers
        assert len(bus._subscribers.get("chat:sess_01", [])) == 0


# ── Invalid topics ─────────────────────────────────────────────────────────────

def test_invalid_topic_raises():
    """Subscribing to a malformed topic should raise ValueError."""
    bus = EventBus()

    with pytest.raises(ValueError, match="Invalid topic"):
        bus.subscribe("invalid_topic_without_colon")


def test_empty_topic_raises():
    """Subscribing to an empty topic should raise ValueError."""
    bus = EventBus()

    with pytest.raises(ValueError, match="Invalid topic"):
        bus.subscribe("")


# ── Multi-topic fanout ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_with_multiple_ids_fans_out():
    """An event with session_id + workflow_id + run_id fans out to all 3 topics."""
    bus = EventBus()

    sub_chat = bus.subscribe("chat:sess_01")
    sub_dag = bus.subscribe("dag:wf_01")
    sub_run = bus.subscribe("run:run_01")

    evt = make_event(
        "execution.node.completed",
        session_id="sess_01",
        workflow_id="wf_01",
        run_id="run_01",
        payload={"node": "n1"},
    )
    await bus.publish(evt)

    r_chat = await collect(sub_chat, 1)
    r_dag = await collect(sub_dag, 1)
    r_run = await collect(sub_run, 1)

    assert len(r_chat) == 1
    assert len(r_dag) == 1
    assert len(r_run) == 1

    # Same event ID across all topics
    assert r_chat[0].id == r_dag[0].id == r_run[0].id

    # Each topic has its own seq counter
    assert r_chat[0].seq == 1
    assert r_dag[0].seq == 1
    assert r_run[0].seq == 1


# ── DomainEvent model ──────────────────────────────────────────────────────────

def test_domain_event_defaults():
    """DomainEvent should populate id, version, timestamp automatically."""
    evt = DomainEvent(type="test.event")
    assert evt.id
    assert evt.version == 1
    assert evt.timestamp
    assert evt.seq == 0  # Assigned by bus
    assert evt.session_id is None


def test_domain_event_frozen():
    """DomainEvent instances should be immutable."""
    evt = DomainEvent(type="test.event")
    with pytest.raises(Exception):
        evt.type = "other.type"  # type: ignore[misc]
