"""
Auto Model Selection for Hermesfy Studio.

Automatically selects the best AI image generation model based on ad type,
quality level, and budget constraints. Uses a decision matrix derived from
research benchmarks.

Usage:
    from engine.model_selector import ModelSelector, AdType, QualityLevel

    selector = ModelSelector()

    # Auto-select by ad type
    model = selector.select(ad_type=AdType.PRODUCT_HERO)
    # → "flux-2-pro"

    # With quality override
    model = selector.select(
        ad_type=AdType.PRODUCT_LIFESTYLE, quality=QualityLevel.BUDGET
    )
    # → "flux-schnell"

    # Get alternatives
    best, alternatives = selector.select_with_alternatives(AdType.TYPOGRAPHY_AD)
    # → ("recraft-v4-pro", ["ideogram-v3", "gpt-image-2"])
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger("hermesfy.model_selector")


# ── Enums ─────────────────────────────────────────────────────────────────────


class AdType(Enum):
    """Types of advertisements with corresponding model recommendations."""

    PRODUCT_HERO = "product_hero"          # Product on background
    PRODUCT_LIFESTYLE = "product_lifestyle"  # Product in context
    SOCIAL_MEDIA = "social_media"          # Bold social graphic
    LUXURY = "luxury"                      # Premium/elegant
    FITNESS = "fitness"                    # Energy/dynamic
    TECH = "tech"                          # Futuristic/modern
    TYPOGRAPHY_AD = "typography"           # Text-heavy
    FOOD = "food"                          # Warm, appetizing
    BEAUTY = "beauty"                      # Soft, skincare
    QUICK_DRAFT = "quick_draft"            # Fast iteration


class QualityLevel(Enum):
    """Quality tiers for model selection."""

    BEST = "best"          # Top tier, higher cost
    HIGH = "high"          # Strong quality
    STANDARD = "standard"  # Good balance
    BUDGET = "budget"      # Fast/cheap


# ── Exceptions ────────────────────────────────────────────────────────────────


class ModelSelectionError(Exception):
    """Exception raised when model selection fails."""


class InvalidModelError(ModelSelectionError):
    """Exception raised when a selected model is not in FAL_MODELS."""

    def __init__(self, model_key: str, ad_type: AdType) -> None:
        super().__init__(
            f"Selected model '{model_key}' for ad type '{ad_type.value}' "
            f"not found in FAL_MODELS registry."
        )
        self.model_key = model_key
        self.ad_type = ad_type


# ── Decision Matrix ───────────────────────────────────────────────────────────

# Format: {AdType: {QualityLevel: model_key}}
# Derived from SPEC V2.1 research benchmarks.
_DECISION_MATRIX: dict[AdType, dict[QualityLevel, str]] = {
    AdType.PRODUCT_HERO: {
        QualityLevel.BEST: "flux-2-pro",
        QualityLevel.HIGH: "nano-banana-pro",
        QualityLevel.STANDARD: "recraft-v4-pro",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.PRODUCT_LIFESTYLE: {
        QualityLevel.BEST: "gpt-image-2",
        QualityLevel.HIGH: "nano-banana-pro",
        QualityLevel.STANDARD: "gemini-3",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.SOCIAL_MEDIA: {
        QualityLevel.BEST: "recraft-v4-pro",
        QualityLevel.HIGH: "gpt-image-2",
        QualityLevel.STANDARD: "ideogram-v3",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.LUXURY: {
        QualityLevel.BEST: "nano-banana-pro",
        QualityLevel.HIGH: "recraft-v4-pro",
        QualityLevel.STANDARD: "flux-2-pro",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.FITNESS: {
        QualityLevel.BEST: "flux-2-pro",
        QualityLevel.HIGH: "gpt-image-2",
        QualityLevel.STANDARD: "recraft-v4-pro",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.TECH: {
        QualityLevel.BEST: "flux-2-pro",
        QualityLevel.HIGH: "gemini-3",
        QualityLevel.STANDARD: "gpt-image-2",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.TYPOGRAPHY_AD: {
        QualityLevel.BEST: "recraft-v4-pro",
        QualityLevel.HIGH: "ideogram-v3",
        QualityLevel.STANDARD: "gpt-image-2",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.FOOD: {
        QualityLevel.BEST: "gpt-image-2",
        QualityLevel.HIGH: "nano-banana-pro",
        QualityLevel.STANDARD: "flux-2-pro",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.BEAUTY: {
        QualityLevel.BEST: "nano-banana-pro",
        QualityLevel.HIGH: "recraft-v4-pro",
        QualityLevel.STANDARD: "gpt-image-2",
        QualityLevel.BUDGET: "flux-schnell",
    },
    AdType.QUICK_DRAFT: {
        QualityLevel.BEST: "flux-schnell",
        QualityLevel.HIGH: "flux-2-flex",
        QualityLevel.STANDARD: "flux-dev",
        QualityLevel.BUDGET: "flux-schnell",
    },
}


# ── ModelSelector Class ───────────────────────────────────────────────────────


class ModelSelector:
    """
    Auto-selects the best AI model based on ad type and quality requirements.

    Uses a decision matrix derived from research benchmarks and validates
    all selections against the FAL_MODELS registry.

    Attributes:
        _fal_models: Reference to FAL_MODELS dict for validation.
        _matrix: The decision matrix mapping.
    """

    def __init__(
        self,
        fal_models: dict[str, Any] | None = None,
        matrix: dict[AdType, dict[QualityLevel, str]] | None = None,
    ) -> None:
        """
        Initialize ModelSelector.

        Args:
            fal_models: FAL_MODELS dict from ai_generator. If None, imports
                       from engine.ai_generator.
            matrix: Custom decision matrix override. If None, uses default.
        """
        if fal_models is not None:
            self._fal_models = fal_models
        else:
            try:
                from engine.ai_generator import FAL_MODELS
                self._fal_models = FAL_MODELS
            except ImportError:
                logger.warning(
                    "Could not import FAL_MODELS from engine.ai_generator. "
                    "Model validation will be skipped."
                )
                self._fal_models = {}

        self._matrix = matrix or _DECISION_MATRIX

    def select(
        self,
        ad_type: AdType,
        quality: QualityLevel = QualityLevel.HIGH,
    ) -> str:
        """
        Select the best model for a given ad type and quality level.

        Args:
            ad_type: The type of advertisement.
            quality: Desired quality level (default: HIGH).

        Returns:
            Model key string (e.g., "flux-2-pro").

        Raises:
            ModelSelectionError: If no mapping exists for the combination.
            InvalidModelError: If the selected model is not in FAL_MODELS.
        """
        if ad_type not in self._matrix:
            logger.warning(
                "Unknown ad type '%s', falling back to QUICK_DRAFT",
                ad_type.value,
            )
            ad_type = AdType.QUICK_DRAFT

        quality_map = self._matrix[ad_type]

        if quality not in quality_map:
            # Fall back to HIGH, then BEST, then first available
            fallback_order = [
                QualityLevel.HIGH, QualityLevel.BEST,
                QualityLevel.STANDARD, QualityLevel.BUDGET,
            ]
            for fb in fallback_order:
                if fb in quality_map:
                    quality = fb
                    break
            else:
                raise ModelSelectionError(
                    f"No model mapping for ad_type={ad_type.value}, "
                    f"quality={quality.value}"
                )

        model_key = quality_map[quality]

        # Validate against FAL_MODELS if available
        if self._fal_models and model_key not in self._fal_models:
            raise InvalidModelError(model_key, ad_type)

        logger.info(
            "Selected model '%s' for ad_type=%s, quality=%s",
            model_key, ad_type.value, quality.value,
        )
        return model_key

    def select_with_alternatives(
        self,
        ad_type: AdType,
        quality: QualityLevel = QualityLevel.HIGH,
    ) -> tuple[str, list[str]]:
        """
        Select the best model and return alternatives.

        Returns the primary model and up to 3 alternatives ordered by
        quality level (BEST → BUDGET, excluding the selected model).

        Args:
            ad_type: The type of advertisement.
            quality: Desired quality level for primary selection.

        Returns:
            Tuple of (primary_model, [alternative_models]).

        Example:
            >>> best, alts = selector.select_with_alternatives(AdType.TYPOGRAPHY_AD)
            >>> # best = "ideogram-v3", alts = ["recraft-v4-pro", "gpt-image-2", "flux-schnell"]
        """
        primary = self.select(ad_type, quality)

        if ad_type not in self._matrix:
            ad_type = AdType.QUICK_DRAFT

        quality_map = self._matrix[ad_type]

        # Build alternatives list in priority order, excluding primary
        priority_order = [
            QualityLevel.BEST, QualityLevel.HIGH,
            QualityLevel.STANDARD, QualityLevel.BUDGET,
        ]
        alternatives: list[str] = []
        for q in priority_order:
            if q in quality_map and quality_map[q] != primary:
                model_key = quality_map[q]
                # Validate if possible
                if self._fal_models and model_key not in self._fal_models:
                    logger.warning(
                        "Alternative model '%s' not in FAL_MODELS, skipping",
                        model_key,
                    )
                    continue
                alternatives.append(model_key)

        return primary, alternatives

    def get_all_mappings(self) -> dict[str, dict[str, str]]:
        """
        Return the complete decision matrix as a serializable dict.

        Returns:
            Dict mapping ad_type name → {quality_level: model_key}.
            All values are strings for JSON serialization.

        Example:
            >>> mappings = selector.get_all_mappings()
            >>> mappings["product_hero"]["best"]
            "flux-2-pro"
        """
        result: dict[str, dict[str, str]] = {}
        for ad_type, quality_map in self._matrix.items():
            result[ad_type.value] = {
                q.value: model for q, model in quality_map.items()
            }
        return result

    def validate_all_models(self) -> dict[str, list[str]]:
        """
        Validate that all models in the matrix exist in FAL_MODELS.

        Returns:
            Dict with keys:
                - "valid": list of model keys found in FAL_MODELS
                - "missing": list of model keys NOT found in FAL_MODELS

        Useful for debugging and health checks.
        """
        if not self._fal_models:
            return {"valid": [], "missing": ["FAL_MODELS not loaded"]}

        all_models: set[str] = set()
        for quality_map in self._matrix.values():
            all_models.update(quality_map.values())

        valid = sorted(m for m in all_models if m in self._fal_models)
        missing = sorted(m for m in all_models if m not in self._fal_models)

        return {"valid": valid, "missing": missing}

    @property
    def supported_ad_types(self) -> list[str]:
        """Return list of supported ad type values."""
        return [at.value for at in self._matrix.keys()]

    @property
    def supported_quality_levels(self) -> list[str]:
        """Return list of supported quality level values."""
        return [ql.value for ql in QualityLevel]
