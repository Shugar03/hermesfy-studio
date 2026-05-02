"""
Hermesfy Budget Gate — Cost Control for Image Generation

Enforces a hard spending cap per flow. Every FAL.ai call must pass through
the gate BEFORE execution. If the budget is exceeded, the pipeline aborts.

Usage:
    from engine.budget_gate import BudgetGate, BudgetExceeded

    gate = BudgetGate(max_budget=0.07)
    if gate.can_spend(0.045):
        gate.record_spend(0.045)
        # ... call FAL.ai ...
    else:
        raise BudgetExceeded(gate.remaining(), 0.045)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("hermesfy.budget_gate")

# Default cost estimates per model (USD per image)
MODEL_COSTS: dict[str, float] = {
    "fal-ai/flux/schnell": 0.003,
    "fal-ai/flux/dev": 0.025,
    "fal-ai/flux/pro": 0.05,
    "fal-ai/flux/1.1-pro": 0.04,
    "fal-ai/flux-pro/kontext": 0.04,
    "fal-ai/ideogram/v3/text-to-image": 0.06,
    "fal-ai/recraft/v4/pro/text-to-image": 0.04,
    "fal-ai/recraft/v3/text-to-image": 0.035,
    "fal-ai/bria/background/remove": 0.01,
    "fal-ai/topaz/upscale/image": 0.015,
}

DEFAULT_MAX_BUDGET = 0.07  # USD


# ── Exceptions ───────────────────────────────────────────────────────────────

class BudgetExceeded(Exception):
    """Raised when a flow would exceed its budget."""
    def __init__(self, remaining: float, attempted: float, model: str = ""):
        self.remaining = remaining
        self.attempted = attempted
        self.model = model
        msg = f"Budget exceeded: ${remaining:.4f} remaining, ${attempted:.4f} needed"
        if model:
            msg += f" (model: {model})"
        super().__init__(msg)


# ── Budget Gate ──────────────────────────────────────────────────────────────

@dataclass
class BudgetGate:
    """
    Cost control gate for image generation flows.

    Tracks cumulative spending and enforces a hard cap.
    """
    max_budget: float = DEFAULT_MAX_BUDGET
    _spent: float = field(default=0.0, repr=False)
    _history: list[dict] = field(default_factory=list, repr=False)

    @property
    def spent(self) -> float:
        return self._spent

    def remaining(self) -> float:
        return round(max(0.0, self.max_budget - self._spent), 6)

    def can_spend(self, amount: float) -> bool:
        """Check if we can afford this spend without exceeding the cap."""
        return self._spent + amount <= self.max_budget

    def estimate_cost(self, model: str) -> float:
        """Get estimated cost for a model."""
        return MODEL_COSTS.get(model, 0.025)

    def can_afford_model(self, model: str) -> bool:
        """Check if we can afford to run a specific model."""
        return self.can_spend(self.estimate_cost(model))

    def record_spend(self, amount: float, model: str = "", detail: str = "") -> None:
        """Record a spend. Raises BudgetExceeded if over cap."""
        if not self.can_spend(amount):
            raise BudgetExceeded(self.remaining(), amount, model)

        self._spent = round(self._spent + amount, 6)
        entry = {"amount": amount, "model": model, "detail": detail, "total": self._spent}
        self._history.append(entry)
        logger.info(
            "Budget: spent $%.4f (model=%s) | remaining $%.4f / $%.4f",
            amount, model or "?", self.remaining(), self.max_budget,
        )

    def record_and_check(self, model: str) -> bool:
        """Estimate cost for model, record it, return True if OK."""
        cost = self.estimate_cost(model)
        if self.can_spend(cost):
            self.record_spend(cost, model=model)
            return True
        return False

    def get_history(self) -> list[dict]:
        return list(self._history)

    def get_summary(self) -> dict:
        return {
            "max_budget": self.max_budget,
            "spent": self._spent,
            "remaining": self.remaining(),
            "num_calls": len(self._history),
            "by_model": self._model_breakdown(),
        }

    def _model_breakdown(self) -> dict[str, float]:
        breakdown: dict[str, float] = {}
        for entry in self._history:
            model = entry.get("model", "unknown")
            breakdown[model] = breakdown.get(model, 0.0) + entry["amount"]
        return breakdown

    def reset(self) -> None:
        """Reset the gate for a new flow."""
        self._spent = 0.0
        self._history.clear()
