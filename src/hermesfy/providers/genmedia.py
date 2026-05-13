"""Genmedia CLI provider — wraps `genmedia` (FAL's official CLI) via subprocess.

Replaces FalProvider's direct HTTP calls with structured CLI invocations.
genmedia handles auth, retries, polling, error formatting, and model discovery.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from typing import Optional

from hermesfy.providers.base import ImageResult, Provider

__all__ = ["GenmediaProvider", "PROVIDER_ERROR", "PROVIDER_AUTH"]

PROVIDER_ERROR = "PROVIDER_ERROR"
PROVIDER_AUTH = "PROVIDER_AUTH"

DEFAULT_TIMEOUT = 360  # seconds for generation (GPT Image 2 needs 3+ min)
UPLOAD_TIMEOUT = 60    # seconds for image upload

logger = logging.getLogger("hermesfy.genmedia")


# ---------------------------------------------------------------------------
# Node-type → model endpoint defaults (when config doesn't specify a model)
# ---------------------------------------------------------------------------

_NODE_DEFAULT_MODELS: dict[str, str] = {
    "image_gen": "fal-ai/flux/schnell",
    "img2img": "fal-ai/flux/dev/image-to-image",
    "inpaint": "fal-ai/flux/inpainting",
    "outpaint": "fal-ai/flux/outpainting",
    "upscale": "fal-ai/clarity-upscaler",
    "remove_bg": "fal-ai/birefnet",
    "face_restore": "fal-ai/codeformer",
    "ip_adapter": "fal-ai/flux/dev",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Models that expect image_url (singular) instead of image_urls (plural)
_IMAGE_URL_SINGULAR_FAMILIES = [
    "fal-ai/flux-pro/kontext",
    "fal-ai/flux/redux",
    "fal-ai/ideogram/",
    "fal-ai/flux/dev/image-to-image",
    "fal-ai/flux/inpainting",
    "fal-ai/topaz/",
    "fal-ai/clarity-upscaler",
    "fal-ai/birefnet",
]


def _model_uses_image_url_singular(model: str) -> bool:
    """Check if this model expects image_url (singular) instead of image_urls."""
    for family in _IMAGE_URL_SINGULAR_FAMILIES:
        if model.startswith(family):
            return True
    return False


def _extract_image_url(config: dict) -> str:
    """Extract image URL from config, handling dict-wrapped formats."""
    img = config.get("image_url", "")
    if isinstance(img, dict):
        img = img.get("url", img.get("image_url", ""))
    return img


def _is_data_uri(url: str) -> bool:
    """True if the URL is a base64 data URI."""
    return url.startswith("data:")


def _save_data_uri_to_temp(data_uri: str) -> str:
    """Save a data URI to a temporary file and return the path."""
    import base64
    header, encoded = data_uri.split(",", 1)
    ext = header.split("/")[1].split(";")[0] if "/" in header else "png"
    suffix = f".{ext}"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(base64.b64decode(encoded))
    return path


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GenmediaProvider(Provider):
    """Image generation provider backed by the `genmedia` CLI.

    Requires `genmedia` in PATH and FAL_KEY (or FAL_API_KEY) set in environment.
    All model calls go through subprocess invocations of genmedia.
    """

    def __init__(self) -> None:
        self._binary = shutil.which("genmedia")
        if self._binary is None:
            raise RuntimeError(
                f"{PROVIDER_ERROR}: genmedia CLI not found in PATH. "
                "Install it: curl https://genmedia.sh/install -fsS | bash"
            )

        # genmedia uses FAL_KEY; Hermesfy historically uses FAL_API_KEY
        self._api_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                f"{PROVIDER_AUTH}: FAL_KEY or FAL_API_KEY environment variable not set"
            )

        # Ensure genmedia doesn't auto-update mid-execution
        self._base_env = {**os.environ, "GENMEDIA_NO_UPDATE": "1", "GENMEDIA_NO_ANALYTICS": "1"}
        if not os.environ.get("FAL_KEY"):
            self._base_env["FAL_KEY"] = self._api_key

    # ── Public interface ──────────────────────────────────────────────────

    async def generate(self, node_type: str, config: dict) -> ImageResult:
        """Generate an image via genmedia CLI.

        Args:
            node_type: Node type (image_gen, img2img, inpaint, etc.)
            config: Node configuration with model, prompt, and parameters.

        Returns:
            ImageResult with URL, dimensions, format, and metadata.
        """
        model = config.get("model", _NODE_DEFAULT_MODELS.get(node_type, "fal-ai/flux/schnell"))

        # Upload image first if the node needs an image input
        image_url = await self._prepare_image_input(node_type, config)

        # Build genmedia arguments
        args = self._build_args(node_type, config, model, image_url)

        # Run genmedia
        stdout, stderr, exit_code = await self._run_genmedia(args, timeout=DEFAULT_TIMEOUT)

        if exit_code != 0:
            self._raise_error(exit_code, stdout, stderr, model)

        return self._parse_result(stdout, model)

    def close(self) -> None:
        """No persistent connections to close."""
        pass

    # ── Image upload ──────────────────────────────────────────────────────

    async def _prepare_image_input(self, node_type: str, config: dict) -> str:
        """Upload image(s) if the node type requires them. Returns the CDN URL."""
        if node_type in ("text_prompt", "seed"):
            return ""

        image_url = _extract_image_url(config)

        # Handle data URIs — save to temp file first
        if _is_data_uri(image_url):
            image_url = _save_data_uri_to_temp(image_url)

        # If it's a local path, upload it
        if image_url and not image_url.startswith("http"):
            image_url = await self._upload_image(image_url)

        return image_url

    async def _upload_image(self, path: str) -> str:
        """Upload a local image file to FAL CDN. Returns the CDN URL."""
        args = ["genmedia", "upload", path]
        stdout, stderr, exit_code = await self._run_genmedia(args, timeout=UPLOAD_TIMEOUT)

        if exit_code != 0:
            raise RuntimeError(f"{PROVIDER_ERROR}: Upload failed: {stderr or 'unknown error'}")

        try:
            data = json.loads(stdout)
            cdn_url = data.get("cdn_url", "")
            if not cdn_url:
                raise RuntimeError(f"{PROVIDER_ERROR}: No cdn_url in upload response: {stdout[:200]}")
            return cdn_url
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{PROVIDER_ERROR}: Invalid JSON from upload: {stdout[:200]}") from e

    # ── Argument builder ──────────────────────────────────────────────────

    def _build_args(self, node_type: str, config: dict, model: str, image_url: str) -> list[str]:
        """Build genmedia CLI arguments for a node type."""
        args = ["genmedia", "run", model, "--json"]

        # Prompt
        prompt = config.get("prompt", "")
        if prompt:
            args.extend(["--prompt", prompt])

        # Image dimensions (for generation nodes)
        if node_type in ("image_gen", "img2img", "inpaint", "outpaint", "ip_adapter"):
            w = config.get("width", 1024)
            h = config.get("height", 1024)
            args.extend(["--image_size", json.dumps({"width": w, "height": h})])

        # Image input (for nodes that transform an existing image)
        if node_type in ("img2img", "inpaint", "outpaint", "upscale", "remove_bg",
                         "face_restore", "ip_adapter"):
            if image_url:
                if _model_uses_image_url_singular(model):
                    args.extend(["--image_url", image_url])
                else:
                    args.extend(["--image_urls", json.dumps([image_url])])

        # img2img specific
        if node_type == "img2img":
            strength = config.get("strength", 0.5)
            args.extend(["--strength", str(strength)])

        # inpaint specific
        if node_type == "inpaint":
            mask_url = config.get("mask_url", "")
            if mask_url:
                args.extend(["--mask_url", mask_url])

        # upscale specific
        if node_type == "upscale":
            scale = config.get("scale", 2)
            args.extend(["--scale", str(scale)])

        # ip_adapter specific
        if node_type == "ip_adapter":
            weight = config.get("ip_adapter_weight", 0.75)
            style = config.get("style_strength_ratio", 35)
            args.extend(["--ip_adapter_weight", str(weight)])
            args.extend(["--style_strength_ratio", str(style)])

        # face_restore specific
        if node_type == "face_restore":
            fidelity = config.get("codeformer_fidelity", 0.5)
            args.extend(["--codeformer_fidelity", str(fidelity)])

        # Optional common params
        if "seed" in config and node_type in ("image_gen", "img2img"):
            args.extend(["--seed", str(config["seed"])])

        if "num_images" in config:
            args.extend(["--num_images", str(config["num_images"])])

        if "num_inference_steps" in config:
            args.extend(["--num_inference_steps", str(config["num_inference_steps"])])

        if "guidance_scale" in config:
            args.extend(["--guidance_scale", str(config["guidance_scale"])])

        if "loras" in config:
            # Pass complex JSON params as JSON string
            args.extend(["--loras", json.dumps(config["loras"])])

        return args

    # ── Subprocess management ─────────────────────────────────────────────

    async def _run_genmedia(self, args: list[str], timeout: int) -> tuple[str, str, int]:
        """Run genmedia as a subprocess. Returns (stdout, stderr, exit_code)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._base_env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return (
                stdout_bytes.decode("utf-8", errors="replace").strip(),
                stderr_bytes.decode("utf-8", errors="replace").strip(),
                proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
                await proc.wait()
            raise RuntimeError(
                f"{PROVIDER_ERROR}: genmedia timed out after {timeout}s "
                f"(args={' '.join(args[:5])}...)"
            )

    # ── Response parsing ──────────────────────────────────────────────────

    def _parse_result(self, stdout: str, model: str) -> ImageResult:
        """Parse genmedia JSON stdout into an ImageResult."""
        if not stdout:
            raise RuntimeError(f"{PROVIDER_ERROR}: Empty response from genmedia (model={model})")

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"{PROVIDER_ERROR}: Invalid JSON from genmedia (model={model}): {stdout[:200]}"
            ) from e

        # Check for API errors
        if data.get("status") and isinstance(data["status"], int) and data["status"] >= 400:
            error_type = data.get("error_type", "UnknownError")
            msg = data.get("error", data.get("message", str(data.get("body", ""))))
            raise RuntimeError(f"{PROVIDER_ERROR}: {error_type}: {msg}")

        if data.get("error"):
            raise RuntimeError(f"{PROVIDER_ERROR}: {data['error']}")

        # Extract result
        request_id = data.get("request_id", "")
        result = data.get("result", data)
        if isinstance(result, dict):
            data = result

        # Standard images array
        images = data.get("images", [])
        if not images:
            img = data.get("image")
            if isinstance(img, dict):
                images = [img]
            elif isinstance(img, str):
                images = [{"url": img}]

        # Output wrapper
        if not images:
            output = data.get("output", {})
            images = output.get("images", [])
            if not images:
                img = output.get("image")
                if isinstance(img, dict):
                    images = [img]
                elif isinstance(img, str):
                    images = [{"url": img}]

        url = ""
        width = 0
        height = 0
        fmt = "png"

        if images:
            image = images[0]
            if isinstance(image, str):
                image = {"url": image}
            url = image.get("url", "")
            width = image.get("width", 0)
            height = image.get("height", 0)
            if "content_type" in image:
                fmt = image["content_type"].split("/")[-1]

        # Downloaded files — prefer the first downloaded file's path as URL
        downloaded = data.get("downloaded_files", [])
        if downloaded and not url:
            first = downloaded[0]
            url = first.get("url", "")
            if not width:
                width = 0
                height = 0

        if not url:
            raise RuntimeError(
                f"{PROVIDER_ERROR}: No image URL in genmedia response "
                f"(keys={list(data.keys())[:10]})"
            )

        return ImageResult(
            url=url,
            width=width,
            height=height,
            format=fmt,
            metadata={"request_id": request_id, "model": model},
        )

    # ── Error handling ────────────────────────────────────────────────────

    def _raise_error(self, exit_code: int, stdout: str, stderr: str, model: str) -> None:
        """Convert genmedia failure into a RuntimeError."""

        # Try parsing JSON from stdout or stderr
        for raw in (stdout, stderr):
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Structured genmedia error
            if "error" in data:
                details = data.get("details", {})
                hint = details.get("hint", "") if isinstance(details, dict) else str(details)
                msg = data["error"]
                if "auth" in msg.lower() or "key" in msg.lower() or "unauthorized" in msg.lower():
                    raise RuntimeError(f"{PROVIDER_AUTH}: {msg}" + (f" — {hint}" if hint else ""))
                raise RuntimeError(f"{PROVIDER_ERROR}: {msg}")

            # Validation errors from FAL API
            if "validation_errors" in data:
                errors = data["validation_errors"]
                details = "; ".join(
                    f"{e.get('field', '?')}: {e.get('message', '?')}"
                    for e in errors[:3]
                )
                raise RuntimeError(f"{PROVIDER_ERROR}: Validation failed: {details}")

        # Fallback: raw stderr
        error_msg = stderr or stdout or f"exit code {exit_code}"
        if "auth" in error_msg.lower() or "key" in error_msg.lower():
            raise RuntimeError(f"{PROVIDER_AUTH}: {error_msg[:300]}")
        raise RuntimeError(f"{PROVIDER_ERROR}: genmedia failed (model={model}): {error_msg[:300]}")
