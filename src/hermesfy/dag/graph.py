"""Graph model dataclasses: Node, Edge, Workflow, and validation logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


INVALID_WORKFLOW = "INVALID_WORKFLOW"
CYCLE_DETECTED = "CYCLE_DETECTED"
NODE_NOT_FOUND = "NODE_NOT_FOUND"


class NodeType(str, Enum):
    """Supported node types in the DAG workflow engine."""

    TEXT_PROMPT = "text_prompt"
    IMAGE_GEN = "image_gen"
    IMG2IMG = "img2img"
    UPSCALE = "upscale"
    SEED = "seed"
    INPAINT = "inpaint"
    OUTPAINT = "outpaint"
    IP_ADAPTER = "ip_adapter"
    REMOVE_BG = "remove_bg"
    FACE_RESTORE = "face_restore"


# Required config fields per node type
REQUIRED_CONFIG: dict[NodeType, set[str]] = {
    NodeType.TEXT_PROMPT: {"prompt"},
    NodeType.IMAGE_GEN: {"model"},
    NodeType.IMG2IMG: {"model", "image_url"},
    NodeType.UPSCALE: {"model", "image_url"},
    NodeType.SEED: {"seed"},
    NodeType.INPAINT: {"model", "image_url", "mask_url"},
    NodeType.OUTPAINT: {"model", "image_url"},
    NodeType.IP_ADAPTER: {"model", "image_url", "ip_adapter_weight", "style_strength_ratio"},
    NodeType.REMOVE_BG: {"model", "image_url"},
    NodeType.FACE_RESTORE: {"model", "image_url"},
}


@dataclass
class Node:
    """A single node in the DAG workflow graph.

    Attributes:
        id: Unique identifier within the workflow.
        type: The NodeType determining execution behavior.
        config: Arbitrary configuration dict (model, prompt, params, etc.).
        position: Optional (x, y) tuple for layout purposes.
    """

    id: str
    type: NodeType
    config: dict = field(default_factory=dict)
    position: tuple[int, int] = (0, 0)

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class Edge:
    """A directed edge connecting source → target nodes in the DAG."""

    source: str
    target: str

    def __hash__(self) -> int:
        return hash((self.source, self.target))


@dataclass
class Workflow:
    """A complete DAG workflow definition.

    Attributes:
        id: Unique identifier for this workflow instance.
        name: Human-readable name.
        nodes: All nodes in the workflow.
        edges: Directed edges between nodes.
    """

    id: str
    name: str
    nodes: list[Node]
    edges: list[Edge]

    def __repr__(self) -> str:
        return f"Workflow(id='{self.id}', name='{self.name}', nodes={len(self.nodes)}, edges={len(self.edges)})"


def validate_workflow(workflow: Workflow) -> None:
    """Validate a workflow for structural and semantic correctness.

    Checks:
        1. At least one node present.
        2. All node IDs are unique.
        3. All required config fields per node type are present.
        4. All edges reference existing node IDs.
        5. No cycles exist (DFS cycle detection).

    Raises:
        ValueError: With an error code prefix (INVALID_WORKFLOW, CYCLE_DETECTED, NODE_NOT_FOUND)
                    if validation fails.
    """
    # 1. At least one node
    if not workflow.nodes:
        raise ValueError(f"{INVALID_WORKFLOW}: Workflow must contain at least one node")

    # 2. Unique node IDs
    seen_ids: set[str] = set()
    for node in workflow.nodes:
        if node.id in seen_ids:
            raise ValueError(f"{INVALID_WORKFLOW}: Duplicate node id '{node.id}'")
        seen_ids.add(node.id)

    # 3. Required config fields per node type
    for node in workflow.nodes:
        required = REQUIRED_CONFIG.get(node.type, set())
        missing = required - set(node.config.keys())
        if missing:
            raise ValueError(
                f"{INVALID_WORKFLOW}: Node '{node.id}' (type={node.type.value}) "
                f"missing required config fields: {', '.join(sorted(missing))}"
            )

    # 4. Edge references valid node IDs
    node_ids = {n.id for n in workflow.nodes}
    for edge in workflow.edges:
        if edge.source not in node_ids:
            raise ValueError(
                f"{NODE_NOT_FOUND}: Edge source '{edge.source}' does not reference an existing node"
            )
        if edge.target not in node_ids:
            raise ValueError(
                f"{NODE_NOT_FOUND}: Edge target '{edge.target}' does not reference an existing node"
            )

    # 5. Cycle detection via Kahn's algorithm
    _detect_cycles(workflow.nodes, workflow.edges)


def _detect_cycles(nodes: list[Node], edges: list[Edge]) -> None:
    """Raise CYCLE_DETECTED if the graph contains any cycles (including self-loops).

    Uses Kahn's algorithm: if we cannot process all nodes topologically,
    a cycle exists.
    """
    # Build adjacency list and in-degree count
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    in_degree: dict[str, int] = {n.id: 0 for n in nodes}

    for edge in edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    # Kahn's algorithm: start with all nodes that have in-degree 0
    queue: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]
    processed: int = 0

    while queue:
        current = queue.pop(0)
        processed += 1
        for neighbor in adj[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if processed != len(nodes):
        raise ValueError(f"{CYCLE_DETECTED}: The workflow graph contains at least one cycle")
