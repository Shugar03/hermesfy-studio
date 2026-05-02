"""
Hermesfy Execution Spec — Formal JSON Contract for Image Generation

The ONLY interface between the LLM (intent router) and the backend (pipeline).
Every generation request MUST be an ExecutionSpec. The pipeline REJECTS
anything that doesn't conform.

Usage:
    from engine.execution_spec import ExecutionSpec, SpecValidationError

    spec = ExecutionSpec.from_dict({
        "routing_decision": {
            "intent_category": "product",
            "action": "generate",
            "target_model": "fal-ai/flux/dev",
            "budget_estimation": 0.045,
            "priority": "quality"
        },
        "dag_workflow": {
            "steps": [
                {"node_id": 1, "action": "base_generation", "model": "fal-ai/flux/schnell", "params": {"width": 1024, "height": 1024}},
                {"node_id": 2, "action": "latent_refiner", "model": "fal-ai/flux/1.1-pro", "params": {"denoising_strength": 0.35}}
            ]
        },
        "error_handling": {"retry_strategy": "exponential_backoff", "max_retries": 3, "fallback_model": "fal-ai/flux/dev"},
        "prompt_metadata": {"cleaned_prompt": "...", "negative_prompt": "", "seed": -1}
    })
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("hermesfy.execution_spec")

# ── Constants ────────────────────────────────────────────────────────────────

SPEC_VERSION = "1.0"

VALID_INTENT_CATEGORIES = frozenset({
    "photorealism", "typography", "illustration", "sketch",
    "product", "lifestyle", "social_media", "editorial",
    "food", "beauty", "tech", "real_estate", "travel", "event",
})

VALID_ACTIONS = frozenset({"generate", "edit", "refine"})
VALID_PRIORITIES = frozenset({"quality", "speed", "cost"})
VALID_STEP_ACTIONS = frozenset({
    "base_generation", "latent_refiner", "upscale",
    "remove_bg", "inpaint", "outpaint", "face_restore",
    "ip_adapter", "img2img",
})
VALID_RETRY_STRATEGIES = frozenset({"exponential_backoff", "linear", "none"})


# ── Exceptions ───────────────────────────────────────────────────────────────

class SpecValidationError(Exception):
    """Raised when an ExecutionSpec fails validation."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Spec validation failed: {'; '.join(errors)}")


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class RoutingDecision:
    """Which model to use and why."""
    intent_category: str = "product"
    action: str = "generate"
    target_model: str = "fal-ai/flux/dev"
    budget_estimation: float = 0.05
    priority: str = "quality"

    def validate(self) -> list[str]:
        errors = []
        if self.intent_category not in VALID_INTENT_CATEGORIES:
            errors.append(f"Invalid intent_category: '{self.intent_category}'")
        if self.action not in VALID_ACTIONS:
            errors.append(f"Invalid action: '{self.action}'")
        if self.priority not in VALID_PRIORITIES:
            errors.append(f"Invalid priority: '{self.priority}'")
        if self.budget_estimation < 0:
            errors.append(f"budget_estimation must be >= 0, got {self.budget_estimation}")
        if not self.target_model:
            errors.append("target_model is required")
        return errors


@dataclass
class DagStep:
    """A single step in the DAG workflow."""
    node_id: int = 0
    action: str = "base_generation"
    model: str = "fal-ai/flux/dev"
    params: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors = []
        if self.node_id < 1:
            errors.append(f"node_id must be >= 1, got {self.node_id}")
        if self.action not in VALID_STEP_ACTIONS:
            errors.append(f"Invalid step action: '{self.action}'")
        if not self.model:
            errors.append(f"Step {self.node_id}: model is required")
        return errors


@dataclass
class ErrorHandling:
    """Retry and fallback configuration."""
    retry_strategy: str = "exponential_backoff"
    max_retries: int = 3
    fallback_model: str = "fal-ai/flux/dev"

    def validate(self) -> list[str]:
        errors = []
        if self.retry_strategy not in VALID_RETRY_STRATEGIES:
            errors.append(f"Invalid retry_strategy: '{self.retry_strategy}'")
        if self.max_retries < 0 or self.max_retries > 10:
            errors.append(f"max_retries must be 0-10, got {self.max_retries}")
        return errors


@dataclass
class PromptMetadata:
    """Cleaned prompt and seed info."""
    cleaned_prompt: str = ""
    negative_prompt: str = ""
    seed: int = -1  # -1 = auto-generate

    def validate(self) -> list[str]:
        errors = []
        if not self.cleaned_prompt:
            errors.append("cleaned_prompt is required")
        if self.seed < -1:
            errors.append(f"seed must be >= -1, got {self.seed}")
        return errors


@dataclass
class DagWorkflow:
    """Ordered list of steps to execute."""
    steps: list[DagStep] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors = []
        if not self.steps:
            errors.append("dag_workflow.steps cannot be empty")
        for step in self.steps:
            errors.extend(step.validate())
        # Check node_ids are sequential
        ids = [s.node_id for s in self.steps]
        if ids != list(range(1, len(ids) + 1)):
            errors.append(f"node_ids must be sequential (1, 2, 3...), got {ids}")
        return errors


# ── Main Spec ────────────────────────────────────────────────────────────────

@dataclass
class ExecutionSpec:
    """
    The formal contract for image generation.

    This is the ONLY data structure that flows between the LLM and the pipeline.
    Every field is validated on construction.
    """
    routing_decision: RoutingDecision = field(default_factory=RoutingDecision)
    dag_workflow: DagWorkflow = field(default_factory=DagWorkflow)
    error_handling: ErrorHandling = field(default_factory=ErrorHandling)
    prompt_metadata: PromptMetadata = field(default_factory=PromptMetadata)
    spec_version: str = SPEC_VERSION

    def validate(self) -> list[str]:
        """Validate the entire spec. Returns list of errors (empty = valid)."""
        errors = []
        if self.spec_version != SPEC_VERSION:
            errors.append(f"Unsupported spec_version: '{self.spec_version}'")
        errors.extend(self.routing_decision.validate())
        errors.extend(self.dag_workflow.validate())
        errors.extend(self.error_handling.validate())
        errors.extend(self.prompt_metadata.validate())
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    def validate_strict(self) -> None:
        """Raise SpecValidationError if invalid."""
        errors = self.validate()
        if errors:
            raise SpecValidationError(errors)

    @property
    def total_budget(self) -> float:
        return self.routing_decision.budget_estimation

    @property
    def target_model(self) -> str:
        return self.routing_decision.target_model

    @property
    def seed(self) -> int:
        return self.prompt_metadata.seed

    @property
    def step_count(self) -> int:
        return len(self.dag_workflow.steps)

    def get_step(self, node_id: int) -> Optional[DagStep]:
        for s in self.dag_workflow.steps:
            if s.node_id == node_id:
                return s
        return None

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "spec_version": self.spec_version,
            "routing_decision": {
                "intent_category": self.routing_decision.intent_category,
                "action": self.routing_decision.action,
                "target_model": self.routing_decision.target_model,
                "budget_estimation": self.routing_decision.budget_estimation,
                "priority": self.routing_decision.priority,
            },
            "dag_workflow": {
                "steps": [
                    {"node_id": s.node_id, "action": s.action, "model": s.model, "params": s.params}
                    for s in self.dag_workflow.steps
                ]
            },
            "error_handling": {
                "retry_strategy": self.error_handling.retry_strategy,
                "max_retries": self.error_handling.max_retries,
                "fallback_model": self.error_handling.fallback_model,
            },
            "prompt_metadata": {
                "cleaned_prompt": self.prompt_metadata.cleaned_prompt,
                "negative_prompt": self.prompt_metadata.negative_prompt,
                "seed": self.prompt_metadata.seed,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionSpec:
        """Parse a dict into an ExecutionSpec. Validates on construction."""
        rd = data.get("routing_decision", {})
        dw = data.get("dag_workflow", {})
        eh = data.get("error_handling", {})
        pm = data.get("prompt_metadata", {})

        spec = cls(
            spec_version=data.get("spec_version", SPEC_VERSION),
            routing_decision=RoutingDecision(
                intent_category=rd.get("intent_category", "product"),
                action=rd.get("action", "generate"),
                target_model=rd.get("target_model", "fal-ai/flux/dev"),
                budget_estimation=rd.get("budget_estimation", 0.05),
                priority=rd.get("priority", "quality"),
            ),
            dag_workflow=DagWorkflow(
                steps=[
                    DagStep(
                        node_id=s.get("node_id", 0),
                        action=s.get("action", "base_generation"),
                        model=s.get("model", ""),
                        params=s.get("params", {}),
                    )
                    for s in dw.get("steps", [])
                ]
            ),
            error_handling=ErrorHandling(
                retry_strategy=eh.get("retry_strategy", "exponential_backoff"),
                max_retries=eh.get("max_retries", 3),
                fallback_model=eh.get("fallback_model", "fal-ai/flux/dev"),
            ),
            prompt_metadata=PromptMetadata(
                cleaned_prompt=pm.get("cleaned_prompt", ""),
                negative_prompt=pm.get("negative_prompt", ""),
                seed=pm.get("seed", -1),
            ),
        )
        return spec

    @classmethod
    def from_json(cls, json_str: str) -> ExecutionSpec:
        """Parse a JSON string into an ExecutionSpec."""
        return cls.from_dict(json.loads(json_str))

    # ── Convenience constructors ─────────────────────────────────────────

    @classmethod
    def simple(cls, prompt: str, model: str = "fal-ai/flux/dev",
               width: int = 1024, height: int = 1024,
               budget: float = 0.05, seed: int = -1) -> ExecutionSpec:
        """Create a simple single-step generation spec."""
        return cls(
            routing_decision=RoutingDecision(
                intent_category="product",
                action="generate",
                target_model=model,
                budget_estimation=budget,
                priority="quality",
            ),
            dag_workflow=DagWorkflow(
                steps=[DagStep(
                    node_id=1,
                    action="base_generation",
                    model=model,
                    params={"width": width, "height": height},
                )]
            ),
            prompt_metadata=PromptMetadata(
                cleaned_prompt=prompt,
                seed=seed,
            ),
        )

    @classmethod
    def draft_then_refine(cls, prompt: str, draft_model: str = "fal-ai/flux/schnell",
                          refine_model: str = "fal-ai/flux/1.1-pro",
                          budget: float = 0.06) -> ExecutionSpec:
        """Create a 2-step spec: fast draft → quality refine."""
        return cls(
            routing_decision=RoutingDecision(
                intent_category="product",
                action="generate",
                target_model=refine_model,
                budget_estimation=budget,
                priority="quality",
            ),
            dag_workflow=DagWorkflow(
                steps=[
                    DagStep(node_id=1, action="base_generation", model=draft_model,
                            params={"width": 1024, "height": 1024, "steps": 4}),
                    DagStep(node_id=2, action="latent_refiner", model=refine_model,
                            params={"denoising_strength": 0.35, "upscale_factor": 1.5}),
                ]
            ),
            prompt_metadata=PromptMetadata(cleaned_prompt=prompt),
        )
