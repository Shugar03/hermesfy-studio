"""Async DAG executor using Kahn's topological sort and sequential node execution.

V4 Integration: ExecutionSpec, BudgetGate, SeedPropagator, IntermediateValidator.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, AsyncGenerator, Optional

from hermesfy.dag.graph import Edge, Node, NodeType, Workflow, CYCLE_DETECTED
from hermesfy.dag.state import NodeEvent, NodeRun, NodeState

# V4 modules
from hermesfy.execution_spec import ExecutionSpec, SpecValidationError
from hermesfy.budget_gate import BudgetGate, BudgetExceeded, MODEL_COSTS
from hermesfy.seed_propagator import SeedPropagator
from hermesfy.intermediate_validator import IntermediateValidator
from hermesfy.model_selector import ModelSelector, AdType, QualityLevel
from hermesfy.intent_router import IntentRouter
logger = logging.getLogger("hermesfy.executor")

# Re-export for test visibility
__all__ = ["execute", "_topological_sort", "_resolve_inputs"]


_REF_PATTERN = re.compile(r"\{\{(\w[\w.-]*)\}\}")


def _topological_sort(workflow: Workflow) -> list[str]:
    """Perform Kahn's topological sort and return node IDs in execution order.

    Args:
        workflow: The workflow to sort.

    Returns:
        List of node IDs in topological order.

    Raises:
        ValueError: With CYCLE_DETECTED prefix if the graph contains a cycle.
    """
    nodes = workflow.nodes
    edges = workflow.edges

    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    in_degree: dict[str, int] = {n.id: 0 for n in nodes}

    for edge in edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    # Start with all nodes that have no incoming edges
    queue: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        current = queue.pop(0)
        order.append(current)
        for neighbor in adj[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError(f"{CYCLE_DETECTED}: The workflow graph contains at least one cycle")

    return order


def _resolve_inputs(config: dict, outputs: dict[str, Any]) -> dict:
    """Resolve {{node_id}} and {{node_id.output}} references in config values.

    Replaces pattern {{node_id}} with:
      - outputs[node_id]["prompt"] if available
      - outputs[node_id]["image_url"] if available
      - outputs[node_id] as fallback (entire output dict)

    Replaces pattern {{node_id.output}} with outputs[node_id].

    Args:
        config: The node configuration dict to resolve.
        outputs: A mapping of node_id → output data from completed upstream nodes.

    Returns:
        A new dict with references resolved.
    """
    resolved: dict = {}

    for key, value in config.items():
        if not isinstance(value, str):
            resolved[key] = value
            continue

        # Find all {{...}} references in the string
        matches = list(_REF_PATTERN.finditer(value))
        if not matches:
            resolved[key] = value
            continue

        # If the value is entirely a single reference, replace with the actual value
        full_match = _REF_PATTERN.fullmatch(value.strip())
        if full_match:
            ref = full_match.group(1)
            resolved[key] = _lookup_ref(ref, outputs)
        else:
            # Multiple references or mixed content — substitute inline
            result = value
            for m in matches:
                ref = m.group(1)
                replacement = _lookup_ref(ref, outputs)
                if isinstance(replacement, dict):
                    replacement = str(replacement)
                result = result.replace(m.group(0), str(replacement) if replacement else m.group(0))
            resolved[key] = result

    return resolved


def _lookup_ref(ref: str, outputs: dict[str, Any]) -> Any:
    """Look up a reference in the outputs dict.

    ref can be:
      - "node_id" → resolves to outputs[node_id]["prompt"] or outputs[node_id]
      - "node_id.output" → resolves to outputs[node_id]
      - "node_id.image_url" → resolves to outputs[node_id]["image_url"]
    """
    parts = ref.split(".")
    node_id = parts[0]
    node_output = outputs.get(node_id)

    if node_output is None:
        return f"{{{{{ref}}}}}"

    if len(parts) == 1:
        # "node_id" — resolve to best value
        if isinstance(node_output, dict):
            return node_output.get("prompt", node_output.get("image_url", node_output.get("url", node_output)))
        return node_output

    # "node_id.field" — resolve nested key
    key = parts[1]
    if isinstance(node_output, dict) and key in node_output:
        return node_output[key]

    return f"{{{{{ref}}}}}"


async def execute(
    workflow: Workflow,
    provider: Any,
    options: dict | None = None,
) -> AsyncGenerator[NodeEvent, None]:
    """Execute a workflow, yielding NodeEvents for each state transition.

    V4 Integration:
    - ExecutionSpec: Validates workflow before execution (if spec provided)
    - BudgetGate: Enforces $0.07/flow spending cap (unless disabled)
    - SeedPropagator: Propagates seeds between nodes for consistency
    - IntermediateValidator: Validates outputs between generative steps

    Args:
        workflow: The Workflow to execute.
        provider: An object with an async generate(node_type, config) → dict method.
        options: Optional execution flags:
            - resolve_inputs: bool (default True)
            - spec: ExecutionSpec for pre-validation (optional)
            - budget: float max budget in USD (default 0.07, None to disable)
            - validate_steps: bool validate intermediate outputs (default False)
            - gemini_api_key: str for intermediate validation (optional)
            - prompt: str original user prompt for validation (optional)

    Yields:
        NodeEvent objects for each state change.
    """
    options = options or {}
    resolve_inputs = options.get("resolve_inputs", True)

    # ── V4: ExecutionSpec validation ───────────────────────────────────────
    spec = options.get("spec")
    if spec is not None:
        if not isinstance(spec, ExecutionSpec):
            try:
                spec = ExecutionSpec.from_dict(spec) if isinstance(spec, dict) else spec
            except Exception as e:
                logger.warning("Invalid ExecutionSpec, skipping validation: %s", e)
                spec = None

        if spec is not None:
            errors = spec.validate()
            if errors:
                yield NodeEvent(
                    node_id="__workflow__",
                    event_type="workflow_error",
                    data={"error": f"ExecutionSpec validation failed: {errors}"},
                )
                return
            logger.info("ExecutionSpec validated OK (target_model=%s, budget=$%.4f)",
                        spec.target_model, spec.total_budget)

    # ── V4: BudgetGate setup ───────────────────────────────────────────────
    budget_limit = options.get("budget", 0.07)
    budget_gate: BudgetGate | None = None
    if budget_limit is not None:
        budget_gate = BudgetGate(max_budget=budget_limit)
        logger.info("BudgetGate initialized: $%.4f cap", budget_limit)

    # ── V4: SeedPropagator setup ──────────────────────────────────────────
    seed_propagator = SeedPropagator()

    # ── V4: IntermediateValidator setup ────────────────────────────────────
    intermediate_validator: IntermediateValidator | None = None
    gemini_key = options.get("gemini_api_key") or os.environ.get("GOOGLE_API_KEY")
    if options.get("validate_steps") and gemini_key:
        intermediate_validator = IntermediateValidator(api_key=gemini_key)
        logger.info("IntermediateValidator enabled (min_confidence=%.2f)",
                     intermediate_validator.min_confidence)

    # Original prompt for validation
    original_prompt = options.get("prompt", "")

    # ── V4: ModelSelector setup ────────────────────────────────────────────
    model_selector = ModelSelector()
    ad_type_str = options.get("ad_type", "product_hero")
    try:
        ad_type = AdType(ad_type_str)
    except ValueError:
        ad_type = AdType.PRODUCT_HERO
    quality_str = options.get("quality", "balanced")
    try:
        quality = QualityLevel(quality_str)
    except ValueError:
        quality = QualityLevel.STANDARD

    # Topological sort
    order = _topological_sort(workflow)

    # Build adjacency for dependency tracking
    node_map: dict[str, Node] = {n.id: n for n in workflow.nodes}
    outputs: dict[str, Any] = {}
    node_states: dict[str, NodeState] = {n.id: NodeState.PENDING for n in workflow.nodes}

    # Build reverse dependency map (who depends on whom)
    dependents: dict[str, set[str]] = {n.id: set() for n in workflow.nodes}
    for edge in workflow.edges:
        dependents[edge.target].add(edge.source)

    # Execute in topological order
    for node_id in order:
        node = node_map[node_id]

        # Check if any upstream dependency failed — if so, skip this node
        upstream_failed = any(
            node_states.get(dep) == NodeState.FAILED
            for dep in dependents.get(node_id, set())
        )
        if upstream_failed:
            node_states[node_id] = NodeState.PENDING  # remains pending
            continue

        node_states[node_id] = NodeState.RUNNING
        yield NodeEvent(node_id=node_id, event_type="node_start", data={"config": dict(node.config)})

        # Resolve inputs from upstream outputs
        config = dict(node.config)
        if resolve_inputs:
            config = _resolve_inputs(config, outputs)
            config["_node_id"] = node_id
            config["_node_type"] = node.type.value

        # Pass-through nodes: text_prompt and seed don't call the provider
        PASS_THROUGH_TYPES = {NodeType.TEXT_PROMPT, NodeType.SEED, NodeType.REFERENCE_IMAGE}
        if node.type in PASS_THROUGH_TYPES:
            outputs[node_id] = config
            node_states[node_id] = NodeState.COMPLETED
            yield NodeEvent(
                node_id=node_id,
                event_type="node_complete",
                data={"output": config},
            )
            continue

        # ── V4: Seed propagation ──────────────────────────────────────────
        model = config.get("model", "")

        # ── V4: Auto-select model if not specified ────────────────────────
        if not model and node.type.value in ("image_gen", "img2img"):
            model = model_selector.select(ad_type=ad_type, quality=quality)
            config["model"] = model
            logger.info("Auto-selected model: %s for node %s (ad_type=%s, quality=%s)",
                         model, node_id, ad_type.value, quality.value)

        if node.type.value in ("image_gen", "img2img"):
            requested_seed = config.get("seed", -1)
            resolved_seed = seed_propagator.resolve_seed(requested_seed)
            config = seed_propagator.propagate(resolved_seed, config, model)
            logger.debug("Seed propagated: %d for node %s (model=%s)",
                         resolved_seed, node_id, model)

        # ── V4: Budget gate check ─────────────────────────────────────────
        if budget_gate is not None and model:
            estimated_cost = budget_gate.estimate_cost(model)
            if not budget_gate.can_spend(estimated_cost):
                node_states[node_id] = NodeState.FAILED
                outputs[node_id] = None
                error_msg = (
                    f"Budget exceeded: ${budget_gate.remaining():.4f} remaining, "
                    f"${estimated_cost:.4f} needed for {model}"
                )
                logger.warning("BudgetGate BLOCKED node %s: %s", node_id, error_msg)
                yield NodeEvent(
                    node_id=node_id,
                    event_type="node_error",
                    data={"error": error_msg, "budget_exceeded": True},
                )
                continue
            # Record the spend optimistically (will be refunded on failure)
            budget_gate.record_spend(estimated_cost, model=model, detail=node_id)

        try:
            result = await provider.generate(node.type.value, config)
            # Convert ImageResult objects to serializable dicts
            if result is not None and hasattr(result, '__dict__'):
                result = result.__dict__
            outputs[node_id] = result if result is not None else {}
            node_states[node_id] = NodeState.COMPLETED

            # ── V4: Intermediate validation ───────────────────────────────
            if (intermediate_validator is not None
                    and node.type.value in ("image_gen", "img2img")
                    and original_prompt):
                validation = intermediate_validator.validate_step(
                    step_result=outputs[node_id],
                    original_prompt=original_prompt,
                    step_action=node.type.value,
                )
                if not validation.should_continue:
                    node_states[node_id] = NodeState.FAILED
                    outputs[node_id] = None
                    error_msg = (
                        f"Intermediate validation failed: "
                        f"confidence={validation.confidence:.2f}, "
                        f"issues={validation.issues}"
                    )
                    logger.warning("IntermediateValidator BLOCKED node %s: %s",
                                   node_id, error_msg)
                    yield NodeEvent(
                        node_id=node_id,
                        event_type="node_error",
                        data={"error": error_msg, "validation_failed": True,
                              "confidence": validation.confidence},
                    )
                    continue

            yield NodeEvent(
                node_id=node_id,
                event_type="node_complete",
                data={"output": outputs[node_id]},
            )
        except Exception as exc:
            node_states[node_id] = NodeState.FAILED
            outputs[node_id] = None
            yield NodeEvent(
                node_id=node_id,
                event_type="node_error",
                data={"error": str(exc)},
            )

    # ── V4: Workflow done with budget summary ──────────────────────────────
    done_data: dict[str, Any] = {"node_states": node_states}
    if budget_gate is not None:
        done_data["budget"] = budget_gate.get_summary()
        logger.info("Workflow done. Budget: $%.4f / $%.4f spent",
                     budget_gate.spent, budget_gate.max_budget)

    yield NodeEvent(node_id="__workflow__", event_type="workflow_done", data=done_data)
