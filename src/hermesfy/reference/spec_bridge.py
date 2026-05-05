"""Spec Bridge — convierte StructuredSpec en ExecutionSpec para Hermesfy DAG.

Fase 2 del pipeline VRH:
  StructuredSpec JSON + user_prompt → ExecutionSpec JSON

El puente construye un prompt estructurado a partir de las secciones visuales
extraídas, y genera los parámetros de generación (modelo, calidad, seed, etc.)
alineados con el SDD visual de la referencia.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from hermesfy.reference.visual_analyzer import StructuredSpec

logger = logging.getLogger("hermesfy.reference.spec_bridge")


# ── Secciones de prompt ───────────────────────────────────────────────────────

PROMPT_SECTIONS = {
    "subject": """[SUBJECT]
{subject} on a {environment} scene
POSITION: center at ({x_pct}%, {y_pct}%), {size_pct}% of canvas width
DEPTH: {depth_blur}, z-index {z_index}
GROUNDING: {grounding}""",

    "environment": """[ENVIRONMENT]
Background: {gradient_type} gradient {gradient_direction}: {gradient_stops}
Elements: {elements}
Lighting: {light_type} from {light_direction}
Shadows: {shadow_type} at {shadow_opacity} opacity{god_rays_str}{bubbles_str}""",

    "style": """[STYLE]
Technique: {technique}
Mood: {mood}
Color palette: {hex_list}
Aspect ratio: {aspect_ratio}, {pixels}
Negative space: {negative_space}%
Rule: {composition_rule}""",

    "typography": """[TYPOGRAPHY]
Families: {type_families}
Hierarchy:
{hierarchy_detail}""",
}


class SpecBridge:
    """Traduce StructuredSpec visual a ExecutionSpec listo para Hermesfy."""

    def __init__(self):
        self._last_spec: StructuredSpec | None = None
        self._last_fidelity: float = 0.85

    # ── Goldilocks Rule ────────────────────────────────────────────────────────

    def _determine_fidelity(self, user_prompt: str) -> tuple[float, float, str]:
        """Goldilocks Rule: determinar fidelity_ratio según el prompt del usuario.

        Retorna:
            (fidelity_ratio, semantic_drift, override_note)
        """
        prompt = user_prompt.lower()

        rules = [
            # Minimal primero (señal más fuerte — override de intención)
            (["ignorá", "sin referencia", "hacé lo que quieras",
              "no uses la imagen", "creativo libre", "de cero",
              "inventá", "creá algo nuevo", "ignorá la foto"], 0.25, "Mínima fidelidad"),
            # High
            (["exactamente igual", "copia exacta", "idéntico", "mismo",
              "sin cambiar", "solo cambia", "mantené todo", "mantené el",
              "cloná", "calcá", "reproducí"], 0.95, "Alta fidelidad"),
            # Medium
            (["parecido", "como esta foto", "similar", "misma onda",
              "mismo estilo", "referencia", "estilo de", "tipo este",
              "como la imagen", "como esta"], 0.85, "Fidelidad media"),
            # Low
            (["inspirado", "algo así", "más o menos", "onda", "vibra",
              "tirando a", "parecido a", "más o menos así"], 0.60, "Baja fidelidad"),
        ]

        for keywords, fidelity, label in rules:
            if any(kw in prompt for kw in keywords):
                return fidelity, round(1.0 - fidelity, 2), label

        return 0.85, 0.15, "Fidelidad media (default)"

    # ── Preview ────────────────────────────────────────────────────────────────

    def preview_text(self, spec: StructuredSpec, fidelity: float | None = None) -> str:
        """Generar preview legible del StructuredSpec para validación del usuario.

        Args:
            spec: StructuredSpec del análisis visual.
            fidelity: Fidelity ratio opcional (se muestra en el preview).

        Returns:
            Texto formateado con emojis y secciones legibles.
        """
        if fidelity is None:
            fidelity = self._last_fidelity

        lines: list[str] = []

        def _quality_indicator(value, threshold=0.5):
            """✅ si el valor es concreto, ⚠️ si es genérico, ❌ si está vacío."""
            if not value or value == "" or value == "unknown":
                return "❌"
            if isinstance(value, str) and value in ("studio", "neutral", "photography",
                                                     "sans-serif", "centered"):
                return "⚠️"
            return "✅"

        # ── Canvas / Layout ──
        lines.append("📐 LAYOUT")
        x = spec.layout.product_position.x_pct
        y = spec.layout.product_position.y_pct
        size = spec.layout.product_size_pct
        lines.append(f"  Producto en ({x}%, {y}%), ocupando {size}% del canvas")
        lines.append(f"  Depth: {len(spec.layout.depth_layers)} capas (z-index {spec.layout.product_z_index})")
        lines.append(f"  Blur: {spec.layout.product_depth_blur} | Grounding: {spec.layout.product_grounding}")
        if spec.layout.text_zones:
            zones = [z.get('zone', '?') for z in spec.layout.text_zones]
            lines.append(f"  Zonas de texto: {', '.join(zones)}")

        # ── Paleta ──
        lines.append("")
        lines.append("🎨 PALETA")
        if spec.palette.colors:
            for c in spec.palette.colors[:5]:
                icon = _quality_indicator(c.role)
                lines.append(f"  {icon} {c.hex} ({c.role}) — {c.pct}%")
        else:
            lines.append("  ❌ No se detectaron colores")
        if spec.palette.gradient:
            g = spec.palette.gradient
            stops_str = ", ".join(g.stops[:3]) if g.stops else "—"
            lines.append(f"  Gradiente: {g.type} {g.direction} [{stops_str}]")

        # ── Iluminación ──
        lines.append("")
        lines.append("💡 ILUMINACIÓN")
        li = spec.lighting
        ico = _quality_indicator(li.type)
        lines.append(f"  {ico} Tipo: {li.type} desde {li.direction}")
        lines.append(f"  Sombras: {li.shadow_type} ({li.shadow_opacity * 100:.0f}% opacidad)")
        if li.god_rays:
            lines.append("  ✅ Rayos de luz volumétricos")
        if li.bubbles and li.bubbles.get("present"):
            b = li.bubbles
            lines.append(f"  ✅ Burbujas: {b.get('count', 'sí')}, {b.get('size_range', '—')}, {b.get('distribution', '—')}")

        # ── Composición ──
        lines.append("")
        lines.append("📝 COMPOSICIÓN")
        c = spec.composition
        lines.append(f"  {_quality_indicator(c.rule)} Regla: {c.rule}")
        lines.append(f"  {_quality_indicator(c.mood)} Mood: {c.mood}")
        lines.append(f"  {_quality_indicator(c.technique)} Técnica: {c.technique}")
        lines.append(f"  Negative space: {c.negative_space_pct}%")

        # ── Semántica ──
        lines.append("")
        lines.append("🏷️ SEMÁNTICA")
        s = spec.semantic
        lines.append(f"  {_quality_indicator(s.subject)} Sujeto: {s.subject or 'no detectado'}")
        lines.append(f"  {_quality_indicator(s.environment)} Entorno: {s.environment or 'no detectado'}")
        if s.brand_vibe:
            lines.append(f"  🏷️ Brand vibe: {s.brand_vibe}")

        # ── Canvas info ──
        lines.append("")
        lines.append(f"📱 Canvas: {spec.canvas.aspect_ratio} {spec.canvas.orientation} ({spec.canvas.original_pixels})")

        # ── Fidelity ──
        lines.append("")
        drift = round(1.0 - fidelity, 2)
        lines.append(f"🎯 FIDELIDAD: {int(fidelity * 100)}% | Drift: {int(drift * 100)}%")

        return "\n".join(lines)

    # ── Build principal ────────────────────────────────────────────────────────

    def build(self, spec: StructuredSpec,
              user_prompt: str = "",
              reference_mode: str = "style_layout",
              quality: str = "high",
              fidelity_override: float | None = None,
              preview: bool = False) -> dict | str:
        """Construir un ExecutionSpec listo para el DAG de Hermesfy.

        Args:
            spec: StructuredSpec del análisis visual.
            user_prompt: Prompt adicional del usuario (ej: "producto Vichy").
            reference_mode: Qué preservar ("style", "layout", "subject", o combinado).
            quality: "high" para final, "low" para prototipado.
            fidelity_override: Forzar un valor de fidelity (opcional).
            preview: Si True, retorna el texto de preview sin ejecutar nada.

        Returns:
            ExecutionSpec dict, o str si preview=True.
        """
        self._last_spec = spec

        # ── Goldilocks Rule ──
        if fidelity_override is not None:
            fidelity = float(fidelity_override)
            drift = round(1.0 - fidelity, 2)
            note = "Fidelidad forzada por el usuario"
        else:
            fidelity, drift, note = self._determine_fidelity(user_prompt)
        self._last_fidelity = fidelity

        # ── Preview mode (no ejecuta generación) ──
        if preview:
            return self.preview_text(spec, fidelity)

        prompt = self._build_prompt(spec, user_prompt, reference_mode)
        negative = self._build_negative_prompt(spec)

        # Aplicar máscara de atención si fidelity > 0.90
        if fidelity > 0.90:
            prompt = f"[FIDELITY HIGH — preservar composición exacta]\n{prompt}"

        # Aplicar "ignore source" si semantic_drift > 0.60
        if drift > 0.60:
            prompt = f"[IGNORE SOURCE — referencia solo para inspiración]\n{prompt}"

        # Elegir modelo según técnica
        model = self._select_model(spec.composition.technique, quality)

        # Elegir seed basado en spec (consistencia)
        seed = self._compute_seed(spec)

        # Calcular costo estimado
        budget = 0.045 if quality == "high" else 0.015

        # Elegir dimensiones
        width, height = self._get_dimensions(spec.canvas.aspect_ratio)

        execution_spec = {
            "routing_decision": {
                "intent_category": "product",
                "action": "generate",
                "target_model": model,
                "budget_estimation": budget,
                "priority": "quality" if quality == "high" else "cost"
            },
            "dag_workflow": {
                "steps": [
                    {
                        "node_id": 1,
                        "action": "base_generation",
                        "model": model,
                        "params": {
                            "prompt": prompt,
                            "negative_prompt": negative,
                            "width": width,
                            "height": height,
                            "num_inference_steps": 28 if quality == "high" else 14,
                            "guidance_scale": 3.5,
                            "seed": seed
                        }
                    }
                ]
            },
            "error_handling": {
                "retry_strategy": "exponential_backoff",
                "max_retries": 2,
                "fallback_model": "fal-ai/flux/dev"
            },
            "prompt_metadata": {
                "cleaned_prompt": prompt,
                "negative_prompt": negative,
                "seed": seed
            },
            # ── VRH-specific params ──
            "vrh": {
                "reference_mode": reference_mode,
                "fidelity_ratio": fidelity,
                "semantic_drift": drift,
                "original_spec": spec.to_dict()
            }
        }

        return execution_spec

    def _build_prompt(self, spec: StructuredSpec,
                      user_prompt: str, mode: str) -> str:
        """Construir prompt estructurado sección por sección."""
        s = spec  # shorthand

        # Elementos decorativos
        elements = []
        if s.lighting.bubbles and s.lighting.bubbles.get("present"):
            bubbles = s.lighting.bubbles
            elements.append(
                f"{bubbles.get('count', 'many')} bubbles, "
                f"{bubbles.get('size_range', '2-15px')}, "
                f"opacity {bubbles.get('opacity', 0.4)}, "
                f"{bubbles.get('distribution', 'random')} distribution"
            )
        if s.composition.framing and s.composition.framing != "none":
            elements.append(f"{s.composition.framing} framing")
        elements_str = ", ".join(elements) if elements else "subtle ambient particles"

        # Gradiente
        grad = spec.palette.gradient
        if grad:
            gradient_stops = ", ".join(grad.stops) if grad.stops else f"{spec.palette.colors[0].hex if spec.palette.colors else '#000'} to {spec.palette.colors[1].hex if len(spec.palette.colors) > 1 else '#fff'}"
        else:
            gradient_stops = f"{spec.palette.colors[0].hex if spec.palette.colors else '#000'} to {spec.palette.colors[1].hex if len(spec.palette.colors) > 1 else '#fff'}"

        # God rays
        god_rays_str = "\nGod rays: volumetric light beams from above" if s.lighting.god_rays else ""

        # Burbujas
        bubbles_str = ""
        if s.lighting.bubbles and s.lighting.bubbles.get("present"):
            b = s.lighting.bubbles
            bubbles_str = f"\nBubbles: {b.get('count', 'many')} translucent rising bubbles, {b.get('size_range', '2-15px')}, scattered {b.get('distribution', 'random')}, opacity {b.get('opacity', 0.4)}"

        # Tipografía
        type_families = ", ".join(
            f"{f['family']} {f['weight']}" for f in spec.typography.families
        ) if spec.typography.families else "sans-serif"

        hierarchy_lines = []
        for h in spec.typography.hierarchy:
            hierarchy_lines.append(
                f"  Level {h.level} ({h.role}): {h.weight}, {h.size_pct}% of height, tracking {h.tracking}"
            )
        hierarchy_detail = "\n".join(hierarchy_lines) if hierarchy_lines else "  Standard editorial hierarchy"

        # Paleta hex list
        hex_list = ", ".join(c.hex for c in spec.palette.colors) if spec.palette.colors else "#FFFFFF, #000000"

        # Dimensiones para aspect ratio
        dims = self._get_dimensions(spec.canvas.aspect_ratio)

        # Construir secciones
        section_subject = PROMPT_SECTIONS["subject"].format(
            subject=s.semantic.subject or "product",
            environment=s.semantic.environment or "studio",
            x_pct=s.layout.product_position.x_pct,
            y_pct=s.layout.product_position.y_pct,
            size_pct=s.layout.product_size_pct,
            depth_blur=s.layout.product_depth_blur,
            z_index=s.layout.product_z_index,
            grounding=s.layout.product_grounding,
        )

        section_env = PROMPT_SECTIONS["environment"].format(
            gradient_type=grad.type if grad else "linear",
            gradient_direction=grad.direction if grad else "top_to_bottom",
            gradient_stops=gradient_stops,
            elements=elements_str,
            light_type=s.lighting.type,
            light_direction=s.lighting.direction,
            shadow_type=s.lighting.shadow_type,
            shadow_opacity=s.lighting.shadow_opacity,
            god_rays_str=god_rays_str,
            bubbles_str=bubbles_str,
        )

        section_style = PROMPT_SECTIONS["style"].format(
            technique=s.composition.technique,
            mood=s.composition.mood,
            hex_list=hex_list,
            aspect_ratio=spec.canvas.aspect_ratio,
            pixels=spec.canvas.original_pixels,
            negative_space=s.composition.negative_space_pct,
            composition_rule=s.composition.rule,
        )

        section_typo = PROMPT_SECTIONS["typography"].format(
            type_families=type_families,
            hierarchy_detail=hierarchy_detail,
        )

        # Armar prompt completo
        sections = [
            "Premium product photography, editorial advertising style.",
            "",
            section_subject,
            "",
            section_env,
            "",
            section_style,
            "",
            section_typo,
        ]

        if user_prompt:
            sections.append("")
            sections.append(f"[USER INSTRUCTION]")
            sections.append(user_prompt)

        sections.append("")
        sections.append(
            f"[TECHNICAL] {dims[0]}x{dims[1]}px, "
            f"professional lighting, high-end commercial photography, "
            f"8K detail, shallow depth of field, soft focus background"
        )

        return "\n".join(sections)

    def _build_negative_prompt(self, spec: StructuredSpec) -> str:
        """Construir negative prompt."""
        negatives = [
            "text", "watermark", "logo", "signature",
            "blurry subject", "deformed", "distorted",
            "low quality", "jpeg artifacts", "oversaturated",
            "cluttered background", "amateur", "snapshot"
        ]

        # Invertir elementos de la referencia que no queremos
        if "dark" in spec.composition.mood:
            negatives.append("bright, harsh lighting")
        if "minimal" in spec.composition.mood:
            negatives.append("busy, crowded, cluttered")

        return ", ".join(negatives)

    def _select_model(self, technique: str, quality: str) -> str:
        """Seleccionar modelo Fal.ai según técnica y calidad."""
        if quality == "low":
            return "fal-ai/flux/schnell"

        technique_models = {
            "product_photography": "fal-ai/flux/1.1-pro",
            "lifestyle": "fal-ai/flux/1.1-pro",
            "3d_render": "fal-ai/flux/dev",
            "illustration": "fal-ai/flux/dev",
            "flat_lay": "fal-ai/flux/1.1-pro",
            "macro": "fal-ai/flux/dev",
        }
        return technique_models.get(technique.lower(), "fal-ai/flux/dev")

    def _compute_seed(self, spec: StructuredSpec) -> int:
        """Calcular seed determinístico basado en el spec para consistencia."""
        import hashlib
        # Usar hash del spec para seed consistente
        spec_str = json.dumps(spec.to_dict(), sort_keys=True)
        hash_obj = hashlib.md5(spec_str.encode())
        return int(hash_obj.hexdigest()[:8], 16)

    def _get_dimensions(self, aspect_ratio: str) -> tuple[int, int]:
        """Obtener dimensiones según aspect ratio."""
        ratio_map = {
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
            "1:1": (1024, 1024),
            "4:5": (1080, 1350),
            "4:3": (1200, 900),
            "3:4": (900, 1200),
            "2:3": (800, 1200),
        }
        return ratio_map.get(aspect_ratio, (1080, 1920))
