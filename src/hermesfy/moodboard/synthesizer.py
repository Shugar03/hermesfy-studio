"""Synthesizer — N StructuredSpecs → 1 MOOD_SPEC unificado.

Toma los análisis individuales del VRH y los sintetiza en un solo
MOOD_SPEC que representa el consenso estético de todo el set de referencias.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger("hermesfy.moodboard.synthesizer")


@dataclass
class MoodSpec:
    """Estructura unificada de un moodboard."""
    session_id: str = ""
    concept: str = ""
    source: str = ""
    source_url: str | None = None
    status: str = "synthesized"

    # Síntesis visual
    dominant_palette: list[str] = field(default_factory=list)
    mood_majority: str = ""
    mood_votes: dict[str, int] = field(default_factory=dict)
    lighting_consensus: str = ""
    composition_mode: str = ""
    technique_majority: str = ""
    texture_trend: str = ""

    # Estadísticas
    total_images_analyzed: int = 0
    images_used: int = 0
    confidence: float = 0.0  # 0-1 qué tan homogéneo es el set

    # Hint para marca (se llena en brand_merge)
    brand_applied: bool = False
    brand_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MoodSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_preview_md(self) -> str:
        """Genera un preview Markdown legible del mood spec."""
        lines = [
            f"# Moodboard: {self.concept}",
            f"",
            f"**ID:** `{self.session_id}` | **Fuente:** {self.source}",
            f"**Análisis:** {self.images_used} imágenes de {self.total_images_analyzed}",
            f"**Confianza:** {self.confidence:.0%}",
            f"**Marca aplicada:** {'Sí (' + self.brand_name + ')' if self.brand_applied else 'No'}",
            f"",
            f"## 🎨 Paleta dominante",
        ]
        for hex_color in self.dominant_palette:
            lines.append(f"- `{hex_color}`")
        lines += [
            f"",
            f"## 😌 Mood",
            f"- **Mayoritario:** {self.mood_majority}",
            f"- **Votos:** {json.dumps(self.mood_votes, indent=2)}",
            f"",
            f"## 💡 Iluminación",
            f"- {self.lighting_consensus}",
            f"",
            f"## 📐 Composición",
            f"- {self.composition_mode}",
            f"",
            f"## 🔧 Técnica",
            f"- {self.technique_majority}",
        ]
        if self.texture_trend:
            lines += ["", f"## 🧵 Textura", f"- {self.texture_trend}"]
        return "\n".join(lines)


class Synthesizer:
    """Sintetiza N StructuredSpecs en un solo MoodSpec."""

    @staticmethod
    def _extract_palette(spec: dict) -> list[str]:
        """Extrae colores HEX de un spec."""
        palette = []
        try:
            p = spec.get("palette", {})
            if isinstance(p, dict):
                colors = p.get("colors", p.get("hex", []))
            elif isinstance(p, list):
                colors = p
            else:
                colors = []
            for c in colors:
                if isinstance(c, str) and c.startswith("#"):
                    palette.append(c.upper())
                elif isinstance(c, dict) and "hex" in c:
                    palette.append(c["hex"].upper())
        except Exception:
            pass
        return palette

    @staticmethod
    def _safe_get(spec: dict, *keys, default="") -> str:
        """Navega seguro por el spec."""
        try:
            val = spec
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k, {})
                elif isinstance(val, str):
                    return val
                else:
                    return default
            return str(val) if val else default
        except Exception:
            return default

    def synthesize(self, specs: list[dict], session_id: str = "", concept: str = "") -> MoodSpec:
        """N specs → 1 MoodSpec unificado."""
        if not specs:
            return MoodSpec(
                session_id=session_id,
                concept=concept,
                status="error",
                images_used=0,
                total_images_analyzed=0,
            )

        # 1. Extraer paletas
        all_colors = []
        for spec in specs:
            all_colors.extend(self._extract_palette(spec))
        # Top 6 colores más repetidos
        color_counts = Counter(all_colors)
        dominant_palette = [c for c, _ in color_counts.most_common(6)]

        # 2. Mood majority
        moods = [
            self._safe_get(s, "composition", "mood") or
            self._safe_get(s, "semantic", "mood") or
            self._safe_get(s, "mood")
            for s in specs
        ]
        moods = [m for m in moods if m]
        mood_counts = Counter(moods)
        mood_majority = mood_counts.most_common(1)[0][0] if mood_counts else ""

        # 3. Lighting consensus
        lightings = [
            self._safe_get(s, "lighting", "direction") or
            self._safe_get(s, "lighting", "type")
            for s in specs
        ]
        lightings = [l for l in lightings if l]
        lighting_consensus = Counter(lightings).most_common(1)[0][0] if lightings else ""

        # 4. Composition mode
        comps = [
            self._safe_get(s, "composition", "rule") or
            self._safe_get(s, "composition", 0) if isinstance(s, dict) else ""
            for s in specs
        ]
        comps = [c for c in comps if c]
        composition_mode = Counter(comps).most_common(1)[0][0] if comps else ""

        # 5. Technique majority
        techs = [self._safe_get(s, "semantic", "technique") for s in specs]
        techs = [t for t in techs if t]
        technique_majority = Counter(techs).most_common(1)[0][0] if techs else ""

        # 6. Texture trend
        textures = [self._safe_get(s, "semantic", "texture") for s in specs]
        textures = [t for t in textures if t]
        texture_trend = Counter(textures).most_common(1)[0][0] if textures else ""

        # 7. Confidence
        n = len(specs)
        total_votes = sum(c for c in mood_counts.values()) if mood_counts else 1
        top_votes = mood_counts.most_common(1)[0][1] if mood_counts else 0
        confidence = top_votes / total_votes if total_votes > 0 else 0.5

        return MoodSpec(
            session_id=session_id,
            concept=concept,
            status="synthesized",
            dominant_palette=dominant_palette,
            mood_majority=mood_majority,
            mood_votes=dict(mood_counts.most_common(5)),
            lighting_consensus=lighting_consensus,
            composition_mode=composition_mode,
            technique_majority=technique_majority,
            texture_trend=texture_trend,
            total_images_analyzed=n,
            images_used=n,
            confidence=round(confidence, 2),
        )
