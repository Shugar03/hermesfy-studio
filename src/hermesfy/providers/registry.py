"""Hardcoded model registry for available Fal.ai models."""

__all__ = ["get_models", "get_model"]

# Model catalog: each entry maps to an endpoint on queue.fal.run
_MODELS: list[dict] = [
    {
        "name": "flux-dev",
        "endpoint": "fal-ai/flux/dev",
        "description": "Flux Dev — fast text-to-image generation, good for rapid iteration",
        "supported_node_types": ["image_gen", "img2img"],
        "default_params": {
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        },
    },
    {
        "name": "flux-pro",
        "endpoint": "fal-ai/flux-pro",
        "description": "Flux Pro — highest quality text-to-image generation",
        "supported_node_types": ["image_gen", "img2img"],
        "default_params": {
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 40,
            "guidance_scale": 7.0,
        },
    },
    {
        "name": "flux-schnell",
        "endpoint": "fal-ai/flux/schnell",
        "description": "Flux Schnell — fastest inference, 4-step distilled model",
        "supported_node_types": ["image_gen"],
        "default_params": {
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 4,
            "guidance_scale": 3.5,
        },
    },
    {
        "name": "flux-depth",
        "endpoint": "fal-ai/flux-depth",
        "description": "Flux Depth — controlled depth-aware image generation",
        "supported_node_types": ["image_gen", "img2img"],
        "default_params": {
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 28,
            "guidance_scale": 5.0,
        },
    },
    {
        "name": "clarity-upscaler",
        "endpoint": "fal-ai/clarity-upscaler",
        "description": "Clarity Upscaler — high-fidelity 2x/4x image upscaling",
        "supported_node_types": ["upscale"],
        "default_params": {
            "scale": 2,
        },
    },
]


def get_models() -> list[dict]:
    """Return the full list of registered models.

    Returns:
        A list of model entry dicts, each containing:
        name, endpoint, description, supported_node_types, default_params.
    """
    return [dict(m) for m in _MODELS]  # Return copies to prevent mutation


def get_model(name: str) -> dict | None:
    """Look up a single model by name.

    Args:
        name: The exact model name (e.g., 'flux-dev', 'flux-pro').

    Returns:
        The model entry dict or None if not found.
    """
    for model in _MODELS:
        if model["name"] == name:
            return dict(model)
    return None
