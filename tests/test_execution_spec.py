"""Tests for execution_spec.py — R1: Formal JSON Contract"""
import json
import pytest
from engine.execution_spec import (
    ExecutionSpec, RoutingDecision, DagStep, DagWorkflow,
    ErrorHandling, PromptMetadata, SpecValidationError,
    VALID_INTENT_CATEGORIES, VALID_ACTIONS, VALID_STEP_ACTIONS,
)


# ── Construction ─────────────────────────────────────────────────────────────

class TestExecutionSpecConstruction:
    def test_default_spec_is_invalid(self):
        """Default spec has empty steps and prompt — should be invalid."""
        spec = ExecutionSpec()
        assert not spec.is_valid
        errors = spec.validate()
        assert any("empty" in e for e in errors)
        assert any("cleaned_prompt" in e for e in errors)

    def test_simple_factory(self):
        spec = ExecutionSpec.simple("a red Nike sneaker")
        assert spec.is_valid
        assert spec.prompt_metadata.cleaned_prompt == "a red Nike sneaker"
        assert spec.step_count == 1
        assert spec.target_model == "fal-ai/flux/dev"

    def test_draft_then_refine_factory(self):
        spec = ExecutionSpec.draft_then_refine("a sunset")
        assert spec.is_valid
        assert spec.step_count == 2
        assert spec.dag_workflow.steps[0].model == "fal-ai/flux/schnell"
        assert spec.dag_workflow.steps[1].model == "fal-ai/flux/1.1-pro"


# ── Validation ───────────────────────────────────────────────────────────────

class TestExecutionSpecValidation:
    def test_valid_spec_passes(self):
        spec = ExecutionSpec(
            routing_decision=RoutingDecision(intent_category="product", action="generate"),
            dag_workflow=DagWorkflow(steps=[DagStep(node_id=1, action="base_generation", model="fal-ai/flux/dev")]),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        assert spec.is_valid
        assert spec.validate() == []

    def test_invalid_intent_category(self):
        spec = ExecutionSpec(
            routing_decision=RoutingDecision(intent_category="invalid_category"),
            dag_workflow=DagWorkflow(steps=[DagStep(node_id=1, action="base_generation", model="fal-ai/flux/dev")]),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        errors = spec.validate()
        assert any("intent_category" in e for e in errors)

    def test_invalid_action(self):
        spec = ExecutionSpec(
            routing_decision=RoutingDecision(action="fly"),
            dag_workflow=DagWorkflow(steps=[DagStep(node_id=1, action="base_generation", model="fal-ai/flux/dev")]),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        errors = spec.validate()
        assert any("action" in e for e in errors)

    def test_empty_steps(self):
        spec = ExecutionSpec(
            dag_workflow=DagWorkflow(steps=[]),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        errors = spec.validate()
        assert any("empty" in e for e in errors)

    def test_non_sequential_node_ids(self):
        spec = ExecutionSpec(
            dag_workflow=DagWorkflow(steps=[
                DagStep(node_id=1, action="base_generation", model="m"),
                DagStep(node_id=3, action="latent_refiner", model="m"),  # skip 2
            ]),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        errors = spec.validate()
        assert any("sequential" in e for e in errors)

    def test_empty_prompt(self):
        spec = ExecutionSpec(
            dag_workflow=DagWorkflow(steps=[DagStep(node_id=1, action="base_generation", model="m")]),
            prompt_metadata=PromptMetadata(cleaned_prompt=""),
        )
        errors = spec.validate()
        assert any("cleaned_prompt" in e for e in errors)

    def test_negative_budget(self):
        spec = ExecutionSpec(
            routing_decision=RoutingDecision(budget_estimation=-1),
            dag_workflow=DagWorkflow(steps=[DagStep(node_id=1, action="base_generation", model="m")]),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        errors = spec.validate()
        assert any("budget" in e for e in errors)

    def test_invalid_retry_strategy(self):
        spec = ExecutionSpec(
            dag_workflow=DagWorkflow(steps=[DagStep(node_id=1, action="base_generation", model="m")]),
            error_handling=ErrorHandling(retry_strategy="magic"),
            prompt_metadata=PromptMetadata(cleaned_prompt="test"),
        )
        errors = spec.validate()
        assert any("retry" in e for e in errors)

    def test_validate_strict_raises(self):
        spec = ExecutionSpec(prompt_metadata=PromptMetadata(cleaned_prompt=""))
        with pytest.raises(SpecValidationError) as exc_info:
            spec.validate_strict()
        assert len(exc_info.value.errors) > 0


# ── Serialization ────────────────────────────────────────────────────────────

class TestExecutionSpecSerialization:
    def test_to_dict_roundtrip(self):
        spec = ExecutionSpec.simple("test prompt", budget=0.05, seed=42)
        d = spec.to_dict()
        spec2 = ExecutionSpec.from_dict(d)
        assert spec2.prompt_metadata.cleaned_prompt == "test prompt"
        assert spec2.prompt_metadata.seed == 42
        assert spec2.routing_decision.budget_estimation == 0.05

    def test_to_json_roundtrip(self):
        spec = ExecutionSpec.draft_then_refine("sunset")
        j = spec.to_json()
        spec2 = ExecutionSpec.from_json(j)
        assert spec2.step_count == 2
        assert spec2.dag_workflow.steps[0].model == "fal-ai/flux/schnell"

    def test_from_dict_missing_fields(self):
        """Empty dict produces invalid spec (missing steps + prompt)."""
        spec = ExecutionSpec.from_dict({})
        assert not spec.is_valid
        errors = spec.validate()
        assert any("empty" in e for e in errors)

    def test_from_dict_partial(self):
        spec = ExecutionSpec.from_dict({
            "routing_decision": {"intent_category": "typography"},
            "prompt_metadata": {"cleaned_prompt": "hello"},
        })
        assert spec.routing_decision.intent_category == "typography"
        assert not spec.is_valid  # still missing steps

    def test_json_output_is_valid_json(self):
        spec = ExecutionSpec.simple("test")
        j = spec.to_json()
        parsed = json.loads(j)
        assert parsed["spec_version"] == "1.0"


# ── Step access ──────────────────────────────────────────────────────────────

class TestStepAccess:
    def test_get_step(self):
        spec = ExecutionSpec.draft_then_refine("test")
        step = spec.get_step(1)
        assert step is not None
        assert step.model == "fal-ai/flux/schnell"

    def test_get_step_not_found(self):
        spec = ExecutionSpec.simple("test")
        assert spec.get_step(99) is None
