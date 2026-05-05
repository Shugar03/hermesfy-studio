"""Hermesfy Visual Reference Harness (VRH) — módulo de análisis y traducción de referencias visuales.

Pipeline: Telegram → VisualAnalyzer → SpecBridge → DAG → Delivery
"""

from hermesfy.reference.visual_analyzer import VisualAnalyzer, StructuredSpec
from hermesfy.reference.spec_bridge import SpecBridge
from hermesfy.reference.delivery import Delivery

__all__ = ["VisualAnalyzer", "StructuredSpec", "SpecBridge", "Delivery"]
