"""Tests for budget_gate.py — R2: Hard Cap $0.07/flow"""
import pytest
from engine.budget_gate import BudgetGate, BudgetExceeded, MODEL_COSTS


# ── Basic Gate Operations ────────────────────────────────────────────────────

class TestBudgetGateBasic:
    def test_default_budget(self):
        gate = BudgetGate()
        assert gate.max_budget == 0.07
        assert gate.remaining() == 0.07
        assert gate.spent == 0.0

    def test_custom_budget(self):
        gate = BudgetGate(max_budget=0.15)
        assert gate.max_budget == 0.15
        assert gate.remaining() == 0.15

    def test_can_spend_under(self):
        gate = BudgetGate(max_budget=0.07)
        assert gate.can_spend(0.05) is True

    def test_can_spend_exact(self):
        gate = BudgetGate(max_budget=0.07)
        assert gate.can_spend(0.07) is True

    def test_can_spend_over(self):
        gate = BudgetGate(max_budget=0.07)
        assert gate.can_spend(0.08) is False

    def test_record_spend(self):
        gate = BudgetGate(max_budget=0.07)
        gate.record_spend(0.03, model="fal-ai/flux/dev")
        assert gate.spent == 0.03
        assert gate.remaining() == 0.04

    def test_record_multiple_spends(self):
        gate = BudgetGate(max_budget=0.07)
        gate.record_spend(0.03, model="a")
        gate.record_spend(0.02, model="b")
        assert gate.spent == 0.05
        assert gate.remaining() == 0.02


# ── Budget Exceeded ──────────────────────────────────────────────────────────

class TestBudgetExceeded:
    def test_over_budget_raises(self):
        gate = BudgetGate(max_budget=0.07)
        gate.record_spend(0.06)
        with pytest.raises(BudgetExceeded) as exc_info:
            gate.record_spend(0.02, model="fal-ai/flux/pro")
        assert exc_info.value.remaining == 0.01
        assert exc_info.value.attempted == 0.02
        assert exc_info.value.model == "fal-ai/flux/pro"

    def test_exceeded_message(self):
        exc = BudgetExceeded(0.01, 0.05, "fal-ai/flux/dev")
        assert "$0.0100" in str(exc)
        assert "$0.0500" in str(exc)
        assert "fal-ai/flux/dev" in str(exc)


# ── Model Cost Estimation ────────────────────────────────────────────────────

class TestModelCosts:
    def test_known_model_cost(self):
        gate = BudgetGate()
        cost = gate.estimate_cost("fal-ai/flux/schnell")
        assert cost == 0.003

    def test_unknown_model_cost(self):
        gate = BudgetGate()
        cost = gate.estimate_cost("fal-ai/unknown-model")
        assert cost == 0.025  # default

    def test_can_afford_model(self):
        gate = BudgetGate(max_budget=0.07)
        assert gate.can_afford_model("fal-ai/flux/schnell") is True

    def test_cant_afford_expensive_model(self):
        gate = BudgetGate(max_budget=0.02)
        assert gate.can_afford_model("fal-ai/flux/pro") is False  # costs 0.05

    def test_record_and_check_success(self):
        gate = BudgetGate(max_budget=0.07)
        result = gate.record_and_check("fal-ai/flux/schnell")
        assert result is True
        assert gate.spent == 0.003

    def test_record_and_check_failure(self):
        gate = BudgetGate(max_budget=0.01)
        result = gate.record_and_check("fal-ai/flux/dev")  # costs 0.025
        assert result is False
        assert gate.spent == 0.0  # nothing recorded


# ── History and Summary ──────────────────────────────────────────────────────

class TestBudgetHistory:
    def test_history_tracking(self):
        gate = BudgetGate()
        gate.record_spend(0.01, model="a", detail="step 1")
        gate.record_spend(0.02, model="b", detail="step 2")
        history = gate.get_history()
        assert len(history) == 2
        assert history[0]["model"] == "a"
        assert history[1]["detail"] == "step 2"

    def test_summary(self):
        gate = BudgetGate(max_budget=0.07)
        gate.record_spend(0.03, model="fal-ai/flux/dev")
        gate.record_spend(0.003, model="fal-ai/flux/schnell")
        summary = gate.get_summary()
        assert summary["max_budget"] == 0.07
        assert summary["spent"] == 0.033
        assert summary["num_calls"] == 2
        assert summary["by_model"]["fal-ai/flux/dev"] == 0.03

    def test_reset(self):
        gate = BudgetGate()
        gate.record_spend(0.05)
        gate.reset()
        assert gate.spent == 0.0
        assert gate.remaining() == 0.07
        assert gate.get_history() == []


# ── Multi-step flow simulation ───────────────────────────────────────────────

class TestMultiStepFlow:
    def test_draft_then_refine_within_budget(self):
        gate = BudgetGate(max_budget=0.07)
        # Step 1: schnell draft
        assert gate.record_and_check("fal-ai/flux/schnell")  # 0.003
        # Step 2: 1.1-pro refine
        assert gate.record_and_check("fal-ai/flux/1.1-pro")  # 0.04
        assert gate.spent == 0.043
        assert gate.remaining() > 0

    def test_three_step_flow_stays_under(self):
        gate = BudgetGate(max_budget=0.07)
        assert gate.record_and_check("fal-ai/flux/schnell")  # 0.003
        assert gate.record_and_check("fal-ai/flux/1.1-pro")  # 0.04
        assert gate.record_and_check("fal-ai/topaz/upscale/image")  # 0.015
        assert gate.spent == 0.058
        assert gate.remaining() == pytest.approx(0.012, abs=0.001)

    def test_budget_aborts_expensive_flow(self):
        gate = BudgetGate(max_budget=0.03)
        assert gate.record_and_check("fal-ai/flux/schnell")  # 0.003
        assert gate.record_and_check("fal-ai/flux/pro") is False  # 0.05 > 0.027 remaining
