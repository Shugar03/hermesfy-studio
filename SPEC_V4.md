═══════════════════════════════════════════════════════════════
SPEC — Hermesfy Studio V4.0 — Protocol-Driven Execution
═══════════════════════════════════════════════════════════════

## Resumen

Incorporar los 4 puntos prioritarios del "Protocolo de Generación" al engine
existente. Todo contacto entre el LLM y el backend Python se formaliza como
JSON estricto (`Execution_Spec`), con gates de presupuesto, propagación de
semilla entre nodos, y validación intermedia entre pasos del DAG.

## Contexto

- **Fuente:** Protocolo de Generación (Gemini conversation, 2026-05-01)
- **Gap:** El intent_router ya retorna un dict, pero no tiene schema formal,
  no hay budget cap, no hay seed inheritance, y la validación post-generación
  corre después del pipeline completo en vez de entre nodos.
- **Código existente:** intent_router.py, ad_pipeline.py, validator.py,
  ai_generator.py, telemetry.py, model_registry.py

---

## Requirements

### R1: Execution_Spec — JSON Schema Formal

**Descripción:** Definir un schema JSON estricto quesea el ÚNICO contrato
entre el LLM (intent_router) y el backend (pipeline). El pipeline RECHAZA
cualquier input que no cumpla el schema.

**Schema:**
```json
{
  "spec_version": "1.0",
  "routing_decision": {
    "intent_category": "photorealism|typography|illustration|sketch|product|lifestyle",
    "action": "generate|edit|refine",
    "target_model": "fal-ai/flux/dev",
    "budget_estimation": 0.045,
    "priority": "quality|speed|cost"
  },
  "dag_workflow": {
    "steps": [
      {
        "node_id": 1,
        "action": "base_generation|latent_refiner|upscale|remove_bg|inpaint",
        "model": "fal-ai/flux/schnell",
        "params": {}
      }
    ]
  },
  "error_handling": {
    "retry_strategy": "exponential_backoff",
    "max_retries": 3,
    "fallback_model": "fal-ai/flux/dev"
  },
  "prompt_metadata": {
    "cleaned_prompt": "string",
    "negative_prompt": "string",
    "seed": -1
  }
}
```

**Criterio de aceptación:**
- [ ] `ExecutionSpec` dataclass con validación en `__post_init__`
- [ ] `ExecutionSpec.from_dict()` valida contra schema, lanza `SpecValidationError`
- [ ] `ExecutionSpec.to_dict()` serializa limpio
- [ ] `IntentRouter.parse()` retorna `ExecutionSpec` (no dict suelto)
- [ ] `AdPipeline` acepta `ExecutionSpec` como input
- [ ] Tests: schema válido → OK, campos faltantes → error, tipos incorrectos → error

**Priority:** must-have

---

### R2: Budget Gate — Hard Cap $0.07/flow

**Descripción:** Antes de CADA llamada a FAL.ai, verificar que el costo
acumulado no exceda el presupuesto. Si lo excede, abortar con error claro.

**Criterio de aceptación:**
- [ ] `BudgetGate` class: `can_spend(amount) -> bool`, `record_spend(amount)`, `remaining() -> float`
- [ ] Hard cap configurable (default $0.07)
- [ ] Cada modelo tiene `cost_per_image` en el registry
- [ ] Gate se ejecuta ANTES de cada llamada FAL en el pipeline
- [ ] Si excede budget → `BudgetExceeded` exception con detalle
- [ ] Telemetry registra cada gasto
- [ ] Tests: spend bajo cap → OK, spend sobre cap → abort, multi-step consume acumulado

**Priority:** must-have

---

### R3: Seed Propagation — Seed Inheritance

**Descripción:** El `seed` generado en el nodo 1 DEBE ser propagado al nodo 2.
Si el usuario no especifica seed, se genera uno y se hereda. Si especifica,
se usa el especificado.

**Criterio de aceptación:**
- [ ] `SeedPropagator`: `generate_seed() -> int`, `propagate(step_results, next_step) -> dict`
- [ ] Si `prompt_metadata.seed == -1`, generar random y guardar
- [ ] Si `prompt_metadata.seed > 0`, usar el especificado
- [ ] El seed del nodo N se inyecta en los params del nodo N+1
- [ ] Si el modelo no soporta seed, se ignora silenciosamente
- [ ] Tests: seed random se hereda, seed fijo se respeta, seed propagado correctamente

**Priority:** must-have

---

### R4: Intermediate Validation — Validate Between Nodes

**Descripción:** Después de cada nodo de generación (NO después del pipeline
completo), validar la imagen intermedia. Si falla, abortar antes de gastar
en el siguiente nodo.

**Criterio de aceptación:**
- [ ] `IntermediateValidator.validate_step(step_result, original_prompt) -> StepValidation`
- [ ] Retorna: `{valid: bool, confidence: float, should_continue: bool, issues: list}`
- [ ] Si `confidence < 0.7` → `should_continue = False` (abort pipeline)
- [ ] Si `confidence >= 0.7` → `should_continue = True`
- [ ] Integrado en el pipeline: se ejecuta entre cada nodo de generación
- [ ] Reutiliza `ImageValidator` existente (Gemini Vision)
- [ ] Tests: imagen válida → continue, imagen rota → abort, sin Gemini key → skip

**Priority:** should-have

---

## Archivos a Crear/Modificar

### Nuevos:
| Archivo | Qué hace |
|---------|----------|
| `engine/execution_spec.py` | ExecutionSpec dataclass + schema validation |
| `engine/budget_gate.py` | BudgetGate + BudgetExceeded exception |
| `engine/seed_propagator.py` | SeedPropagator — seed generation + inheritance |
| `engine/intermediate_validator.py` | IntermediateValidator — step-by-step validation |
| `tests/test_execution_spec.py` | Tests para R1 |
| `tests/test_budget_gate.py` | Tests para R2 |
| `tests/test_seed_propagator.py` | Tests para R3 |
| `tests/test_intermediate_validator.py` | Tests para R4 |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `engine/intent_router.py` | `parse()` retorna `ExecutionSpec` |
| `engine/ad_pipeline.py` | Acepta `ExecutionSpec`, integra budget + seed + validation |

---

## Tech Stack

- Python 3.10+ (dataclasses, json, random)
- pytest (testing)
- No dependencias nuevas — todo stdlib + lo existente

---

## Tiempo Estimado

**M** — 2 sesiones de trabajo

| Fase | Tiempo |
|------|--------|
| Fase 1: SPEC + execution_spec.py + tests | 0.5 sesión |
| Fase 2: budget_gate.py + seed_propagator.py + tests | 0.5 sesión |
| Fase 3: intermediate_validator.py + tests | 0.5 sesión |
| Fase 4: Integrar en intent_router + ad_pipeline | 0.5 sesión |

═══════════════════════════════════════════════════════════════
