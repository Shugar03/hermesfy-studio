"""Unit tests for Fal.ai HTTP provider using pytest-httpx mocking."""

import os

import pytest
import httpx

from hermesfy.providers.base import Provider, ImageResult


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def fal_api_key_env(monkeypatch):
    """Set FAL_API_KEY env var for tests."""
    monkeypatch.setenv("FAL_API_KEY", "test-key-abc123")


@pytest.fixture
def mock_submit_response():
    """Mock response from Fal.ai submit endpoint."""
    return {"request_id": "fal-req-abc123"}


@pytest.fixture
def mock_status_in_progress():
    """Mock status response: IN_PROGRESS."""
    return {"request_id": "fal-req-abc123", "status": "IN_PROGRESS"}


@pytest.fixture
def mock_status_completed():
    """Mock status response: COMPLETED with output."""
    return {
        "request_id": "fal-req-abc123",
        "status": "COMPLETED",
        "output": {
            "images": [
                {
                    "url": "https://fal.ai/images/output.png",
                    "width": 1024,
                    "height": 768,
                    "content_type": "image/png",
                }
            ]
        },
    }


@pytest.fixture
def mock_auth_error():
    """Mock 401 auth error."""
    return httpx.Response(401, json={"detail": "Invalid API key"})


@pytest.fixture
def mock_server_error():
    """Mock 500 server error."""
    return httpx.Response(500, json={"detail": "Internal server error"})


# ── Abstract Provider Tests ────────────────────────────────────────────


class TestAbstractProvider:
    """Verify the base Provider class cannot be instantiated directly."""

    def test_provider_is_abstract(self):
        """Provider ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Provider()  # type: ignore[abstract]

    def test_generate_is_abstract(self):
        """generate() must be implemented by subclasses."""
        assert hasattr(Provider, "generate")
        assert hasattr(Provider.generate, "__isabstractmethod__")


class TestImageResult:
    """Tests for the ImageResult dataclass."""

    def test_image_result_defaults(self):
        """ImageResult has sensible defaults."""
        result = ImageResult(url="https://example.com/img.png", width=1024, height=768)
        assert result.url == "https://example.com/img.png"
        assert result.width == 1024
        assert result.height == 768
        assert result.format == "png"
        assert result.metadata == {}

    def test_image_result_with_metadata(self):
        """ImageResult stores arbitrary metadata."""
        result = ImageResult(
            url="https://fal.ai/images/test.png",
            width=512,
            height=512,
            format="jpeg",
            metadata={"seed": 42, "inference_time": 3.14},
        )
        assert result.metadata["seed"] == 42
        assert result.format == "jpeg"


# ── Registry Tests ─────────────────────────────────────────────────────


class TestRegistry:
    """Tests for the model registry."""

    def test_registry_has_flux_dev(self):
        """Registry MUST contain flux-dev model."""
        from hermesfy.providers.registry import get_models
        models = get_models()
        model_names = [m["name"] for m in models]
        assert "flux-dev" in model_names

    def test_registry_has_flux_pro(self):
        """Registry MUST contain flux-pro model."""
        from hermesfy.providers.registry import get_models
        models = get_models()
        model_names = [m["name"] for m in models]
        assert "flux-pro" in model_names

    def test_registry_has_flux_schnell(self):
        """Registry MUST contain flux-schnell model."""
        from hermesfy.providers.registry import get_models
        models = get_models()
        model_names = [m["name"] for m in models]
        assert "flux-schnell" in model_names

    def test_registry_has_flux_depth(self):
        """Registry MUST contain flux-depth model."""
        from hermesfy.providers.registry import get_models
        models = get_models()
        model_names = [m["name"] for m in models]
        assert "flux-depth" in model_names

    def test_registry_has_clarity_upscaler(self):
        """Registry MUST contain clarity-upscaler."""
        from hermesfy.providers.registry import get_models
        models = get_models()
        model_names = [m["name"] for m in models]
        assert "clarity-upscaler" in model_names

    def test_get_model_returns_entry(self):
        """get_model() returns a specific model entry."""
        from hermesfy.providers.registry import get_model
        model = get_model("flux-dev")
        assert model is not None
        assert model["name"] == "flux-dev"
        assert "endpoint" in model
        assert "supported_node_types" in model

    def test_get_model_unknown_returns_none(self):
        """get_model() returns None for unknown models."""
        from hermesfy.providers.registry import get_model
        model = get_model("nonexistent-model")
        assert model is None

    def test_each_model_has_required_fields(self):
        """Every registered model has name, endpoint, description, node_types, defaults."""
        from hermesfy.providers.registry import get_models
        required_fields = {"name", "endpoint", "description", "supported_node_types", "default_params"}
        for model in get_models():
            missing = required_fields - set(model.keys())
            assert not missing, f"Model {model.get('name', '?')} missing fields: {missing}"


# ── FalProvider HTTP Tests (pytest-httpx) ──────────────────────────────


class TestFalProviderGenerate:
    """Tests for FalProvider.generate() with httpx mocking."""

    @pytest.mark.asyncio
    async def test_generate_successful(self, httpx_mock, fal_api_key_env, mock_submit_response, mock_status_in_progress, mock_status_completed):
        """Happy path: submit → poll IN_PROGRESS → COMPLETED → ImageResult."""
        from hermesfy.providers.fal import FalProvider

        # Mock submit endpoint
        httpx_mock.add_response(
            method="POST",
            url="https://queue.fal.run/fal-ai/flux/dev",
            json=mock_submit_response,
            status_code=200,
        )
        # Mock status: IN_PROGRESS (first poll)
        httpx_mock.add_response(
            method="GET",
            url="https://queue.fal.run/fal-ai/flux/dev/requests/fal-req-abc123/status",
            json=mock_status_in_progress,
            status_code=200,
        )
        # Mock status: COMPLETED (second poll)
        httpx_mock.add_response(
            method="GET",
            url="https://queue.fal.run/fal-ai/flux/dev/requests/fal-req-abc123/status",
            json=mock_status_completed,
            status_code=200,
        )
        # Mock result endpoint
        httpx_mock.add_response(
            method="GET",
            url="https://queue.fal.run/fal-ai/flux/dev/requests/fal-req-abc123",
            json=mock_status_completed,
            status_code=200,
        )

        provider = FalProvider()
        result = await provider.generate("image_gen", {"model": "flux-dev", "prompt": "a cat", "width": 1024, "height": 768})

        assert result is not None
        assert result.url == "https://fal.ai/images/output.png"
        assert result.width == 1024
        assert result.height == 768
        assert result.format == "png"

    def test_generate_missing_api_key(self, monkeypatch):
        """PROV-004: Missing FAL_API_KEY raises PROVIDER_AUTH."""
        from hermesfy.providers.fal import FalProvider, PROVIDER_AUTH

        monkeypatch.delenv("FAL_API_KEY", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            FalProvider()
        assert PROVIDER_AUTH in str(exc_info.value)

  
    @pytest.mark.asyncio
    async def test_generate_auth_error(self, httpx_mock, fal_api_key_env):
        """PROV-005: 401 Unauthorized → PROVIDER_AUTH error."""
        from hermesfy.providers.fal import FalProvider, PROVIDER_AUTH

        httpx_mock.add_response(
            method="POST",
            url="https://queue.fal.run/fal-ai/flux/dev",
            status_code=401,
            json={"detail": "Invalid API key"},
        )

        provider = FalProvider()
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate("image_gen", {"model": "flux-dev", "prompt": "test"})
        assert PROVIDER_AUTH in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_server_error(self, httpx_mock, fal_api_key_env, mock_submit_response):
        """PROV-005: 500 error → PROVIDER_ERROR with model and status info."""
        from hermesfy.providers.fal import FalProvider, PROVIDER_ERROR

        httpx_mock.add_response(
            method="POST",
            url="https://queue.fal.run/fal-ai/flux-pro",
            status_code=500,
            json={"detail": "Internal server error"},
        )

        provider = FalProvider()
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate("image_gen", {"model": "flux-pro", "prompt": "test"})
        assert PROVIDER_ERROR in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_timeout(self, httpx_mock, fal_api_key_env):
        """A timeout during submission raises PROVIDER_ERROR."""
        from hermesfy.providers.fal import FalProvider, PROVIDER_ERROR

        # Add 3 timeout exceptions for 3 retry attempts
        for _ in range(3):
            httpx_mock.add_exception(
                httpx.TimeoutException("Connection timed out"),
                method="POST",
                url="https://queue.fal.run/fal-ai/flux/dev",
            )

        provider = FalProvider()
        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate("image_gen", {"model": "flux-dev", "prompt": "test"})
        assert PROVIDER_ERROR in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_auth_header_is_set(self, httpx_mock, fal_api_key_env, mock_submit_response, mock_status_completed):
        """The Authorization header contains the FAL_API_KEY."""
        from hermesfy.providers.fal import FalProvider

        httpx_mock.add_response(
            method="POST",
            url="https://queue.fal.run/fal-ai/flux/dev",
            json=mock_submit_response,
            status_code=200,
        )
        httpx_mock.add_response(
            method="GET",
            url="https://queue.fal.run/fal-ai/flux/dev/requests/fal-req-abc123/status",
            json=mock_status_completed,
            status_code=200,
        )
        httpx_mock.add_response(
            method="GET",
            url="https://queue.fal.run/fal-ai/flux/dev/requests/fal-req-abc123",
            json=mock_status_completed,
            status_code=200,
        )

        provider = FalProvider()
        await provider.generate("image_gen", {"model": "flux-dev", "prompt": "test"})

        # Check the auth header was sent
        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Key test-key-abc123"
