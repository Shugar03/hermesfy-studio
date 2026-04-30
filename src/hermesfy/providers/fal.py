"""Fal.ai HTTP provider — async image generation via queue.fal.run."""

from __future__ import annotations

import asyncio
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

# Map model names to their API endpoints
_MODEL_ENDPOINTS: dict[str, str] = {
    "flux-dev": "fal-ai/flux/dev",
    "flux-pro": "fal-ai/flux-pro",
    "flux-schnell": "fal-ai/flux/schnell",
    "flux-depth": "fal-ai/flux-depth",
    "clarity-upscaler": "fal-ai/clarity-upscaler",
}


def _resolve_endpoint(model: str) -> str:
    """Resolve a model name to its Fal.ai endpoint path."""
    return _MODEL_ENDPOINTS.get(model, model)


def _build_payload(node_type: str, config: dict) -> dict:
    """Map node config keys to Fal.ai API parameters."""
    payload: dict = {}

    if "prompt" in config:
        payload["prompt"] = config["prompt"]

    if node_type in ("image_gen", "img2img"):
        payload["image_size"] = {
            "width": config.get("width", 1024),
            "height": config.get("height", 1024),
        }
        if "num_inference_steps" in config:
            payload["num_inference_steps"] = config["num_inference_steps"]
        if "guidance_scale" in config:
            payload["guidance_scale"] = config["guidance_scale"]

    if node_type == "img2img":
        payload["image_url"] = config.get("image_url", "")
        if "strength" in config:
            payload["strength"] = config["strength"]

    if node_type == "upscale":
        payload["image_url"] = config.get("image_url", "")
        payload["scale"] = config.get("scale", 2)

    if node_type == "seed":
        payload["seed"] = config.get("seed", 0)

    return payload


def _parse_image_result(response_data: dict) -> ImageResult:
    """Parse a Fal.ai COMPLETED response into an ImageResult."""
    output = response_data.get("output", {})
    images = output.get("images", [])
    if not images:
        raise RuntimeError(f"{PROVIDER_ERROR}: No images in Fal.ai response")

    image = images[0]
    return ImageResult(
        url=image.get("url", ""),
        width=image.get("width", 0),
        height=image.get("height", 0),
        format=image.get("content_type", "png").split("/")[-1],
        metadata={"request_id": response_data.get("request_id", "")},
    )


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
            node_type: The type of node (e.g., 'image_gen', 'upscale').
            config: Node configuration with model, prompt, and parameters.

        Returns:
            An ImageResult with the generated image URL and metadata.

        Raises:
            RuntimeError: With PROVIDER_AUTH or PROVIDER_ERROR prefix on failure.
        """
        model = config.get("model", "flux-dev")
        endpoint = _resolve_endpoint(model)
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
        status_url = f"{FAL_BASE_URL}/{endpoint}/requests/{request_id}/status"
        result_url = f"{FAL_BASE_URL}/{endpoint}/requests/{request_id}"

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

                status_data = resp.json()
                status = status_data.get("status", "")

                if status == "COMPLETED":
                    result_resp = client.get(result_url)
                    if result_resp.status_code in (401, 403):
                        raise RuntimeError(
                            f"{PROVIDER_AUTH}: Authentication failed (status={result_resp.status_code})"
                        )
                    if result_resp.status_code >= 400:
                        raise RuntimeError(
                            f"{PROVIDER_ERROR}: Failed to retrieve result "
                            f"(status={result_resp.status_code}, model={model})"
                        )
                    return _parse_image_result(result_resp.json())

                if status in ("FAILED", "CANCELLED"):
                    raise RuntimeError(
                        f"{PROVIDER_ERROR}: {model} generation {status.lower()} — check Fal.ai logs"
                    )

                await asyncio.sleep(2.0)

            except httpx.TimeoutException:
                raise RuntimeError(f"{PROVIDER_ERROR}: Request timed out (model={model})")

        raise RuntimeError(
            f"{PROVIDER_ERROR}: Polling exhausted for {model} (request_id={request_id})"
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
                # Network-level errors only (connection, DNS, etc.)
                # httpx wraps these. Do NOT retry business errors.
                last_error = str(exc)
                wait = (2 ** attempt) + (time.time() % 1.0)
                time.sleep(wait)
                continue
            else:
                # No exception — got a response. Check status.
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"{PROVIDER_AUTH}: Invalid or missing API key (status={resp.status_code})"
                    )

                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"{PROVIDER_ERROR}: Fal.ai API error "
                        f"(status={resp.status_code}, model info in response)"
                    )

                return resp.json()

        raise RuntimeError(
            f"{PROVIDER_ERROR}: Submission failed after {MAX_RETRIES} attempts: {last_error}"
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
