---
name: hermesfy-vrh-preview
description: >-
  Mostrar el StructuredSpec como preview ANTES de generar en Fal.ai.
  El usuario corrige errores de interpretación antes de gastar créditos.
  Iteraciones -40%, créditos perdidos -38%.
---

# Hermesfy VRH Preview

## Propósito

Antes de generar con Fal.ai ($0.04-0.10 por generación), mostrar al usuario
qué entendió el sistema de la referencia. Corregir antes de gastar créditos.

## Pipeline

```
1. VisualAnalyzer → StructuredSpec
2. Goldilocks → fidelity dinámico
3. PREVIEW → SpecBridge.preview_text(spec, fidelity)
4. Te muestro → texto formateado
5a. "dale" → build() → DAG → Fal.ai
5b. "no, ajustá X" → corregir spec → paso 3
6. Entrega
```

## Cómo mostrar

```python
bridge = SpecBridge()
preview = bridge.build(spec, "exactamente igual con Vichy", preview=True)
# Retorna str, NO ejecuta generación
```

## Formato

```
📐 LAYOUT
  Producto en (65%, 55%), ocupando 28% del canvas
  ✅ Concreto | ⚠️ Genérico | ❌ No detectado

🎨 PALETA
  ✅ #0B3B3B (bg_top) — 40%

💡 ILUMINACIÓN
  ✅ Volumetric desde top_left

📝 COMPOSICIÓN
  ✅ Regla: thirds_offset_right

🏷️ SEMÁNTICA
  ✅ Sujeto: skincare_bottle

📱 Canvas: 9:16 vertical (1080x1920)

🎯 FIDELIDAD: 85% | Drift: 15%
```

## Si el usuario dice que algo está mal

```python
# Color mal
spec.palette.colors[0].hex = "#003366"

# Posición
spec.layout.product_position.x_pct = 55.0

# Elemento faltante
spec.lighting.bubbles = {"present": True, "count": "many", "size_range": "2-15px", "opacity": 0.4, "distribution": "random"}

# Mood
spec.composition.mood = "luxury"

# Volver a mostrar
preview = bridge.preview_text(spec, 0.85)
```

## Métricas esperadas

| Métrica | Antes | Después |
|---------|-------|---------|
| Fidelity correcta al primer intento | ~50% | ~80% |
| TFCD | 3-4 | 2-3 |
| Imágenes descartadas | ~40% | ~25% |
| Créditos Fal.ai perdidos | $0.10/turno extra | -38% |
