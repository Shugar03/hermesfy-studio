"""Tool: hermesfy_reference_analyze — analizar imagen de referencia para ad generation.

Analiza una imagen de referencia usando el Visual Analyzer y devuelve
el StructuredSpec JSON completo para usarlo como input del DAG.

Uso (desde agente):
  result = hermesfy_reference_analyze(
      image_path="/home/hermes/.hermes/cache/images/img_xxx.jpg",
      user_prompt="cambiar la botella por Vichy"
  )
  # → spec JSON con layout, palette, typography, etc.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("hermesfy.tools.reference_analyze")


def reference_analyze(image_path: str,
                      user_prompt: str = "",
                      return_json: bool = True) -> dict:
    """Analizar imagen de referencia y devolver StructuredSpec.

    NOTA para el agente:
      Esta tool NO llama al vision tool directamente (el agente no tiene acceso
      a la cámara desde el plugin). En cambio:
      1. El agente llama a vision_analyze(image_path, get_vision_prompt())
      2. Pasa el resultado a parse_vision_text()
      3. Si return_json=True, convierte a dict

    Esta tool sirve como interfaz unificada para el pipeline VRH.
    Puede recibir el resultado del vision tool y procesarlo.

    Args:
        image_path: Ruta absoluta a la imagen local.
        user_prompt: Prompt adicional (ej: "cambiar fondo mantener producto").
        return_json: Si True, devuelve dict. Si False, devuelve StructuredSpec.

    Returns:
        Dict con el StructuredSpec (o error).
    """
    try:
        from hermesfy.reference.visual_analyzer import VisualAnalyzer
        analyzer = VisualAnalyzer()

        # Obtener el prompt de visión
        vision_prompt = analyzer.get_vision_prompt(user_prompt)

        # Devolver instrucciones para el agente
        return {
            "status": "ready",
            "vision_prompt": vision_prompt,
            "image_path": image_path,
            "instruction": (
                "Call vision_analyze(image_path, vision_prompt) then pass the "
                "response to VisualAnalyzer.parse_vision_text(response) to get "
                "the StructuredSpec. Then use SpecBridge to build ExecutionSpec."
            ),
        }

    except ImportError as e:
        return {"status": "error", "error": str(e)}


# ── Schema para registro como tool ────────────────────────────────────────────

REFERENCE_ANALYZE_SCHEMA = {
    "type": "object",
    "properties": {
        "image_path": {
            "type": "string",
            "description": "Ruta absoluta a la imagen local (ej: /home/hermes/.hermes/cache/images/img_xxx.jpg)",
        },
        "user_prompt": {
            "type": "string",
            "description": "Prompt adicional del usuario (ej: 'cambiar botella por Vichy')",
            "default": "",
        },
        "return_json": {
            "type": "boolean",
            "description": "Si True, devuelve dict. Si False, devuelve StructuredSpec.",
            "default": True,
        },
    },
    "required": ["image_path"],
}
