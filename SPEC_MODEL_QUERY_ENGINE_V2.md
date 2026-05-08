# SPEC: ModelQueryEngine Score Calibration v2

**Problema:** v1 favorece capacidades estructurales (mask, multi-ref) sobre calidad real.
Modelos de inpainting baratos rankean sobre GPT Image 2 y Seedream.

---

## 1. Diagnóstico de fallas v1

| Sesgo | Efecto | Evidencia |
|-------|--------|-----------|
| `supports_mask` = +0.35 | Cualquier inpainter supera a GPT Image 2 | `z-image/turbo/inpaint` rankea #1 en edit |
| `supports_image_input` = +0.25 | Modelos de edición rankean en tareas de generación | `flux-lora/inpainting` rankea en generate beauty |
| Provider reputation solo +0.08 | Insuficiente para diferenciar OpenAI de utilidades | GPT Image 2 rankea #4 |
| Sin filtro de relevancia | Modelos de personajes rankean para producto | `ideogram/character/remix` #1 en composite |
| Todas las resoluciones = 1K | Extracción falló, sin diferenciación | Ningún modelo muestra 2K/4K |
| Costos = $0.04 default | 90% de modelos tienen costo inventado | Solo z-image tiene $0.01 real |

---

## 2. Cambios de arquitectura v2

### 2.1 Reemplazar pesos brutos por SCORE COMPONENTS

```
Score = QUALITY × 0.40 + TASK_FIT × 0.35 + COST × 0.15 + SPEED × 0.10
```

| Componente | Qué mide | Cómo se calcula |
|------------|----------|-----------------|
| **QUALITY** | Calidad objetiva del modelo (independiente del task) | Provider rep + tags + editorial curation |
| **TASK_FIT** | Qué tan bien matchea el modelo con el task específico | Capabilities match + content_type match |
| **COST** | Eficiencia de costo | 1.0 - (cost / max_budget), escala no lineal |
| **SPEED** | Velocidad estimada | Categoría + complexity signals |

### 2.2 QUALITY component (0-1)

```python
quality = 0.0

# Base por provider (pesos recalibrados)
provider_bonus = {
    "openai": 0.25,      # GPT Image — best instruction following
    "bytedance": 0.22,   # Seedream — best compositing
    "fal-ai": 0.15,      # Neutral (hosts many)
    "google": 0.20,      # Gemini native
    "xai": 0.12,         # Grok — newer
    "ideogram": 0.18,    # Good text
}
quality += provider_bonus.get(provider, 0.10)

# Tags bonus
if "realism" in tags: quality += 0.08
if "typography" in tags: quality += 0.08

# Editorial curation bonus (models FAL recommends)
CURATED_MODELS = {
    "fal-ai/nano-banana-2/edit": 0.10,
    "fal-ai/nano-banana-pro/edit": 0.12,
    "openai/gpt-image-2": 0.12,
    "openai/gpt-image-2/edit": 0.12,
    "fal-ai/bytedance/seedream/v4.5/edit": 0.10,
    "fal-ai/flux-2-pro": 0.08,
    "fal-ai/ideogram/v3": 0.08,
}
quality += CURATED_MODELS.get(endpoint_id, 0.0)

# Anti-bonus: utility models
if endpoint_id contains "tiling", "material", "character", "lora": quality -= 0.10

quality = clamp(quality, 0.0, 1.0)
```

### 2.3 TASK_FIT component (0-1)

```
task_fit = 0.0

# Category match
if action == "generate" and category == "text-to-image":     task_fit += 0.30
if action in ("edit","composite") and category == "image-to-image": task_fit += 0.30

# Capability REQUIRED (not bonus)
if reference_count >= 2 and not supports_multiple_refs:      TASK_FIT = 0  # HARD FAIL
if needs_mask and not supports_mask:                          TASK_FIT = 0  # HARD FAIL

# Capability BONUS (nice to have, not required)
if action in ("edit","composite") and supports_image_input:   task_fit += 0.20
if needs_text and ("typography" in tags or provider == "openai"): task_fit += 0.20
if needs_text and not ("typography" in tags):                 task_fit -= 0.10

# Content type affinity
CONTENT_AFFINITY = {
    "beauty": ["nano-banana", "gpt-image", "seedream"],
    "product": ["gpt-image", "seedream", "nano-banana", "flux"],
    "luxury": ["nano-banana", "gpt-image", "flux-2-pro"],
    "social": ["gpt-image", "ideogram", "flux"],
}
for keyword in CONTENT_AFFINITY.get(content_type, []):
    if keyword in endpoint_id: task_fit += 0.10; break

task_fit = clamp(task_fit, 0.0, 1.0)
```

### 2.4 COST component (0-1)

```python
# Non-linear: cheap models get bonus, expensive get penalty
# Use real costs from genmedia pricing where available
if cost <= 0.01:   cost_score = 0.95
elif cost <= 0.03:  cost_score = 0.85
elif cost <= 0.05:  cost_score = 0.70
elif cost <= 0.08:  cost_score = 0.50
elif cost <= 0.15:  cost_score = 0.25
else:               cost_score = 0.10

# Budget ceiling: if cost > max_budget, FILTER OUT (not score 0)
if cost > max_budget: EXCLUDE
```

---

## 3. Ejemplos esperados post-calibración

```
Query: composite, 2 refs, product, budget $0.10
→ 1. bytedance/seedream/v4.5/edit (quality=0.22, task=0.60, cost=0.70) = 0.56
→ 2. openai/gpt-image-2/edit (quality=0.37, task=0.50, cost=0.70) = 0.50
→ 3. fal-ai/nano-banana-2/edit (quality=0.18, task=0.55, cost=0.85) = 0.47

Query: edit, needs_mask, budget $0.05
→ 1. openai/gpt-image-2/edit (quality=0.37, task=0.60, cost=0.70) = 0.53
→ 2. fal-ai/flux-2-pro/edit (quality=0.23, task=0.50, cost=0.50) = 0.42
→ 3. fal-ai/nano-banana-2/edit (quality=0.18, task=0.50, cost=0.85) = 0.43

Query: generate, beauty, best quality
→ 1. fal-ai/nano-banana-pro (quality=0.23, task=0.60, cost=0.50) = 0.46
→ 2. openai/gpt-image-2 (quality=0.37, task=0.50, cost=0.70) = 0.48
→ 3. fal-ai/flux-2-pro (quality=0.23, task=0.40, cost=0.50) = 0.38
```

---

## 4. Criterios de aceptación

- [ ] Composite → Seedream o GPT Image 2 en top 3 (no utility models)
- [ ] Edit + mask → GPT Image 2 edit en top 2
- [ ] Generate beauty → Nano Banana Pro o GPT Image 2 en top 3
- [ ] `quick_select(PRODUCT_HERO, BEST)` → GPT Image 2 o Nano Banana Pro (no z-image/tiling)
- [ ] Ningún modelo con "tiling", "character", "material", "lora" en top 5 para queries de producto
- [ ] Costos reales donde estén disponibles (z-image $0.01, gpt-image-2 $0.04)
- [ ] Tests: al menos 3 assertions de ranking esperado
