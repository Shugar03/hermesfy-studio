"""Visual Analyzer — extrae StructuredSpec JSON de una imagen de referencia.

Fase 1 del pipeline VRH:
  Image path → [Vision LLM] → StructuredSpec JSON

El análisis se hace mediante un prompt estructurado enviado al modelo de visión
(Gemini Vision / GPT-4o según disponibilidad). El resultado es un JSON con:
  - layout: posición producto, depth layers, zonas de texto
  - palette: colores HEX dominantes, gradientes
  - typography: familias, jerarquía, tracking
  - lighting: dirección, tipo, sombras
  - composition: regla, negative space, mood
  - semantic: objetos, entorno, técnica
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("hermesfy.reference.visual_analyzer")

# ── StructuredSpec Schema ─────────────────────────────────────────────────────

@dataclass
class CanvasSpec:
    aspect_ratio: str = "9:16"
    orientation: str = "vertical"
    original_pixels: str = "1080x1920"

@dataclass
class LayoutPosition:
    x_pct: float = 50.0
    y_pct: float = 50.0

@dataclass
class DepthLayer:
    layer: int = 0
    content: str = ""
    opacity: float = 1.0
    blur: str = "none"
    focus: bool = False

@dataclass
class LayoutSpec:
    product_position: LayoutPosition = field(default_factory=LayoutPosition)
    product_size_pct: float = 30.0
    product_z_index: int = 2
    product_grounding: str = "shadow_soft"
    product_depth_blur: str = "sharp"
    text_zones: list[dict] = field(default_factory=list)
    depth_layers: list[DepthLayer] = field(default_factory=list)

@dataclass
class PaletteColor:
    hex: str = "#000000"
    role: str = "unknown"
    pct: float = 10.0

@dataclass
class GradientSpec:
    type: str = "linear"
    direction: str = "top_to_bottom"
    stops: list[str] = field(default_factory=list)

@dataclass
class PaletteSpec:
    colors: list[PaletteColor] = field(default_factory=list)
    gradient: Optional[GradientSpec] = None

@dataclass
class TypeHierarchy:
    level: int = 1
    size_pct: float = 5.0
    weight: str = "regular"
    tracking: str = "normal"
    role: str = "body"

@dataclass
class TypographySpec:
    families: list[dict] = field(default_factory=list)
    hierarchy: list[TypeHierarchy] = field(default_factory=list)

@dataclass
class LightingSpec:
    type: str = "diffuse"
    direction: str = "top_left"
    shadow_type: str = "soft"
    shadow_opacity: float = 0.3
    god_rays: bool = False
    bubbles: Optional[dict] = None

@dataclass
class CompositionSpec:
    rule: str = "centered"
    negative_space_pct: float = 20.0
    framing: str = "none"
    mood: str = "neutral"
    technique: str = "photography"

@dataclass
class SemanticSpec:
    subject: str = ""
    environment: str = ""
    brand_vibe: str = ""
    target_audience: str = ""
    detected_objects: list[str] = field(default_factory=list)

@dataclass
class StructuredSpec:
    """Salida completa del análisis visual de una imagen de referencia."""
    canvas: CanvasSpec = field(default_factory=CanvasSpec)
    layout: LayoutSpec = field(default_factory=LayoutSpec)
    palette: PaletteSpec = field(default_factory=PaletteSpec)
    typography: TypographySpec = field(default_factory=TypographySpec)
    lighting: LightingSpec = field(default_factory=LightingSpec)
    composition: CompositionSpec = field(default_factory=CompositionSpec)
    semantic: SemanticSpec = field(default_factory=SemanticSpec)

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self)))

    @classmethod
    def from_dict(cls, data: dict) -> StructuredSpec:
        """Construct from nested dict, converting sub-dicts to dataclasses."""
        if not data:
            return cls()

        def _dict_to_dataclass(d: Any, dc_class: Any) -> Any:
            """Recursively convert dict to dataclass instance."""
            if d is None:
                return dc_class() if hasattr(dc_class, '__dataclass_fields__') else None
            if isinstance(d, dc_class):
                return d
            if isinstance(d, dict):
                # If dc_class is a Union/Optional, find the dataclass type
                actual_class = dc_class
                if hasattr(actual_class, '__origin__') and actual_class.__origin__ is __import__('typing').Union:
                    # Unwrap Union/Optional to find the dataclass
                    for arg in actual_class.__args__:
                        if hasattr(arg, '__dataclass_fields__'):
                            actual_class = arg
                            break
                
                if not hasattr(actual_class, '__dataclass_fields__'):
                    # Not a dataclass, return dict as-is
                    return d
                
                hints = __import__('typing').get_type_hints(actual_class)
                kwargs = {}
                for field_name in actual_class.__dataclass_fields__:
                    if field_name in d:
                        val = d[field_name]
                        field_type = hints.get(field_name)
                        
                        # Unwrap Optional/Union
                        resolved_type = field_type
                        if hasattr(resolved_type, '__origin__') and resolved_type.__origin__ is __import__('typing').Union:
                            for arg in resolved_type.__args__:
                                if hasattr(arg, '__dataclass_fields__') or arg is type(None):
                                    resolved_type = arg if hasattr(arg, '__dataclass_fields__') else resolved_type
                                    break
                        
                        # Check if field_type is a dataclass
                        if hasattr(resolved_type, '__dataclass_fields__'):
                            kwargs[field_name] = _dict_to_dataclass(val, resolved_type)
                        elif hasattr(resolved_type, '__origin__') and resolved_type.__origin__ is list:
                            args = resolved_type.__args__
                            if args and hasattr(args[0], '__dataclass_fields__'):
                                kwargs[field_name] = [_dict_to_dataclass(v, args[0]) for v in (val or [])]
                            else:
                                kwargs[field_name] = val or []
                        else:
                            kwargs[field_name] = val
                return actual_class(**kwargs)
            return d

        return _dict_to_dataclass(data, cls)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ── Vision Prompt Template ────────────────────────────────────────────────────

VISION_PROMPT_TEMPLATE = """Analizá esta imagen de referencia para AD GENERATION con PRECISIÓN ABSOLUTA.

Necesito extraer CADA UNO de los siguientes datos en JSON. Sé EXHAUSTIVO — cada campo debe estar completado.

## 1. CANVAS
- aspect_ratio: (ej: "9:16", "1:1", "4:5", "16:9")
- orientation: "vertical" o "horizontal"
- original_pixels: (ej: "1080x1920")

## 2. LAYOUT — posiciones en % (0-100) del canvas
- product_position: {"x_pct": X, "y_pct": Y} — centro del producto
- product_size_pct: tamaño del producto como % del ancho del canvas
- product_z_index: qué capa ocupa (0=fondo, 5=primer plano)
- product_grounding: cómo se apoya ("shadow_soft", "shadow_hard", "plinth", "floating", "water")
- product_depth_blur: ("sharp", "soft_bokeh", "heavy_bokeh")
- text_zones: array de {zone: "top"|"bottom"|"left"|"right", height_pct: %, alignment: "center"|"left"|"right", content: "header"|"cta"|"body"}
- depth_layers: array de {layer: 0-5, content: descripción, opacity: 0-1, blur: "none"|"soft"|"heavy", focus: true/false}

## 3. PALETTE — colores HEX exactos
- colors: array de {hex: "#XXXXXX", role: "bg_top"|"bg_bottom"|"accent"|"product"|"text"|"liquid", pct: % del canvas}
- gradient: {type: "linear"|"radial", direction: "top_to_bottom"|"left_to_right"|"radial_outward", stops: ["#XXXXXX@0%", ...]}

## 4. TYPOGRAPHY
- families: array de {family: "serif"|"sans-serif"|"script"|"display", weight: "light"|"regular"|"bold", role: "header"|"body"|"label"}
- hierarchy: array de {level: 1-4, size_pct: % del alto, weight: "light"|"regular"|"bold"|"black", tracking: "tight"|"normal"|"wide", role: "headline"|"subhead"|"body"|"cta"}

## 5. LIGHTING
- type: "diffuse"|"direct"|"volumetric"|"studio"|"natural"|"rim"|"backlit"
- direction: "top"|"top_left"|"top_right"|"left"|"right"|"back"|"bottom"
- shadow_type: "soft"|"hard"|"none"
- shadow_opacity: 0-1
- god_rays: true/false — rayos de luz volumétricos
- bubbles: si hay burbujas/partículas -> {present: true/false, count: "few"|"many"|"dozens", size_range: "2-15px", opacity: 0-1, distribution: "uniform"|"gaussian"|"random"}

## 6. COMPOSITION
- rule: "centered"|"thirds"|"thirds_offset_right"|"thirds_offset_left"|"symmetry"|"z_pattern"|"diagonal"|"frame"|"minimal"
- negative_space_pct: % de espacio vacío
- framing: "none"|"coral_at_edges"|"vignette"|"geometric"|"organic"
- mood: "serene"|"energetic"|"luxury"|"natural"|"tech"|"editorial"|"minimal"|"romantic"|"dramatic"
- technique: "product_photography"|"lifestyle"|"3d_render"|"illustration"|"flat_lay"|"macro"

## 7. SEMANTIC
- subject: qué es el objeto principal ("skincare_bottle", "perfume", "sneaker", etc.)
- environment: dónde está ("underwater", "studio", "nature", "urban", etc.)
- brand_vibe: sensación de marca ("premium_natural", "luxury_tech", "organic", "edgy", etc.)
- detected_objects: lista de todos los objetos visibles en la imagen

DEVOLVÉ SOLO EL JSON, sin markdown ni explicaciones.
El JSON debe seguir EXACTAMENTE esta estructura."""


class VisualAnalyzer:
    """Analiza una imagen de referencia y produce un StructuredSpec."""

    def __init__(self):
        self._last_raw_response: str | None = None

    def analyze(self, image_path: str, vision_prompt: str | None = None) -> StructuredSpec:
        """Analizar imagen de referencia.

        Args:
            image_path: Ruta absoluta a la imagen local.
            vision_prompt: Prompt opcional adicional del usuario (ej: "cambia el fondo").

        Returns:
            StructuredSpec completo.
        """
        if not image_path or not Path(image_path).exists():
            logger.warning("Image not found at %s, returning empty spec", image_path)
            return StructuredSpec()

        return self._parse_vision_response(image_path, vision_prompt)

    def _parse_vision_response(self, image_path: str, user_hint: str | None) -> StructuredSpec:
        """Procesar la respuesta de visión y extraer StructuredSpec.

        NOTA: Esta función es llamada desde el skill/script que tiene acceso
        al vision_analyze / mcp_minimax_understand_image tool.
        El agente DEBE:
          1. Llamar vision_analyze(image_path, VISION_PROMPT_TEMPLATE)
          2. Pasar el resultado a parse_vision_text()
        """
        # Placeholder — el agente debe llamar vision_analyze y luego parse_vision_text
        logger.info("VisualAnalyzer: ready — call analyze_image() then parse_vision_text()")
        return StructuredSpec()

    @staticmethod
    def get_vision_prompt(user_hint: str | None = None) -> str:
        """Obtener el prompt de visión completo para enviar al vision tool."""
        prompt = VISION_PROMPT_TEMPLATE
        if user_hint:
            prompt += f"\n\nCONTEXTO ADICIONAL DEL USUARIO: {user_hint}"
        return prompt

    @staticmethod
    def parse_vision_text(vision_response: str) -> StructuredSpec:
        """Parsear la respuesta JSON del vision tool a StructuredSpec.

        Args:
            vision_response: Texto plano devuelto por vision_analyze.

        Returns:
            StructuredSpec con los datos extraídos (o defaults si falla el parseo).
        """
        # Try to extract JSON from response (may contain markdown fences)
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', vision_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Assume entire response is JSON
            json_str = vision_response.strip()

        # Remove any non-JSON prefix/suffix
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to find JSON object boundaries
            brace_start = vision_response.find('{')
            brace_end = vision_response.rfind('}')
            if brace_start >= 0 and brace_end > brace_start:
                try:
                    data = json.loads(vision_response[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    logger.error("Failed to parse vision response as JSON")
                    return StructuredSpec()
            else:
                logger.error("No JSON found in vision response")
                return StructuredSpec()

        return StructuredSpec.from_dict(data)
