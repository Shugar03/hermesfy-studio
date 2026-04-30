"""Quality gate retry loop — evaluates node output and retries if quality is insufficient."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable

from hermesfy.dag.state import NodeRun, NodeState

__all__ = ["retry_loop", "QualityEvaluator"]

#: A quality evaluator callable: receives (output, config) and returns (passed: bool, reason: str).
QualityEvaluator = Callable[[dict, dict], Awaitable[tuple[bool, str]]]


async def retry_loop(
    node_id: str,
    config: dict,
    provider: Any,
    evaluator: QualityEvaluator,
    max_retries: int = 0,
    retry_delay: float = 1.0,
) -> AsyncGenerator[NodeRun, None]:
    """Execute a node with retry logic, evaluating output quality on each attempt.

    Flow:
        1. Call provider.generate() to get output
        2. Call evaluator(output, config) to check quality
        3. If pass → yield COMPLETED run with output
        4. If fail and retries remain → yield FAILED, then RETRYING, wait, retry
        5. If fail and no retries remain → yield QUALITY_EXHAUSTED

    Args:
        node_id: The node identifier.
        config: The resolved node configuration.
        provider: Object with async generate(node_type, config) → dict method.
        evaluator: Async callable returning (passed: bool, reason: str).
        max_retries: Maximum number of retry attempts after the initial attempt.
        retry_delay: Seconds to wait between retries.

    Yields:
        NodeRun instances tracking each attempt.
    """
    total_attempts = max_retries + 1  # initial attempt + retries
    last_output: Any = None

    for attempt in range(total_attempts):
        # Emit RUNNING
        yield NodeRun(attempt=attempt, state=NodeState.RUNNING, error=None)

        # Try to generate
        try:
            output = await provider.generate(config.get("_node_type", "image_gen"), config)
            last_output = output
        except Exception as exc:
            # Provider failure
            if attempt < max_retries:
                yield NodeRun(attempt=attempt, state=NodeState.FAILED, error=str(exc))
                yield NodeRun(attempt=attempt, state=NodeState.RETRYING, error=str(exc))
                await asyncio.sleep(retry_delay)
                continue
            else:
                yield NodeRun(
                    attempt=attempt,
                    state=NodeState.QUALITY_EXHAUSTED,
                    error=str(exc),
                    output=None,
                )
                return

        # Evaluate quality
        eval_config = dict(config)
        eval_config["_attempt"] = attempt
        passed, reason = await evaluator(output, eval_config)

        if passed:
            yield NodeRun(attempt=attempt, state=NodeState.COMPLETED, output=output)
            return

        # Quality failed
        if attempt < max_retries:
            yield NodeRun(attempt=attempt, state=NodeState.FAILED, error=reason)
            yield NodeRun(attempt=attempt, state=NodeState.RETRYING, error=reason)
            await asyncio.sleep(retry_delay)
        else:
            yield NodeRun(
                attempt=attempt,
                state=NodeState.QUALITY_EXHAUSTED,
                error=reason,
                output=output,
            )
            return
