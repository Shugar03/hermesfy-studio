# SDD — Hermesfy Moodboard Engine

**Version:** 0.2 (DRAFT — post-pilot validation)
**Author:** Hermes Agent (Sherman)
**Date:** 2026-05-05
**Status:** Draft ready for implementation

---

## 1. Purpose

Sistema que permite al usuario construir un **moodboard visual estructurado** a partir de referencias curadas (Pinterest, imágenes subidas, boards propios) y convertirlo en un **MOOD_SPEC** que guíe la generación de imágenes manteniendo coherencia estética + manual de marca.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                               │
│  "moodboard: hotel luxury jungle"  │  Board link   │  Uploads   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    ORCHESTRATOR (moodboard.py)                   │
│  Orquesta el pipeline completo: search → curate → analyze →     │
│  synthesize → merge_with_brand → output                        │
└──────┬──────────────┬────────────────┬──────────────┬──────────┘
       │              │                │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐ ┌─────▼──────────┐
│  SEARCHER   │ │  CURATOR   │ │SYNTHESIZER  │ │  BRAND MERGER  │
│ (searcher.py)│ │(curator.py)│ │(synthesizer │ │ (brand_merge.py)│
│             │ │            │ │ .py)        │ │                │
│ • Pinterest │ │ • Download │ │ • N→1 spec  │ │ • Carga DESIGN │
│   via PW    │ │ • Hash     │ │ • Paleta    │ │   .md          │
│ • Brave fb  │ │ • Score    │ │   promedio  │ │ • Fusiona specs│
│ • Queries   │ │ • Filter   │ │ • Mood mode │ │ • Marca gana   │
│   multidim  │ │ • Diversity│ │ • Consensus │ │   en colores   │
└─────────────┘ └────────────┘ └─────────────┘ └────────────────┘
                           │
                    ┌──────▼──────┐
                    │  FILESYSTEM │
                    │  ~/.hermesfy│
                    │  /moodboard/│
                    │  <session>/ │
                    └─────────────┘
```

---

## 3. Module Structure

```
src/hermesfy/moodboard/
├── __init__.py
├── searcher.py        # Búsqueda multiplataforma (Pinterest + fallback)
├── curator.py         # Descarga, scoring, filtrado, dedup
├── synthesizer.py     # N StructuredSpec → 1 MOOD_SPEC
├── brand_merge.py     # MOOD_SPEC + DESIGN.md → MOOD_SPEC final
├── orchestrator.py    # Pipeline completo unificado
└── templates/
    ├── search_templates.yaml  # Queries predefinidas por categoría
    └── brand_schema.yaml      # Schema del DESIGN.md
```

---

## 4. Componentes

### 4.1 Searcher (searcher.py)

**Input:** Concept keywords + opciones (formato, estilo, fuente)
**Output:** Lista de URLs de imágenes con alt text

#### Estrategia de búsqueda multidimensional

Genera queries combinando dimensiones:

| Dimensión | Valores | Ejemplo |
|-----------|---------|---------|
| **Concepto** | Lo que pide el usuario | hotel, perfume, auto |
| **Formato** | advertising, editorial, social, product | ad, campaign, post |
| **Estilo** | luxury, minimalist, vintage, gothic | premium, retro |
| **Plataforma** | instagram, pinterest, billboard | feed, story, poster |

```python
# Templates base por categoría
SEARCH_TEMPLATES = {
    "default": [  # Si no se especifica formato
        "{concept} advertising campaign",
        "{concept} editorial photography",
        "{concept} social media post",
        "{concept} moodboard visual reference",
    ],
    "advertising": [
        "{concept} advertising campaign",
        "{concept} commercial photography",
        "{concept} ad poster billboard",
    ],
    "editorial": [
        "{concept} editorial photography",
        "{concept} magazine lookbook",
        "{concept} fashion editorial",
    ],
    "social_media": [
        "{concept} instagram post design",
        "{concept} social media feed",
        "{concept} social media campaign aesthetic",
    ],
    "product": [
        "{concept} product photography",
        "{concept} product advertising commercial",
        "{concept} packshot studio",
    ],
}
```

#### Fuentes

1. **Pinterest (primary)** — Playwright headless + xvfb-run
   - Scrollea y extrae imágenes en 736px
   - Sin login para búsqueda pública
   - Acceso a boards públicos por URL
2. **Brave Image Search (fallback)** — API REST
   - Si Pinterest falla o está caído
   - Devuelve thumbnails directos

#### Scoring por alt text

```python
def score_image(alt_text: str, concept_keywords: list[str]) -> int:
    """Puntúa relevancia de imagen por su alt text."""
    score = 0
    text = alt_text.lower()
    # Palabras de formato (advertising, campaign, editorial)
    for w in FORMAT_KEYWORDS: score += 5 if w in text else 0
    # Palabras del concepto (hotel, luxury, perfume)
    for w in concept_keywords: score += 3 if w in text else 0
    # Penalizar genéricos
    if len(text) < 15: score -= 5
    # Bloquear negativos (food, diy, recipe)
    for w in NEGATIVE_KEYWORDS: return -10 if w in text else score
    return score
```

---

### 4.2 Curator (curator.py)

**Input:** Lista de URLs candidatas
**Output:** N imágenes descargadas, filtradas y listas para VRH

| Etapa | Método | Umbral |
|-------|--------|--------|
| **Descarga** | requests con headers Pinterest | Timeout 15s |
| **Resolución** | Mínimo 500px en un eje | <500px descartado |
| **Deduplicación** | Perceptual hash (pHash) | Hamming < 10 = duplicado |
| **Diversidad** | Máximo 3 del mismo alt text | Agrupar por pinner |
| **Score** | Ordenar por score descendente | Top N (default 15) |
| **Formato** | Preferir vertical (9:16 / 4:5) | Para Instagram |

---

### 4.3 Synthesizer (synthesizer.py)

**Input:** N estructuras StructuredSpec (del VRH)
**Output:** 1 MOOD_SPEC unificado

#### MOOD_SPEC Schema

```python
@dataclass
class MoodSpec:
    session_id: str
    source: str  # "pinterest_board" | "search" | "uploads"
    source_url: str | None  # Pinterest board link si aplica
    
    # Síntesis
    dominant_palette: list[str]  # Top 6 HEX más repetidos entre todas las specs
    mood_majority: str           # Mood que aparece en >50% de las imágenes
    mood_votes: dict[str, int]   # Todos los moods detectados con conteo
    lighting_consensus: str      # Tipo de luz + dirección más común
    composition_mode: str        # Regla de composición más frecuente
    technique_majority: str      # Técnica/estética mayoritaria
    texture_trend: str           # Textura más repetida
    
    # Estadísticas
    total_images_analyzed: int
    images_used: int             # Después de filtros
    confidence: float            # 0.0-1.0 qué tan homogéneo es el set
```

#### Algoritmo de síntesis

Para cada campo:
- **Colores:** Agrupar HSV, cluster por cercanía, seleccionar top 6 del cluster principal
- **Mood:** Votación simple (moda). Si hay empate → el más específico gana
- **Iluminación:** Votación ponderada por confianza de cada VRH
- **Composición:** Moda simple
- **Confianza:** Ratio imágenes mayoritarias / total. >0.7 = set homogéneo

---

### 4.4 Brand Merger (brand_merge.py)

**Input:** MOOD_SPEC + DESIGN.md (archivo YAML/markdown con identidad de marca)
**Output:** MOOD_SPEC final con brand constraints aplicados

#### Reglas de fusión

| Campo | Prioridad | Regla |
|-------|-----------|-------|
| **Paleta** | 🔴 Marca | Los colores de la marca REEMPLAZAN a los de la paleta del mood |
| **Mood** | 🟡 Igual | Se mantiene el mood mayoritario (si compatible con marca) |
| **Iluminación** | 🟡 Igual | Se mantiene de la referencia |
| **Composición** | 🟢 Referencia | Se mantiene de la referencia |
| **Tipografía** | 🔴 Marca | Tipografía de la marca siempre |
| **Elementos** | 🟢 Fusión | Elementos locales de marca + composición de referencia |

#### DESIGN.md Schema

```yaml
# ~/.hermesfy/brands/provincial-plaza/design.md
brand: Provincial Plaza Hotel
colors:
  primary: "#8B7355"       # Dorado/beige
  secondary: "#2F4F4F"     # Verde oscuro
  accent: "#D4AF37"        # Dorado brillante
  background: "#F5F0E8"    # Crema
typography:
  headings: Cormorant Garamond
  body: Montserrat
  sizes: {h1: 48, h2: 32, body: 16}
tone: "Elegante, cálido, regional salteño"
elements:
  - Arquitectura colonial
  - Paisajes de Salta
  - Detalles artesanales locales
formats:
  - instagram_post: "4:5"
  - story: "9:16"
  - feed: "1:1"
```

---

## 5. Pipeline completo

```
Tú: "moodboard: provincial plaza instagram post
      con vibra del board que te pasé"

┌─────────────────────────────────────────────────────────────────┐
│ 1. ORCHESTRATOR recibe:                                        │
│    • board_url = "https://pin.it/6tbRV9DTE"                    │
│    • concept = "provincial plaza hotel"                        │
│    • format = "social_media"                                   │
│    • brand = "provincial-plaza"                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ 2. SEARCHER: Scrapea el board → 19 imágenes con alt text       │
│    • Opcional: si no hay board, genera queries + Pinterest      │
│    • Retorna: 19 URLs con metadata                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ 3. CURATOR: Descarga, filtra, puntúa                           │
│    • Dedup perceptual → elimina duplicados                     │
│    • Score por alt text                                        │
│    • Filtro diversidad (máx 3 por pinner)                      │
│    • Retorna: top 15 imágenes descargadas                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ 4. VRH (existing): Analiza cada imagen → 15 StructuredSpecs     │
│    • Cada spec: palette, mood, lighting, composition, technique │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ 5. SYNTHESIZER: 15 specs → 1 MOOD_SPEC                         │
│    • Paleta: top 6 HEX más repetidos                            │
│    • Mood: modo mayoritario                                     │
│    • Iluminación: consenso                                      │
│    • Composición: regla más frecuente                           │
│    • Confianza: 0.72 (qué tan homogéneo es)                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ 6. BRAND MERGER: MOOD_SPEC + DESIGN.md → MOOD_SPEC FINAL       │
│    • Colors: #8B7355, #2F4F4F, #D4AF37 (marca gana)            │
│    • Mood: "elegante premium" (de referencia, compatible)       │
│    • Lighting: "golden hour cálido" (de referencia)             │
│    • Typography: Cormorant + Montserrat (marca gana)            │
│    • Tone: "Elegante, cálido, regional salteño" (marca gana)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ 7. OUTPUT:                                                     │
│    • mood_spec.json (final, brand-aware)                        │
│    • mood_spec.preview.md (legible para usuario)                │
│    • Almacenado en ~/.hermesfy/moodboard/<session>/            │
│    • Listo para SpecBridge + generación                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Tool Interface

### `hermesfy_moodboard` — Esquema

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "search",           // Buscar imágenes por concepto
        "board",            // Scrapear board de Pinterest
        "analyze",          // Analizar imágenes ya descargadas
        "synthesize",       // N imágenes analizadas → MOOD_SPEC
        "merge_brand",      // MOOD_SPEC + brand → final
        "run",              // Pipeline completo: concept→final
        "use"               // Reusar sesión anterior
      ]
    },
    "concept": {
      "type": "string",
      "description": "Concepto para moodboard: 'hotel lujo selva'"
    },
    "source": {
      "type": "string",
      "enum": ["pinterest_search", "pinterest_board", "uploads", "brave"],
      "default": "pinterest_board"
    },
    "source_url": {
      "type": "string",
      "description": "URL del board de Pinterest (si source='pinterest_board')"
    },
    "brand": {
      "type": "string",
      "description": "Nombre de brand config: 'provincial-plaza'"
    },
    "format": {
      "type": "string",
      "enum": ["advertising", "editorial", "social_media", "product", "default"],
      "default": "default"
    },
    "session_id": {
      "type": "string",
      "description": "Para reusar sesión existente"
    }
  },
  "required": ["action"]
}
```

---

## 7. Storage — SQLite Database

### Schema

```sql
CREATE TABLE moodboards (
    id          TEXT PRIMARY KEY,           -- "mb_a1b2c3d4"
    created_at  TEXT NOT NULL,              -- ISO 8601
    updated_at  TEXT,
    
    -- Origen
    concept     TEXT NOT NULL,              -- "hotel luxury jungle"
    source      TEXT NOT NULL,              -- "pinterest_board" | "pinterest_search" | "uploads"
    source_url  TEXT,                       -- Board link si aplica
    
    -- Config
    format      TEXT DEFAULT 'default',     -- advertising, editorial, social_media
    brand       TEXT,                       -- "provincial-plaza" (opcional)
    
    -- Estado del pipeline
    status      TEXT DEFAULT 'created',     -- created | searching | analyzing | synthesized | merged | error
    error_msg   TEXT,
    
    -- Outputs (rutas + JSON serializado)
    image_count     INTEGER DEFAULT 0,
    images_path     TEXT,                   -- ~/.hermesfy/moodboard/mb_a1b2/images/
    source_data     TEXT,                   -- JSON: metadata de búsqueda (queries, scores)
    mood_spec       TEXT,                   -- JSON: MOOD_SPEC final
    mood_spec_md    TEXT,                   -- Preview markdown
    
    -- Tags para búsqueda
    tags            TEXT,                   -- CSV: "hotel, lujo, selva, instagram"
    
    -- Reusabilidad
    used_in_generations INTEGER DEFAULT 0,  -- Cuántas veces se usó
    last_used_at    TEXT
);

CREATE INDEX idx_moodboards_concept ON moodboards(concept);
CREATE INDEX idx_moodboards_brand ON moodboards(brand);
CREATE INDEX idx_moodboards_created ON moodboards(created_at);
```

### Filesystem (imágenes + assets)

```
~/.hermesfy/moodboard/
├── moodboards.db              ← SQLite
├── mb_a1b2c3d4/               ← Carpeta por moodboard
│   ├── images/                ← Imágenes descargadas
│   │   ├── 01_concept.jpg
│   │   ├── 02_concept.jpg
│   │   └── ...
│   └── analysis/              ← Specs individuales VRH
│       ├── 01_spec.json
│       └── ...
├── mb_e5f6g7h8/               ← Otro moodboard
│   └── ...
└── brands/
    └── provincial-plaza/
        └── design.md
```

### Cómo se usa

```python
# Crear
mb_id = db.create_moodboard(
    concept="hotel luxury jungle",
    source="pinterest_board",
    source_url="https://pin.it/6tbRV9DTE",
    tags="hotel, lujo, selva, instagram"
)
# → "mb_a1b2c3d4"

# Listar
db.list_moodboards(limit=10)
# → [mb_a1b2, mb_e5f6, ...]

# Buscar por concepto
db.search_moodboards("hotel lujo")
# → [mb_a1b2, ...]

# Recuperar
mb = db.get_moodboard("mb_a1b2c3d4")
# → Moodboard(id=..., concept=..., mood_spec={...})

# Reciclar: generar NUEVO concepto con MISMA estética
# "tomá el moodboard mb_a1b2 y generá un post de auto"
mb = db.get_moodboard("mb_a1b2")
spec = mb.mood_spec  # → MOOD_SPEC reutilizable
nuevo_output = orchestrator.regenerate(
    moodboard_id="mb_a1b2",
    new_concept="auto deportivo"
)
# Mantiene paleta, mood, iluminación; cambia sujeto

# Estadísticas
db.get_stats()
# → {"total": 12, "brands": 3, "avg_images": 14.2}
```

### IDs

Formato: `mb_` + shortid (8 chars hex) → `mb_a1b2c3d4`

- Legibles, copiables, únicos
- Se muestran en previews del moodboard
- Se referencian en comandos: `moodboard use mb_a1b2`

---

## 8. Dependencies

| Dependencia | Uso |
|------------|-----|
| `playwright` | Scraping Pinterest (ya instalado) |
| `xvfb-run` | Headless browser (ya instalado) |
| `requests` | Download imágenes (ya instalado) |
| `PIL / Pillow` | Perceptual hashing (verificar) |
| `imagehash` | pHash para dedup (instalar si falta) |

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Pinterest cambia estructura HTML | Selectores resilientes (img[src*="pinimg"]) + fallback a Brave |
| Pinterest bloquea headless | xvfb-run + user-agent realista + perfil persistente |
| Board privado requiere login | Mensaje claro: "este board es privado, hacelo público o subí las imágenes" |
| VRH tarda 15 análisis | Paralelizar con delegate_task |
| DESIGN.md no existe para la marca | Usar defaults genéricos + pedir que lo cree |
| pHash en imágenes pequeñas | Fallback a hash de URL |
| Sesión expira | Eliminar sesiones viejas automáticamente (>30 días) |

---

## 10. Hitos de implementación

| # | Hito | Depende de |
|---|------|-----------|
| 1 | Searcher + Curator (Pinterest + scoring) | — |
| 2 | Synthesizer (N→1 MOOD_SPEC) | VRH module |
| 3 | Brand Merger (MOOD_SPEC + DESIGN.md) | 2 |
| 4 | Orchestrator (pipeline completo) | 1, 2, 3 |
| 5 | Tool registration + Skill | 4 |
| 6 | Test end-to-end con board real | 5 |
| 7 | DESIGN.md de Provincial Plaza | 6 |

---

## 11. Criterios de éxito

- [ ] Pipeline completo corre sin errores
- [ ] MOOD_SPEC generado es coherente con las referencias del board
- [ ] Brand merger aplica colores de marca correctamente
- [ ] Se puede reusar sesión: `moodboard use <session>`
- [ ] Skill `hermesfy-moodboard` cargable via `skill_view`
- [ ] Parity repo (skill en repo + symlink en sistema)
