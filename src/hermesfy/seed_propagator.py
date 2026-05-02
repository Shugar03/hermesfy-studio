"""
Hermesfy Seed Propagator — Seed Inheritance Between DAG Nodes

Ensures that the seed generated in node 1 is propagated to node 2+.
This prevents wasted credits on inconsistent compositions when refining.

Usage:
    from engine.seed_propagator import SeedPropagator

    propagator = SeedPropagator()

    # Auto-generate seed
    seed = propagator.resolve_seed(-1)
    # Propagate to next step
    params = propagator.propagate(seed, {"denoising_strength": 0.35})
    # Returns: {"denoising_strength": 0.35, "seed": 1234567890}
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger("hermesfy.seed_propagator")

# Models that support seed parameter
SEED_SUPPORTED_MODELS = frozenset({
    "fal-ai/flux/schnell",
    "fal-ai/flux/dev",
    "fal-ai/flux/pro",
    "fal-ai/flux/1.1-pro",
    "fal-ai/flux-pro/kontext",
    "fal-ai/ideogram/v3/text-to-image",
    "fal-ai/recraft/v3/text-to-image",
    "fal-ai/recraft/v4/pro/text-to-image",
})

# Models where seed goes in different param names
SEED_PARAM_NAMES = {
    "default": "seed",
    "fal-ai/flux-pro/kontext": "seed",
}

# Models that DON'T support seed (utility models)
SEED_EXCLUDED_MODELS = frozenset({
    "fal-ai/bria/background/remove",
    "fal-ai/topaz/upscale/image",
    "fal-ai/topaz/upscale/video",
    "fal-ai/flux-kontext-trainer",
    "fal-ai/flux-lora",
    "fal-ai/flux-lora-portrait-trainer",
    "fal-ai/flux-lora-fast-training",
})


@dataclass
class SeedPropagator:
    """
    Manages seed generation and propagation between DAG nodes.

    The seed ensures visual consistency when a pipeline generates an image
    in node 1 and refines it in node 2. Without seed inheritance, the
    composition changes between steps, wasting credits.
    """
    _current_seed: int = field(default=-1, repr=False)
    _history: list[dict] = field(default_factory=list, repr=False)

    @property
    def current_seed(self) -> int:
        return self._current_seed

    def resolve_seed(self, requested_seed: int) -> int:
        """
        Resolve the seed for the current step.

        Args:
            requested_seed: -1 = auto-generate, >0 = use specified

        Returns:
            The resolved seed value.
        """
        if requested_seed > 0:
            self._current_seed = requested_seed
            logger.info("Seed: using specified seed %d", requested_seed)
        elif self._current_seed > 0:
            # Inherit from previous step
            logger.info("Seed: inheriting seed %d from previous step", self._current_seed)
        else:
            # Generate new random seed
            self._current_seed = random.randint(0, 2**32 - 1)
            logger.info("Seed: auto-generated seed %d", self._current_seed)

        self._history.append({
            "step": len(self._history) + 1,
            "seed": self._current_seed,
            "source": "specified" if requested_seed > 0 else ("inherited" if len(self._history) > 0 else "generated"),
        })
        return self._current_seed

    def propagate(self, seed: int, params: dict, model: str = "") -> dict:
        """
        Inject seed into step params if the model supports it.

        Args:
            seed: The seed value to propagate
            params: The step parameters dict
            model: The model endpoint (to check seed support)

        Returns:
            New params dict with seed injected (if supported).
        """
        if model in SEED_EXCLUDED_MODELS:
            logger.debug("Seed: model %s doesn't support seed, skipping", model)
            return dict(params)

        if not self._model_supports_seed(model):
            logger.debug("Seed: model %s seed support unknown, injecting anyway", model)

        param_name = SEED_PARAM_NAMES.get(model, SEED_PARAM_NAMES["default"])
        new_params = dict(params)
        new_params[param_name] = seed
        logger.debug("Seed: injected %s=%d into params for %s", param_name, seed, model or "?")
        return new_params

    def _model_supports_seed(self, model: str) -> bool:
        """Check if a model is known to support seed."""
        if not model:
            return True  # Assume yes if unknown
        return model in SEED_SUPPORTED_MODELS

    def reset(self) -> None:
        """Reset for a new flow."""
        self._current_seed = -1
        self._history.clear()

    def get_history(self) -> list[dict]:
        return list(self._history)
