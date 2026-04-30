"""Shared test fixtures for Hermesfy Studio."""

import pytest


@pytest.fixture
def fal_api_key() -> str:
    """Return a test Fal.ai API key."""
    return "test-fal-api-key-12345"


@pytest.fixture
def sample_workflow_dag() -> dict:
    """Return a minimal workflow DAG for testing."""
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
