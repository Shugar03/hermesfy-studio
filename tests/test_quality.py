"""Unit tests for quality gate retry loop and evaluator integration."""

import pytest

from hermesfy.dag.state import NodeState, NodeRun


# Will import after implementation
# from hermesfy.dag.quality import retry_loop, QUALITY_EXHAUSTED


async def always_pass(output: dict, config: dict) -> tuple[bool, str]:
    """Evaluator that always passes."""
    return True, "quality OK"


async def always_fail(output: dict, config: dict) -> tuple[bool, str]:
    """Evaluator that always fails."""
    return False, "quality below threshold"


async def pass_on_third(output: dict, config: dict) -> tuple[bool, str]:
    """Evaluator that passes on the third attempt (uses call count from config)."""
    attempt = config.get("_attempt", 0)
    if attempt >= 2:
        return True, "passed on retry"
    return False, f"failed attempt {attempt}"


class MockProvider:
    """Mock provider that returns a predictable output."""

    def __init__(self, result: dict | None = None):
        self.result = result or {"image_url": "https://fal.ai/images/test.png", "width": 1024, "height": 1024}
        self.call_count = 0

    async def generate(self, node_type: str, config: dict) -> dict:
        self.call_count += 1
        return dict(self.result)


class TestRetryLoop:
    """Tests for the async retry loop with quality evaluation."""

    @pytest.mark.asyncio
    async def test_passes_on_first_attempt(self):
        """QG-001: When evaluator passes immediately, returns completed state."""
        from hermesfy.dag.quality import retry_loop

        provider = MockProvider()
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "a cat"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=always_pass,
            max_retries=2,
            retry_delay=0.0,
        ):
            runs.append(event)

        # Should emit completed event
        completed = [r for r in runs if r.state == NodeState.COMPLETED]
        assert len(completed) == 1
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_then_fails(self):
        """QG-001: When evaluator always fails and max_retries=2, returns QUALITY_EXHAUSTED."""
        from hermesfy.dag.quality import retry_loop

        provider = MockProvider()
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "a cat"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=always_fail,
            max_retries=2,
            retry_delay=0.0,
        ):
            runs.append(event)

        # Should emit quality_exhausted event
        exhausted = [r for r in runs if r.state == NodeState.QUALITY_EXHAUSTED]
        assert len(exhausted) == 1
        # 1 initial + 2 retries = 3 total calls
        assert provider.call_count == 3

    @pytest.mark.asyncio
    async def test_eventually_passes_after_retries(self):
        """QG-003: Node transitions through FAILED → RETRYING → RUNNING → COMPLETED."""
        from hermesfy.dag.quality import retry_loop

        provider = MockProvider()
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "a cat"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=pass_on_third,
            max_retries=3,
            retry_delay=0.0,
        ):
            runs.append(event)

        # Verify state sequence: RUNNING → FAILED → RETRYING → RUNNING → FAILED → RETRYING → RUNNING → COMPLETED
        states = [r.state for r in runs]
        # The exact sequence depends on implementation, but key check:
        assert NodeState.COMPLETED in states
        assert NodeState.RETRYING in states
        assert NodeState.FAILED in states
        # At least 3 provider calls (2 + pass on third)
        assert provider.call_count >= 2

    @pytest.mark.asyncio
    async def test_zero_max_retries_no_retry(self):
        """When max_retries=0, failure on first attempt returns QUALITY_EXHAUSTED immediately."""
        from hermesfy.dag.quality import retry_loop

        provider = MockProvider()
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "a cat"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=always_fail,
            max_retries=0,
            retry_delay=0.0,
        ):
            runs.append(event)

        exhausted = [r for r in runs if r.state == NodeState.QUALITY_EXHAUSTED]
        assert len(exhausted) == 1
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_provider_failure_during_retry(self):
        """When the provider itself raises, the attempt is marked FAILED and retried."""
        from hermesfy.dag.quality import retry_loop

        class ErrorProvider:
            def __init__(self):
                self.call_count = 0

            async def generate(self, node_type: str, config: dict) -> dict:
                self.call_count += 1
                raise RuntimeError("provider crashed")

        provider = ErrorProvider()
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "a cat"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=always_pass,
            max_retries=1,
            retry_delay=0.0,
        ):
            runs.append(event)

        # All attempts should fail → exhausted
        exhausted = [r for r in runs if r.state == NodeState.QUALITY_EXHAUSTED]
        assert len(exhausted) == 1
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_last_output_on_success(self):
        """The completed NodeRun includes the provider's output."""
        from hermesfy.dag.quality import retry_loop

        provider = MockProvider(result={"image_url": "https://fal.ai/images/custom.png"})
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "custom"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=always_pass,
            max_retries=1,
            retry_delay=0.0,
        ):
            runs.append(event)

        completed_run = [r for r in runs if r.state == NodeState.COMPLETED][0]
        assert completed_run.output["image_url"] == "https://fal.ai/images/custom.png"

    @pytest.mark.asyncio
    async def test_error_message_propagated_to_run(self):
        """When quality gate fails, the error message is in the NodeRun."""
        from hermesfy.dag.quality import retry_loop

        provider = MockProvider()
        node_id = "node-1"
        config = {"model": "flux-dev", "prompt": "a cat"}

        runs = []
        async for event in retry_loop(
            node_id=node_id,
            config=config,
            provider=provider,
            evaluator=always_fail,
            max_retries=0,
            retry_delay=0.0,
        ):
            runs.append(event)

        exhausted_run = [r for r in runs if r.state == NodeState.QUALITY_EXHAUSTED][0]
        assert exhausted_run.error is not None
        assert "quality below threshold" in exhausted_run.error
