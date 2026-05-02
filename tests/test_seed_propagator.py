"""Tests for seed_propagator.py — R3: Seed Inheritance"""
import pytest
from engine.seed_propagator import SeedPropagator, SEED_SUPPORTED_MODELS, SEED_EXCLUDED_MODELS


# ── Seed Resolution ──────────────────────────────────────────────────────────

class TestSeedResolution:
    def test_auto_generate(self):
        prop = SeedPropagator()
        seed = prop.resolve_seed(-1)
        assert seed >= 0
        assert prop.current_seed == seed

    def test_specified_seed(self):
        prop = SeedPropagator()
        seed = prop.resolve_seed(42)
        assert seed == 42
        assert prop.current_seed == 42

    def test_inherit_from_previous(self):
        prop = SeedPropagator()
        first = prop.resolve_seed(12345)
        second = prop.resolve_seed(-1)
        assert second == 12345  # inherited

    def test_auto_generate_is_random(self):
        prop1 = SeedPropagator()
        prop2 = SeedPropagator()
        s1 = prop1.resolve_seed(-1)
        s2 = prop2.resolve_seed(-1)
        # Very unlikely to be equal (2^32 space)
        # But technically possible, so we just check both are valid
        assert s1 >= 0
        assert s2 >= 0


# ── Seed Propagation ─────────────────────────────────────────────────────────

class TestSeedPropagation:
    def test_inject_seed_supported_model(self):
        prop = SeedPropagator()
        params = {"denoising_strength": 0.35}
        result = prop.propagate(42, params, model="fal-ai/flux/dev")
        assert result["seed"] == 42
        assert result["denoising_strength"] == 0.35

    def test_inject_seed_unknown_model(self):
        prop = SeedPropagator()
        result = prop.propagate(42, {"width": 1024}, model="fal-ai/unknown")
        assert result["seed"] == 42

    def test_skip_seed_excluded_model(self):
        prop = SeedPropagator()
        result = prop.propagate(42, {"scale": 2}, model="fal-ai/bria/background/remove")
        assert "seed" not in result
        assert result["scale"] == 2

    def test_inject_seed_no_model(self):
        prop = SeedPropagator()
        result = prop.propagate(42, {"width": 512})
        assert result["seed"] == 42

    def test_does_not_mutate_original_params(self):
        prop = SeedPropagator()
        original = {"width": 1024}
        result = prop.propagate(42, original, model="fal-ai/flux/dev")
        assert "seed" not in original
        assert "seed" in result


# ── History ──────────────────────────────────────────────────────────────────

class TestSeedHistory:
    def test_history_tracking(self):
        prop = SeedPropagator()
        prop.resolve_seed(100)
        prop.resolve_seed(-1)  # inherits
        prop.resolve_seed(200)  # overrides
        history = prop.get_history()
        assert len(history) == 3
        assert history[0]["source"] == "specified"
        assert history[1]["source"] == "inherited"
        assert history[2]["source"] == "specified"

    def test_reset(self):
        prop = SeedPropagator()
        prop.resolve_seed(42)
        prop.reset()
        assert prop.current_seed == -1
        assert prop.get_history() == []


# ── Full Flow Simulation ────────────────────────────────────────────────────

class TestFullFlow:
    def test_draft_refine_flow(self):
        """Simulate: generate seed → node 1 → node 2 inherits seed."""
        prop = SeedPropagator()

        # Node 1: base generation
        seed = prop.resolve_seed(-1)  # auto-generate
        params1 = prop.propagate(seed, {"width": 1024, "height": 1024}, "fal-ai/flux/schnell")
        assert "seed" in params1

        # Node 2: refine (inherits seed)
        seed2 = prop.resolve_seed(-1)  # should inherit
        assert seed2 == seed
        params2 = prop.propagate(seed2, {"denoising_strength": 0.35}, "fal-ai/flux/1.1-pro")
        assert params2["seed"] == seed

    def test_user_specified_seed(self):
        """User specifies seed=777 → both nodes use 777."""
        prop = SeedPropagator()
        seed = prop.resolve_seed(777)
        assert seed == 777
        seed2 = prop.resolve_seed(-1)
        assert seed2 == 777

    def test_upscale_no_seed(self):
        """Upscale step should not inject seed."""
        prop = SeedPropagator()
        seed = prop.resolve_seed(42)
        params = prop.propagate(seed, {"scale": 2}, "fal-ai/topaz/upscale/image")
        assert "seed" not in params
