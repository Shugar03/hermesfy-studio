---
name: hermesfy-vrh-workflow
description: >-
  Orquestar el pipeline completo VRH (Visual Reference Harness) de Hermesfy.
  Telegram → VisualAnalysis → SpecBridge → DAG → Delivery.
  1 solo workflow que cubre análisis, generación y entrega.
---

# Hermesfy VRH Workflow

## Cuándo usarlo

El usuario envía una imagen de referencia por Telegram y pide generar
algo nuevo basado en ella. Este skill orquesta TODO el pipeline:
análisis visual → spec → DAG → entrega.

## Pipeline completo

```
┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌────────┐    ┌──────────┐
│ Telegram │───→│ VisualAnalyzer│───→│ SpecBridge│───→│ DAG    │───→│ Delivery │
│ (image)  │    │ Phase 1      │    │ Phase 2   │    │ Phase 3│    │ Phase 4  │
└──────────┘    └──────────────┘    └──────────┘    └────────┘    └──────────┘
                                                      │
                                                 ┌────┴────┐
                                                 │ Fal.ai  │
                                                 └─────────┘
```

## Workflow paso a paso

### FASE 1: Visual Analysis

```python
# Detectar la imagen (ya está en cache desde Telegram)
image_path = "/home/hermes/.hermes/cache/images/img_xxx.jpg"

from hermesfy.reference.visual_analyzer import VisualAnalyzer
analyzer = VisualAnalyzer()
vision_prompt = analyzer.get_vision_prompt(user_hint)

# Llamar vision_analyze tool o mcp_minimax_understand_image
vision_response = vision_analyze(image_path=image_path, question=vision_prompt)

# Parsear a StructuredSpec
spec = VisualAnalyzer.parse_vision_text(vision_response)
```

### FASE 2: Goldilocks + Preview

```python
from hermesfy.reference.spec_bridge import SpecBridge
bridge = SpecBridge()

# Mostrar preview al usuario
preview = bridge.build(spec, user_prompt, preview=True)
# "¿Genero así o ajustamos algo?"

# Si el usuario dice "dale":
exec_spec = bridge.build(spec, user_prompt, reference_mode="style_layout", quality="high")
```

### FASE 3: DAG Execution

```python
prompt = exec_spec["dag_workflow"]["steps"][0]["params"]["prompt"]
negative = exec_spec["dag_workflow"]["steps"][0]["params"]["negative_prompt"]
seed = exec_spec["dag_workflow"]["steps"][0]["params"]["seed"]
# Llamar a hermesfy_run_agentic_workflow o construir DAG manual
```

### FASE 4: Delivery

```python
from hermesfy.reference.delivery import Delivery
delivery = Delivery()
image_url = extract_url_from_fal_response(fal_output)
local_path = delivery.download(image_url)
# Incluir MEDIA:path en la respuesta
```

## Modos de referencia

| mode | uso |
|------|-----|
| `style_layout` | Default. Mantener estilo visual + composición |
| `style_only` | Cambiar composición, mantener paleta/iluminación |
| `layout_only` | Cambiar estilo, mantener layout |
| `subject_only` | Solo mantener el sujeto, todo lo demás nuevo |

## Errores comunes

- Fal.ai URL expira → delivery.py descarga inmediatamente
- Vision alucina spec → preview + confirmación del usuario
- El generador ignora la paleta → subir fidelity_ratio a 0.95
