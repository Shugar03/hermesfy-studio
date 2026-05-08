"""
ModelQueryEngine — Dynamic model selection for Hermesfy Studio.

Replaces the hardcoded ModelSelector (AdType×QualityLevel matrix) with a
search engine that filters and ranks FAL models by real capabilities.

Architecture:
  1. ModelIndex (cached JSON from genmedia schema scan)
  2. QueryFilter (capability matching)
  3. Ranker (weighted scoring by task type)

Usage:
    from hermesfy.model_query_engine import ModelQueryEngine, TaskSpec

    engine = ModelQueryEngine()
    results = engine.query(TaskSpec(
        action="edit",
        reference_count=2,
        content_type="product",
        max_budget=0.10,
    ))
    # → [RankedModel(endpoint_id="...", score=0.92), ...]
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("hermesfy.model_query_engine")


# ── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class TaskSpec:
    """Specification of the image generation/editing task."""

    action: str = "generate"  # "generate" | "edit" | "composite"
    reference_count: int = 0  # 0, 1, 2+
    needs_text: bool = False  # Requires legible typography
    needs_mask: bool = False  # Requires mask-based editing
    content_type: str = "product"  # "product"|"beauty"|"luxury"|"social"|etc
    max_budget: float = 0.10  # USD
    min_resolution: str = "1K"  # "1K"|"2K"|"4K"
    prioritize: str = "quality"  # "quality"|"speed"|"cost"


@dataclass
class RankedModel:
    """A model with its relevance score and metadata."""

    endpoint_id: str
    name: str
    score: float
    estimated_cost: float
    max_resolution: str
    reason: str


# ── Provider reputation ──────────────────────────────────────────────────────

_PROVIDER_REPUTATION: dict[str, float] = {
    "openai": 0.08,       # Best instruction following
    "bytedance": 0.05,    # Best compositing
    "fal-ai": 0.02,       # Neutral (hosts many models)
    "google": 0.04,       # Gemini native
    "xai": 0.01,          # Newer, less tested
    "ideogram": 0.03,     # Good at text
    "alibaba": 0.01,
    "nvidia": 0.02,
    "tripo3d": 0.00,
}

# ── Approximate costs (will be overridden by genmedia pricing when available) ─

_ESTIMATED_COSTS: dict[str, float] = {
    "fal-ai/flux/schnell": 0.005,
    "fal-ai/flux/dev": 0.02,
    "fal-ai/flux-2-pro": 0.06,
    "fal-ai/flux-pro/v1.1": 0.05,
    "fal-ai/flux-pro/kontext": 0.04,
    "openai/gpt-image-2": 0.04,
    "openai/gpt-image-2/edit": 0.04,
    "fal-ai/nano-banana-2": 0.02,
    "fal-ai/nano-banana-pro": 0.15,
    "fal-ai/nano-banana": 0.02,
    "fal-ai/nano-banana-2/edit": 0.03,
    "fal-ai/nano-banana-pro/edit": 0.15,
    "fal-ai/bytedance/seedream/v4.5/edit": 0.04,
    "fal-ai/bytedance/seedream/v4/edit": 0.035,
    "fal-ai/bytedance/seedream/v5/lite/edit": 0.03,
    "fal-ai/gemini-3-pro-image-preview/edit": 0.05,
    "xai/grok-imagine-image": 0.022,
    "xai/grok-imagine-image/edit": 0.022,
    "xai/grok-imagine-image/quality/edit": 0.022,  # V3: empirically verified
    "fal-ai/ideogram/v3": 0.04,
    "fal-ai/z-image/turbo": 0.01,
    "fal-ai/flux-2": 0.05,
    "fal-ai/flux-pro/v1.1-ultra": 0.08,
}

_DEFAULT_COST = 0.04  # Conservative estimate for unknown models

# ── V2: Curated model quality ─────────────────────────────────────────────────

_CURATED_MODELS: dict[str, float] = {
    "openai/gpt-image-2": 0.12,
    "openai/gpt-image-2/edit": 0.12,
    "fal-ai/nano-banana-pro": 0.12,
    "fal-ai/nano-banana-pro/edit": 0.12,
    "fal-ai/nano-banana-2": 0.08,
    "fal-ai/nano-banana-2/edit": 0.10,
    "fal-ai/bytedance/seedream/v4.5/edit": 0.10,
    "fal-ai/bytedance/seedream/v5/lite/edit": 0.10,
    "fal-ai/bytedance/seedream/v4/edit": 0.08,
    "fal-ai/gemini-3-pro-image-preview/edit": 0.08,
    "fal-ai/flux-2-pro": 0.08,
    "fal-ai/flux-pro/v1.1": 0.06,
    "fal-ai/flux-2-pro/edit": 0.08,
    "fal-ai/ideogram/v3": 0.08,
    "xai/grok-imagine-image/quality/edit": 0.11,  # V3: top edit value
    "xai/grok-imagine-image/edit": 0.08,
    "xai/grok-imagine-image": 0.06,
    "fal-ai/flux/schnell": 0.02,
}

_UTILITY_PATTERNS = [
    "tiling", "material", "character", "lora", "inpaint", "remove",
    "demucs", "sam", "birefnet", "bria", "topaz", "seedvr",
    "clarity", "moondream", "florence", "llava", "video", "3d", "audio",
]

_CONTENT_AFFINITY: dict[str, list[str]] = {
    "beauty": ["nano-banana-pro", "nano-banana-2", "gpt-image-2", "seedream", "gemini", "grok"],
    "product": ["gpt-image-2", "grok", "seedream", "nano-banana-pro", "flux-2-pro", "flux-pro"],
    "luxury": ["nano-banana-pro", "gpt-image-2", "grok", "flux-2-pro"],
    "food": ["gpt-image-2", "nano-banana-pro", "flux-2-pro"],
    "fitness": ["flux-2-pro", "gpt-image-2", "nano-banana-pro"],
    "tech": ["flux-2-pro", "gemini", "gpt-image-2"],
    "social": ["gpt-image-2", "ideogram", "nano-banana-2", "schnell"],
}


# ── V3: Task Champions (empirically validated best models per task) ───────────

_TASK_CHAMPIONS: dict[str, dict[str, float]] = {
    "edit": {
        "xai/grok-imagine-image/quality/edit": 0.18,
        "xai/grok-imagine-image/edit": 0.12,
        "openai/gpt-image-2/edit": 0.15,
        "fal-ai/gemini-3-pro-image-preview/edit": 0.10,
    },
    "composite": {
        "fal-ai/bytedance/seedream/v4.5/edit": 0.20,
    },
    "generate": {
        "openai/gpt-image-2": 0.12,
        "fal-ai/nano-banana-pro": 0.12,
    },
}


# ── Engine ────────────────────────────────────────────────────────────────────


class ModelQueryEngine:
    """Query engine for finding the best FAL model for a task."""

    def __init__(
        self,
        index_path: str | None = None,
    ) -> None:
        """Load the model index from JSON.

        Args:
            index_path: Path to model_index.json. If None, uses the default
                       location at src/hermesfy/data/model_index.json.
        """
        if index_path is None:
            # Resolve relative to this file's location
            base = os.path.dirname(os.path.abspath(__file__))
            index_path = os.path.join(base, "data", "model_index.json")

        self._models: dict[str, dict] = {}
        self._path = index_path

        try:
            with open(index_path) as f:
                self._models = json.load(f)
            logger.info("Loaded %d models from %s", len(self._models), index_path)
        except FileNotFoundError:
            logger.warning(
                "Model index not found at %s. Run model_indexer first. "
                "Falling back to empty index.",
                index_path,
            )
        except json.JSONDecodeError:
            logger.error("Corrupted model index at %s", index_path)

    @property
    def model_count(self) -> int:
        """Number of models in the index."""
        return len(self._models)

    # ── Public API ────────────────────────────────────────────────────────

    def query(self, task: TaskSpec, top_n: int = 5) -> list[RankedModel]:
        """Query the best models for a task.

        Args:
            task: TaskSpec describing what we need.
            top_n: Maximum number of results to return.

        Returns:
            List of RankedModel ordered by score (highest first).
        """
        # Step 1: Filter by task capabilities
        candidates = self._filter(task)

        if not candidates:
            logger.warning(
                "No models match filters. Relaxing constraints..."
            )
            # Relax mask requirement
            relaxed = TaskSpec(
                action=task.action,
                reference_count=task.reference_count,
                needs_text=task.needs_text,
                needs_mask=False,  # <-- relaxed
                content_type=task.content_type,
                max_budget=task.max_budget * 2,  # <-- relaxed
                min_resolution="1K",  # <-- relaxed
                prioritize=task.prioritize,
            )
            candidates = self._filter(relaxed)

        # Step 2: Score and rank
        scored = []
        for model_id, caps in candidates.items():
            score, reasons = self._score(caps, task)
            cost = self._estimate_cost(model_id)
            scored.append(
                RankedModel(
                    endpoint_id=model_id,
                    name=caps.get("name", model_id),
                    score=round(score, 3),
                    estimated_cost=cost,
                    max_resolution=caps.get("max_resolution", "1K"),
                    reason="; ".join(reasons),
                )
            )

        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_n]

    def quick_select(
        self,
        action: str = "generate",
        content_type: str = "product",
        quality: str = "high",
    ) -> str:
        """Quick single-model selection (backward compatible with old API).

        Args:
            action: "generate" | "edit" | "composite"
            content_type: Ad type string
            quality: "best" | "high" | "standard" | "budget"

        Returns:
            FAL endpoint ID string.
        """
        budget_map = {
            "best": 0.20,
            "high": 0.10,
            "standard": 0.05,
            "budget": 0.02,
        }
        task = TaskSpec(
            action=action,
            reference_count=1 if action == "edit" else 0,
            content_type=content_type,
            max_budget=budget_map.get(quality, 0.10),
            prioritize="quality" if quality in ("best", "high") else "cost",
        )
        results = self.query(task, top_n=1)
        if results:
            return results[0].endpoint_id
        return "fal-ai/flux/schnell"  # Ultimate fallback

    # ── Filtering ──────────────────────────────────────────────────────────

    def _filter(self, task: TaskSpec) -> dict[str, dict]:
        """Filter models by task requirements."""
        candidates = {}

        for model_id, caps in self._models.items():
            # Category filter
            category = caps.get("category", "")
            if task.action == "generate":
                if category != "text-to-image":
                    continue
            elif task.action in ("edit", "composite"):
                if category != "image-to-image":
                    continue
                if not caps.get("supports_image_input"):
                    continue

            # Reference count filter
            if task.reference_count >= 2:
                if not caps.get("supports_multiple_refs"):
                    continue

            # Mask filter
            if task.needs_mask:
                if not caps.get("supports_mask"):
                    continue

            # Budget filter
            cost = self._estimate_cost(model_id)
            if cost > task.max_budget:
                continue

            # Resolution filter
            max_res = caps.get("max_resolution", "1K")
            if task.min_resolution == "4K" and max_res != "4K":
                continue
            elif task.min_resolution == "2K" and max_res not in ("2K", "4K"):
                continue

            candidates[model_id] = caps

        return candidates

    # ── V2 Scoring (QUALITY + TASK_FIT + COST + SPEED) ─────────────────────

    def _score(self, caps: dict, task: TaskSpec) -> tuple[float, list[str]]:
        """V2: QUALITY(0.40) + TASK_FIT(0.35) + COST(0.15) + SPEED(0.10)."""
        reasons: list[str] = []
        eid = caps.get("endpoint_id", "")
        provider = caps.get("provider", "")
        tags = caps.get("tags", [])
        category = caps.get("category", "")

        # --- QUALITY (0-1) ---
        quality = 0.0
        provider_bonus = {
            "openai": 0.25, "bytedance": 0.22, "google": 0.20,
            "ideogram": 0.18, "fal-ai": 0.15, "xai": 0.12,
        }
        quality += provider_bonus.get(provider, 0.10)
        if "realism" in tags: quality += 0.08
        if "typography" in tags: quality += 0.08
        quality += _CURATED_MODELS.get(eid, 0.0)

        # Anti-bonus: utility models
        for pat in _UTILITY_PATTERNS:
            if pat in eid.lower():
                quality -= 0.10
                if quality <= 0.05:
                    return 0.0, ["utility-filtered"]
                break
        quality = min(max(quality, 0.0), 1.0)

        # --- TASK_FIT (0-1) ---
        task_fit = 0.0
        if task.action == "generate" and category == "text-to-image":
            task_fit += 0.30
        elif task.action in ("edit", "composite") and category == "image-to-image":
            task_fit += 0.30
        else:
            task_fit -= 0.20

        # Required capabilities
        if task.reference_count >= 2 and not caps.get("supports_multiple_refs"):
            return 0.0, ["lacks-multi-ref"]
        if task.needs_mask and not caps.get("supports_mask"):
            return 0.0, ["lacks-mask"]

        # Bonus capabilities
        if task.action in ("edit", "composite") and caps.get("supports_image_input"):
            task_fit += 0.15
        if caps.get("supports_mask"):
            task_fit += 0.08
            reasons.append("mask-capable")

        # Text affinity
        if task.needs_text:
            if "typography" in tags or provider == "openai":
                task_fit += 0.15
                reasons.append("typography")
            else:
                task_fit -= 0.05

        # Content type affinity
        for keyword in _CONTENT_AFFINITY.get(task.content_type, []):
            if keyword in eid:
                task_fit += 0.10
                reasons.append(f"affinity:{keyword}")
                break

        # V3: Task champion bonus (empirically validated best models)
        champion_bonus = _TASK_CHAMPIONS.get(task.action, {}).get(eid, 0.0)
        if champion_bonus > 0:
            task_fit += champion_bonus
            reasons.append(f"champion:{task.action}")

        task_fit = min(max(task_fit, 0.0), 1.0)

        # --- COST (0-1) ---
        cost = self._estimate_cost(eid)
        if cost <= 0.01:      cost_score = 0.95
        elif cost <= 0.03:    cost_score = 0.85
        elif cost <= 0.05:    cost_score = 0.70
        elif cost <= 0.08:    cost_score = 0.50
        elif cost <= 0.15:    cost_score = 0.25
        else:                 cost_score = 0.10
        if cost <= 0.01:
            reasons.append(f"cheap(${cost:.3f})")
        reasons.append(f"res={caps.get('max_resolution','1K')}")

        # --- SPEED (0-1) ---
        if caps.get("supports_thinking"):
            speed_score = 0.3
        elif category == "text-to-image" and caps.get("num_input_params", 99) < 8:
            speed_score = 0.9
        else:
            speed_score = 0.6

        # --- WEIGHTED SUM ---
        total = (
            quality * 0.40
            + task_fit * 0.35
            + cost_score * 0.15
            + speed_score * 0.10
        )
        return round(total, 3), reasons

    def _estimate_cost(self, model_id: str) -> float:
        """Estimate cost for a model."""
        # Check exact match
        if model_id in _ESTIMATED_COSTS:
            return _ESTIMATED_COSTS[model_id]
        # Check prefix match
        for prefix, cost in sorted(_ESTIMATED_COSTS.items(), key=lambda x: -len(x[0])):
            if model_id.startswith(prefix):
                return cost
        return _DEFAULT_COST

    # ── Index status ───────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return index status for debugging."""
        cats = {}
        for caps in self._models.values():
            cat = caps.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1

        return {
            "total_models": len(self._models),
            "index_path": self._path,
            "categories": cats,
            "edit_capable": sum(1 for m in self._models.values() if m.get("supports_image_input")),
            "mask_capable": sum(1 for m in self._models.values() if m.get("supports_mask")),
        }
