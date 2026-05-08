"""VRH Gate — Anti-bypass hard block for Visual Reference Harness.

Prevents the DAG executor from running image generation workflows
that use visual references until the user has seen and approved
the StructuredSpec preview.

This is NOT a suggestion. This is a code-level gate. If you're
thinking "I'll just call genmedia directly" — this module exists
to make that impossible when references are involved.

Integration:
    from hermesfy.vrh_gate import VRHGate
    
    gate = VRHGate()
    gate.require_preview(workflow_id, reference_count=2)
    # ... agent shows preview, user confirms ...
    gate.approve(workflow_id)
    # ... now execute_workflow passes the gate ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("hermesfy.vrh_gate")

# ── VRH Block Reason (why execution was denied) ─────────────────────────

class VRHBlocked(Exception):
    """Raised when execution is blocked by the VRH Gate."""
    pass


# ── VRH Approval State ──────────────────────────────────────────────────

@dataclass
class VRHState:
    """Tracks the VRH approval state for a single workflow."""
    workflow_id: str
    requires_vrh: bool = False
    reference_count: int = 0
    preview_shown: bool = False
    approved: bool = False
    fidelity: float = 0.85
    preview_text: str = ""


# ── VRH Gate ────────────────────────────────────────────────────────────

class VRHGate:
    """Code-level gate that blocks image generation without VRH preview approval.
    
    Lifecycle:
        1. require_preview(workflow_id) → marks workflow as needing VRH
        2. Agent runs FASE 1 (VisualAnalyzer) + FASE 2 (Goldilocks + Preview)
        3. Agent shows preview_text to user
        4. User confirms → approve(workflow_id)
        5. execute_workflow() checks gate → passes
    """
    
    # In-memory state store (survives within a session)
    
    def __init__(self):
        self._states: dict[str, VRHState] = {}
    
    # ── Public API ──────────────────────────────────────────────────────
    
    def require_preview(
        self,
        workflow_id: str,
        reference_count: int = 0,
        has_references: bool = False,
    ) -> VRHState:
        """Mark a workflow as requiring VRH preview before execution.
        
        Call this when:
        - Workflow has image references (reference_images in config)
        - User prompt contains "cambiar X por Y", "igual pero con...", etc.
        - Any VRH trigger condition is met (see hermesfy-vrh-workflow skill)
        
        Args:
            workflow_id: The workflow to gate.
            reference_count: Number of reference images.
            has_references: Explicit flag from workflow config.
            
        Returns:
            VRHState with requires_vrh=True, blocking execution.
        """
        requires = has_references or reference_count > 0
        
        state = VRHState(
            workflow_id=workflow_id,
            requires_vrh=requires,
            reference_count=reference_count,
        )
        self._states[workflow_id] = state
        logger.info(
            "VRHGate: workflow %s requires VRH preview (refs=%d, requires=%s)",
            workflow_id, reference_count, requires,
        )
        return state
    
    def approve(self, workflow_id: str, fidelity: float = 0.85) -> VRHState:
        """Approve the VRH preview for a workflow, allowing execution.
        
        Call this AFTER the user has seen the preview and confirmed.
        """
        state = self._states.get(workflow_id)
        if state is None:
            state = VRHState(workflow_id=workflow_id, requires_vrh=True)
            self._states[workflow_id] = state
        
        state.approved = True
        state.preview_shown = True
        state.fidelity = fidelity
        logger.info("VRHGate: workflow %s APPROVED (fidelity=%.0f%%)", workflow_id, fidelity * 100)
        return state
    
    def reject(self, workflow_id: str) -> VRHState:
        """Reject/cancel the VRH state for a workflow."""
        state = self._states.get(workflow_id)
        if state is None:
            state = VRHState(workflow_id=workflow_id)
            self._states[workflow_id] = state
        
        state.approved = False
        state.preview_shown = True  # was shown, just rejected
        logger.info("VRHGate: workflow %s REJECTED by user", workflow_id)
        return state
    
    def set_preview(self, workflow_id: str, preview_text: str) -> None:
        """Store the preview text for a workflow (shown to user)."""
        state = self._states.get(workflow_id)
        if state is None:
            state = VRHState(workflow_id=workflow_id)
            self._states[workflow_id] = state
        
        state.preview_text = preview_text
        state.preview_shown = True
    
    def is_approved(self, workflow_id: str) -> bool:
        """Check if a workflow has passed the VRH gate."""
        state = self._states.get(workflow_id)
        if state is None:
            return True  # No state → no VRH required → allowed
        
        if not state.requires_vrh:
            return True  # VRH not required for this workflow
        
        return state.approved
    
    def check(self, workflow_id: str) -> None:
        """Check the gate. Raises VRHBlocked if execution is not allowed.
        
        Call this at the start of execute_workflow().
        """
        state = self._states.get(workflow_id)
        
        # No state = no VRH requirement = allowed
        if state is None:
            return
        
        if not state.requires_vrh:
            return
        
        if not state.preview_shown:
            raise VRHBlocked(
                f"⛔ VRH GATE BLOCKED: Workflow '{workflow_id}' has "
                f"{state.reference_count} reference image(s) but VRH preview "
                f"has NOT been shown. You MUST run FASE 1 (VisualAnalyzer) + "
                f"FASE 2 (Goldilocks + Preview) and get user approval before "
                f"executing this workflow. "
                f"Load skill 'hermesfy-vrh-workflow' for the full pipeline."
            )
        
        if not state.approved:
            raise VRHBlocked(
                f"⛔ VRH GATE BLOCKED: Workflow '{workflow_id}' preview was "
                f"shown but NOT approved by the user. Wait for user confirmation "
                f"('ok', 'dale', 'generá', 'vamos') before executing."
            )
        
        logger.info("VRHGate: workflow %s PASSED (approved, fidelity=%.0f%%)",
                     workflow_id, state.fidelity * 100)
    
    def get_state(self, workflow_id: str) -> Optional[VRHState]:
        """Get the VRH state for a workflow (or None if not tracked)."""
        return self._states.get(workflow_id)
    
    def clear(self, workflow_id: str) -> None:
        """Clear VRH state for a workflow (after execution or on reset)."""
        self._states.pop(workflow_id, None)
        logger.debug("VRHGate: cleared state for workflow %s", workflow_id)
    
    def reset(self) -> None:
        """Clear ALL VRH states (for testing)."""
        self._states.clear()


# ── Singleton ───────────────────────────────────────────────────────────

# Global gate instance — shared across all imports
gate = VRHGate()
