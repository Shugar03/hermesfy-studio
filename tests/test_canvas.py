"""Tests for text canvas rendering with various workflows and states."""

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow
from hermesfy.rendering.canvas import render_canvas, STATE_EMOJI


class TestRenderCanvas:
    """Tests for the render_canvas function."""

    def test_empty_workflow(self):
        """A workflow with no nodes renders header only."""
        wf = Workflow(id="wf1", name="empty", nodes=[], edges=[])
        canvas = render_canvas(wf)
        assert "empty" in canvas
        assert "Progress: 0/0" in canvas

    def test_single_node_no_edges(self):
        """Single node without edges renders with its config."""
        wf = Workflow(
            id="wf2",
            name="solo",
            nodes=[Node(id="n1", type=NodeType.TEXT_PROMPT, config={"prompt": "hello world"})],
            edges=[],
        )
        canvas = render_canvas(wf)
        assert "n1" in canvas
        assert "hello world" in canvas
        assert "TEXT" in canvas

    def test_linear_chain_renders_ordered(self):
        """Linear A→B→C renders all three nodes."""
        wf = Workflow(
            id="wf3",
            name="linear",
            nodes=[
                Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "a"}),
                Node(id="B", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"}),
                Node(id="C", type=NodeType.UPSCALE, config={"model": "clarity-upscaler", "image_url": "{{B}}"}),
            ],
            edges=[Edge(source="A", target="B"), Edge(source="B", target="C")],
        )
        canvas = render_canvas(wf)
        assert "A" in canvas
        assert "B" in canvas
        assert "C" in canvas

    def test_node_states_emoji(self):
        """Node states render correct emoji."""
        wf = Workflow(
            id="wf4",
            name="states",
            nodes=[Node(id="n1", type=NodeType.TEXT_PROMPT, config={"prompt": "test"})],
            edges=[],
        )
        states = {"n1": "completed"}
        canvas = render_canvas(wf, node_states=states)
        assert "✅" in canvas
        assert "Progress: 1/1" in canvas

    def test_failed_node_shows_error(self):
        """Failed node renders error message inline."""
        wf = Workflow(
            id="wf5",
            name="failed-node",
            nodes=[Node(id="bad", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"})],
            edges=[],
        )
        states = {"bad": "failed"}
        errors = {"bad": "Rate limit exceeded"}
        canvas = render_canvas(wf, node_states=states, node_errors=errors)
        assert "❌" in canvas
        assert "Rate limit exceeded" in canvas

    def test_retrying_node_shows_emoji(self):
        """Retrying state renders 🔄 emoji."""
        wf = Workflow(
            id="wf6",
            name="retrying",
            nodes=[Node(id="r1", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"})],
            edges=[],
        )
        states = {"r1": "retrying"}
        canvas = render_canvas(wf, node_states=states)
        assert "🔄" in canvas

    def test_quality_exhausted_shows_emoji(self):
        """Quality exhausted state renders 💀 emoji."""
        wf = Workflow(
            id="wf7",
            name="exhausted",
            nodes=[Node(id="q1", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"})],
            edges=[],
        )
        states = {"q1": "quality_exhausted"}
        canvas = render_canvas(wf, node_states=states)
        assert "💀" in canvas

    def test_progress_calculation(self):
        """Progress line shows completed/total correctly."""
        wf = Workflow(
            id="wf8",
            name="progress",
            nodes=[
                Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "x"}),
                Node(id="b", type=NodeType.TEXT_PROMPT, config={"prompt": "y"}),
                Node(id="c", type=NodeType.TEXT_PROMPT, config={"prompt": "z"}),
            ],
            edges=[],
        )
        states = {"a": "completed", "b": "completed", "c": "running"}
        canvas = render_canvas(wf, node_states=states)
        assert "Progress: 2/3" in canvas

    def test_seed_node_renders_seed_value(self):
        """SEED node shows the seed value in config summary."""
        wf = Workflow(
            id="wf9",
            name="seeded",
            nodes=[Node(id="s1", type=NodeType.SEED, config={"seed": 42})],
            edges=[],
        )
        canvas = render_canvas(wf)
        assert "seed=42" in canvas

    def test_all_state_emojis_defined(self):
        """All required state emojis are present in STATE_EMOJI."""
        required = {"pending", "running", "completed", "failed", "retrying", "quality_exhausted"}
        assert required.issubset(set(STATE_EMOJI.keys()))
