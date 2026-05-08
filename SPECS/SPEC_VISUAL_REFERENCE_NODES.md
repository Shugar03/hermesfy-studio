# SPEC: Visual Reference Nodes + HTML Canvas — Hermesfy Studio V6

**Author:** Hermes Agent  
**Date:** 2026-05-07  
**Status:** Draft → Implementation  
**Depends on:** SPEC_MODEL_QUERY_ENGINE (V5), VRHGate (V5)

---

## 1. Overview

### 1.1 Problem

El canvas actual de Hermesfy es **solo texto** (emojis + resúmenes de config).  
No hay forma de:

1. **Ver imágenes de referencia en el canvas** — los workflows que usan referencias visuales
   las tienen como strings en `image_url`, invisibles en la representación visual.
2. **Distinguir nodos de input visual de nodos de ejecución** — todos los nodos se ven iguales.
3. **Tener un canvas que se parezca a Higgsfield/ComfyUI** — con thumbnails reales,
   conexiones visuales, y nodos de referencia que muestran la imagen que contienen.

### 1.2 Solution

Dos fases implementadas en esta SPEC:

| Fase | Alcance | Output |
|------|---------|--------|
| **FASE 1: REFERENCE_IMAGE NodeType** | Engine core — nuevo tipo de nodo passthrough para imágenes de referencia | `graph.py`, `executor.py`, `canvas.py`, validación |
| **FASE 2: HTML Canvas Renderer** | Visual — canvas HTML con thumbnails reales, colores por tipo, conexiones SVG | `canvas_html.py`, `templates/canvas.html` |

### 1.3 Inspiración: Higgsfield

Higgsfield UI tiene nodos de imagen que:
- Muestran un **thumbnail real** de la imagen (no un ícono genérico)
- Son nodos de **solo input** — no ejecutan, solo proveen datos visuales
- Se conectan a nodos de generación como **referencias visuales**
- El canvas es **oscuro** con nodos claros, líneas curvas, y layout automático

---

## 2. Arquitectura Actual vs Target

### 2.1 Current (V5)

```
NodeType enum: TEXT_PROMPT, IMAGE_GEN, IMG2IMG, UPSCALE, SEED, 
               INPAINT, OUTPAINT, IP_ADAPTER, REMOVE_BG, FACE_RESTORE

PASS_THROUGH_TYPES: {TEXT_PROMPT, SEED}

Canvas: render_canvas() → texto con emojis
        render_minimal_canvas() → alias backward-compat
```

### 2.2 Target (V6)

```
NodeType enum: + REFERENCE_IMAGE  ← NUEVO

PASS_THROUGH_TYPES: {TEXT_PROMPT, SEED, REFERENCE_IMAGE}

Canvas: render_canvas() → texto con emojis (backward compat)
        render_canvas_html() → HTML con thumbnails + SVG connections  ← NUEVO
```

---

## 3. FASE 1: REFERENCE_IMAGE NodeType

### 3.1 NodeType Addition

**File:** `src/hermesfy/dag/graph.py`

```python
class NodeType(str, Enum):
    # ... existing types ...
    REFERENCE_IMAGE = "reference_image"  # ← NEW
```

### 3.2 Required Config

```python
REQUIRED_CONFIG[NodeType.REFERENCE_IMAGE] = {"image_url"}
```

El nodo DEBE tener `image_url` en su config.  
Opcionalmente puede tener `label` (nombre descriptivo) y `reference_role` 
(`layout`, `subject`, `style`, `composition` — semántica de Seedream/VRH).

### 3.3 Config Schema

```python
# Ejemplo de nodo REFERENCE_IMAGE
{
    "id": "ref-stanley",
    "type": "reference_image",
    "config": {
        "image_url": "https://example.com/stanley-tumbler.jpg",
        "label": "Stanley Tumbler",
        "reference_role": "subject"  # opcional
    }
}
```

### 3.4 Executor Integration

**File:** `src/hermesfy/dag/executor.py`

Agregar `NodeType.REFERENCE_IMAGE` a `PASS_THROUGH_TYPES`:

```python
PASS_THROUGH_TYPES = {NodeType.TEXT_PROMPT, NodeType.SEED, NodeType.REFERENCE_IMAGE}
```

El nodo no llama al provider. Su output es su config completo, incluyendo `image_url`.  
Cuando otro nodo referencia `{{ref-stanley}}`, `_resolve_inputs()` devuelve el `image_url`.

### 3.5 Input Resolution para REFERENCE_IMAGE

**File:** `src/hermesfy/dag/executor.py` → `_lookup_ref()`

Cuando se resuelve `{{ref_node}}` y el output es un dict con `image_url`, 
el sistema ya devuelve `image_url` gracias a la lógica existente en `_lookup_ref()`:

```python
if isinstance(node_output, dict):
    return node_output.get("prompt", node_output.get("image_url", ...))
```

Esto ya funciona para REFERENCE_IMAGE sin cambios adicionales.

### 3.6 Canvas Textual Update

**File:** `src/hermesfy/rendering/canvas.py`

Agregar al `TYPE_LABEL`:

```python
TYPE_LABEL = {
    # ... existing ...
    NodeType.REFERENCE_IMAGE.value: "🖼️ REF",
}
```

Agregar a `_config_summary()` para mostrar el `label` o `image_url` abreviado:

```python
if "image_url" in config and node.type == NodeType.REFERENCE_IMAGE:
    label = config.get("label", "")
    if label:
        parts.append(f'🖼️ "{label}"')
    else:
        u = str(config["image_url"])
        parts.append(f"🖼️ {u[:30]}...")
```

### 3.7 Validation

El `validate_workflow()` en `graph.py` ya valida `REQUIRED_CONFIG` — 
al agregar `REFERENCE_IMAGE: {"image_url"}`, automáticamente exige que 
los nodos de referencia tengan `image_url`.

### 3.8 Tool Schema Update

**File:** `src/hermesfy/tools/define_workflow.py`

El schema `DEFINE_WORKFLOW_SCHEMA` usa `[e.value for e in NodeType]` — 
automáticamente incluye `reference_image` cuando se agrega al enum.

---

## 4. FASE 2: HTML Canvas Renderer

### 4.1 Design Goals

1. **Thumbnails reales** — nodos REFERENCE_IMAGE muestran la imagen como `<img>` tag
2. **Colores por tipo** — cada NodeType tiene un color distintivo
3. **Conexiones visuales** — líneas curvas SVG entre nodos conectados
4. **Layout automático** — topological sort → posiciones en grid/capas
5. **Dark theme** — fondo oscuro tipo Higgsfield/ComfyUI
6. **Responsive** — se adapta al viewport
7. **Self-contained HTML** — un solo archivo, sin dependencias externas

### 4.2 File Structure

```
src/hermesfy/rendering/
├── canvas.py           # Text canvas (existing, unchanged)
├── canvas_html.py      # NEW — HTML canvas renderer
└── templates/
    └── canvas.css      # NEW — estilos base (opcional, puede ir inline)
```

### 4.3 API

```python
def render_canvas_html(
    workflow: Workflow,
    node_states: dict | None = None,
    node_errors: dict | None = None,
    title: str = "Hermesfy Studio",
) -> str:
    """Render a visual HTML canvas with thumbnails and SVG connections.
    
    Args:
        workflow: The workflow to render.
        node_states: Optional dict of node_id → state.
        node_errors: Optional dict of node_id → error message.
        title: Page title.
        
    Returns:
        Complete self-contained HTML string.
    """
```

### 4.4 Node Type Color Scheme

```python
NODE_COLORS = {
    "reference_image": {"bg": "#1a3a4a", "border": "#4fc3f7", "label": "REF"},
    "text_prompt":     {"bg": "#2a1a3a", "border": "#ce93d8", "label": "TXT"},
    "image_gen":       {"bg": "#1a2a1a", "border": "#81c784", "label": "GEN"},
    "img2img":         {"bg": "#2a2a1a", "border": "#fff176", "label": "I2I"},
    "upscale":         {"bg": "#1a1a3a", "border": "#64b5f6", "label": "UP"},
    "inpaint":         {"bg": "#3a1a1a", "border": "#ef5350", "label": "INP"},
    "seed":            {"bg": "#2a2a2a", "border": "#bdbdbd", "label": "🌱"},
    "remove_bg":       {"bg": "#1a2a2a", "border": "#4db6ac", "label": "BG"},
}
```

### 4.5 Layout Algorithm

Topological sort → N capas verticales (columnas):

```
Layer 0 (inputs):    [ref-img-1]  [ref-img-2]  [text-prompt]
Layer 1 (generation):          [image-gen]
Layer 2 (post):                      [upscale]
Layer 3 (output):                         [final]
```

Posiciones calculadas:
- `x = layer_index * 320 + 40` (320px entre columnas)
- `y = position_in_layer * 180 + 60` (180px entre filas)
- Centrado verticalmente dentro de cada capa

### 4.6 Node Rendering

Cada nodo es un `<div>` con:
- **Header:** color de fondo según tipo, label del tipo, node.id
- **Body:** 
  - Si es REFERENCE_IMAGE: `<img>` tag con `image_url`, max-width 200px, border-radius
  - Si es TEXT_PROMPT: primeras 100 chars del prompt
  - Si es SEED: valor de seed
  - Si es generación: nombre del modelo + resolución
- **Footer:** estado (✅ completed, ⏳ running, ❌ failed, ○ pending)
- **Border:** 2px solid con color del tipo

### 4.7 Connection Rendering

Conexiones como `<path>` SVG con curvas de Bézier:

```html
<svg class="connections">
  <path d="M x1,y1 C cx1,cy1 cx2,cy2 x2,y2" 
        stroke="#4fc3f7" stroke-width="2" fill="none" />
</svg>
```

Puntos de conexión:
- **Salida:** centro-derecha del nodo origen
- **Entrada:** centro-izquierda del nodo destino

### 4.8 VRH Gate Integration

Cuando el workflow tiene nodos REFERENCE_IMAGE, el VRH Gate automáticamente 
detecta las referencias (vía `_count_references()` que ya busca `image_url` en configs).

El HTML canvas es perfecto para la **FASE 2 del VRH (Preview)**:
- Mostrar el canvas HTML con los nodos de referencia visibles
- El usuario ve exactamente qué imágenes se van a usar
- Confirmación → `gate.approve()` → ejecución

### 4.9 Delivery

El HTML se entrega como archivo vía `MEDIA:/path/to/canvas.html` o se 
sirve localmente. Self-contained: todos los estilos inline, imágenes 
cargadas desde URLs (no embebidas para mantener el HTML liviano).

---

## 5. VRH Integration Impact

### 5.1 Flujo VRH con Reference Nodes

```
Usuario manda 2 imágenes (layout + producto)
         ↓
FASE 1: VisualAnalyzer → StructuredSpec para cada imagen
         ↓
Se crea workflow con:
  - ref-layout (REFERENCE_IMAGE, image_url=layout.jpg)
  - ref-product (REFERENCE_IMAGE, image_url=product.jpg)
  - gen-final (IMAGE_GEN, prompt={{ref-layout}} + {{ref-product}})
         ↓
Canvas HTML se genera con thumbnails reales
         ↓
FASE 2: Preview → usuario ve el canvas con sus imágenes
         ↓
Usuario confirma → gate.approve()
         ↓
FASE 3: execute_workflow()
```

### 5.2 Cambios en VRHGate

Sin cambios necesarios. `_count_references()` ya detecta `image_url` en configs de nodos.  
Los nodos REFERENCE_IMAGE tienen `image_url` → son detectados automáticamente.

### 5.3 Cambios en la skill VRH

Agregar mención de que los nodos REFERENCE_IMAGE son la forma canónica de 
incluir referencias visuales en workflows. El canvas HTML reemplaza el 
preview textual para FASE 2.

---

## 6. Test Plan

### 6.1 Unit Tests (FASE 1)

| Test ID | Description |
|---------|-------------|
| REF-001 | REFERENCE_IMAGE node with valid image_url passes validation |
| REF-002 | REFERENCE_IMAGE node without image_url fails validation |
| REF-003 | REFERENCE_IMAGE is treated as pass-through (no provider call) |
| REF-004 | `{{ref_node}}` resolves to image_url in downstream node |
| REF-005 | Multiple REFERENCE_IMAGE nodes in one workflow |
| REF-006 | REFERENCE_IMAGE connected to IMAGE_GEN node |
| REF-007 | REFERENCE_IMAGE connected to IMG2IMG node |
| REF-008 | Canvas renders REFERENCE_IMAGE with 🖼️ emoji |

### 6.2 Unit Tests (FASE 2)

| Test ID | Description |
|---------|-------------|
| HTML-001 | render_canvas_html() returns valid HTML string |
| HTML-002 | HTML contains <img> tags for REFERENCE_IMAGE nodes |
| HTML-003 | HTML contains SVG connections for edges |
| HTML-004 | Canvas respects topological order in layout |
| HTML-005 | Node colors match NodeType |
| HTML-006 | State emojis render correctly |
| HTML-007 | Empty workflow renders without errors |
| HTML-008 | Workflow with only REFERENCE_IMAGE nodes renders |

### 6.3 Integration Tests

| Test ID | Description |
|---------|-------------|
| INT-001 | Full VRH flow with REFERENCE_IMAGE nodes + VRHGate |
| INT-002 | define_workflow() accepts reference_image type |
| INT-003 | execute_workflow() passes reference_image nodes through |

---

## 7. Implementation Order

### Step 1: FASE 1 Core (graph.py + executor.py + canvas.py)
- Agregar `NodeType.REFERENCE_IMAGE` al enum
- Agregar `REQUIRED_CONFIG` entry
- Agregar a `PASS_THROUGH_TYPES` en executor
- Agregar a `TYPE_LABEL` en canvas
- Actualizar `_config_summary()` para mostrar label/thumbnail info
- 8 tests unitarios

### Step 2: FASE 2 HTML Canvas (canvas_html.py)
- Implementar `render_canvas_html()` 
- Layout engine con topological sort
- Node rendering con colores por tipo
- SVG connection rendering
- Template HTML wrapper
- 8 tests unitarios

### Step 3: Integration + Skill Update
- Verificar VRHGate integración
- Actualizar `hermesfy-vrh-workflow.md` con referencias al canvas HTML
- 3 integration tests
- Full test suite run

---

## 8. Constraints & Non-Goals

### Constraints
- Backward compatible: `render_canvas()` y `render_minimal_canvas()` no se tocan
- El HTML canvas es self-contained (no requiere servidor)
- Las imágenes se cargan desde URLs (no se embeben en base64 para no inflar el HTML)
- El layout es automático (no manual como en ComfyUI)

### Non-Goals (fuera de esta SPEC)
- Canvas interactivo (drag & drop, editar conexiones) → FASE 3 futuro
- Editor visual completo → requeriría frontend React/Vue
- Undo/redo, zoom, pan → futuro
- Exportación a formato ComfyUI → futuro

---

## 9. Success Criteria

- [ ] `NodeType.REFERENCE_IMAGE` existe y funciona en el DAG engine
- [ ] Workflows con nodos de referencia se validan, ejecutan, y persisten
- [ ] Canvas HTML muestra thumbnails reales de las imágenes de referencia
- [ ] Conexiones SVG entre nodos son visualmente correctas
- [ ] VRH Gate integración funciona sin cambios
- [ ] 16+ tests unitarios nuevos pasan
- [ ] 375+ tests existentes siguen pasando
- [ ] Skill VRH actualizada
