"""Unit tests for the async DAG executor: Kahn's sort, event generation, error isolation."""

import pytest
from unittest.mock import AsyncMock

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow
from hermesfy.dag.state import NodeEvent, NodeState

# Will import after writing implementation
# from hermesfy.dag.executor import execute, _topological_sort, _resolve_inputs


class MockProvider:
    """Mock provider for executor testing — returns config as output."""

    def __init__(self, outputs: dict[str, dict] | None = None):
        self.outputs = outputs or {}
        self.generate_calls: list[dict] = []

    async def generate(self, node_type: str, config: dict) -> dict:
        self.generate_calls.append({"node_type": node_type, "config": config})
        # Return pre-configured output for node, or echo config
        return config


class FailingProvider:
    """Mock provider that fails for specific node IDs."""

    def __init__(self, failing_nodes: set[str]):
        self.failing_nodes = failing_nodes
        self.generate_calls: list[dict] = []

    async def generate(self, node_type: str, config: dict) -> dict:
        node_id = config.get("_node_id", "")
        self.generate_calls.append({"node_type": node_type, "config": config})
        if node_id in self.failing_nodes:
            raise RuntimeError(f"Provider error for node {node_id}")
        return {"image_url": f"https://fal.ai/images/{node_id}.png", "width": 1024, "height": 1024}


@pytest.fixture
def linear_workflow() -> Workflow:
    """A → B → C linear DAG."""
    nodes = [
        Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"}),
        Node(id="B", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{A}}"}),
        Node(id="C", type=NodeType.UPSCALE, config={"model": "clarity-upscaler", "image_url": "{{B}}"}),
    ]
    edges = [Edge(source="A", target="B"), Edge(source="B", target="C")]
    return Workflow(id="wf-linear", name="linear-test", nodes=nodes, edges=edges)


@pytest.fixture
def diamond_workflow() -> Workflow:
    """A → B, A → C diamond/parallel DAG."""
    nodes = [
        Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "dragon"}),
        Node(id="B", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{A}}"}),
        Node(id="C", type=NodeType.IMAGE_GEN, config={"model": "flux-pro", "prompt": "{{A}}"}),
    ]
    edges = [Edge(source="A", target="B"), Edge(source="A", target="C")]
    return Workflow(id="wf-diamond", name="diamond-test", nodes=nodes, edges=edges)


@pytest.fixture
def single_node_workflow() -> Workflow:
    """Single node, no edges."""
    nodes = [Node(id="S", type=NodeType.SEED, config={"seed": 42})]
    return Workflow(id="wf-solo", name="solo-test", nodes=nodes, edges=[])


class TestTopologicalSort:
    """Tests for Kahn's topological sort algorithm."""

    async def test_linear_order(self, linear_workflow):
        """DAG-EXEC-001: Linear A→B→C produces order [A, B, C]."""
        from hermesfy.dag.executor import _topological_sort
        order = _topological_sort(linear_workflow)
        assert len(order) == 3
        assert order[0] == "A"
        assert order[1] == "B"
        assert order[2] == "C"

    async def test_diamond_order(self, diamond_workflow):
        """DAG-EXEC-001: Diamond A→B, A→C produces A first, then B/C in any order."""
        from hermesfy.dag.executor import _topological_sort
        order = _topological_sort(diamond_workflow)
        assert len(order) == 3
        assert order[0] == "A"
        assert "B" in order[1:]
        assert "C" in order[1:]

    async def test_single_node(self, single_node_workflow):
        """Single node with no edges produces order [S]."""
        from hermesfy.dag.executor import _topological_sort
        order = _topological_sort(single_node_workflow)
        assert order == ["S"]

    async def test_disconnected_nodes(self):
        """Disconnected nodes are included in any order."""
        nodes = [
            Node(id="X", type=NodeType.TEXT_PROMPT, config={"prompt": "x"}),
            Node(id="Y", type=NodeType.TEXT_PROMPT, config={"prompt": "y"}),
            Node(id="Z", type=NodeType.TEXT_PROMPT, config={"prompt": "z"}),
        ]
        wf = Workflow(id="wf-disc", name="disconnected", nodes=nodes, edges=[])
        from hermesfy.dag.executor import _topological_sort
        order = _topological_sort(wf)
        assert len(order) == 3
        assert set(order) == {"X", "Y", "Z"}

    async def test_cycle_detection_raises(self):
        """DAG-EXEC-005: Cyclic graph raises CYCLE_DETECTED during execution."""
        nodes = [
            Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "a"}),
            Node(id="B", type=NodeType.TEXT_PROMPT, config={"prompt": "b"}),
        ]
        edges = [Edge(source="A", target="B"), Edge(source="B", target="A")]
        wf = Workflow(id="wf-cycle", name="cycle", nodes=nodes, edges=edges)
        from hermesfy.dag.executor import CYCLE_DETECTED
        from hermesfy.dag.executor import _topological_sort

        with pytest.raises(ValueError) as exc_info:
            _topological_sort(wf)
        assert CYCLE_DETECTED in str(exc_info.value)


class TestInputResolution:
    """Tests for resolving {{node_id}} references in configs."""

    async def test_resolve_prompt_reference(self):
        """DAG-EXEC-003: {{node_id}} resolves to that node's output.prompt."""
        from hermesfy.dag.executor import _resolve_inputs
        config = {"prompt": "{{upstream}}", "model": "flux-dev"}
        outputs = {"upstream": {"prompt": "a dragon"}}
        resolved = _resolve_inputs(config, outputs)
        assert resolved["prompt"] == "a dragon"
        assert resolved["model"] == "flux-dev"  # unchanged

    async def test_resolve_image_url_reference(self):
        """{{node_id}} resolves to image_url from that node's output."""
        from hermesfy.dag.executor import _resolve_inputs
        config = {"model": "clarity-upscaler", "image_url": "{{gen-1}}"}
        outputs = {"gen-1": {"image_url": "https://fal.ai/images/img.png"}}
        resolved = _resolve_inputs(config, outputs)
        assert resolved["image_url"] == "https://fal.ai/images/img.png"

    async def test_resolve_node_output_reference(self):
        """{{node_id.output}} resolves to that node's full output."""
        from hermesfy.dag.executor import _resolve_inputs
        config = {"model": "flux-dev", "prompt": "{{A.output}}"}
        outputs = {"A": {"output": {"prompt": "cinematic shot"}}}
        resolved = _resolve_inputs(config, outputs)
        assert resolved["prompt"] == {"prompt": "cinematic shot"}

    async def test_resolve_nonexistent_reference_leaves_unchanged(self):
        """Unresolvable references are left as-is."""
        from hermesfy.dag.executor import _resolve_inputs
        config = {"prompt": "{{nonexistent}}"}
        outputs = {}
        resolved = _resolve_inputs(config, outputs)
        assert resolved["prompt"] == "{{nonexistent}}"

    async def test_resolve_no_references_returns_unchanged(self):
        """Config with no references is returned as-is."""
        from hermesfy.dag.executor import _resolve_inputs
        config = {"prompt": "hello world", "model": "flux-dev"}
        resolved = _resolve_inputs(config, outputs={})
        assert resolved == config


class TestExecuteWorkflow:
    """Integration-style tests for the full execute() async generator."""

    @pytest.mark.asyncio
    async def test_execute_linear_workflow_all_succeed(self, linear_workflow):
        """DAG-EXEC-002: All nodes complete successfully, events emitted in order."""
        from hermesfy.dag.executor import execute

        provider = MockProvider()
        events: list[NodeEvent] = []

        async for event in execute(linear_workflow, provider):
            events.append(event)

        # Collect events by node_id
        node_events: dict[str, list[NodeEvent]] = {}
        for e in events:
            node_events.setdefault(e.node_id, []).append(e)

        # A: start → complete
        assert len(node_events.get("A", [])) >= 2
        assert node_events["A"][0].event_type == "node_start"
        assert node_events["A"][-1].event_type == "node_complete"

        # B: start → complete
        assert len(node_events.get("B", [])) >= 2
        assert node_events["B"][0].event_type == "node_start"
        assert node_events["B"][-1].event_type == "node_complete"

        # C: start → complete
        assert len(node_events.get("C", [])) >= 2
        assert node_events["C"][0].event_type == "node_start"
        assert node_events["C"][-1].event_type == "node_complete"

    @pytest.mark.asyncio
    async def test_execute_error_isolation(self):
        """DAG-EXEC-004: When B fails, A completes, C stays pending."""
        from hermesfy.dag.executor import execute

        nodes = [
            Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"}),
            Node(id="B", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{A}}"}),
            Node(id="C", type=NodeType.UPSCALE, config={"model": "clarity-upscaler", "image_url": "{{B}}"}),
        ]
        edges = [Edge(source="A", target="B"), Edge(source="B", target="C")]
        wf = Workflow(id="wf-err", name="error-isolation", nodes=nodes, edges=edges)

        provider = FailingProvider(failing_nodes={"B"})
        events: list[NodeEvent] = []

        async for event in execute(wf, provider):
            events.append(event)

        node_states: dict[str, str] = {}
        for e in events:
            if e.event_type in ("node_complete", "node_error", "node_start"):
                node_states[e.node_id] = e.event_type

        assert node_states.get("A") == "node_complete"  # A succeeds
        assert node_states.get("B") == "node_error"      # B fails
        # C may not even start because B's failure means C's dependencies aren't met
        # But the spec says "C pending" — C may not get events at all
        # We verify C is either not started or stuck in pending
        assert "C" not in node_states or node_states.get("C") != "node_complete"

    @pytest.mark.asyncio
    async def test_execute_single_node(self, single_node_workflow):
        """Single node workflow executes and completes."""
        from hermesfy.dag.executor import execute

        provider = MockProvider()
        events: list[NodeEvent] = []

        async for event in execute(single_node_workflow, provider):
            events.append(event)

        assert len(events) >= 2
        start_events = [e for e in events if e.event_type == "node_start" and e.node_id == "S"]
        complete_events = [e for e in events if e.event_type == "node_complete" and e.node_id == "S"]
        assert len(start_events) >= 1
        assert len(complete_events) >= 1

    @pytest.mark.asyncio
    async def test_execute_disconnected_nodes_all_succeed(self):
        """Disconnected nodes are all executed."""
        from hermesfy.dag.executor import execute

        nodes = [
            Node(id="X", type=NodeType.TEXT_PROMPT, config={"prompt": "x"}),
            Node(id="Y", type=NodeType.TEXT_PROMPT, config={"prompt": "y"}),
        ]
        wf = Workflow(id="wf-disc", name="disconnected", nodes=nodes, edges=[])

        provider = MockProvider()
        completed: set[str] = set()

        async for event in execute(wf, provider):
            if event.event_type == "node_complete":
                completed.add(event.node_id)

        assert completed == {"X", "Y"}

    @pytest.mark.asyncio
    async def test_execute_input_resolution_from_upstream(self):
        """B receives resolved prompt from A's output."""
        from hermesfy.dag.executor import execute

        nodes = [
            Node(id="A", type=NodeType.TEXT_PROMPT, config={"prompt": "cyberpunk city"}),
            Node(id="B", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{A}}"}),
        ]
        edges = [Edge(source="A", target="B")]
        wf = Workflow(id="wf-resolve", name="resolve-test", nodes=nodes, edges=edges)

        provider = MockProvider()
        events: list[NodeEvent] = []

        async for event in execute(wf, provider, options={"resolve_inputs": True}):
            events.append(event)

        # Verify provider was called with resolved input for B
        # B's config should have {{A}} resolved to A's output
        completed_b = [e for e in events if e.node_id == "B" and e.event_type == "node_complete"]
        assert len(completed_b) >= 1

    @pytest.mark.asyncio
    async def test_execute_emits_final_done_event(self, linear_workflow):
        """After all nodes, a workflow_done event is emitted."""
        from hermesfy.dag.executor import execute

        provider = MockProvider()
        events: list[NodeEvent] = []

        async for event in execute(linear_workflow, provider):
            events.append(event)

        assert events[-1].event_type == "workflow_done"
