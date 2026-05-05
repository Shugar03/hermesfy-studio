---
name: hermesfy-goldilocks-rule
description: >-
  Goldilocks Rule para Hermesfy VRH. Determina dinámicamente el fidelity_ratio
  según keywords en el prompt del usuario. TFCD -25%, Tasa de Rechazo -38%.
---

# Hermesfy Goldilocks Rule

## Propósito

El fidelity_ratio ya no es hardcodeado (0.85). Se ajusta dinámicamente
según la intención del usuario.

**Meta:** Ni muy pegado a la referencia ni muy suelto. Justo en el punto justo.

## Implementación

```python
bridge = SpecBridge()
fidelity, drift, label = bridge._determine_fidelity("exactamente igual pero cambia la botella")
# → (0.95, 0.05, "Alta fidelidad")
```

Retorna `tuple[float, float, str]`: (fidelity_ratio, semantic_drift, label)

## Tabla de Keywords

| Grupo | Keywords | fidelity | drift |
|-------|----------|----------|-------|
| **Minimal** | "ignorá", "sin referencia", "hacé lo que quieras", "no uses la imagen", "creativo libre", "de cero", "inventá", "creá algo nuevo" | 0.25 | 0.75 |
| **High** | "exactamente igual", "copia exacta", "idéntico", "mismo", "sin cambiar", "solo cambia", "mantené todo", "mantené el", "cloná", "calcá", "reproducí" | 0.95 | 0.05 |
| **Medium** | "parecido", "como esta foto", "similar", "misma onda", "mismo estilo", "referencia", "estilo de", "tipo este", "como la imagen" | 0.85 | 0.15 |
| **Low** | "inspirado", "algo así", "más o menos", "onda", "vibra", "tirando a", "parecido a" | 0.60 | 0.40 |
| **Default** | Sin indicación clara | 0.85 | 0.15 |

## Orden de matching

**Minimal → High → Medium → Low**

"ignorá la referencia" → contiene "referencia" (Medium), pero Minimal
matchea primero con "ignorá" → 0.25.

## Efectos secundarios en build()

- **fidelity > 0.90** → `[FIDELITY HIGH — preservar composición exacta]`
- **drift > 0.60** → `[IGNORE SOURCE — referencia solo para inspiración]`

## Cuándo override manual

- Usuario dice "mantené el 70%" → fidelity_override=0.7
- Prompt largo y ambiguo → default 0.85
- Iteración con correcciones → usar último fidelity conocido
