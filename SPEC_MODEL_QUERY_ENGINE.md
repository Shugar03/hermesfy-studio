# SPEC: ModelQueryEngine — Reemplazo de ModelSelector hardcodeado

**Versión:** 1.0
**Estado:** Draft → Implementación
**Reemplaza:** `model_selector.py` (matriz hardcodeada AdType×QualityLevel)

---

## 1. Problema

`ModelSelector` usa una matriz hardcodeada de 10×4 celdas con 7 nombres de modelos
inventados que no matchean los endpoint IDs reales de FAL. 1333 modelos existen,
la matriz solo conoce 7.

## 2. Solución

`ModelQueryEngine` — motor de búsqueda + ranking dinámico que:

1. **Indexa** los 1333 modelos con sus capacidades reales (extraídas vía `genmedia schema`)
2. **Filtra** por task type y constraints (no por un nombre de AdType fijo)
3. **Rankea** por métricas ponderadas según el task
4. **Devuelve top N** (default 5) ordenados por score

## 3. Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                 ModelQueryEngine                      │
│                                                       │
│  query(task_spec) → [RankedModel, ...]               │
│                                                       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────┐ │
│  │ ModelIndex   │   │ QueryFilter  │   │ Ranker   │ │
│  │ (cached JSON)│   │ (capability  │   │ (scoring │ │
│  │ 1333 models  │   │  matching)   │   │  weights)│ │
│  └──────────────┘   └──────────────┘   └──────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 4. TaskSpec (input)

```python
@dataclass
class TaskSpec:
    action: str          # "generate" | "edit" | "composite"
    reference_count: int # 0, 1, 2+
    needs_text: bool     # ¿requiere tipografía legible?
    needs_mask: bool     # ¿edición quirúrgica con máscara?
    content_type: str    # "product" | "beauty" | "luxury" | etc.
    max_budget: float    # USD
    min_resolution: str  # "1K" | "2K" | "4K"
    prioritize: str      # "quality" | "speed" | "cost"
```

---

## 5. Filtros (QueryFilter)

Cada filtro elimina modelos del pool:

| Filtro | Regla |
|--------|-------|
| `action == "generate"` | Solo `text-to-image` |
| `action in ("edit", "composite")` | Solo `image-to-image` + `supports_image_input` |
| `reference_count >= 2` | `supports_multiple_refs == true` |
| `needs_mask == true` | `supports_mask == true` |
| `needs_text == true` | Tags contienen `typography` o provider es `openai` o `fal-ai/ideogram` |
| `min_resolution == "4K"` | `max_resolution == "4K"` |
| `max_budget < 0.02` | Solo modelos budget: `flux/schnell`, `z-image/turbo`, `grok-imagine` |

---

## 6. Ranking (Scorer)

Score = Σ(weight × normalized_metric)

| Métrica | Peso por task type | Cómo se calcula |
|---------|-------------------|-----------------|
| **Context preservation** | edit: 0.40, composite: 0.50, generate: 0.10 | `supports_mask` + `supports_image_input` + `supports_multiple_refs` |
| **Product fidelity** | edit: 0.30, composite: 0.25, generate: 0.20 | `supports_seed` + `supports_strength` + provider reputation |
| **Text quality** | needs_text: 0.30, default: 0.05 | `tags include typography` + provider (`openai`, `ideogram`) |
| **Cost efficiency** | budget: 0.40, default: 0.15 | 1.0 - (estimated_cost / max_budget) |
| **Speed** | quick_draft: 0.40, default: 0.10 | `category == "text-to-image"` + no `thinking_level` → fast |

**Provider reputation bonus:**
- `openai` → +0.05 (instruction following)
- `bytedance` → +0.03 (compositing)
- `fal-ai` → 0.00 (neutral)
- `xai` → -0.02 (newer, less tested)

---

## 7. Output

```python
@dataclass
class RankedModel:
    endpoint_id: str      # "fal-ai/bytedance/seedream/v4.5/edit"
    name: str             # "Bytedance Seedream v4.5 Edit"
    score: float          # 0.0 - 1.0
    estimated_cost: float # USD
    max_resolution: str   # "4K"
    reason: str           # "Best context preservation, supports 10 reference images"
```

---

## 8. API

```python
engine = ModelQueryEngine(index_path="data/model_index.json")

# Full query
results = engine.query(TaskSpec(
    action="composite",
    reference_count=2,
    needs_text=False,
    content_type="product",
    max_budget=0.10,
    prioritize="quality"
))
# → [RankedModel(score=0.92, ...), RankedModel(score=0.87, ...), ...]

# Quick select (backward compatible with old ModelSelector)
model = engine.quick_select(
    action="generate",
    content_type="beauty", 
    quality="best"
)
# → "fal-ai/nano-banana-pro"
```

---

## 9. Migración desde ModelSelector

```python
# ANTES (hardcodeado)
from hermesfy.model_selector import ModelSelector, AdType, QualityLevel
s = ModelSelector()
model = s.select(AdType.PRODUCT_HERO, QualityLevel.BEST)
# → "flux-2-pro" (nombre inventado, no matchea nada en FAL)

# AHORA (dinámico)
from hermesfy.model_query_engine import ModelQueryEngine, TaskSpec
e = ModelQueryEngine()
results = e.query(TaskSpec(action="generate", content_type="product", max_budget=0.10, prioritize="quality"))
# → [
#     RankedModel(endpoint_id="openai/gpt-image-2", score=0.93, reason="Best instruction following"),
#     RankedModel(endpoint_id="fal-ai/nano-banana-pro", score=0.88, reason="Excellent realism + typography"),
#     RankedModel(endpoint_id="fal-ai/flux-2-pro", score=0.82, reason="High quality generation"),
#     ...
# ]
```

## 10. Criterios de aceptación

- [ ] Indexa 1200+ modelos desde `genmedia schema`
- [ ] Filtra correctamente por task type (generate/edit/composite)
- [ ] Filtra por máscara, multi-ref, resolución, budget
- [ ] Rankea con pesos diferenciados por task type
- [ ] Devuelve top 5 (no 1 solo)
- [ ] Cada resultado incluye `reason` explicando por qué fue seleccionado
- [ ] `quick_select()` mantiene backward compatibility para código existente
- [ ] Tests: al menos 5 casos de query verificando que los resultados tienen sentido
- [ ] No hardcodea ningún nombre de modelo en la lógica de scoring
