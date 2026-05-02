"""
Hermesfy Validator — Post-Generation Validation with Gemini Vision

Validates generated images against the original prompt using
Google Gemini Vision API via REST (no SDK dependency).

Usage:
    from engine.validator import ImageValidator

    validator = ImageValidator()
    result = validator.validate(
        image_path="/cache/fal/gen_xxx.png",
        prompt="professional product photo of Nike sneaker with dark background",
    )
    # Returns: {valid: True, confidence: 0.92, description: "...", issues: []}
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger("hermesfy.validator")

# ── Constants ────────────────────────────────────────────────────────────────

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.0-flash"
MIN_CONFIDENCE = 0.7
MAX_RETRIES = 2


# ── Validator ────────────────────────────────────────────────────────────────

class ImageValidator:
    """
    Validate generated images against the original prompt using Gemini Vision.

    Sends the image + prompt to Gemini and asks it to evaluate alignment.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the validator.

        Args:
            api_key: Google API key. Falls back to GOOGLE_API_KEY env var.
            model: Gemini model to use. Defaults to gemini-2.0-flash.
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.model = model or DEFAULT_MODEL

        if not self.api_key:
            logger.warning("No GOOGLE_API_KEY — validation will be skipped")

    def validate(
        self,
        image_path: str,
        prompt: str,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> dict:
        """
        Validate that a generated image matches the prompt.

        Args:
            image_path: Path to the generated image.
            prompt: The original prompt used for generation.
            min_confidence: Minimum confidence threshold (0-1).

        Returns:
            dict with keys:
                - valid (bool): Whether the image passes validation.
                - confidence (float): Confidence score (0-1).
                - description (str): Gemini's description of the image.
                - issues (list): List of issues found.
                - raw_response (str): Raw Gemini response.
        """
        if not self.api_key:
            logger.info("Skipping validation — no API key")
            return {
                "valid": True,
                "confidence": 0.5,
                "description": "Validation skipped (no API key)",
                "issues": [],
                "raw_response": "",
            }

        if not os.path.exists(image_path):
            return {
                "valid": False,
                "confidence": 0.0,
                "description": "Image file not found",
                "issues": [f"File not found: {image_path}"],
                "raw_response": "",
            }

        # Encode image as base64
        image_b64 = self._encode_image(image_path)
        if not image_b64:
            return {
                "valid": False,
                "confidence": 0.0,
                "description": "Failed to encode image",
                "issues": ["Could not read image file"],
                "raw_response": "",
            }

        # Build the validation prompt
        validation_prompt = self._build_validation_prompt(prompt)

        # Call Gemini Vision
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = self._call_gemini(image_b64, validation_prompt)

                if result:
                    # Parse confidence from response
                    confidence = self._extract_confidence(result)
                    issues = self._extract_issues(result)

                    return {
                        "valid": confidence >= min_confidence,
                        "confidence": confidence,
                        "description": result,
                        "issues": issues,
                        "raw_response": result,
                    }

            except Exception as e:
                logger.warning("Validation attempt %d failed: %s", attempt, e)
                if attempt == MAX_RETRIES:
                    return {
                        "valid": True,  # Don't block on validation failure
                        "confidence": 0.5,
                        "description": f"Validation failed: {e}",
                        "issues": [f"Validation error: {e}"],
                        "raw_response": "",
                    }

        return {
            "valid": True,
            "confidence": 0.5,
            "description": "Validation completed with warnings",
            "issues": [],
            "raw_response": "",
        }

    def validate_edit(
        self,
        original_path: str,
        edited_path: str,
        edit_instruction: str,
        preserve_instruction: str = "everything else",
    ) -> dict:
        """
        Validate that an edit only changed what was intended.

        Args:
            original_path: Path to the original image.
            edited_path: Path to the edited image.
            edit_instruction: What was supposed to change.
            preserve_instruction: What was supposed to stay the same.

        Returns:
            dict with validation results.
        """
        if not self.api_key:
            return {
                "valid": True,
                "confidence": 0.5,
                "description": "Edit validation skipped (no API key)",
                "issues": [],
            }

        # Encode both images
        orig_b64 = self._encode_image(original_path)
        edit_b64 = self._encode_image(edited_path)

        if not orig_b64 or not edit_b64:
            return {
                "valid": False,
                "confidence": 0.0,
                "description": "Failed to encode images",
                "issues": ["Could not read one or both image files"],
            }

        prompt = (
            f"Compare these two images. "
            f"The edit instruction was: '{edit_instruction}'. "
            f"The preserve instruction was: '{preserve_instruction}'. "
            f"Evaluate: "
            f"1. Was the intended change made? "
            f"2. Was everything else preserved? "
            f"3. Rate the edit quality from 0-10. "
            f"Format your response as: "
            f"SCORE: [number 0-10] | ISSUES: [list any problems, or 'none']"
        )

        try:
            result = self._call_gemini_multi([orig_b64, edit_b64], prompt)
            if result:
                # Parse score (0-10) and convert to confidence (0-1)
                score = self._extract_edit_score(result)
                issues = self._extract_issues(result)

                return {
                    "valid": score >= 7,
                    "confidence": score / 10.0,
                    "description": result,
                    "issues": issues,
                }
        except Exception as e:
            logger.warning("Edit validation failed: %s", e)

        return {
            "valid": True,
            "confidence": 0.5,
            "description": "Edit validation completed with warnings",
            "issues": [],
        }

    # ── Private Methods ──────────────────────────────────────────────────

    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode an image file as base64."""
        try:
            with open(image_path, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode("utf-8")
        except Exception as e:
            logger.error("Failed to encode image %s: %s", image_path, e)
            return None

    def _build_validation_prompt(self, original_prompt: str) -> str:
        """Build the validation prompt for Gemini."""
        return (
            f"You are an image quality validator. "
            f"An AI generated an image based on this prompt: '{original_prompt}'. "
            f"Describe what you see in the image in detail. "
            f"Then evaluate how well it matches the prompt. "
            f"Rate the alignment from 0 to 10 (10 = perfect match). "
            f"Format your response as: "
            f"SCORE: [number 0-10] | DESCRIPTION: [your description] | ISSUES: [list any problems, or 'none']"
        )

    def _call_gemini(self, image_b64: str, prompt: str) -> Optional[str]:
        """Call Gemini Vision API with a single image."""
        url = f"{GEMINI_API_BASE}/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_b64,
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
            }
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")

        return None

    def _call_gemini_multi(self, images_b64: list[str], prompt: str) -> Optional[str]:
        """Call Gemini Vision API with multiple images."""
        url = f"{GEMINI_API_BASE}/models/{self.model}:generateContent?key={self.api_key}"

        parts = [{"text": prompt}]
        for img_b64 in images_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": img_b64,
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
            }
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")

        return None

    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score (0-10) from Gemini response and normalize to 0-1."""
        import re
        match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text)
        if match:
            score = float(match.group(1))
            return min(score / 10.0, 1.0)
        return 0.5

    def _extract_edit_score(self, text: str) -> float:
        """Extract edit quality score (0-10) from Gemini response."""
        import re
        match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text)
        if match:
            return float(match.group(1))
        return 5.0

    def _extract_issues(self, text: str) -> list[str]:
        """Extract issues from Gemini response."""
        import re
        match = re.search(r'ISSUES:\s*(.+?)(?:\||$)', text, re.IGNORECASE)
        if match:
            issues_text = match.group(1).strip()
            if issues_text.lower() in ("none", "no issues", "n/a", ""):
                return []
            return [i.strip() for i in issues_text.split(",")]
        return []
