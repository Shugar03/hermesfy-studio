"""Tests for YAML style loading and merge override semantics."""

import pytest

from hermesfy.styles.loader import load_style, merge_style


class TestLoadStyle:
    """Tests for loading style YAML files."""

    def test_load_cinematic(self):
        """cinematic.yaml loads without error and has prompt_prefix."""
        style = load_style("cinematic")
        assert "prompt_prefix" in style
        assert "cinematic" in style["prompt_prefix"].lower()

    def test_load_anime(self):
        """anime.yaml loads and has anime-related prefix."""
        style = load_style("anime")
        assert "prompt_prefix" in style
        assert "anime" in style["prompt_prefix"].lower()

    def test_load_photorealistic(self):
        """photorealistic.yaml loads correctly."""
        style = load_style("photorealistic")
        assert "prompt_prefix" in style
        assert "photorealistic" in style["prompt_prefix"].lower()

    def test_load_digital_art(self):
        """digital-art.yaml loads correctly."""
        style = load_style("digital-art")
        assert "prompt_prefix" in style
        assert "digital art" in style["prompt_prefix"].lower()

    def test_load_nonexistent_style_raises(self):
        """Loading a non-existent style raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_style("nonexistent-style")


class TestMergeStyle:
    """Tests for merge_style function — node config takes precedence."""

    def test_merge_preserves_node_values(self):
        """Node config values override style defaults."""
        style = {"guidance_scale": 7.5, "width": 1024}
        node_config = {"guidance_scale": 9.0, "prompt": "a dragon"}
        merged = merge_style(node_config, style)
        # Node value wins
        assert merged["guidance_scale"] == 9.0
        # Style default applied
        assert merged["width"] == 1024

    def test_merge_prepends_prompt_prefix(self):
        """Prompt prefix from style is prepended to node prompt."""
        style = {"prompt_prefix": "cinematic, 8k"}
        node_config = {"prompt": "a forest"}
        merged = merge_style(node_config, style)
        assert merged["prompt"] == "cinematic, 8k, a forest"

    def test_merge_without_prompt_prefix_keeps_original(self):
        """Without prompt_prefix, node prompt stays as-is."""
        style = {"guidance_scale": 7.0}
        node_config = {"prompt": "sunset over mountains"}
        merged = merge_style(node_config, style)
        assert merged["prompt"] == "sunset over mountains"

    def test_merge_empty_style_preserves_node(self):
        """Empty style dict leaves node config unchanged."""
        node_config = {"prompt": "test", "model": "flux-dev"}
        merged = merge_style(node_config, {})
        assert merged == node_config

    def test_merge_adds_style_keys_not_in_node(self):
        """Keys only in style are added to the result."""
        style = {"guidance_scale": 3.5, "num_inference_steps": 28}
        node_config = {"prompt": "test"}
        merged = merge_style(node_config, style)
        assert merged["guidance_scale"] == 3.5
        assert merged["num_inference_steps"] == 28
        assert merged["prompt"] == "test"
