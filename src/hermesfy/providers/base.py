"""Abstract base provider and ImageResult dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ImageResult:
    """Result from an image generation provider.

    Attributes:
        url: Public URL of the generated image.
        width: Image width in pixels.
        height: Image height in pixels.
        format: Image format (e.g., png, jpeg, webp).
        metadata: Arbitrary additional metadata (seed, inference time, etc.).
    """

    url: str
    width: int
    height: int
    format: str = "png"
    metadata: dict = field(default_factory=dict)


class Provider(ABC):
    """Abstract base class for image generation providers.

    Subclasses must implement generate() to produce an ImageResult.
    """

    @abstractmethod
    async def generate(self, node_type: str, config: dict) -> ImageResult:
        """Generate an image from the given configuration (async).

        Args:
            node_type: The type of node being executed (e.g., 'image_gen', 'upscale').
            config: Node-specific configuration dict with model, prompt, params.

        Returns:
            An ImageResult with the generated image URL and metadata.

        Raises:
            RuntimeError: On provider-level errors (auth, rate limit, timeout, etc.).
        """
        ...
