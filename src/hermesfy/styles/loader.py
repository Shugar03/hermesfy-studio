"""YAML style loader — load and merge preset styles into node configs."""

from pathlib import Path

import yaml

_STYLES_DIR = Path(__file__).parent


def load_style(name: str) -> dict:
    """Load a style preset from a YAML file.

    Args:
        name: Style name without extension (e.g., 'cinematic', 'anime').

    Returns:
        Dict with style parameters.

    Raises:
        FileNotFoundError: If the style file doesn't exist.
        ValueError: If the YAML is invalid.
    """
    filepath = _STYLES_DIR / f"{name}.yaml"
    if not filepath.exists():
        raise FileNotFoundError(f"Style '{name}' not found at {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Style '{name}' is not a valid YAML dict")
    return data


def merge_style(node_config: dict, style: dict) -> dict:
    """Merge a style preset into node config. Node config values take precedence.

    Args:
        node_config: The node's current configuration.
        style: The style preset dict to merge.

    Returns:
        A new dict with style defaults applied, overridden by node_config values.
    """
    merged = dict(style)
    merged.update(node_config)

    # Special handling: if the style has a prompt_prefix, prepend it
    if "prompt_prefix" in style and "prompt" in node_config:
        prefix = style["prompt_prefix"]
        merged["prompt"] = f"{prefix}, {node_config['prompt']}"

    return merged
