"""Unit tests for DAG graph models: Node, Edge, Workflow, NodeType, validation."""

import pytest
from hermesfy.dag.graph import Node, Edge, Workflow, NodeType, validate_workflow
from hermesfy.dag.graph import INVALID_WORKFLOW, CYCLE_DETECTED, NODE_NOT_FOUND


class TestNodeType:
    """Tests for the NodeType enum."""

    def test_node_type_values(self):
        """NodeType enum MUST contain all five node types."""
        assert NodeType.TEXT_PROMPT.value == "text_prompt"
        assert NodeType.IMAGE_GEN.value == "image_gen"
        assert NodeType.IMG2IMG.value == "img2img"
        assert NodeType.UPSCALE.value == "upscale"
        assert NodeType.SEED.value == "seed"

    def test_node_type_from_string(self):
        """NodeType can be constructed from a string value."""
        assert NodeType("text_prompt") == NodeType.TEXT_PROMPT
        assert NodeType("image_gen") == NodeType.IMAGE_GEN

    def test_node_type_invalid_raises(self):
        """Invalid node type string raises ValueError."""
        with pytest.raises(ValueError):
            NodeType("invalid_type")


class TestNode:
    """Tests for the Node dataclass."""

    def test_node_creation_with_defaults(self):
        """Node can be created with minimal required fields."""
        node = Node(id="n1", type=NodeType.TEXT_PROMPT, config={"prompt": "test"})
        assert node.id == "n1"
        assert node.type == NodeType.TEXT_PROMPT
        assert node.config == {"prompt": "test"}
        assert node.position == (0, 0)  # default

    def test_node_creation_with_position(self):
        """Node can be created with an explicit position."""
        node = Node(
            id="n2", type=NodeType.IMAGE_GEN,
            config={"model": "flux-dev"}, position=(10, 20)
        )
        assert node.position == (10, 20)

    def test_node_equality_by_value(self):
        """Two nodes with same fields are equal."""
        n1 = Node(id="a", type=NodeType.SEED, config={"seed": 42})
        n2 = Node(id="a", type=NodeType.SEED, config={"seed": 42})
        assert n1 == n2

    def test_node_not_equal_different_id(self):
        """Nodes with different IDs are not equal."""
        n1 = Node(id="a", type=NodeType.SEED, config={"seed": 42})
        n2 = Node(id="b", type=NodeType.SEED, config={"seed": 42})
        assert n1 != n2

    def test_node_hashable(self):
        """Node can be used in a set."""
        n = Node(id="n1", type=NodeType.TEXT_PROMPT, config={"prompt": "x"})
        s = {n}
        assert n in s


class TestEdge:
    """Tests for the Edge dataclass."""

    def test_edge_creation(self):
        """Edge connects a source node to a target node."""
        edge = Edge(source="n1", target="n2")
        assert edge.source == "n1"
        assert edge.target == "n2"

    def test_edge_equality(self):
        """Two edges with same source and target are equal."""
        e1 = Edge(source="a", target="b")
        e2 = Edge(source="a", target="b")
        assert e1 == e2

    def test_edge_not_equal_different_source(self):
        """Edges with different sources are not equal."""
        e1 = Edge(source="a", target="b")
        e2 = Edge(source="x", target="b")
        assert e1 != e2

    def test_edge_hashable(self):
        """Edge can be used in a set."""
        e = Edge(source="n1", target="n2")
        s = {e}
        assert e in s


class TestWorkflow:
    """Tests for the Workflow dataclass."""

    def test_workflow_creation(self):
        """Workflow holds an id, name, nodes list, and edges list."""
        nodes = [
            Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "hello"}),
            Node(id="b", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"}),
        ]
        edges = [Edge(source="a", target="b")]
        wf = Workflow(id="wf-1", name="test-flow", nodes=nodes, edges=edges)
        assert wf.id == "wf-1"
        assert wf.name == "test-flow"
        assert len(wf.nodes) == 2
        assert len(wf.edges) == 1

    def test_workflow_empty_nodes(self):
        """Workflow with no nodes is allowed (validated separately)."""
        wf = Workflow(id="empty", name="empty-flow", nodes=[], edges=[])
        assert len(wf.nodes) == 0

    def test_workflow_repr(self):
        """String representation includes workflow id and name."""
        nodes = [Node(id="x", type=NodeType.SEED, config={"seed": 1})]
        wf = Workflow(id="wf-1", name="myflow", nodes=nodes, edges=[])
        r = repr(wf)
        assert "wf-1" in r
        assert "myflow" in r


class TestValidateWorkflow:
    """Tests for workflow validation: cycle detection, missing refs, required fields."""

    def test_valid_linear_workflow_passes(self):
        """WF-DEF-001: A valid linear DAG passes validation."""
        nodes = [
            Node(id="prompt", type=NodeType.TEXT_PROMPT, config={"prompt": "a cat"}),
            Node(id="gen", type=NodeType.IMAGE_GEN, config={"model": "flux-dev"}),
        ]
        edges = [Edge(source="prompt", target="gen")]
        wf = Workflow(id="wf1", name="linear", nodes=nodes, edges=edges)
        # Should not raise
        validate_workflow(wf)

    def test_single_node_workflow_passes(self):
        """A workflow with a single node and no edges is valid."""
        nodes = [Node(id="solo", type=NodeType.TEXT_PROMPT, config={"prompt": "test"})]
        wf = Workflow(id="wf2", name="solo", nodes=nodes, edges=[])
        validate_workflow(wf)

    def test_disconnected_nodes_passes(self):
        """Nodes without edges are valid (disconnected sub-DAGs allowed)."""
        nodes = [
            Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "x"}),
            Node(id="b", type=NodeType.TEXT_PROMPT, config={"prompt": "y"}),
        ]
        wf = Workflow(id="wf3", name="disconnected", nodes=nodes, edges=[])
        validate_workflow(wf)

    def test_empty_nodes_raises_invalid_workflow(self):
        """A workflow with zero nodes is invalid."""
        wf = Workflow(id="wf4", name="empty", nodes=[], edges=[])
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert INVALID_WORKFLOW in str(exc_info.value)

    def test_edge_refs_missing_source_node(self):
        """WF-DEF-003: Edge referencing a non-existent source node is rejected."""
        nodes = [Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "x"})]
        edges = [Edge(source="nonexistent", target="a")]
        wf = Workflow(id="wf5", name="bad-edge", nodes=nodes, edges=edges)
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert NODE_NOT_FOUND in str(exc_info.value)

    def test_edge_refs_missing_target_node(self):
        """Edge referencing a non-existent target node is rejected."""
        nodes = [Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "x"})]
        edges = [Edge(source="a", target="nonexistent")]
        wf = Workflow(id="wf6", name="bad-edge2", nodes=nodes, edges=edges)
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert NODE_NOT_FOUND in str(exc_info.value)

    def test_direct_cycle_detected(self):
        """WF-DEF-003: A→B→A cycle is rejected as CYCLE_DETECTED."""
        nodes = [
            Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "x"}),
            Node(id="b", type=NodeType.TEXT_PROMPT, config={"prompt": "y"}),
        ]
        edges = [Edge(source="a", target="b"), Edge(source="b", target="a")]
        wf = Workflow(id="wf7", name="cycle", nodes=nodes, edges=edges)
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert CYCLE_DETECTED in str(exc_info.value)

    def test_three_node_cycle_detected(self):
        """WF-DEF-003: A→B→C→A three-node cycle is rejected."""
        nodes = [
            Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "a"}),
            Node(id="b", type=NodeType.TEXT_PROMPT, config={"prompt": "b"}),
            Node(id="c", type=NodeType.TEXT_PROMPT, config={"prompt": "c"}),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="b", target="c"),
            Edge(source="c", target="a"),
        ]
        wf = Workflow(id="wf8", name="cycle3", nodes=nodes, edges=edges)
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert CYCLE_DETECTED in str(exc_info.value)

    def test_self_loop_detected(self):
        """A node with an edge to itself is a cycle."""
        nodes = [Node(id="a", type=NodeType.TEXT_PROMPT, config={"prompt": "x"})]
        edges = [Edge(source="a", target="a")]
        wf = Workflow(id="wf9", name="self-loop", nodes=nodes, edges=edges)
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert CYCLE_DETECTED in str(exc_info.value)

    def test_text_prompt_requires_prompt_field(self):
        """WF-DEF-004: text_prompt node must have 'prompt' in config."""
        nodes = [Node(id="bad", type=NodeType.TEXT_PROMPT, config={})]
        wf = Workflow(id="wf10", name="bad-config", nodes=nodes, edges=[])
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert INVALID_WORKFLOW in str(exc_info.value)
        assert "prompt" in str(exc_info.value).lower()

    def test_image_gen_requires_model_field(self):
        """WF-DEF-004: image_gen node must have 'model' in config."""
        nodes = [Node(id="bad", type=NodeType.IMAGE_GEN, config={"prompt": "x"})]
        wf = Workflow(id="wf11", name="bad-config", nodes=nodes, edges=[])
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert INVALID_WORKFLOW in str(exc_info.value)
        # 'model' is the required field for image_gen
        assert "model" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_image_gen_blank_prompt_supported_by_input_ref(self):
        """image_gen may use {{node_id}} reference instead of literal prompt."""
        nodes = [Node(id="gen", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{upstream}}"})]
        wf = Workflow(id="wf12", name="ref-prompt", nodes=nodes, edges=[])
        # This should validate because config has the required 'model' field
        validate_workflow(wf)

    def test_duplicate_node_ids_raises(self):
        """Two nodes with the same id are rejected."""
        nodes = [
            Node(id="dup", type=NodeType.TEXT_PROMPT, config={"prompt": "a"}),
            Node(id="dup", type=NodeType.TEXT_PROMPT, config={"prompt": "b"}),
        ]
        wf = Workflow(id="wf13", name="dup", nodes=nodes, edges=[])
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(wf)
        assert "duplicate" in str(exc_info.value).lower()

    def test_complex_dag_passes_validation(self):
        """A diamond-shaped DAG with valid configs passes validation."""
        nodes = [
            Node(id="prompt", type=NodeType.TEXT_PROMPT, config={"prompt": "dragon"}),
            Node(id="gen1", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{prompt}}"}),
            Node(id="gen2", type=NodeType.IMAGE_GEN, config={"model": "flux-dev", "prompt": "{{prompt}}"}),
            Node(id="upscale", type=NodeType.UPSCALE, config={"model": "clarity-upscaler", "image_url": "{{gen1}}"}),
        ]
        edges = [
            Edge(source="prompt", target="gen1"),
            Edge(source="prompt", target="gen2"),
            Edge(source="gen1", target="upscale"),
        ]
        wf = Workflow(id="wf14", name="diamond", nodes=nodes, edges=edges)
        validate_workflow(wf)
