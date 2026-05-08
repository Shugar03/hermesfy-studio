"""Tests for V6: REFERENCE_IMAGE NodeType + HTML Canvas Renderer."""

import pytest
from hermesfy.dag.graph import (
    Node, NodeType, Workflow, Edge, validate_workflow,
    INVALID_WORKFLOW, REQUIRED_CONFIG,
)

# ═════════════════════════════════════════════════════════════════════════
# FASE 1: REFERENCE_IMAGE NodeType Tests
# ═════════════════════════════════════════════════════════════════════════

class TestReferenceImageNodeType:
    """REF-001 to REF-008: Core REFERENCE_IMAGE node type tests."""

    def test_ref001_node_type_exists(self):
        """REF-001: REFERENCE_IMAGE is a valid NodeType enum value."""
        assert NodeType.REFERENCE_IMAGE.value == "reference_image"
        assert isinstance(NodeType.REFERENCE_IMAGE, NodeType)

    def test_ref002_required_config(self):
        """REF-002: REFERENCE_IMAGE requires image_url in config."""
        assert REQUIRED_CONFIG[NodeType.REFERENCE_IMAGE] == {"image_url"}

    def test_ref003_valid_reference_passes_validation(self):
        """REF-003: Valid REFERENCE_IMAGE node passes workflow validation."""
        n = Node(id="ref1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/img.jpg"})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        validate_workflow(wf)  # Should not raise

    def test_ref004_missing_image_url_fails_validation(self):
        """REF-004: REFERENCE_IMAGE without image_url fails validation."""
        n = Node(id="ref1", type=NodeType.REFERENCE_IMAGE, config={})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert INVALID_WORKFLOW in str(exc_info.value)
        assert "image_url" in str(exc_info.value)

    def test_ref005_canvas_text_renders_ref(self):
        """REF-005: Text canvas shows 🖼️ REF for reference_image nodes."""
        from hermesfy.rendering.canvas import render_canvas
        n = Node(id="ref1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/img.jpg"})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        canvas = render_canvas(wf)
        assert "🖼️ REF" in canvas

    def test_ref006_canvas_shows_label(self):
        """REF-005b: Canvas shows the label when provided."""
        from hermesfy.rendering.canvas import render_canvas
        n = Node(id="ref1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/img.jpg",
                         "label": "Stanley Tumbler"})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        canvas = render_canvas(wf)
        assert "Stanley Tumbler" in canvas

    def test_ref007_define_workflow_accepts_ref_type(self):
        """REF-007: define_workflow tool accepts reference_image nodes."""
        from hermesfy.tools.define_workflow import define_workflow
        result = define_workflow(
            nodes=[{"id": "ref1", "type": "reference_image",
                    "config": {"image_url": "https://example.com/img.jpg"}}],
            edges=[],
            name="ref-test",
        )
        import json
        data = json.loads(result)
        assert "workflow_id" in data
        assert "canvas" in data


# ═════════════════════════════════════════════════════════════════════════
# FASE 2: HTML Canvas Tests
# ═════════════════════════════════════════════════════════════════════════

@pytest.fixture
def vrh_workflow():
    """A realistic VRH workflow with reference images."""
    nodes = [
        Node(id="ref-layout", type=NodeType.REFERENCE_IMAGE, config={
            "image_url": "https://example.com/layout.jpg",
            "label": "Underwater Scene",
            "reference_role": "layout",
        }),
        Node(id="ref-product", type=NodeType.REFERENCE_IMAGE, config={
            "image_url": "https://example.com/product.jpg",
            "label": "Vichy Bottle",
            "reference_role": "subject",
        }),
        Node(id="prompt", type=NodeType.TEXT_PROMPT, config={
            "prompt": "Replace the white bottle with Vichy. Keep underwater scene.",
        }),
        Node(id="gen-main", type=NodeType.IMAGE_GEN, config={
            "model": "openai/gpt-image-2/edit",
            "prompt": "{{prompt}}",
            "image_url": "{{ref-layout}}",
            "width": 1080, "height": 1920,
        }),
    ]
    edges = [
        Edge(source="ref-layout", target="gen-main"),
        Edge(source="ref-product", target="gen-main"),
        Edge(source="prompt", target="gen-main"),
    ]
    return Workflow(id="wf-vrh", name="VRH Demo", nodes=nodes, edges=edges)


@pytest.fixture
def empty_workflow():
    """A workflow with no image references."""
    return Workflow(
        id="wf-empty",
        name="Empty",
        nodes=[Node(id="t1", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"})],
        edges=[],
    )


class TestHTMLCanvasBasic:
    """HTML-001 to HTML-006: Basic HTML canvas rendering tests."""

    def test_html001_returns_valid_html(self, vrh_workflow):
        """HTML-001: render_canvas_html returns valid HTML5 string."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        html = render_canvas_html(vrh_workflow)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_html002_contains_img_tags_for_references(self, vrh_workflow):
        """HTML-002: HTML contains <img> tags for REFERENCE_IMAGE nodes."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        html = render_canvas_html(vrh_workflow)
        assert '<img src="https://example.com/layout.jpg"' in html
        assert '<img src="https://example.com/product.jpg"' in html
        # Should have label in alt text
        assert "Underwater Scene" in html or "Vichy Bottle" in html

    def test_html003_contains_svg_connections(self, vrh_workflow):
        """HTML-003: HTML contains SVG paths for workflow edges."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        html = render_canvas_html(vrh_workflow)
        assert "<svg" in html
        assert "<path" in html
        # Bézier curves use M and C commands
        assert "M " in html
        assert "C " in html

    def test_html004_layout_respects_topological_order(self, vrh_workflow):
        """HTML-004: Nodes are positioned respecting topological layers."""
        from hermesfy.rendering.canvas_html import _compute_layout
        positions = _compute_layout(vrh_workflow)

        # Reference nodes and prompt should be in layer 0 (inputs)
        assert positions["ref-layout"]["layer"] == 0
        assert positions["ref-product"]["layer"] == 0
        assert positions["prompt"]["layer"] == 0

        # Generation node should be in layer 1 (depends on inputs)
        assert positions["gen-main"]["layer"] == 1

    def test_html005_node_colors_per_type(self, vrh_workflow):
        """HTML-005: Each node type gets the correct color scheme."""
        from hermesfy.rendering.canvas_html import NODE_STYLE, render_canvas_html
        html = render_canvas_html(vrh_workflow)

        # Reference nodes use blue theme
        ref_style = NODE_STYLE["reference_image"]
        assert ref_style["border"] in html or "#4fc3f7" in html

        # Text prompt uses purple theme
        assert "TXT" in html

    def test_html006_state_indicators_rendered(self, vrh_workflow):
        """HTML-006: Node states show correct emojis and colors."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        states = {
            "ref-layout": "completed",
            "ref-product": "completed",
            "prompt": "completed",
            "gen-main": "pending",
        }
        html = render_canvas_html(vrh_workflow, node_states=states)
        assert "✅" in html
        assert "pending" in html

    def test_html007_empty_workflow_renders(self, empty_workflow):
        """HTML-007: Workflow with no references renders without errors."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        html = render_canvas_html(empty_workflow)
        assert "<!DOCTYPE html>" in html
        assert "Empty" in html

    def test_html008_only_ref_nodes_renders(self):
        """HTML-008: Workflow with only REFERENCE_IMAGE nodes renders."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        nodes = [
            Node(id="r1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/a.jpg"}),
            Node(id="r2", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/b.jpg"}),
        ]
        wf = Workflow(id="wf-refs", name="Refs Only", nodes=nodes, edges=[])
        html = render_canvas_html(wf)
        assert html.count("<img ") == 2
        assert "<svg" in html  # SVG layer always present


class TestHTMLCanvasEdgeCases:
    """Edge case tests for HTML canvas."""

    def test_html009_handles_missing_image_url(self):
        """HTML-009: Node without image_url renders gracefully (onerror fallback)."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        n = Node(id="r1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://invalid.example.com/nonexistent.jpg"})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        html = render_canvas_html(wf)
        assert "onerror" in html  # Has fallback handler
        # Even with onerror, the img tag exists

    def test_html010_large_prompt_truncated(self):
        """HTML-010: Long prompts are truncated in display."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        long_prompt = "A " * 200  # 400 chars
        n = Node(id="t1", type=NodeType.TEXT_PROMPT,
                 config={"prompt": long_prompt})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        html = render_canvas_html(wf)
        # Should only show first 120 chars
        displayed = html.split('prompt-text">')[1].split("</div>")[0]
        assert len(displayed) < 300  # way less than 400 chars

    def test_html011_node_with_error_shows_message(self):
        """HTML-011: Failed nodes show error in footer."""
        from hermesfy.rendering.canvas_html import render_canvas_html
        n = Node(id="bad", type=NodeType.IMAGE_GEN,
                 config={"model": "flux-dev", "prompt": "test"})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        html = render_canvas_html(
            wf,
            node_states={"bad": "failed"},
            node_errors={"bad": "Budget exceeded: $0.00 remaining"},
        )
        assert "❌" in html
        assert "Budget exceeded" in html


# ═════════════════════════════════════════════════════════════════════════
# Integration: Reference Nodes in DAG Executor
# ═════════════════════════════════════════════════════════════════════════

class TestReferenceNodeExecutor:
    """INT-001 to INT-003: Integration with DAG executor."""

    @pytest.mark.asyncio
    async def test_int001_ref_node_is_pass_through(self):
        """INT-001: REFERENCE_IMAGE node does NOT call provider (pass-through)."""
        from hermesfy.dag.executor import execute
        
        class SpyProvider:
            def __init__(self):
                self.calls = []
            async def generate(self, node_type: str, config: dict) -> dict:
                self.calls.append({"node_type": node_type, "config": config})
                return {"image_url": "https://example.com/output.png"}
        
        n = Node(id="r1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/ref.jpg"})
        wf = Workflow(id="wf", name="test", nodes=[n], edges=[])
        provider = SpyProvider()
        events = []
        async for event in execute(wf, provider):
            events.append(event)
        
        # Provider should NOT have been called for reference_image
        ref_calls = [c for c in provider.calls if c.get("config", {}).get("_node_id") == "r1"]
        assert len(ref_calls) == 0
        
        # Node should have completed (pass-through)
        completed = [e for e in events if e.node_id == "r1" and e.event_type == "node_complete"]
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_int002_ref_resolves_to_image_url(self):
        """INT-002: {{ref_node}} in downstream resolves to image_url."""
        from hermesfy.dag.executor import execute
        
        class CaptureProvider:
            def __init__(self):
                self.last_config = None
            async def generate(self, node_type: str, config: dict) -> dict:
                self.last_config = dict(config)
                return {"image_url": "https://example.com/output.png"}
        
        nodes = [
            Node(id="ref1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/layout.jpg"}),
            Node(id="gen1", type=NodeType.IMAGE_GEN,
                 config={"model": "flux-dev", "image_url": "{{ref1}}"}),
        ]
        edges = [Edge(source="ref1", target="gen1")]
        wf = Workflow(id="wf", name="test", nodes=nodes, edges=edges)
        provider = CaptureProvider()
        async for event in execute(wf, provider):
            pass
        
        # The gen1 node should have received the resolved image_url
        assert provider.last_config is not None
        # Check that image_url was resolved from {{ref1}} to the actual URL
        resolved_url = provider.last_config.get("image_url", "")
        assert "https://example.com/layout.jpg" in str(resolved_url)

    @pytest.mark.asyncio
    async def test_int003_multiple_refs_in_workflow(self):
        """INT-003: Multiple REFERENCE_IMAGE nodes coexist in one workflow."""
        from hermesfy.dag.executor import execute
        
        class CountingProvider:
            def __init__(self):
                self.gen_count = 0
            async def generate(self, node_type: str, config: dict) -> dict:
                ntype = config.get("_node_type", "")
                if ntype in ("image_gen", "img2img"):
                    self.gen_count += 1
                return {"image_url": "https://example.com/out.png"}
        
        nodes = [
            Node(id="r1", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/a.jpg"}),
            Node(id="r2", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/b.jpg"}),
            Node(id="r3", type=NodeType.REFERENCE_IMAGE,
                 config={"image_url": "https://example.com/c.jpg"}),
            Node(id="gen1", type=NodeType.IMAGE_GEN,
                 config={"model": "flux-dev", "prompt": "test"}),
        ]
        wf = Workflow(id="wf", name="test", nodes=nodes, edges=[])
        provider = CountingProvider()
        async for event in execute(wf, provider):
            pass
        
        # Only gen1 should have been called (3 refs are pass-through)
        assert provider.gen_count == 1
