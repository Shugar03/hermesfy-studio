---
name: hermesfy-spec-bridge
description: >-
  Convertir StructuredSpec visual (de VisualAnalyzer) en ExecutionSpec listo
  para el DAG de Hermesfy. Pipeline Fase 2: spec visual → prompt estructurado
  + parámetros de generación + Goldilocks Rule.
---

# Hermesfy Spec Bridge

## Cuándo usarlo

Después de tener un `StructuredSpec` del VisualAnalyzer. Convertir ese spec
en un ExecutionSpec que Hermesfy pueda ejecutar como DAG.

Ahora incluye **Goldilocks Rule** (fidelity dinámico según prompt del usuario)
y **Transparency Layer** (preview del spec antes de generar).

## Pipeline

```
StructuredSpec JSON → SpecBridge.build() → ExecutionSpec JSON → Hermesfy DAG
                                         ↓
                              [Goldilocks + Preview]
```

## Pasos exactos

### 1. Tener el StructuredSpec

```python
from hermesfy.reference.spec_bridge import SpecBridge
from hermesfy.reference.visual_analyzer import StructuredSpec

spec = StructuredSpec.from_dict(spec_dict)
```

### 2a. Preview antes de generar

```python
bridge = SpecBridge()
preview = bridge.build(spec, user_prompt="exactamente igual pero Vichy", preview=True)
# Retorna str con 📐 Layout, 🎨 Paleta, 💡 Iluminación, 🎯 Fidelidad
```

Mostrar al usuario y preguntar si está bien antes de generar.

### 2b. Generar directo con fidelity dinámico

```python
exec_spec = bridge.build(spec, user_prompt="exactamente igual pero Vichy",
                         reference_mode="style_layout", quality="high")
# fidelity automático: 0.95 para "exactamente igual"
```

### 2c. Forzar fidelity manual

```python
exec_spec = bridge.build(spec, user_prompt="Vichy", fidelity_override=0.7)
```

## Goldilocks Rule

| Keywords | fidelity | drift |
|----------|----------|-------|
| "exactamente igual", "copia exacta", "idéntico", "mismo" | 0.95 | 0.05 |
| "parecido", "similar", "mismo estilo", "referencia" | 0.85 | 0.15 |
| "inspirado", "algo así", "onda", "vibra" | 0.60 | 0.40 |
| "ignorá", "sin referencia", "creativo libre" | 0.25 | 0.75 |
| Sin indicación clara (default) | 0.85 | 0.15 |

**Orden:** Minimal primero → High → Medium → Low

## Máscaras automáticas

- **fidelity > 0.90** → `[FIDELITY HIGH — preservar composición exacta]`
- **drift > 0.60** → `[IGNORE SOURCE — referencia solo para inspiración]`

## Formato ExecutionSpec

```json
{
  "routing_decision": {"target_model": "fal-ai/flux/1.1-pro", ...},
  "dag_workflow": {"steps": [{"params": {"prompt": "...", "width": 1080, "height": 1920, ...}}]},
  "vrh": {"fidelity_ratio": 0.95, "semantic_drift": 0.05, "original_spec": {...}}
}
```

El prompt se construye en 4 secciones: [SUBJECT] [ENVIRONMENT] [STYLE] [TYPOGRAPHY]
usando datos EXACTOS del spec visual.
