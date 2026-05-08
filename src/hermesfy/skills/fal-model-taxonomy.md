---
name: fal-model-taxonomy
description: >-
  Taxonomía completa de los 780 modelos de FAL.ai agrupados en 12 familias
  con patrones de prompting documentados. Guía de selección de modelo
  según tipo de task. Symlink al repo de Hermesfy Studio.
---

# FAL Model Taxonomy — 12 Familias de Prompting

**Creado desde investigación exhaustiva de 780 modelos en FAL.ai.**
No necesitás conocer 780 modelos — necesitás conocer 12 familias.

---

## FAMILIAS DE GENERACIÓN / EDICIÓN

---

### 1. FLUX Family (Black Forest Labs) — ~18 modelos

| Modelo | Velocidad | Calidad | Precio | Uso |
|--------|-----------|---------|--------|-----|
| `fal-ai/flux/schnell` | ⚡ Rápido | Media | $0.005 | Borradores, iteración |
| `fal-ai/flux/dev` | Medio | Alta | $0.02 | Generación estándar |
| `fal-ai/flux-pro/v1.1` | Lento | Máxima | $0.06 | Producción final |
| `fal-ai/flux-2-pro` | Lento | Máxima | $0.08 | Última generación |
| `fal-ai/flux-pro/kontext` | Medio | Alta | $0.05 | img2img, preserva contexto |
| `fal-ai/flux-lora` | Medio | Alta | $0.02 | Con LoRAs custom |
| `fal-ai/flux-2-pro/edit` | Medio | Máxima | $0.08 | Edición con FLUX 2 |

**Patrón de prompting FLUX:**
```
Subject: [qué o quién — PRIMERO, es lo más importante]
Environment: [dónde, fondo, contexto]
Details: [materiales, texturas, colores exactos — usar HEX si es posible]
Lighting: [dirección, tipo, intensidad]
Camera: [lente, ángulo, profundidad de campo]
Style: [photorealistic / cinematic / editorial / minimalist]
Constraints: [no watermark, no text, no extra objects]
```

**Reglas FLUX:**
- Subject SIEMPRE primero
- Usar HEX para colores: `background #8B0000 to #4A0000 gradient`
- Evitar adjetivos vagos ("beautiful", "stunning") — usar hechos visuales
- `guidance_scale`: 3.5-4.5 para generación, 2.0-3.0 para edición

---

### 2. Nano Banana Family (Google Gemini) — ~5 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/nano-banana-2` | Text-to-image, hasta 14 refs |
| `fal-ai/nano-banana-2/edit` | Edición semántica con thinking |
| `fal-ai/nano-banana-pro` | Premium, razonamiento profundo |
| `fal-ai/nano-banana-pro/edit` | Edición premium, texto perfecto |
| `fal-ai/nano-banana/edit` | Edición básica |

**Patrón de prompting Nano Banana:**
```
Action + Subject + Style/Lighting + Scene/Constraints
```

**Ejemplo:**
```
Replace the white bottle with a dark perfume bottle. 
Keep the same background, lighting, and composition. 
Only change the product. No other modifications.
```

**Parámetros clave:**
- `thinking_level`: `high` para edits complejos, `minimal` para simples
- `resolution`: `1K`/`2K`/`4K`
- `system_prompt`: opcional para steering del modelo
- Soporta hasta 14 imágenes de referencia

---

### 3. GPT Image Family (OpenAI) — 2 modelos

| Modelo | Uso |
|--------|-----|
| `openai/gpt-image-2` | Text-to-image, máxima calidad |
| `openai/gpt-image-2/edit` | Edición con máscara opcional |

**Patrón de prompting GPT Image (FAL official):**

**Para edición:**
```
Change:
[exactamente qué debe cambiar]

Preserve:
[iluminación, encuadre, fondo, composición, texturas, colores fuera del área editada]

Constraints:
[no extra objects, no redesign, no logo drift, no watermark]
```

**Para generación:**
```
Scene:
[donde ocurre, hora del día, fondo, ambiente]

Subject:
[quién o qué es el foco principal]

Important details:
[materiales, ropa, textura, iluminación, ángulo de cámara, composición, mood]

Use case:
[editorial photo / product mockup / poster / UI screen / infographic]

Constraints:
[no watermark / no logos / no extra text / preserve face / preserve layout]
```

**Reglas GPT Image:**
- NUNCA usar adjetivos vagos: ❌ stunning, incredible, masterpiece
- SIEMPRE usar hechos visuales: ✅ overcast daylight, brushed aluminum, chipped paint
- En ediciones: 1 cambio por turno, repetir la lista de "preserve"
- `mask_image_url`: edición quirúrgica pixel-perfect (solo toca el área blanca)
- `quality`: `low`/`medium`/`high`
- `input_fidelity`: `high` para preservar la imagen original

---

### 4. Seedream Family (ByteDance) — ~6 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/bytedance/seedream/v4.5/edit` | Compositing multi-imagen |
| `fal-ai/bytedance/seedream/v5/lite/edit` | Edición rápida high-res |
| `fal-ai/bytedance/seedream/v4/edit` | Edición con style transfer |
| `fal-ai/bytedance/seedream/v4.5/text-to-image` | Generación |

**Patrón de prompting Seedream (4 roles de referencia):**
```
Image 1: [scene reference — preservar fondo, composición, iluminación]
Image 2: [product reference — usar este diseño, forma, color, branding]
Image 3: [style reference — paleta de colores, tratamiento]
Image 4: [composition reference — encuadre, ángulo]

Instruction:
Use the scene from Image 1. Replace the product with the item from Image 2.
Keep the lighting from Image 1. Keep the composition from Image 1.
No other changes.
```

**Reglas Seedream:**
- Subject description PRIMERO en el prompt
- Asignar roles explícitos a cada imagen de referencia
- Usar términos fotográficos: "85mm lens", "shallow depth of field", "golden hour"
- Hasta 10 imágenes de referencia

---

### 5. Grok Imagine Family (xAI) — ~3 modelos

| Modelo | Uso |
|--------|-----|
| `xai/grok-imagine-image` | Text-to-image |
| `xai/grok-imagine-image/edit` | Edición |

**Patrón de prompting Grok:** 
Similar a FLUX — subject-first, instrucciones directas.
Precio: ~$0.022/edit (el más barato para edición).

---

### 6. Ideogram — 1 modelo

| Modelo | Uso |
|--------|-----|
| `fal-ai/ideogram/v3` | Realismo + tipografía premium |

**Fortalezas:** Texto preciso en imágenes, realismo fotográfico.
**Patrón:** Similar a FLUX, énfasis en descripción de tipografía.

---

### 7. Z-Image Family — ~3 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/z-image/turbo` | Alternativa rápida a FLUX |

**Fortalezas:** Velocidad, good para iteración rápida.

---

### 8. Gemini Native Family (Google vía FAL) — 2 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/gemini-3-pro-image-preview/edit` | Edición con preservación de contexto |

**Fortalezas:** El mejor para "cambiar solo una cosa y dejar todo lo demás igual".
**Patrón:** Instrucciones en lenguaje natural. "Replace the bottle. Keep everything else identical."

---

### 9. Qwen Image Family (Alibaba) — ~2 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/qwen-image-edit-2511` | Edición fiel — el favorito de Reddit |

**Patrón de prompting Qwen (de Reddit):**
```
Recreate this image exactly, especially the [elementos clave], 
[estilo], [fondo], composition and dimensions. 
Only make one change: [cambio específico]. 
Change nothing else. Keep everything else unchanged.
```
**Regla de oro:** Siempre terminar con "Keep everything else unchanged."

---

## FAMILIAS DE UTILIDAD

---

### 10. SAM Family (Meta) — 3 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/sam-3/image` | Segmentación por texto — genera máscaras |
| `fal-ai/sam2/image` | Segmentación video + imagen |
| `fal-ai/sam-3-1/image` | SAM 3.1 con Object Multiplex |

**Uso en pipeline:**
```
SAM 3 → prompt "white dropper bottle" → máscara binaria
      → GPT Image 2 Edit + mask_url → reemplazo quirúrgico
```

---

### 11. Remove Background Family — ~8 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/birefnet/v2` | Alta resolución, bordes precisos |
| `fal-ai/bria/background/remove` | Bria RMBG 2.0 |
| `pixelcut/background-removal` | Pixelcut, e-commerce optimizado |

---

### 12. Upscale / Restore Family — ~6 modelos

| Modelo | Uso |
|--------|-----|
| `fal-ai/clarity-upscaler` | Upscaling high-res |
| `fal-ai/topaz/upscale/image` | Topaz, calidad premium |
| `fal-ai/seedvr/upscale/image` | SeedVR upscale |
| `fal-ai/codeformer` | Face restore |

---

## GUÍA RÁPIDA DE SELECCIÓN

| Si necesitás... | Usá... | Porque... |
|-----------------|--------|-----------|
| **Reemplazar producto, preservar TODO** | GPT Image 2 Edit + mask | Cambio quirúrgico, Change/Preserve/Constraints |
| **Compositing multi-imagen** | Seedream 4.5 Edit | Hasta 10 refs, roles explícitos |
| **Edición con instrucciones complejas** | Nano Banana Pro Edit | Thinking level high, razonamiento |
| **Generar desde cero, máxima calidad** | FLUX Pro o GPT Image 2 | Calidad premium |
| **Texto preciso en imagen** | Ideogram o Nano Banana Pro | Tipografía superior |
| **Iteración rápida, bajo costo** | FLUX Schnell o Grok | $0.005-0.022 |
| **Segmentar objeto → máscara** | SAM 3 | Prompt por texto, bounding boxes |
| **Remover fondo** | BiRefNet v2 o Bria RMBG | Alta precisión |
| **Upscale a 4K** | Clarity o Topaz | Calidad profesional |

---

## PIPELINE RECOMENDADO (Product Replacement)

```
1. SAM 3 segmenta el producto → máscara
2. GPT Image 2 Edit + mask → reemplazo quirúrgico
3. (Opcional) Seedream 4.5 → compositing si hay múltiples referencias
4. (Opcional) Clarity Upscaler → 4K si es necesario
```

---

## REGLAS DE ORO TRANSVERSALES

1. **NUNCA improvisar el formato de prompt** — cada familia tiene el suyo
2. **Separar CHANGE de PRESERVE** — aplica a GPT Image, Nano Banana, Qwen
3. **Hechos visuales > adjetivos vagos** — "overcast daylight" no "beautiful"
4. **Una revisión por turno** — no pedir 5 cambios en un solo prompt
5. **Máscara para edición quirúrgica** — SAM 3 + modelo edit con mask_url
6. **Siempre terminar con constraints** — "No other changes. Keep everything else identical."
