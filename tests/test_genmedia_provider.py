"""Tests for GenmediaProvider — subprocess-based FAL provider."""

import asyncio
import json
import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hermesfy.providers.genmedia import (
    PROVIDER_AUTH,
    PROVIDER_ERROR,
    GenmediaProvider,
    _save_data_uri_to_temp,
    _is_data_uri,
    _NODE_DEFAULT_MODELS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_run():
    """Mock asyncio.create_subprocess_exec to return a fake genmedia response."""
    with patch("asyncio.create_subprocess_exec") as m:
        yield m


@pytest.fixture
def provider():
    """Create a GenmediaProvider with mocked genmedia check."""
    with patch.object(GenmediaProvider, "__init__", lambda self: None):
        p = GenmediaProvider()
        p._binary = "/usr/bin/genmedia"
        p._api_key = "test-key"
        p._base_env = {
            "FAL_KEY": "test-key",
            "GENMEDIA_NO_UPDATE": "1",
            "GENMEDIA_NO_ANALYTICS": "1",
        }
        return p


def _fake_proc(stdout="", stderr="", returncode=0):
    """Create a fake asyncio subprocess mock."""
    proc = AsyncMock()
    stdout_bytes = stdout.encode() if isinstance(stdout, str) else stdout
    stderr_bytes = stderr.encode() if isinstance(stderr, str) else stderr
    proc.communicate = AsyncMock(return_value=(stdout_bytes, stderr_bytes))
    proc.returncode = returncode
    proc.pid = 12345
    return proc


# ── Initialization ────────────────────────────────────────────────────────────


def test_init_no_binary():
    """Raises error if genmedia is not in PATH."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="genmedia CLI not found"):
            GenmediaProvider()


def test_init_no_api_key():
    """Raises auth error if no FAL_KEY or FAL_API_KEY."""
    with patch("shutil.which", return_value="/usr/bin/genmedia"):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="FAL_KEY or FAL_API_KEY"):
                GenmediaProvider()


def test_init_with_fal_api_key():
    """Accepts FAL_API_KEY (legacy env var)."""
    with patch("shutil.which", return_value="/usr/bin/genmedia"):
        with patch.dict(os.environ, {"FAL_API_KEY": "legacy-key"}, clear=True):
            p = GenmediaProvider()
            assert p._api_key == "legacy-key"


def test_init_with_fal_key():
    """Accepts FAL_KEY (genmedia standard)."""
    with patch("shutil.which", return_value="/usr/bin/genmedia"):
        with patch.dict(os.environ, {"FAL_KEY": "standard-key"}, clear=True):
            p = GenmediaProvider()
            assert p._api_key == "standard-key"


def test_init_prefers_fal_key():
    """FAL_KEY takes priority over FAL_API_KEY."""
    with patch("shutil.which", return_value="/usr/bin/genmedia"):
        with patch.dict(os.environ, {"FAL_KEY": "primary", "FAL_API_KEY": "legacy"}, clear=True):
            p = GenmediaProvider()
            assert p._api_key == "primary"


# ── Image upload helpers ──────────────────────────────────────────────────────


def test_is_data_uri():
    assert _is_data_uri("data:image/jpeg;base64,/9j/4AAQ")
    assert not _is_data_uri("https://example.com/image.jpg")
    assert not _is_data_uri("/local/path.png")


def test_save_data_uri_to_temp():
    """Data URIs are saved to temp files."""
    # Minimal valid JPEG data URI
    data_uri = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEA"
    path = _save_data_uri_to_temp(data_uri)
    assert os.path.exists(path)
    assert path.endswith(".jpeg")
    with open(path, "rb") as f:
        content = f.read()
        assert len(content) > 0
    os.unlink(path)


# ── Argument building ─────────────────────────────────────────────────────────


def test_build_args_image_gen(provider):
    """image_gen produces correct genmedia run args."""
    args = provider._build_args(
        "image_gen",
        {"prompt": "a cat", "model": "fal-ai/flux/schnell", "width": 512, "height": 512},
        "fal-ai/flux/schnell",
        "",
    )
    assert args[0] == "genmedia"
    assert args[1] == "run"
    assert "fal-ai/flux/schnell" in args
    assert "--prompt" in args
    assert "a cat" in args
    assert "--image_size" in args
    # JSON-encoded dimensions
    size_idx = args.index("--image_size")
    size_obj = json.loads(args[size_idx + 1])
    assert size_obj == {"width": 512, "height": 512}


def test_build_args_img2img(provider):
    """img2img includes image_url and strength."""
    args = provider._build_args(
        "img2img",
        {
            "prompt": "change background",
            "model": "fal-ai/flux/dev/image-to-image",
            "image_url": "https://cdn.fal.ai/img.png",
            "strength": 0.25,
        },
        "fal-ai/flux/dev/image-to-image",
        "https://cdn.fal.ai/img.png",
    )
    assert "--image_url" in args
    assert "https://cdn.fal.ai/img.png" in args
    assert "--strength" in args
    assert "0.25" in args


def test_build_args_inpaint(provider):
    """inpaint includes image_url and mask_url."""
    args = provider._build_args(
        "inpaint",
        {
            "prompt": "remove object",
            "image_url": "https://cdn.fal.ai/img.png",
            "mask_url": "https://cdn.fal.ai/mask.png",
        },
        "fal-ai/flux/inpainting",
        "https://cdn.fal.ai/img.png",
    )
    assert "--image_url" in args
    assert "--mask_url" in args
    assert "https://cdn.fal.ai/mask.png" in args


def test_build_args_upscale(provider):
    """upscale includes scale parameter."""
    args = provider._build_args(
        "upscale",
        {"image_url": "https://cdn.fal.ai/img.png", "scale": 4},
        "fal-ai/clarity-upscaler",
        "https://cdn.fal.ai/img.png",
    )
    assert "--scale" in args
    assert "4" in args


def test_build_args_remove_bg(provider):
    """remove_bg only needs image_url, no prompt."""
    args = provider._build_args(
        "remove_bg",
        {"image_url": "https://cdn.fal.ai/img.png"},
        "fal-ai/birefnet",
        "https://cdn.fal.ai/img.png",
    )
    assert "--image_url" in args
    assert "--prompt" not in args or args[args.index("--prompt") + 1] == ""


def test_build_args_seed(provider):
    """seed parameter is forwarded for image_gen and img2img."""
    args = provider._build_args(
        "image_gen",
        {"prompt": "test", "seed": 42, "model": "fal-ai/flux/schnell"},
        "fal-ai/flux/schnell",
        "",
    )
    assert "--seed" in args
    assert "42" in args


def test_build_args_loras(provider):
    """LoRA arrays are JSON-encoded."""
    loras = [{"path": "https://fal.ai/my-lora.safetensors", "scale": 1.0}]
    args = provider._build_args(
        "image_gen",
        {"prompt": "test", "loras": loras, "model": "fal-ai/flux/dev"},
        "fal-ai/flux/dev",
        "",
    )
    assert "--loras" in args
    lora_idx = args.index("--loras")
    parsed = json.loads(args[lora_idx + 1])
    assert parsed == loras


def test_build_args_node_defaults():
    """All node types with _NODE_DEFAULT_MODELS entries are covered."""
    for node_type, expected_model in _NODE_DEFAULT_MODELS.items():
        assert node_type in _NODE_DEFAULT_MODELS
        # Each node type that calls FAL should have a default model
        if node_type not in ("text_prompt", "seed"):
            assert expected_model.startswith("fal-ai/"), \
                f"{node_type} default model should be fal-ai/*"


# ── Response parsing ──────────────────────────────────────────────────────────


def test_parse_result_images_array(provider):
    """Parses standard images[0] response."""
    stdout = json.dumps({
        "status": "completed",
        "request_id": "abc-123",
        "result": {
            "images": [{"url": "https://fal.ai/img.jpg", "width": 1024, "height": 1024,
                        "content_type": "image/jpeg"}]
        }
    })
    result = provider._parse_result(stdout, "fal-ai/flux/schnell")
    assert result.url == "https://fal.ai/img.jpg"
    assert result.width == 1024
    assert result.height == 1024
    assert result.format == "jpeg"
    assert result.metadata["request_id"] == "abc-123"


def test_parse_result_singular_image(provider):
    """Parses singular image dict response."""
    stdout = json.dumps({
        "result": {
            "image": {"url": "https://fal.ai/img.png", "width": 512, "height": 512}
        }
    })
    result = provider._parse_result(stdout, "test")
    assert result.url == "https://fal.ai/img.png"
    assert result.width == 512


def test_parse_result_image_string(provider):
    """Parses image as plain string URL."""
    stdout = json.dumps({
        "result": {
            "images": ["https://fal.ai/img.webp"]
        }
    })
    result = provider._parse_result(stdout, "test")
    assert result.url == "https://fal.ai/img.webp"


def test_parse_result_output_wrapper(provider):
    """Parses output.images wrapper format."""
    stdout = json.dumps({
        "output": {
            "images": [{"url": "https://fal.ai/wrapped.jpg", "width": 768, "height": 768}]
        }
    })
    result = provider._parse_result(stdout, "test")
    assert result.url == "https://fal.ai/wrapped.jpg"


def test_parse_result_no_images(provider):
    """Raises error when no image URL is found."""
    stdout = json.dumps({"result": {}})
    with pytest.raises(RuntimeError, match="No image URL"):
        provider._parse_result(stdout, "test")


def test_parse_result_api_error(provider):
    """Converts API error to RuntimeError."""
    stdout = json.dumps({
        "status": 422,
        "error_type": "ValidationError",
        "error": "prompt is required",
        "validation_errors": [{"field": "prompt", "message": "Field required"}]
    })
    with pytest.raises(RuntimeError, match="ValidationError"):
        provider._parse_result(stdout, "test")


# ── Error handling ────────────────────────────────────────────────────────────


def test_raise_error_auth(provider):
    """Auth errors get PROVIDER_AUTH prefix."""
    stderr = json.dumps({"error": "Authentication failed", "details": {"hint": "Check your key"}})
    with pytest.raises(RuntimeError, match=PROVIDER_AUTH):
        provider._raise_error(1, "", stderr, "test-model")


def test_raise_error_validation(provider):
    """Validation errors from genmedia."""
    stdout = json.dumps({
        "validation_errors": [
            {"field": "image_url", "message": "Field required", "type": "missing"}
        ]
    })
    with pytest.raises(RuntimeError, match="Validation failed"):
        provider._raise_error(1, stdout, "", "test-model")


def test_raise_error_generic(provider):
    """Generic error with PROVIDER_ERROR prefix."""
    with pytest.raises(RuntimeError, match=PROVIDER_ERROR):
        provider._raise_error(1, "", "Something went wrong", "test-model")


# ── Full generate flow ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_image_gen(mock_run, provider):
    """Full image_gen flow returns ImageResult."""
    proc = _fake_proc(stdout=json.dumps({
        "status": "completed",
        "request_id": "req-1",
        "result": {
            "images": [{"url": "https://fal.ai/gen.jpg", "width": 1024, "height": 1024,
                        "content_type": "image/jpeg"}]
        }
    }))
    mock_run.return_value = proc

    result = await provider.generate("image_gen", {
        "prompt": "a dragon",
        "model": "fal-ai/flux/schnell",
    })

    assert result.url == "https://fal.ai/gen.jpg"
    assert result.width == 1024
    assert result.height == 1024
    assert result.format == "jpeg"


@pytest.mark.asyncio
async def test_generate_error(mock_run, provider):
    """Errors are propagated as RuntimeError."""
    proc = _fake_proc(stdout="", stderr=json.dumps({"error": "API rate limit exceeded"}), returncode=1)
    mock_run.return_value = proc

    with pytest.raises(RuntimeError, match="API rate limit"):
        await provider.generate("image_gen", {"prompt": "test"})


# ── Model defaults ────────────────────────────────────────────────────────────


def test_default_models_all_nodes():
    """Every Hermesfy node type has a default model in genmedia provider."""
    expected_nodes = {
        "image_gen", "img2img", "inpaint", "outpaint",
        "upscale", "remove_bg", "face_restore", "ip_adapter",
    }
    covered = set(_NODE_DEFAULT_MODELS.keys())
    assert expected_nodes <= covered, f"Missing defaults for: {expected_nodes - covered}"
