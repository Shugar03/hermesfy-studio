"""Unit tests for VRHGate — anti-bypass hard block for VRH workflows."""

import pytest
from hermesfy.vrh_gate import VRHGate, VRHBlocked, VRHState


class TestVRHGateBasic:
    """Basic VRHGate lifecycle tests."""

    def test_no_state_passes(self):
        """Workflows with no VRH state pass the gate."""
        gate = VRHGate()
        gate.check("wf-unknown")  # Should not raise

    def test_require_preview_creates_state(self):
        """require_preview creates a VRHState with requires_vrh=True."""
        gate = VRHGate()
        state = gate.require_preview("wf-1", reference_count=3, has_references=True)
        assert state.requires_vrh is True
        assert state.reference_count == 3
        assert state.approved is False
        assert state.preview_shown is False

    def test_require_preview_no_refs_no_require(self):
        """require_preview with 0 refs and has_references=False does NOT require VRH."""
        gate = VRHGate()
        state = gate.require_preview("wf-2", reference_count=0, has_references=False)
        assert state.requires_vrh is False

    def test_check_blocks_before_approve(self):
        """check raises VRHBlocked when preview not shown."""
        gate = VRHGate()
        gate.require_preview("wf-3", reference_count=2, has_references=True)
        with pytest.raises(VRHBlocked) as exc_info:
            gate.check("wf-3")
        assert "VRH GATE BLOCKED" in str(exc_info.value)
        assert "wf-3" in str(exc_info.value)
        assert "2 reference image" in str(exc_info.value)

    def test_check_blocks_after_reject(self):
        """check raises VRHBlocked when preview was rejected."""
        gate = VRHGate()
        gate.require_preview("wf-4", reference_count=1, has_references=True)
        gate.set_preview("wf-4", "some preview text")
        gate.reject("wf-4")
        with pytest.raises(VRHBlocked) as exc_info:
            gate.check("wf-4")
        assert "NOT approved" in str(exc_info.value)

    def test_approve_passes_gate(self):
        """approve allows execution to proceed."""
        gate = VRHGate()
        gate.require_preview("wf-5", reference_count=1, has_references=True)
        gate.set_preview("wf-5", "preview content")
        gate.approve("wf-5", fidelity=0.95)
        gate.check("wf-5")  # Should not raise

    def test_is_approved_returns_correctly(self):
        """is_approved reflects the approval state."""
        gate = VRHGate()
        # Unknown workflow = True (no VRH required)
        assert gate.is_approved("wf-unknown") is True

        gate.require_preview("wf-6", reference_count=1, has_references=True)
        assert gate.is_approved("wf-6") is False

        gate.set_preview("wf-6", "preview")
        gate.approve("wf-6")
        assert gate.is_approved("wf-6") is True

    def test_clear_removes_state(self):
        """clear removes the VRH state for a workflow."""
        gate = VRHGate()
        gate.require_preview("wf-7", reference_count=1, has_references=True)
        assert gate.get_state("wf-7") is not None
        gate.clear("wf-7")
        assert gate.get_state("wf-7") is None

    def test_reset_clears_all(self):
        """reset clears ALL states."""
        gate = VRHGate()
        gate.require_preview("wf-a", reference_count=1, has_references=True)
        gate.require_preview("wf-b", reference_count=2, has_references=True)
        assert len(gate._states) == 2
        gate.reset()
        assert len(gate._states) == 0


class TestVRHStateTransitions:
    """Test VRH state lifecycle transitions."""

    def test_full_happy_path(self):
        """Complete VRH lifecycle: require → preview → approve → check."""
        gate = VRHGate()

        # Step 1: Require
        state = gate.require_preview("wf-happy", reference_count=2, has_references=True)
        assert state.requires_vrh
        assert not state.approved

        # Step 2: Preview shown (doesn't unblock yet)
        gate.set_preview("wf-happy", "Preview: layout, palette, lighting...")
        state = gate.get_state("wf-happy")
        assert state.preview_shown
        assert not state.approved

        # Still blocked (preview shown but not approved)
        with pytest.raises(VRHBlocked):
            gate.check("wf-happy")

        # Step 3: User approves
        gate.approve("wf-happy", fidelity=0.95)
        state = gate.get_state("wf-happy")
        assert state.approved
        assert state.fidelity == 0.95

        # Step 4: Gate passes
        gate.check("wf-happy")  # No exception

    def test_reject_resets_approval(self):
        """Reject sets approved=False even if it was True before."""
        gate = VRHGate()
        gate.require_preview("wf-rej", reference_count=1, has_references=True)
        gate.set_preview("wf-rej", "preview")
        gate.approve("wf-rej")
        assert gate.get_state("wf-rej").approved

        gate.reject("wf-rej")
        assert not gate.get_state("wf-rej").approved
        with pytest.raises(VRHBlocked):
            gate.check("wf-rej")

    def test_approve_without_require_works(self):
        """approve on untracked workflow creates state and approves."""
        gate = VRHGate()
        gate.approve("wf-new", fidelity=0.60)
        state = gate.get_state("wf-new")
        assert state is not None
        assert state.approved
        gate.check("wf-new")  # Passes


class TestVRHGateSingleton:
    """Test the global gate singleton."""

    def test_singleton_exists(self):
        """The global 'gate' instance is importable and is a VRHGate."""
        from hermesfy.vrh_gate import gate
        assert isinstance(gate, VRHGate)

    def test_singleton_state_persists(self):
        """State set on the singleton is visible across imports."""
        from hermesfy.vrh_gate import gate
        gate.reset()
        gate.require_preview("wf-singleton", reference_count=1, has_references=True)
        assert gate.is_approved("wf-singleton") is False
        gate.approve("wf-singleton")
        assert gate.is_approved("wf-singleton") is True
        gate.reset()


class TestVRHBlockedException:
    """Test the VRHBlocked exception details."""

    def test_exception_is_importable(self):
        """VRHBlocked can be imported and caught."""
        from hermesfy.vrh_gate import VRHBlocked
        try:
            raise VRHBlocked("test message")
        except VRHBlocked as e:
            assert str(e) == "test message"

    def test_exception_inherits_from_exception(self):
        """VRHBlocked is a proper Exception subclass."""
        from hermesfy.vrh_gate import VRHBlocked
        assert issubclass(VRHBlocked, Exception)


class TestReferenceDetection:
    """Test _count_references function from execute_workflow."""

    def test_count_zero_for_no_references(self):
        """Workflow with no image_url returns 0."""
        from hermesfy.dag.graph import Node, NodeType, Workflow
        from hermesfy.tools.execute_workflow import _count_references

        wf = Workflow(
            id="wf-no-refs",
            name="no refs",
            nodes=[Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"})],
            edges=[],
        )
        assert _count_references(wf) == 0

    def test_count_single_image_url(self):
        """Single image_url in config is detected."""
        from hermesfy.dag.graph import Node, NodeType, Workflow
        from hermesfy.tools.execute_workflow import _count_references

        wf = Workflow(
            id="wf-one-ref",
            name="one ref",
            nodes=[Node(id="A", type=NodeType.IMG2IMG, config={
                "model": "flux-dev",
                "image_url": "https://example.com/img.jpg",
            })],
            edges=[],
        )
        assert _count_references(wf) == 1

    def test_count_multiple_references(self):
        """Multiple reference URLs across nodes are counted."""
        from hermesfy.dag.graph import Node, NodeType, Workflow
        from hermesfy.tools.execute_workflow import _count_references

        wf = Workflow(
            id="wf-multi-ref",
            name="multi ref",
            nodes=[
                Node(id="A", type=NodeType.IMG2IMG, config={
                    "model": "flux-dev",
                    "image_url": "https://example.com/layout.jpg",
                }),
                Node(id="B", type=NodeType.INPAINT, config={
                    "model": "inpaint",
                    "image_url": "https://example.com/layout.jpg",  # duplicate
                    "mask_url": "https://example.com/mask.png",
                }),
            ],
            edges=[],
        )
        # layout.jpg appears twice but should be de-duplicated
        assert _count_references(wf) == 2

    def test_count_reference_images_list(self):
        """List of reference_images in config is detected."""
        from hermesfy.dag.graph import Node, NodeType, Workflow
        from hermesfy.tools.execute_workflow import _count_references

        wf = Workflow(
            id="wf-list-ref",
            name="list ref",
            nodes=[Node(id="A", type=NodeType.IMAGE_GEN, config={
                "model": "seedream",
                "reference_images": [
                    "https://example.com/img1.jpg",
                    "https://example.com/img2.jpg",
                ],
            })],
            edges=[],
        )
        assert _count_references(wf) == 2
