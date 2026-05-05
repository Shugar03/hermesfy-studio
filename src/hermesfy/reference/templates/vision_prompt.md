# Vision Prompt Template — Hermesfy VRH

Este es el prompt para enviar al vision tool (Gemini Vision / Minimax VLM / GPT-4o)
cuando se recibe una imagen de referencia para generar un ad.

## Template completo

```
Analizá esta imagen de referencia para AD GENERATION con PRECISIÓN ABSOLUTA.

Necesito extraer CADA UNO de los siguientes datos en JSON. Sé EXHAUSTIVO.

## 1. CANVAS
- aspect_ratio: ("9:16", "1:1", "4:5", "16:9")
- orientation: "vertical" | "horizontal"
- original_pixels: "1080x1920"

## 2. LAYOUT — posiciones en % (0-100)
- product_position: {"x_pct": X, "y_pct": Y}
- product_size_pct: % del ancho del canvas
- product_z_index: 0-5
- product_grounding: "shadow_soft" | "shadow_hard" | "plinth" | "floating" | "water"
- product_depth_blur: "sharp" | "soft_bokeh" | "heavy_bokeh"
- text_zones: [{zone, height_pct, alignment, content}]
- depth_layers: [{layer, content, opacity, blur, focus}]

## 3. PALETTE — colores HEX exactos
- colors: [{hex, role, pct}]
- gradient: {type, direction, stops}

## 4. TYPOGRAPHY
- families: [{family, weight, role}]
- hierarchy: [{level, size_pct, weight, tracking, role}]

## 5. LIGHTING
- type: "diffuse"|"direct"|"volumetric"|"studio"|"natural"|"rim"|"backlit"
- direction: "top"|"top_left"|"top_right"|"left"|"right"
- shadow_type: "soft"|"hard"|"none"
- shadow_opacity: 0-1
- god_rays: true/false
- bubbles: {present, count, size_range, opacity, distribution}

## 6. COMPOSITION
- rule: "centered"|"thirds"|"thirds_offset_right"|"symmetry"|"z_pattern"
- negative_space_pct: %
- framing: "none"|"coral_at_edges"|"vignette"|"geometric"
- mood: "serene"|"energetic"|"luxury"|"natural"|"tech"|"editorial"
- technique: "product_photography"|"lifestyle"|"3d_render"|"illustration"|"flat_lay"

## 7. SEMANTIC
- subject: objeto principal
- environment: entorno
- brand_vibe: sensación de marca
- detected_objects: lista de objetos visibles

DEVOLVÉ SOLO EL JSON, sin markdown.
```

## Uso desde código

```python
from hermesfy.reference.visual_analyzer import VisualAnalyzer

analyzer = VisualAnalyzer()
vision_prompt = analyzer.get_vision_prompt("cambiar botella por Vichy")
# → enviar a vision_analyze(image_path, vision_prompt)

# Recibir respuesta y parsear:
spec = VisualAnalyzer.parse_vision_text(vision_response)
```
