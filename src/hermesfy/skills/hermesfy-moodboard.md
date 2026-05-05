---
name: hermesfy-moodboard
description: "Moodboard Engine: busca referencias visuales (Pinterest/boards), las analiza con VRH, sintetiza un MOOD_SPEC unificado y lo fusiona con el manual de marca. Pipeline completo con persistencia SQLite + IDs reusables."
tags: [moodboard, pinterest, vrh, brand, design-system, sqLite]
---

# Hermesfy Moodboard Engine

Crea moodboards visuales estructurados a partir de referencias curadas y los convierte en un MOOD_SPEC que guía la generación de imágenes con coherencia estética + manual de marca.

## Cuándo usarlo

- El usuario pide inspiración visual para un concepto ("moodboard: hotel lujo selva")
- El usuario pasa un board de Pinterest como referencia
- El usuario quiere reusar la estética de un moodboard anterior
- El usuario tiene un manual de marca (DESIGN.md) y quiere mantener coherencia

## Tool: `hermesfy_moodboard`

### Acciones principales

| Acción | Descripción |
|--------|-------------|
| `run` | Pipeline completo: buscar + curar + analizar + sintetizar + merge |
| `board` | Scrapear board de Pinterest + pipeline completo |
| `search` | Solo buscar imágenes (sin análisis) |
| `list` | Listar moodboards guardados |
| `get` | Ver moodboard por ID (ej: `mb_a1b2c3d4`) |
| `stats` | Estadísticas del sistema |
| `use` | Reusar moodboard existente con nuevo concepto |

### Parámetros

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `action` | string | Requerido: run, board, search, list, get, stats, use |
| `concept` | string | "hotel lujo selva" |
| `format` | enum | default, advertising, editorial, social_media, product, hospitality, fashion |
| `source` | enum | pinterest_search (default), pinterest_board, brave |
| `source_url` | string | Link del board de Pinterest |
| `brand` | string | Nombre de marca: "provincial-plaza" |
| `moodboard_id` | string | ID para get/use |
| `new_concept` | string | Nuevo concepto para reciclar moodboard |

### Ejemplos

```
hermesfy_moodboard action=run concept="hotel lujo selva"
hermesfy_moodboard action=board source_url="https://pin.it/xxx" concept="referencias hotel"
hermesfy_moodboard action=run concept="provincial plaza" brand=provincial-plaza format=social_media
hermesfy_moodboard action=list
hermesfy_moodboard action=get moodboard_id=mb_a1b2c3d4
hermesfy_moodboard action=use moodboard_id=mb_a1b2 new_concept="auto deportivo"
hermesfy_moodboard action=stats
```

## Pipeline: search → curate → VRH → synthesize → brand_merge

```
1. SEARCHER: Pinterest queries multidimensionales o board scraping
2. CURATOR: Download, pHash dedup, score por alt text, diversidad
3. VRH (existing): Analiza cada imagen → StructuredSpec
4. SYNTHESIZER: N specs → 1 MOOD_SPEC (paleta, mood, luz, composición)
5. BRAND MERGER: MOOD_SPEC + ~/.hermesfy/brands/<name>/design.md
```

## Estrategia de búsqueda

NO buscar términos genéricos. Usar queries multidimensionales:
- **Dominio**: hotel, perfume, auto (lo que pide el usuario)
- **Formato**: advertising, editorial, social media, product (cómo se ve)
- **Estilo**: luxury, minimalist, vintage, gothic (la estética)
- **Referencia**: moodboard, campaign, lookbook (intención de búsqueda)

Ejemplo: no "perfume" sino "perfume advertising campaign luxury editorial".

## Scoring por alt text (validado en pilot)

El alt text de Pinterest contiene descripciones reales. Se puntúa:
- +5 por palabras de formato (advertising, campaign, commercial)
- +3 por palabras del concepto (hotel, luxury, resort)
- +3 por palabras de estilo (luxury, minimalist, elegant)
- -5 si la descripción es genérica (< 15 chars)
- -10 si contiene palabras negativas (food, recipe, diy, tutorial, cat, wedding)

## Filtro de diversidad (lección del pilot)

SIN diversity filter: 9/12 imágenes del mismo pinner ("@lepetit_hotel_").
SOLUCIÓN: agrupar por primeros 30 chars del alt text, máximo 3 por grupo.

## Brand merge

La marca SIEMPRE gana en:
- **Colores** → reemplazan la paleta del mood
- **Tipografía** → reemplaza cualquier font de la referencia
- **Tono** → se inyecta en el spec

La referencia mantiene:
- **Composición** → layout, regla visual
- **Iluminación** → dirección, tipo de luz
- **Mood** → atmósfera (si compatible con marca)

## Persistencia

- **SQLite:** `~/.hermesfy/moodboard/moodboards.db`
- **IDs:** `mb_a1b2c3d4` — únicos, referenciables, reusables
- **Imágenes:** `~/.hermesfy/moodboard/images/<mb_id>/`
- **Marcas:** `~/.hermesfy/brands/<brand>/design.md`

## DESIGN.md — Manual de marca

```yaml
brand: Provincial Plaza Hotel
colors:
  primary: "#8B7355"       # Dorado/beige
  secondary: "#2F4F4F"     # Verde oscuro
  accent: "#D4AF37"        # Dorado brillante
  background: "#F5F0E8"    # Crema
typography:
  headings: Cormorant Garamond
  body: Montserrat
tone: "Elegante, cálido, regional salteño"
elements:
  - Arquitectura colonial
  - Paisajes de Salta
formats:
  instagram_post: "4:5"
  story: "9:16"
```

## Pitfalls

- **Diversity**: sin filtrar, un solo pinner puede dominar el moodboard
- **Alt text**: a veces el alt text no describe la imagen (falla el scoring). El VRH lo compensa.
- **Board privado**: si el board es secreto, Pinterest redirige al login. Hacerlo público o subir imágenes directo.
- **VRH no disponible**: sin Vision LLM, el synthesizer usa defaults. El MoodSpec sigue siendo válido pero menos rico.
- **originals/ 403**: Pinterest bloquea `i.pinimg.com/originals/`. Siempre usar `736x/`.

## Archivos del módulo

| Archivo | Propósito |
|---------|-----------|
| `moodboard/searcher.py` | Pinterest scraper (Playwright) + query templates |
| `moodboard/curator.py` | Descarga, scoring, dedup, diversidad |
| `moodboard/synthesizer.py` | N specs → 1 MoodSpec |
| `moodboard/brand_merge.py` | Fusión con DESIGN.md |
| `moodboard/orchestrator.py` | Pipeline completo |
| `moodboard/database.py` | SQLite persistence |
| `moodboard/tool.py` | Tool handler |
| `moodboard/templates/search_templates.py` | 7 categorías de queries |
