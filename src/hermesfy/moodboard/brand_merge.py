"""Brand Merger — fusiona MOOD_SPEC con DESIGN.md de marca.

Toma el mood spec sintetizado y le aplica las restricciones del manual
de marca. La marca SIEMPRE gana en: colores, tipografía, tono.
La referencia mantiene: composición, iluminación, mood (si compatible).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger("hermesfy.moodboard.brand_merge")

BRANDS_DIR = Path.home() / ".hermesfy" / "brands"


def load_design_md(brand_name: str) -> dict | None:
    """Carga el DESIGN.md de una marca.

    Busca en ~/.hermesfy/brands/<brand_name>/design.md
    """
    paths = [
        BRANDS_DIR / brand_name / "design.md",
        BRANDS_DIR / brand_name / "design.yaml",
        BRANDS_DIR / brand_name / "design.yml",
    ]
    for p in paths:
        if p.exists():
            try:
                content = p.read_text()
                # Intentar YAML primero (por schema), fallback a raw dict
                if content.strip().startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 2:
                        return yaml.safe_load(parts[1]) or {}
                return yaml.safe_load(content) or {}
            except Exception as e:
                logger.warning("Failed to parse %s: %s", p, e)
                return None
    return None


def merge_with_brand(
    mood_spec: dict,
    brand_name: str,
    brand_config: dict | None = None,
) -> dict:
    """Fusiona el mood_spec con la identidad de marca.

    Args:
        mood_spec: Dict del MoodSpec.to_dict()
        brand_name: Nombre de la marca
        brand_config: Config opcional (si ya está cargada)

    Returns:
        MoodSpec modificado con brand constraints aplicados
    """
    if brand_config is None:
        brand_config = load_design_md(brand_name)

    if not brand_config:
        logger.info("No brand config found for '%s', returning raw spec", brand_name)
        return mood_spec

    mood_spec = dict(mood_spec)  # Copia para no mutar original

    # 🔴 Marca gana: colores
    brand_colors = brand_config.get("colors", {})
    if brand_colors:
        color_values = []
        for key in ("primary", "secondary", "accent", "background", "text"):
            val = brand_colors.get(key)
            if val and isinstance(val, str) and val.startswith("#"):
                color_values.append(val.upper())
        if color_values:
            mood_spec["dominant_palette"] = color_values
            logger.info("Brand colors applied: %s", color_values)

    # 🔴 Marca gana: tipografía
    typography = brand_config.get("typography", {})
    if typography:
        mood_spec["typography"] = {
            "headings": typography.get("headings", ""),
            "body": typography.get("body", ""),
            "sizes": typography.get("sizes", {}),
        }

    # 🔴 Marca gana: tono
    tone = brand_config.get("tone", "")
    if tone:
        mood_spec["brand_tone"] = tone

    # 🟢 Se mantiene: mood (si compatible con marca)
    # Si el brand tiene 'tone', podemos verificar compatibilidad
    # pero por ahora lo dejamos pasar

    # 🟢 Se mantiene: iluminación
    # (no hay conflicto con marca)

    # 🟢 Se mantiene: composición
    # (no hay conflicto con marca)

    # Marcar que brand fue aplicado
    mood_spec["brand_applied"] = True
    mood_spec["brand_name"] = brand_name

    # Agregar elementos de marca si existen
    elements = brand_config.get("elements", [])
    if elements:
        mood_spec["brand_elements"] = elements

    # Agregar formatos disponibles
    formats = brand_config.get("formats", {})
    if formats:
        mood_spec["brand_formats"] = formats

    return mood_spec
