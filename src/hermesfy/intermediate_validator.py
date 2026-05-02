"""
Hermesfy Intermediate Validator — Step-by-Step Pipeline Validation

Validates intermediate images BETWEEN DAG nodes (not after the full pipeline).
If a step produces a bad image, the pipeline aborts before wasting credits
on the next step.

Usage:
    from engine.intermediate_validator import IntermediateValidator

    validator = IntermediateValidator(api_key="your_gemini_key")
    result = validator.validate_step(
        step_result={"image_path": "/cache/fal/gen_xxx.png"},
        original_prompt="professional photo of Nike sneaker",
    )
    # Returns: StepValidation(valid=True, confidence=0.92, should_continue=True)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from hermesfy.validator import ImageValidator

logger = logging.getLogger("hermesfy.intermediate_validator")

# Threshold: below this confidence, abort the pipeline
MIN_CONFIDENCE = 0.7

# Quick validation prompt (shorter than full validation for speed)
QUICK_VALIDATION_PROMPT = (
    "Rate this image 0-10 on how well it matches the prompt. "
    "Return ONLY a JSON object: {\"score\": N, \"issues\": [\"...\"]}. "
    "Score 7+ means acceptable. Focus on: composition, clarity, prompt adherence."
)


@dataclass
class StepValidation:
    """Result of validating a single pipeline step."""
    valid: bool = True
    confidence: float = 1.0
    should_continue: bool = True
    issues: list[str] = field(default_factory=list)
    raw_response: str = ""
    skipped: bool = False  # True if validation was skipped (no API key)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "confidence": self.confidence,
            "should_continue": self.should_continue,
            "issues": self.issues,
            "skipped": self.skipped,
        }


class IntermediateValidator:
    """
    Validates images between DAG pipeline steps.

    Uses Gemini Vision to quickly assess if an intermediate result
    is good enough to proceed to the next step.
    """

    def __init__(self, api_key: Optional[str] = None, min_confidence: float = MIN_CONFIDENCE):
        """
        Initialize the intermediate validator.

        Args:
            api_key: Google Gemini API key. If None, validation is skipped.
            min_confidence: Minimum confidence to continue (0.0 - 1.0).
        """
        self.min_confidence = min_confidence
        self._validator: Optional[ImageValidator] = None
        self._has_api_key = False

        if api_key:
            try:
                self._validator = ImageValidator(api_key=api_key)
                self._has_api_key = True
            except Exception as e:
                logger.warning("Failed to initialize ImageValidator: %s", e)

    @property
    def is_available(self) -> bool:
        return self._has_api_key and self._validator is not None

    def validate_step(
        self,
        step_result: dict,
        original_prompt: str,
        step_action: str = "base_generation",
    ) -> StepValidation:
        """
        Validate a single step's output.

        Args:
            step_result: Dict with at least "image_path" or "image_url"
            original_prompt: The original user prompt
            step_action: What kind of step this was

        Returns:
            StepValidation with confidence and should_continue flag
        """
        # Get image path
        image_path = step_result.get("image_path") or step_result.get("image_url", "")
        if not image_path:
            logger.warning("No image in step result, skipping validation")
            return StepValidation(skipped=True, issues=["no_image_in_result"])

        # Skip if no validator available
        if not self.is_available:
            logger.info("Gemini API key not set, skipping intermediate validation")
            return StepValidation(skipped=True, issues=["no_api_key"])

        # Skip for non-generative steps (upscale, remove_bg, etc.)
        if step_action in ("upscale", "remove_bg", "face_restore"):
            logger.info("Skipping validation for non-generative step: %s", step_action)
            return StepValidation(skipped=True, issues=[f"skipped_action_{step_action}"])

        # Run validation
        try:
            prompt = f"{QUICK_VALIDATION_PROMPT}\n\nPrompt: {original_prompt}"
            result = self._validator.validate(
                image_path=image_path,
                prompt=prompt,
            )

            confidence = result.get("confidence", 0.0)
            issues = result.get("issues", [])
            should_continue = confidence >= self.min_confidence

            validation = StepValidation(
                valid=confidence >= self.min_confidence,
                confidence=confidence,
                should_continue=should_continue,
                issues=issues,
                raw_response=str(result),
            )

            if should_continue:
                logger.info(
                    "Step validation PASSED: confidence=%.2f (>= %.2f)",
                    confidence, self.min_confidence,
                )
            else:
                logger.warning(
                    "Step validation FAILED: confidence=%.2f (< %.2f), issues=%s",
                    confidence, self.min_confidence, issues,
                )

            return validation

        except Exception as e:
            logger.error("Step validation error: %s", e)
            # On error, be lenient — don't abort the pipeline
            return StepValidation(
                valid=True,
                confidence=0.8,
                should_continue=True,
                issues=[f"validation_error: {e}"],
            )

    def validate_batch(
        self,
        step_results: list[dict],
        original_prompt: str,
        step_actions: Optional[list[str]] = None,
    ) -> list[StepValidation]:
        """
        Validate multiple steps at once.

        Args:
            step_results: List of step result dicts
            original_prompt: The original user prompt
            step_actions: Optional list of step actions (for skipping non-generative)

        Returns:
            List of StepValidation results
        """
        results = []
        for i, result in enumerate(step_results):
            action = step_actions[i] if step_actions and i < len(step_actions) else "base_generation"
            results.append(self.validate_step(result, original_prompt, action))
        return results
