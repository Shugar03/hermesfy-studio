---
name: visual-reference-analyzer
description: >-
  Analizar una imagen de referencia para AD GENERATION y extraer un StructuredSpec
  JSON completo. Pipeline Fase 1: imagen → spec estructurado con layout, palette,
  tipografía, iluminación, composición y semántica.
---

# Visual Reference Analyzer

## Cuándo usarlo

El usuario envía una imagen por Telegram y pide:
- "hacé un ad como esta foto pero con [producto X]"
- "generá algo parecido a esto"
- "tomá esta referencia y creá..."

## Pipeline

```
[Telegram image] → vision_analyze() → StructuredSpec JSON → SpecBridge → ExecutionSpec
```

## Pasos exactos

### 1. Recibir la imagen

La imagen está en disco en: `/home/hermes/.hermes/cache/images/img_*.jpg`

### 2. Obtener el prompt de visión estructurado

```python
from hermesfy.reference.visual_analyzer import VisualAnalyzer

analyzer = VisualAnalyzer()
vision_prompt = analyzer.get_vision_prompt("cambiar botella por Vichy, mantener fondo")
```

### 3. Llamar al vision tool

```python
# Usar vision_analyze (tool de Hermes Agent):
vision_response = vision_analyze(image_path="/home/hermes/.hermes/cache/images/img_xxx.jpg",
                                 question=vision_prompt)

# O mcp_minimax_understand_image si Minimax está activo
```

### 4. Parsear la respuesta a StructuredSpec

```python
spec = VisualAnalyzer.parse_vision_text(vision_response)
```

### 5. Verificar spec (opcional)

```python
if not spec.palette.colors:
    # Fallback: re-intentar con prompt más simple
    pass
```

## Estructura del StructuredSpec

```json
{
  "canvas": {"aspect_ratio": "9:16", "orientation": "vertical"},
  "layout": {"product_position": {"x_pct": 65, "y_pct": 55}, "depth_layers": []},
  "palette": {"colors": [{"hex": "#0B3B3B", "role": "bg_top", "pct": 40}], "gradient": null},
  "typography": {"families": [{"family": "sans-serif", "weight": "bold", "role": "header"}]},
  "lighting": {"type": "volumetric", "direction": "top_left", "god_rays": true},
  "composition": {"rule": "thirds_offset_right", "mood": "serene", "technique": "product_photography"},
  "semantic": {"subject": "skincare_bottle", "environment": "underwater"}
}
```

## Pitfalls

### from_dict

Usar SIEMPRE `StructuredSpec.from_dict(dict)` en vez del constructor.
El from_dict maneja conversión recursiva de dicts anidados a dataclasses.

### JSON con fences

`parse_vision_text()` ya extrae JSON de ```json ... ``` fences.
Si no encuentra fences, asume que todo el texto es JSON.
Si falla, busca el primer `{` y último `}`.

### Errores comunes

- ❌ Vision tool devuelve markdown con fences → parse_vision_text lo maneja
- ❌ from_dict falla con `dict object has no attribute` → usar from_dict siempre
- ❌ La imagen no existe en disco → verificar path en cache/images/
