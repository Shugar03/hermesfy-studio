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

### Pitfall: keywords compartidos entre grupos

"referencia" aparece en Medium ("estilo de", "referencia"), pero también
está en frases Minimal ("sin referencia", "ignorá la referencia").
Si Minimal va último (High → Medium → Low → Minimal), "ignorá la referencia"
matchea "referencia" (Medium → 0.85) ANTES que "ignorá" (Minimal → 0.25).

Este bug se descubrió testeando. La implementación inicial tenía Minimal
al final y fallaba silenciosamente — el código se ejecutaba sin error pero
daba fidelity incorrecto.

**Solución:** checkear Minimal primero (señal de override más fuerte),
High segundo, Medium tercero, Low cuarto. Además agregar frases combinadas
como "ignorá la foto" para agarrar edge cases donde Minimal y Medium
comparten tokens.

### Test methodology

Para verificar matching correcto, testear TODOS los grupos + edge cases:

```python
tests = {
    'exactamente igual pero Vichy':       (0.95, 0.05),  # High
    'mismo estilo pero X':                (0.95, 0.05),  # High
    'parecido a esto':                    (0.85, 0.15),  # Medium
    'inspirado en esta foto':             (0.60, 0.40),  # Low
    'ignorá la referencia':               (0.25, 0.75),  # Minimal (edge!)
    'hacé lo que quieras':                (0.25, 0.75),  # Minimal
    '':                                   (0.85, 0.15),  # Default
    'producto de skincare':               (0.85, 0.15),  # Default
}

for prompt, (exp_f, exp_d) in tests.items():
    f, d, _ = bridge._determine_fidelity(prompt)
    assert (f, d) == (exp_f, exp_d), f'FAIL: "{prompt}" → ({f},{d})'
```

El test con "ignorá la referencia" es el detector del bug. Siempre
testear edge cases donde keywords coexisten entre grupos.

## Efectos secundarios en build()

- **fidelity > 0.90** → `[FIDELITY HIGH — preservar composición exacta]`
- **drift > 0.60** → `[IGNORE SOURCE — referencia solo para inspiración]`

## Cuándo override manual

- Usuario dice "mantené el 70%" → fidelity_override=0.7
- Prompt largo y ambiguo → default 0.85
- Iteración con correcciones → usar último fidelity conocido
