"""Tests for ModelQueryEngine."""
import json
import tempfile
from pathlib import Path

import pytest

from hermesfy.model_query_engine import (
    ModelQueryEngine,
    TaskSpec,
    RankedModel,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_index():
    """Small mock index with known models for testing."""
    return {
        "fal-ai/flux/schnell": {
            "endpoint_id": "fal-ai/flux/schnell",
            "name": "FLUX.1 [schnell]",
            "category": "text-to-image",
            "provider": "fal-ai",
            "tags": [],
            "supports_image_input": False,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": False,
            "supports_seed": True,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "1K",
        },
        "openai/gpt-image-2": {
            "endpoint_id": "openai/gpt-image-2",
            "name": "GPT Image 2",
            "category": "text-to-image",
            "provider": "openai",
            "tags": ["typography"],
            "supports_image_input": False,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": False,
            "supports_seed": True,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "1K",
        },
        "openai/gpt-image-2/edit": {
            "endpoint_id": "openai/gpt-image-2/edit",
            "name": "GPT Image 2 Edit",
            "category": "image-to-image",
            "provider": "openai",
            "tags": ["typography"],
            "supports_image_input": True,
            "supports_mask": True,
            "supports_prompt": True,
            "supports_multiple_refs": True,
            "supports_seed": True,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "2K",
            "max_reference_images": 16,
        },
        "fal-ai/bytedance/seedream/v4.5/edit": {
            "endpoint_id": "fal-ai/bytedance/seedream/v4.5/edit",
            "name": "Seedream 4.5 Edit",
            "category": "image-to-image",
            "provider": "bytedance",
            "tags": ["stylized", "transform"],
            "supports_image_input": True,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": True,
            "supports_seed": True,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "4K",
            "max_reference_images": 10,
        },
        "fal-ai/nano-banana-pro": {
            "endpoint_id": "fal-ai/nano-banana-pro",
            "name": "Nano Banana Pro",
            "category": "text-to-image",
            "provider": "fal-ai",
            "tags": ["realism", "typography"],
            "supports_image_input": False,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": False,
            "supports_seed": True,
            "supports_thinking": True,
            "supports_strength": False,
            "max_resolution": "1K",
        },
        "fal-ai/nano-banana-2/edit": {
            "endpoint_id": "fal-ai/nano-banana-2/edit",
            "name": "Nano Banana 2 Edit",
            "category": "image-to-image",
            "provider": "fal-ai",
            "tags": [],
            "supports_image_input": True,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": True,
            "supports_seed": True,
            "supports_thinking": True,
            "supports_strength": False,
            "max_resolution": "2K",
            "max_reference_images": 14,
        },
        "fal-ai/ideogram/v3": {
            "endpoint_id": "fal-ai/ideogram/v3",
            "name": "Ideogram v3",
            "category": "text-to-image",
            "provider": "ideogram",
            "tags": ["realism", "typography"],
            "supports_image_input": False,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": False,
            "supports_seed": True,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "1K",
        },
        "xai/grok-imagine-image": {
            "endpoint_id": "xai/grok-imagine-image",
            "name": "Grok Imagine",
            "category": "text-to-image",
            "provider": "xai",
            "tags": [],
            "supports_image_input": False,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": False,
            "supports_seed": False,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "1K",
        },
        "fal-ai/sam-3/image": {
            "endpoint_id": "fal-ai/sam-3/image",
            "name": "SAM 3",
            "category": "image-to-image",
            "provider": "fal-ai",
            "tags": [],
            "supports_image_input": True,
            "supports_mask": False,
            "supports_prompt": True,
            "supports_multiple_refs": False,
            "supports_seed": False,
            "supports_thinking": False,
            "supports_strength": False,
            "max_resolution": "1K",
        },
    }


@pytest.fixture
def engine(sample_index):
    """Engine with sample index."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_index, f)
        path = f.name
    engine = ModelQueryEngine(index_path=path)
    yield engine
    Path(path).unlink(missing_ok=True)


# ── Tests: Query ─────────────────────────────────────────────────────────────


class TestQueryGenerate:
    """Test generation queries."""

    def test_generate_product_hero(self, engine):
        """Generate: product hero, best quality."""
        task = TaskSpec(
            action="generate",
            content_type="product",
            max_budget=0.15,
            prioritize="quality",
        )
        results = engine.query(task, top_n=5)
        assert len(results) > 0
        assert all(r.score > 0 for r in results)
        # GPT Image 2 should rank high (openai reputation)
        gpt_models = [r for r in results if "gpt-image-2" in r.endpoint_id]
        assert len(gpt_models) > 0

    def test_generate_budget(self, engine):
        """Generate: budget constraint."""
        task = TaskSpec(
            action="generate",
            max_budget=0.01,
            prioritize="cost",
        )
        results = engine.query(task, top_n=5)
        assert len(results) > 0
        # Schnell should be top (cheapest)
        assert any("schnell" in r.endpoint_id for r in results)

    def test_generate_with_text(self, engine):
        """Generate: needs typography."""
        task = TaskSpec(
            action="generate",
            needs_text=True,
            max_budget=0.10,
        )
        results = engine.query(task, top_n=3)
        assert len(results) > 0
        # Ideogram or GPT Image should rank high for text
        top_ids = [r.endpoint_id for r in results]
        text_specialists = ["ideogram", "gpt-image-2", "nano-banana-pro"]
        assert any(any(t in eid for t in text_specialists) for eid in top_ids)


class TestQueryEdit:
    """Test editing queries."""

    def test_edit_single_ref(self, engine):
        """Edit: 1 reference image."""
        task = TaskSpec(
            action="edit",
            reference_count=1,
            content_type="product",
            max_budget=0.10,
        )
        results = engine.query(task, top_n=5)
        assert len(results) > 0
        # All should be image-to-image with image input
        for r in results:
            caps = engine._models[r.endpoint_id]
            assert caps["category"] == "image-to-image"
            assert caps["supports_image_input"]

    def test_edit_with_mask(self, engine):
        """Edit: requires mask."""
        task = TaskSpec(
            action="edit",
            reference_count=1,
            needs_mask=True,
            max_budget=0.10,
        )
        results = engine.query(task, top_n=5)
        assert len(results) > 0
        # All should support mask
        for r in results:
            caps = engine._models[r.endpoint_id]
            assert caps["supports_mask"]

    def test_composite_multi_ref(self, engine):
        """Composite: 2+ reference images."""
        task = TaskSpec(
            action="composite",
            reference_count=3,
            max_budget=0.10,
        )
        results = engine.query(task, top_n=5)
        assert len(results) > 0
        # All should support multiple refs
        for r in results:
            caps = engine._models[r.endpoint_id]
            assert caps.get("supports_multiple_refs")


class TestQueryEdgeCases:
    """Test edge cases."""

    def test_empty_index(self):
        """Engine with empty index returns empty results."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            path = f.name
        engine = ModelQueryEngine(index_path=path)
        results = engine.query(TaskSpec(), top_n=5)
        assert results == []
        Path(path).unlink(missing_ok=True)

    def test_missing_index_file(self):
        """Missing index file — engine loads with warning, returns empty."""
        engine = ModelQueryEngine(index_path="/nonexistent/path.json")
        assert engine.model_count == 0
        results = engine.query(TaskSpec(), top_n=5)
        assert results == []

    def test_scores_are_normalized(self, engine):
        """All scores should be between 0 and 1."""
        task = TaskSpec(action="generate", max_budget=1.0)
        results = engine.query(task, top_n=20)
        for r in results:
            assert 0.0 <= r.score <= 1.0, f"{r.endpoint_id}: score={r.score}"

    def test_results_have_reason(self, engine):
        """Each result should have a non-empty reason string."""
        results = engine.query(TaskSpec(), top_n=3)
        for r in results:
            assert r.reason, f"{r.endpoint_id}: empty reason"


# ── Tests: Quick Select ──────────────────────────────────────────────────────


class TestQuickSelect:
    """Test backward-compatible quick_select()."""

    def test_quick_select_returns_string(self, engine):
        """quick_select returns a string endpoint ID."""
        model = engine.quick_select(action="generate", content_type="product")
        assert isinstance(model, str)
        assert "/" in model  # should be like "fal-ai/flux/schnell"

    def test_quick_select_edit(self, engine):
        """quick_select for editing returns image-to-image model."""
        model = engine.quick_select(action="edit", content_type="product")
        assert isinstance(model, str)
        assert model in engine._models

    def test_quick_select_fallback(self, engine):
        """quick_select with impossible constraints falls back."""
        model = engine.quick_select(
            action="edit",
            content_type="product",
            quality="budget",
        )
        # Should still return something valid
        assert isinstance(model, str)


# ── Tests: Status ────────────────────────────────────────────────────────────


class TestStatus:
    """Test status() method."""

    def test_status_returns_dict(self, engine):
        """status() returns a dict with expected keys."""
        s = engine.status()
        assert "total_models" in s
        assert "categories" in s
        assert s["total_models"] == len(engine._models)
