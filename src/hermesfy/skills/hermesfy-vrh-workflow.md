---
name: hermesfy-vrh-workflow
description: >-
  MOTHER SKILL — Orquesta COMPLETO el pipeline VRH de Hermesfy Studio.
  Gatekeeper MANDATORIO para TODA generación con imágenes de referencia.
  Incluye: Goldilocks Rule, SpecBridge, Preview, DAG multi-modelo, Delivery.
  Telegram → VisualAnalysis → Goldilocks → Preview → DAG → Delivery.
---

# ⛔ HERMESFY VRH WORKFLOW — GATEKEEPER MANDATORIO ⛔

**ESTA SKILL ES EL PUNTO DE ENTRADA ÚNICO para toda generación de imágenes
con referencias visuales en Hermesfy Studio.**

Si hay imágenes del usuario involucradas, esta skill DEBE ejecutarse.
No hay atajos. No hay bypass. No hay "voy directo a genmedia".

---

## 🚨 GATEKEEPER — FASE 0 (ANTES que nada)

### Cuando esta skill DEBE activarse

Cualquiera de estos triggers la vuelve MANDATORIA:

| Trigger | Ejemplo |
|---------|---------|
| Usuario manda 1+ imágenes | `[image]` en Telegram |
| Pide "cambiar X por Y" sobre una referencia | "cambiale la botella por Vichy" |
| Pide "igual pero con..." | "exactamente igual pero con Quencher" |
| Pide "usá esta imagen de referencia" | "basate en esta foto" |
| Menciona "reemplazar", "mantener layout", "mismo estilo" | "mismo estilo pero otro producto" |
| Pide generar algo "como esta imagen" | "como la del escritorio pero con..." |

### ⛔ PROHIBIDO — NUNCA hacer esto cuando hay referencias

```
❌ Llamar image_generate directamente
❌ Llamar terminal(genmedia run ...) sin pasar por el pipeline
❌ Escribir prompts a mano sin StructuredSpec previo
❌ Generar sin preguntar al usuario (sin Preview Fase 2)
❌ Usar UN solo modelo cuando el task requiere DAG multi-step
```

### ✅ OBLIGATORIO — Siempre seguir este orden

```
FASE 0 → Gatekeeper: ¿hay imágenes? → ACTIVAR ESTA SKILL
FASE 1 → VisualAnalyzer: extraer StructuredSpec de CADA imagen
FASE 2 → Goldilocks + Preview: determinar fidelity, MOSTRAR preview, PREGUNTAR
FASE 3 → DAG Execution: multi-modelo con seed propagation
FASE 4 → Delivery: descargar, verificar, entregar
```

---

## FASE 1: Visual Analysis

### 1.1 Detectar imágenes

Las imágenes llegan a `~/.hermes/cache/images/`. Buscar las más recientes:

```bash
ls -lt ~/.hermes/cache/images/ | head -5
```

### 1.2 Analizar CADA imagen con StructuredSpec

```python
import sys
sys.path.insert(0, '/opt/hermesfy-studio/src')
from hermesfy.reference.visual_analyzer import VisualAnalyzer

analyzer = VisualAnalyzer()

# Para cada imagen de referencia:
for image_path in reference_images:
    # Usar vision_analyze con el prompt estructurado
    vision_prompt = analyzer.get_vision_prompt(user_hint="lo que el usuario quiere")
    # → llamar a mcp_minimax_understand_image o vision_analyze
    # Parsear resultado:
    spec = VisualAnalyzer.parse_vision_text(vision_response)
```

**StructuredSpec extrae:**
- Layout (zonas, posiciones, % de pantalla)
- Paleta de colores exacta (hex aproximados)
- Iluminación (dirección, tipo, intensidad)
- Objetos (qué, dónde, tamaño relativo)
- Tipografía (posición, estilo, tamaño)
- Profundidad de campo (qué está en foco vs blur)

### 1.3 Múltiples referencias

Cuando el usuario manda 2+ imágenes (ej: una del layout, otra del producto):
- **Imagen A** → spec de composición/estilo (el "dónde")
- **Imagen B** → spec del sujeto/producto (el "qué")
- El SpecBridge fusiona ambas specs

---

## FASE 2: Goldilocks Rule — Fidelity Matching

### 2.1 Detección automática de fidelity

```python
from hermesfy.reference.spec_bridge import SpecBridge
bridge = SpecBridge()
fidelity, drift, label = bridge._determine_fidelity(user_prompt)
```

| Grupo | Keywords | fidelity | drift |
|-------|----------|----------|-------|
| **Minimal** | "ignorá", "sin referencia", "creativo libre", "de cero", "inventá" | 0.25 | 0.75 |
| **High** | "exactamente igual", "idéntico", "mismo", "sin cambiar", "solo cambia", "mantené todo", "copiá", "calcá", "reproducí", "100% fidelidad" | 0.95 | 0.05 |
| **Medium** | "parecido", "similar", "mismo estilo", "referencia", "como esta foto" | 0.85 | 0.15 |
| **Low** | "inspirado", "algo así", "onda", "vibra", "tirando a" | 0.60 | 0.40 |
| **Default** | Sin keywords claras | 0.85 | 0.15 |

**Orden de matching:** Minimal primero → High → Medium → Low
(Minimal va primero porque "ignorá la referencia" matchea "referencia" en Medium si no)

### 2.2 Preview — OBLIGATORIO preguntar al usuario

```python
# Build preview
preview = bridge.build(spec, user_prompt, preview=True)

# MOSTRAR al usuario:
# 📐 Layout: ...
# 🎨 Paleta: ...
# 💡 Iluminación: ...
# 🎯 Fidelidad: Alta (95%)
# 🖼️ Referencias: [lista de imágenes]
# 
# ¿Genero así o ajustamos algo?
```

**NUNCA generar sin antes mostrar el preview y recibir confirmación.**

Si el usuario dice "dale", "ok", "generá", "vamos" → continuar a Fase 3.

### 2.3 Build ExecutionSpec

```python
exec_spec = bridge.build(
    spec,
    user_prompt,
    reference_mode="style_layout",  # default
    quality="high"
)
```

**Modos de referencia:**
| mode | uso |
|------|-----|
| `style_layout` | Default. Mantener TODO: estilo visual + composición |
| `style_only` | Cambiar composición, mantener paleta/iluminación |
| `layout_only` | Cambiar estilo, mantener layout |
| `subject_only` | Solo mantener el sujeto, todo lo demás nuevo |

---

## FASE 3: DAG Multi-Model Execution

### 3.1 ⚠️ DISTINCIÓN CRÍTICA: Modelos GENERATIVOS vs Modelos EDIT

**Descubrimiento empírico (sesión 2026-05-07):** FAL tiene DOS categorías de modelos, y usar la equivocada produce resultados basura.

| Categoría | Qué hacen | Ejemplos |
|-----------|-----------|----------|
| **GENERATIVOS** | Crean imágenes DESDE CERO. No preservan la imagen original. | `fal-ai/flux/schnell`, `fal-ai/flux/dev`, `openai/gpt-image-2`, `fal-ai/nano-banana-2` |
| **EDIT** | Toman una imagen base y hacen cambios PUNTUALES. Preservan lo no modificado. | `fal-ai/gemini-3-pro-image-preview/edit`, `fal-ai/nano-banana-pro/edit`, `fal-ai/bytedance/seedream/v5/lite/edit`, `fal-ai/flux-2-pro/edit`, `openai/gpt-image-2/edit` |

**Regla de oro:** Si el usuario pide "reemplazar X por Y manteniendo todo lo demás" → usar modelos EDIT, NUNCA generativos.

### 3.2 Estrategia de modelos por tipo de task

| Task type | ¿Qué modelos? | Estrategia |
|-----------|--------------|------------|
| **Creación desde cero** (sin referencias) | GENERATIVOS | `flux/schnell` → `gpt-image-2` → `nano-banana-pro` |
| **Reemplazo de producto** (fidelity > 0.90) | EDIT | `gemini-3-pro-image-preview/edit` o `nano-banana-pro/edit` con `--image_urls` de layout + producto |
| **Reemplazo con máscara** (fidelity máxima) | EDIT + máscara | `gpt-image-2/edit` o `flux/inpainting` con `--mask_url` |
| **Texto preciso** | EDIT (tipografía) | `nano-banana-pro/edit` |
| **Estilo artístico** | GENERATIVOS | `flux/dev` → `nano-banana-2` |
| **Rápido/borrador** | GENERATIVO simple | `flux/schnell` solo |

### 3.2 Ejecutar vía GenmediaProvider

```python
import asyncio
from hermesfy.providers.genmedia import GenmediaProvider

async def run_dag(exec_spec):
    p = GenmediaProvider()
    
    # Nodo 1: base rápida
    r1 = await p.generate('image_gen', {
        'prompt': exec_spec['dag_workflow']['steps'][0]['params']['prompt'],
        'width': exec_spec['dag_workflow']['steps'][0]['params'].get('width', 1024),
        'height': exec_spec['dag_workflow']['steps'][0]['params'].get('height', 1024),
        'guidance_scale': 3.5,
        'model': 'fal-ai/flux/schnell',
    })
    
    # Nodo 2: refinar con modelo superior (si fidelity > 0.85)
    if fidelity > 0.85:
        r2 = await p.generate('image_gen', {
            'prompt': prompt_refinado,
            'model': 'openai/gpt-image-2',
            # heredar dimensiones del nodo 1
            'width': r1.width, 'height': r1.height,
        })
        return r2
    return r1
```

### 3.3 Seed propagation

Mantener la seed entre nodos para consistencia visual:

```python
seed = result.metadata.get('seed', random.randint(0, 2**32))
# Pasar la misma seed al siguiente nodo
config['seed'] = seed
```

---

## FASE 4: Delivery + Verificación

### 4.1 Descargar imagen

```python
from hermesfy.reference.delivery import Delivery
delivery = Delivery()
local_path = delivery.download(image_url)
```

### 4.2 Verificar contra el spec

```python
# Verificar dimensiones, formato
# Si hay problemas → flaggear para iteración
```

### 4.3 Entregar

Responder con `MEDIA:/path/to/file.jpg` + resumen de lo generado.

---

## Manejo de múltiples referencias (COMPOSITING)

Cuando el usuario manda 2+ imágenes de referencia con intenciones distintas:

1. **Analizar cada imagen por separado** (Fase 1 para cada una)
2. **Clasificar roles:**
   - Imagen A → "layout_reference" (la escena, composición)
   - Imagen B → "subject_reference" (el producto a insertar)
3. **SpecBridge fusiona:** toma layout de A + sujeto de B
4. **Prompt resultante:** `[SUBJECT de Spec B] [ENVIRONMENT de Spec A] [STYLE de Spec A]`
5. **Si fidelity=0.95 y hay subject_reference:** usar img2img o GPT Image 2 con la imagen del sujeto como input visual para preservar su diseño exacto

---

## ⚠️ LIMITACIÓN CRÍTICA: Fidelidad de producto en text-to-image

**Descubrimiento empírico (sesión 2026-05-07):** Los modelos text-to-image, incluso GPT Image 2 con `--image_urls`, **no preservan el diseño exacto de productos con marca**. El modelo interpreta la referencia como "inspiración" y crea un producto similar pero distinto.

| Test | Referencia | Resultado |
|------|-----------|-----------|
| Quencher GOODAL tumbler | Matte black, banda dorada, mango C, straw | Tumbler genérico sin marca |
| Perfume "9 pm REBEL" | Cuboid oscuro, líquido azul, etiqueta específica | "Maison des Parfums Bella" (inventado) |

**Causa raíz:** Los modelos de difusión no tienen "memoria visual" de productos específicos. El parámetro `--image_urls` en GPT Image 2 se usa como guía compositiva, no como calco de diseño.

### Estrategias que SÍ funcionan (por orden de efectividad)

| Estrategia | Fidelidad | Cuándo usarla |
|-----------|-----------|---------------|
| **Img2img con producto como BASE** | Alta | Usar `fal-ai/flux/dev/image-to-image` con la foto del producto como `--image_url` y strength 0.3–0.5. El modelo PARTE de la foto real y agrega el entorno. |
| **Inpainting sobre layout** | Máxima | Usar `fal-ai/flux/inpainting` con la foto del layout como base + máscara donde va el producto + la foto del producto como referencia. Requiere crear una máscara. |
| **GPT Image 2 edit con máscara** | Máxima | `openai/gpt-image-2/edit` + `--mask_url` sobre la imagen del layout, con prompt indicando qué producto insertar. |
| **Post-procesado manual** | 100% | Generar layout sin producto, generar producto por separado, compositar en Photoshop/GIMP. Fuera del alcance de Hermesfy. |

### Cómo manejar esto con el usuario

Cuando el task requiera **100% fidelidad de producto con marca específica:**
1. Advertir en FASE 2 (Preview): "El diseño exacto del producto puede no preservarse al 100% con text-to-image."
2. Ofrecer alternativas: img2img con la foto del producto como base, o inpainting.
3. Si el usuario confirma "generá igual", proceder aceptando el riesgo.

## Errores comunes — CÓMO EVITARLOS

| Error | Causa | Prevención |
|-------|-------|------------|
| Producto no se parece a la referencia | Text-to-image no preserva marcas | **NO usar texto para describir el producto.** Usar img2img con la foto como `--image_url` (strength 0.3–0.5) o inpainting con máscara. |
| Layout no respeta el original | FLUX inventa composición | fidelity 0.95 incluye `[FIDELITY HIGH — preservar composición exacta]` en el prompt |
| Tipografía ilegible o incorrecta | FLUX texto pobre | Usar Nano Banana Pro para texto, o GPT Image 2 |
| Colores wrong | No se pasó la paleta al prompt | StructuredSpec incluye colores exactos → van al prompt |
| Generar sin preguntar | Saltarse Fase 2 | **NUNCA saltar Preview.** Siempre preguntar. |
| Un solo modelo para todo | No usar DAG | DAG multi-step para tasks complejos |
| GPT Image 2 `--image_urls` no preserva diseño | El parámetro es guía, no calco | Usar img2img real (strength < 0.5) o inpainting. Ver sección LIMITACIÓN CRÍTICA arriba. |

---

## Checklist de auto-verificación

Antes de responder al usuario, verificar:

- [ ] ¿Cargué esta skill? (hermesfy-vrh-workflow)
- [ ] ¿Analicé TODAS las imágenes de referencia? (Fase 1)
- [ ] ¿Ejecuté Goldilocks y detecté fidelity correcto? (Fase 2)
- [ ] ¿Mostré preview al usuario y esperé confirmación? (Fase 2)
- [ ] ¿Usé DAG multi-modelo (no un solo modelo)? (Fase 3)
- [ ] ¿Usé GenmediaProvider, no genmedia CLI directo? (Fase 3)
- [ ] ¿Descargué la imagen y la entregué como MEDIA:? (Fase 4)
- [ ] ¿Verifiqué el output contra el spec? (Fase 4)

---

## Sub-skills relacionadas (cargadas automáticamente por esta skill madre)

- `hermesfy-goldilocks-rule` → Fidelity matching automático
- `hermesfy-spec-bridge` → Conversión StructuredSpec → ExecutionSpec
- `hermesfy-vrh-preview` → Preview visual antes de generar
- `visual-reference-analyzer` → Análisis de imagen de referencia
