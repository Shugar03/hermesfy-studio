---
name: image-editing-vs-generation
description: >-
  CRITICAL — Determina si un request necesita EDICIÓN (preservar imagen original,
  cambiar solo un elemento) o GENERACIÓN (crear de cero). Usa SAM 3 + edición con
  máscara para ediciones precisas. NO uses generadores (FLUX) para tasks de edición.
triggers:
  - "reemplaza X por Y"
  - "cambia esto por esto otro"
  - "mantené todo igual pero"
  - "solo cambia"
  - "swap"
  - "borrá esto y poné esto"
  - "editá"
  - "modificá esta imagen"
  - reference image + replacement request
---

# Image Editing vs Generation — Gatekeeper

## ⛔ REGLA DE ORO

**Si el usuario quiere preservar una imagen existente y cambiar SOLO una parte → es EDICIÓN, no generación.**

NUNCA uses modelos de text-to-image (FLUX schnell, GPT Image 2 text-to-image) para tasks de edición.
Esos modelos REGENERAN todo desde cero. El resultado será genérico y no preservará la imagen original.

## Cuándo activar esta skill

| Trigger | Tipo | Pipeline |
|---------|------|----------|
| "reemplaza X por Y" | **EDITING** | SAM 3 mask → Edit with mask |
| "cambia esto, dejá el resto igual" | **EDITING** | SAM 3 mask → Edit with mask |
| "creá una imagen de..." | GENERATION | Text-to-image directo |
| "generá algo como..." | GENERATION | Text-to-image + img2img refine |

## Pipeline de EDICIÓN (el que funciona)

### Paso 1: SAM 3 — segmentar el objeto a reemplazar

```bash
genmedia run fal-ai/sam-3/image --json \
  --image_url "URL_IMAGEN_LAYOUT" \
  --prompt "descripción del objeto a segmentar" \
  --return_multiple_masks false \
  --include_boxes true
```

SAM 3 soporta segmentación por texto. Describí el objeto que querés reemplazar.
Ej: "white dropper bottle", "amber pill bottle", "serum dropper"

### Paso 2: Editar con máscara

```python
import subprocess, json

cmd = [
    "genmedia", "run", "openai/gpt-image-2/edit", "--json",
    "--image_urls", json.dumps([layout_url, subject_url]),
    "--mask_url", mask_url,
    "--prompt", "Replace ONLY the masked area with [producto]. Keep everything outside the mask IDENTICAL.",
    "--quality", "high",
    "--output_format", "png"
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
```

### Modelos que soportan máscara (mask_url / mask_image_url)

| Modelo | Soporta mask? | Mejor para |
|--------|--------------|------------|
| `openai/gpt-image-2/edit` | ✅ `mask_url` | Edición precisa, alta calidad |
| `fal-ai/nano-banana-pro/edit` | ✅ (verificar) | Realism + typography |

### Modelos que NO soportan máscara (editan todo)

| Modelo | Problema |
|--------|----------|
| `fal-ai/flux/schnell` | ❌ Genera de cero, no preserva nada |
| `openai/gpt-image-2` | ❌ Mismo problema, text-to-image |
| `fal-ai/bytedance/seedream/*/edit` | ⚠️ Edita sin máscara, puede tocar áreas no deseadas |
| `fal-ai/gemini-3-pro-image-preview/edit` | ⚠️ Edita todo, puede reinterpretar |

## ⛔ NO HACER

```
❌ Usar FLUX schnell/dev para "reemplazar X por Y"
❌ Usar GPT Image 2 text-to-image para "cambiar esto"
❌ Escribir prompts largos describiendo la escena cuando solo necesitás cambiar un elemento
❌ Iterar 5+ veces con modelos generativos cuando el task es edición
❌ Asumir que "--image_urls" en un modelo edit significa "usa esto como referencia exacta"
   (sin máscara, el modelo reinterpreta todo)
```

## ✅ HACER

```
✅ Primero preguntarse: ¿es edición o generación?
✅ Si es edición → SAM 3 → máscara → edición con máscara
✅ Usar json.dumps() en Python para pasar arrays a genmedia (evitar problemas de quoting en bash)
✅ Verificar el resultado: ¿las áreas fuera de la máscara están intactas?
```

## Pitfalls descubiertos

### JSON quoting en bash
```bash
# ❌ MAL — las comillas se pierden en bash
--image_urls "[url1,url2]"

# ✅ BIEN — usar Python con json.dumps()
cmd = ["genmedia", ..., "--image_urls", json.dumps([url1, url2])]
```

### SAM 3 prompt
- Usar descripciones simples: "white dropper bottle" no "the white serum dropper bottle with a white cap that contains AHA solution"
- Si no segmenta bien, probar con términos más genéricos: "bottle", "product"

### Máscara invertida
- SAM 3 genera máscara blanca sobre negro. La máscara ya está lista para usar como `mask_url`.
- El área blanca = área a editar. No necesita inversión.

## Lección de esta sesión

Gastamos ~20 créditos iterando con FLUX, GPT Image 2, Seedream, Gemini 3 Pro, Nano Banana 2...
todos modelos de generación o edición sin máscara. NINGUNO funcionó para "reemplazar este producto
por este otro manteniendo todo igual".

El pipeline SAM 3 + edición con máscara lo resolvió en 2 llamadas (1 segmentación + 1 edición).
Es la diferencia entre editar y regenerar.
