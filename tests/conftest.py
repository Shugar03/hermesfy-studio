"""Shared test fixtures for Hermesfy Studio."""

import uuid

import pytest

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow


@pytest.fixture
def fal_api_key() -> str:
    """Return a test Fal.ai API key."""
    return "test-fal-api-key-12345"


@pytest.fixture
def sample_workflow_dag() -> dict:
    """Return a minimal workflow DAG for testing (legacy dict format)."""
    return {
        "nodes": [
            {"id": "step-1", "provider": "fal", "model": "flux-pro", "prompt": "a cat"},
            {"id": "step-2", "provider": "fal", "model": "flux-dev", "prompt": "a dog"},
        ],
        "edges": [{"from": "step-1", "to": "step-2"}],
    }


@pytest.fixture
def fal_generate_response() -> dict:
    """Mock successful Fal.ai generation response."""
    return {
        "id": "fal-123",
        "status": "completed",
        "output": {"images": [{"url": "https://fal.ai/images/test.png"}]},
    }


@pytest.fixture
def fal_quality_gate_passed() -> dict:
    """Mock quality gate result — passed."""
    return {"passed": True, "score": 0.92, "feedback": []}


# ── New fixtures for the DAG engine model ──────────────────────────────


@pytest.fixture
def sample_nodes() -> dict[str, Node]:
    """Return a dict of pre-built Node instances for reuse across tests."""
    return {
        "prompt": Node(
            id="prompt-1",
            type=NodeType.TEXT_PROMPT,
            config={"prompt": "a majestic dragon flying over mountains"},
        ),
        "gen": Node(
            id="gen-1",
            type=NodeType.IMAGE_GEN,
            config={"model": "flux-dev", "prompt": "{{prompt-1}}", "width": 1024, "height": 1024},
        ),
        "upscale": Node(
            id="upscale-1",
            type=NodeType.UPSCALE,
            config={"model": "clarity-upscaler", "image_url": "{{gen-1}}"},
        ),
        "seed": Node(
            id="seed-1",
            type=NodeType.SEED,
            config={"seed": 42},
        ),
    }


@pytest.fixture
def sample_workflow(sample_nodes) -> Workflow:
    """Return a complete 3-node linear DAG workflow: prompt → gen → upscale."""
    nodes = [
        sample_nodes["prompt"],
        sample_nodes["gen"],
        sample_nodes["upscale"],
    ]
    edges = [
        Edge(source="prompt-1", target="gen-1"),
        Edge(source="gen-1", target="upscale-1"),
    ]
    return Workflow(
        id=str(uuid.uuid4()),
        name="test-dragon-workflow",
        nodes=nodes,
        edges=edges,
    )


@pytest.fixture
def mock_fal_response() -> dict:
    """Extended Fal.ai mock response with full metadata for tests."""
    return {
        "request_id": "fal-req-abc123",
        "status": "COMPLETED",
        "output": {
            "images": [
                {
                    "url": "https://fal.ai/images/test-output.png",
                    "width": 1024,
                    "height": 1024,
                    "content_type": "image/png",
                }
            ]
        },
        "logs": [],
        "metrics": {"inference_time": 3.42},
    }


@pytest.fixture
def mock_fal_response_polling() -> list[dict]:
    """Mock responses for polling: IN_QUEUE → IN_PROGRESS → COMPLETED."""
    return [
        {"request_id": "fal-req-abc123", "status": "IN_QUEUE"},
        {"request_id": "fal-req-abc123", "status": "IN_PROGRESS", "logs": [{"message": "generating..."}]},
        {
            "request_id": "fal-req-abc123",
            "status": "COMPLETED",
            "output": {"images": [{"url": "https://fal.ai/images/test-output.png", "width": 1024, "height": 1024, "content_type": "image/png"}]},
        },
    ]
