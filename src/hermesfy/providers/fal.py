"""Fal.ai HTTP provider — async image generation via queue.fal.run."""

from __future__ import annotations

import asyncio
import io
import os
import time

import httpx

from hermesfy.providers.base import ImageResult, Provider

__all__ = ["FalProvider", "PROVIDER_ERROR", "PROVIDER_AUTH"]

FAL_API_KEY_ENV = "FAL_API_KEY"
FAL_BASE_URL = "https://queue.fal.run"
DEFAULT_TIMEOUT = 120  # seconds
MAX_RETRIES = 3

PROVIDER_ERROR = "PROVIDER_ERROR"
PROVIDER_AUTH = "PROVIDER_AUTH"


# ---------------------------------------------------------------------------
# Post-processing: replace dark backgrounds with white
# ---------------------------------------------------------------------------

def _replace_dark_background(image_bytes: bytes, threshold: int = 60) -> bytes:
    """Replace near-black background pixels with white in an image.

    Uses Pillow to detect pixels where R, G, B are all below threshold
    and replaces them with pure white. This fixes clarity-upscaler's
    tendency to produce black backgrounds for product photos.

    Args:
        image_bytes: Raw image bytes (PNG or JPEG).
        threshold: Pixel value below which a channel is considered "dark" (0-255).

    Returns:
        Processed image as bytes (PNG format).
    """
    try:
        from PIL import Image
    except ImportError:
        return image_bytes  # Pillow not available, return unchanged

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return image_bytes

    pixels = img.load()
    w, h = img.size
    modified = False

    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if r < threshold and g < threshold and b < threshold:
                pixels[x, y] = (255, 255, 255)
                modified = True

    if not modified:
        return image_bytes  # No dark pixels found, return original

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Endpoint resolution
# ---------------------------------------------------------------------------

# Base model → endpoint (text-to-image default)
_MODEL_ENDPOINTS: dict[str, str] = {
    "flux-dev": "fal-ai/flux/dev",
    "flux-pro": "fal-ai/flux-pro",
    "flux-schnell": "fal-ai/flux/schnell",
    "flux-depth": "fal-ai/flux-depth",
    "clarity-upscaler": "fal-ai/clarity-upscaler",
    "birefnet": "fal-ai/birefnet",
    "codeformer": "fal-ai/codeformer",
}

# Node type → endpoint overrides (when a node_type needs a different endpoint)
# Key format: (base_endpoint, node_type) → override endpoint
_ENDPOINT_OVERRIDES: dict[tuple[str, str], str] = {
    # Img2img overrides
    ("fal-ai/flux/dev", "img2img"): "fal-ai/flux/dev/image-to-image",
    # flux-pro handles img2img on same endpoint, no override needed

    # Inpainting — dedicated endpoint
    ("fal-ai/flux/dev", "inpaint"): "fal-ai/flux/inpainting",

    # Outpainting — dedicated endpoint
    ("fal-ai/flux/dev", "outpaint"): "fal-ai/flux/outpainting",
}


def _resolve_endpoint(node_type: str, model: str) -> str:
    """Resolve the full Fal.ai endpoint for a given node type and model.

    Priority:
      1. (base_endpoint, node_type) override from _ENDPOINT_OVERRIDES
      2. Base model endpoint from _MODEL_ENDPOINTS
      3. Use model string as raw endpoint
    """
    base = _MODEL_ENDPOINTS.get(model, model)
    override = _ENDPOINT_OVERRIDES.get((base, node_type))
    return override or base


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def _extract_image_url(config: dict) -> str:
    """Extract image URL from config, handling dict-wrapped formats."""
    img = config.get("image_url", "")
    if isinstance(img, dict):
        img = img.get("url", img.get("image_url", ""))
    return img


def _build_payload(node_type: str, config: dict) -> dict:
    """Map node config keys to Fal.ai API parameters per node type."""
    payload: dict = {}

    if "prompt" in config:
        payload["prompt"] = config["prompt"]

    # --- image_gen / img2img (shared params) ---
    if node_type in ("image_gen", "img2img", "inpaint", "outpaint", "ip_adapter"):
        payload["image_size"] = {
            "width": config.get("width", 1024),
            "height": config.get("height", 1024),
        }
        if "num_inference_steps" in config:
            payload["num_inference_steps"] = config["num_inference_steps"]
        if "guidance_scale" in config:
            payload["guidance_scale"] = config["guidance_scale"]

    # --- image_gen: optional LoRA ---
    if node_type == "image_gen":
        if "loras" in config:
            payload["loras"] = config["loras"]
        if "seed" in config:
            payload["seed"] = config["seed"]

    # --- img2img ---
    if node_type == "img2img":
        payload["image_url"] = _extract_image_url(config)
        if "strength" in config:
            payload["strength"] = config["strength"]

    # --- upscale ---
    if node_type == "upscale":
        payload["image_url"] = _extract_image_url(config)
        payload["scale"] = config.get("scale", 2)
        if "prompt" in config:
            payload["prompt"] = config["prompt"]
        if "num_inference_steps" in config:
            payload["num_inference_steps"] = config["num_inference_steps"]
        if "guidance_scale" in config:
            payload["guidance_scale"] = config["guidance_scale"]

    # --- seed ---
    if node_type == "seed":
        payload["seed"] = config.get("seed", 0)

    # --- inpaint ---
    if node_type == "inpaint":
        payload["image_url"] = _extract_image_url(config)
        payload["mask_url"] = config.get("mask_url", "")

    # --- outpaint ---
    if node_type == "outpaint":
        payload["image_url"] = _extract_image_url(config)

    # --- ip_adapter ---
    if node_type == "ip_adapter":
        payload["image_url"] = _extract_image_url(config)
        payload["ip_adapter_weight"] = config.get("ip_adapter_weight", 0.75)
        payload["style_strength_ratio"] = config.get("style_strength_ratio", 35)

    # --- remove_bg (birefnet) ---
    if node_type == "remove_bg":
        payload["image_url"] = _extract_image_url(config)

    # --- face_restore (codeformer) ---
    if node_type == "face_restore":
        payload["image_url"] = _extract_image_url(config)
        if "codeformer_fidelity" in config:
            payload["codeformer_fidelity"] = config["codeformer_fidelity"]

    return payload


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def _parse_image_result(response_data: dict) -> ImageResult:
    """Parse a Fal.ai COMPLETED response into an ImageResult.

    Handles multiple response formats:
      - images[0] (standard)
      - image (singular dict or string)
      - output.images / output.image (wrapped)
      - mask, cropped_images (inpaint/outpaint)
      - images (multiple outputs — takes first)
    """
    # Try standard "images" array first
    images = response_data.get("images", [])
    if not images:
        # Try singular "image" field
        img = response_data.get("image")
        if img and isinstance(img, dict):
            images = [img]
        elif img and isinstance(img, str):
            images = [{"url": img}]
    if not images:
        # Fallback: check output wrapper
        output = response_data.get("output", {})
        images = output.get("images", [])
        if not images:
            img = output.get("image")
            if img and isinstance(img, dict):
                images = [img]
            elif img and isinstance(img, str):
                images = [{"url": img}]

    # Handle inpaint/outpaint: check mask + cropped_images
    if not images:
        mask = response_data.get("mask")
        if mask and isinstance(mask, dict):
            images = [mask]
        elif mask and isinstance(mask, str):
            images = [{"url": mask}]
    if not images:
        cropped = response_data.get("cropped_images", [])
        if cropped:
            images = cropped

    if not images:
        raise RuntimeError(
            f"{PROVIDER_ERROR}: No images in Fal.ai response (keys={list(response_data.keys())})"
        )

    image = images[0]
    if isinstance(image, str):
        image = {"url": image}

    return ImageResult(
        url=image.get("url", ""),
        width=image.get("width", 0),
        height=image.get("height", 0),
        format=image.get("content_type", "png").split("/")[-1],
        metadata={"request_id": response_data.get("request_id", "")},
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class FalProvider(Provider):
    """Fal.ai image generation provider.

    Reads FAL_API_KEY from environment. Uses sync httpx.Client internally
    (wrapped in async method for Provider interface compatibility).

    API flow:
        1. POST https://queue.fal.run/{endpoint} → request_id
        2. GET .../requests/{request_id}/status → poll until COMPLETED
        3. GET .../requests/{request_id} → parse ImageResult
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get(FAL_API_KEY_ENV)
        if not self._api_key:
            raise RuntimeError(f"{PROVIDER_AUTH}: {FAL_API_KEY_ENV} environment variable not set")
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Lazily create the httpx client."""
        if self._client is None:
            self._client = httpx.Client(
                headers={
                    "Authorization": f"Key {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=DEFAULT_TIMEOUT,
            )
        return self._client

    async def generate(self, node_type: str, config: dict) -> ImageResult:
        """Submit a generation request and poll until complete (async wrapper).

        Args:
            node_type: The type of node (e.g., 'image_gen', 'inpaint').
            config: Node configuration with model, prompt, and parameters.

        Returns:
            An ImageResult with the generated image URL and metadata.

        Raises:
            RuntimeError: With PROVIDER_AUTH or PROVIDER_ERROR prefix on failure.
        """
        model = config.get("model", "flux-dev")
        endpoint = _resolve_endpoint(node_type, model)
        payload = _build_payload(node_type, config)

        submit_url = f"{FAL_BASE_URL}/{endpoint}"

        client = self._get_client()

        # Submit with retry
        response_data = self._submit_with_retry(client, submit_url, payload)
        request_id = response_data.get("request_id", "")

        if not request_id:
            raise RuntimeError(
                f"{PROVIDER_ERROR}: No request_id returned from Fal.ai (model={model})"
            )

        # Poll for completion
        status_url = response_data.get(
            "status_url",
            f"{FAL_BASE_URL}/{endpoint}/requests/{request_id}/status",
        )
        result_url = response_data.get(
            "response_url",
            f"{FAL_BASE_URL}/{endpoint}/requests/{request_id}",
        )

        max_polls = MAX_RETRIES * 10
        for _ in range(max_polls):
            try:
                resp = client.get(status_url)
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"{PROVIDER_AUTH}: Authentication failed (status={resp.status_code})"
                    )
                if resp.status_code >= 500:
                    resp.raise_for_status()

                try:
                    status_data = resp.json()
                except Exception as e:
                    raise RuntimeError(
                        f"Polling error: Invalid JSON from status endpoint "
                        f"(status={resp.status_code}, body='{resp.text[:200]}')"
                    ) from e
                status = status_data.get("status", "")

                if status == "COMPLETED":
                    result_resp = client.get(result_url)
                    if result_resp.status_code in (401, 403):
                        raise RuntimeError(
                            f"{PROVIDER_AUTH}: Authentication failed "
                            f"(status={result_resp.status_code})"
                        )
                    if result_resp.status_code >= 400:
                        raise RuntimeError(
                            f"{PROVIDER_ERROR}: Failed to retrieve result "
                            f"(status={result_resp.status_code}, model={model})"
                        )
                    try:
                        data = result_resp.json()
                    except Exception as e:
                        raise RuntimeError(
                            f"{PROVIDER_ERROR}: Invalid JSON response "
                            f"(status={result_resp.status_code}, "
                            f"body='{result_resp.text[:100]}')"
                        ) from e
                    return _parse_image_result(data)

                if status in ("FAILED", "CANCELLED"):
                    raise RuntimeError(
                        f"{PROVIDER_ERROR}: {model} generation {status.lower()} "
                        f"— check Fal.ai logs"
                    )

                await asyncio.sleep(2.0)

            except httpx.TimeoutException:
                raise RuntimeError(
                    f"{PROVIDER_ERROR}: Request timed out (model={model})"
                )

        raise RuntimeError(
            f"{PROVIDER_ERROR}: Polling exhausted for {model} "
            f"(request_id={request_id})"
        )

    def _submit_with_retry(self, client: httpx.Client, url: str, payload: dict) -> dict:
        """Submit a generation request with retry on transient network failures only."""
        last_error: str | None = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = client.post(url, json=payload)
            except httpx.TimeoutException:
                last_error = f"Timeout during submission (attempt {attempt + 1})"
                wait = (2 ** attempt) + (time.time() % 1.0)
                time.sleep(wait)
                continue
            except Exception as exc:
                last_error = str(exc)
                wait = (2 ** attempt) + (time.time() % 1.0)
                time.sleep(wait)
                continue
            else:
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"{PROVIDER_AUTH}: Invalid or missing API key "
                        f"(status={resp.status_code})"
                    )

                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"{PROVIDER_ERROR}: Fal.ai API error "
                        f"(status={resp.status_code}, model info in response)"
                    )

                try:
                    return resp.json()
                except Exception as e:
                    raise RuntimeError(
                        f"Submission error: Invalid JSON "
                        f"(status={resp.status_code}, body='{resp.text[:200]}')"
                    ) from e

        raise RuntimeError(
            f"{PROVIDER_ERROR}: Submission failed after {MAX_RETRIES} attempts: "
            f"{last_error}"
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
