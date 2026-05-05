---
name: hermesfy-moodboard-pinterest
description: >-
  Moodboard engine for Hermesfy — source images from Pinterest via Playwright,
  analyze with VRH, synthesize a unified MOOD_SPEC, and guide Fal.ai generation.
  Pinterest is accessible without login using Firefox + xvfb-run.
---

# Hermesfy Moodboard Engine (Pinterest Source)

## Key Discovery

**Pinterest is fully accessible via Playwright without login.** Using Firefox with
a persistent user data directory + `xvfb-run`, we can search Pinterest, scroll
for more results, and extract images at 736px resolution. No API key, no OAuth,
no Brave Image Search fallback needed.

## ⚠️ CRITICAL: Pinterest URL Resolution (Learned Empirically)

| URL Pattern | Status | Resolution |
|-------------|--------|------------|
| `.../originals/...` | **403 Forbidden** | ❌ No se puede acceder |
| `.../736x/...` | ✅ 200 OK | 736px ancho (máxima sin login) |
| `.../474x/...` | ✅ 200 OK | 474px ancho (fallback) |
| `.../236x/...` | ✅ 200 OK | 236px ancho (thumbnail) |

**REGLAS:**
- Las URLs de Pinterest tienen segmentos como `236x/`, `474x/`, `736x/`, NO `60x60/` ni `originals/`
- Para máxima resolución: convertir `/\d+x\d*?/` → `/736x/`
- `originals` siempre da 403 — NO USAR
- Ejemplo: `https://i.pinimg.com/236x/ab/cd/ef/...jpg` → `https://i.pinimg.com/736x/ab/cd/ef/...jpg`

## Multi-Dimensional Query Strategy

This is the critical insight — a generic search like "hotel" gives random results.
The moodboard engine generates **multiple queries across 4 dimensions**:

| Dimension | Purpose | Examples |
|-----------|---------|----------|
| **DOMINIO** | What the thing IS | "hotel lujo", "skincare cream", "perfume" |
| **FORMATO** | How it's presented | "advertising", "editorial", "commercial photography", "campaign" |
| **ESTILO** | The aesthetic | "premium", "minimalist", "boutique", "eco luxury" |
| **REFERENCIA** | The framing | "moodboard", "lookbook", "visual reference" |

The searcher generates 6-12 queries by combining these dimensions:

```
"luxury hotel advertising moodboard"
"hotel boutique editorial photography"  
"eco resort premium campaign"
"travel luxury lookbook"
```

### Template Sets by Intended Use

```python
SEARCH_TEMPLATES = {
    "ad_product": [        # default: ads/campaigns
        "{concept} advertising campaign",
        "{concept} commercial photography",
        "{concept} ad poster billboard",
        "{concept} product advertising",
    ],
    "editorial": [         # editorial/lookbook
        "{concept} editorial photography",
        "{concept} magazine lookbook",
        "{concept} fashion editorial vogue",
    ],
    "product_shot": [      # studio/product
        "{concept} product photography",
        "{concept} studio shot minimalist",
        "{concept} packshot photography",
    ],
    "mood_inspiration": [  # moodboard/inspo
        "{concept} moodboard aesthetic",
        "{concept} visual reference",
        "{concept} color palette campaign",
    ],
    "social_media": [      # Instagram/social
        "{concept} instagram post",
        "{concept} social media campaign",
        "{concept} feed aesthetic",
    ],
}
```

## Alt Text Scoring (Critical for Relevance)

Pinterest returns alt text with every image. Use it to **score relevance**:

```python
POSITIVE = {
    # Domain keywords (high weight)
    "hotel": 10, "luxury": 8, "boutique": 8, "resort": 6,
    # Format keywords (very important - signals intent)
    "advertising": 8, "campaign": 8, "editorial": 6,
    "instagram": 10, "social media": 10, "post": 8, "feed": 6,
    # Style keywords
    "premium": 7, "elegant": 5, "modern": 4, "minimalist": 4,
    # Context/location
    "argentina": 10, "salta": 12,
}

NEGATIVE = {
    "food": 8, "recipe": 10, "diy": 10, "tutorial": 10,  # irrelevant content
    "cat": 8, "dog": 8, "animal": 8, "wedding": 6,        # wrong category
    "fashion": 4, "outfit": 5, "makeup": 6,                # cosmetics (unless concept matches)
}
```

### ⚠️ DIVERSITY FILTER (Essential!)

**Problem detected in pilot:** Same alt text = same pinner account. Without filtering,
you get 9/12 images from the same source.

**Solution:** Group images by normalized alt text. Only keep 1-2 per group:

```python
def deduplicate_by_alt(candidates, max_per_group=2):
    groups = {}
    for img in candidates:
        key = (img['alt'][:60] or '')  # same alt prefix = same pinner
        groups.setdefault(key, []).append(img)
    result = []
    for key, group in groups.items():
        result.extend(group[:max_per_group])
    return result
```

## Critical Workflow Discovery: Board Curation > Auto-Search

**The most important finding from the pilot:** Having the user create their own Pinterest
board and pass the link is **strictly better** than auto-search. Here's why:

| Approach | Control | Noise | Result |
|----------|---------|-------|--------|
| Auto-search (queries) | ⭐⭐ | High | Mixed relevance |
| **User-curated board** | **⭐⭐⭐⭐⭐** | **None** | **Exactly what user wants** |

The user curates 10-20 pins they like → passes the link → we scrape the board →
analyze → synthesize → apply brand guidelines. Zero noise, zero guesswork.

### Board Scraping (Verified)

```python
# pin.it shortlinks resolve to full board URLs
# Example: https://pin.it/6tbRV9DTE → 
#   https://www.pinterest.com/username/board-name/?invite_code=...&sender=...

with sync_playwright() as p:
    context = p.firefox.launch_persistent_context(
        user_data_dir=profile_dir, headless=False, viewport={"width": 1280, "height": 900}
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(board_url, wait_until="domcontentloaded", timeout=25000)
    page.wait_for_timeout(5000)
    for _ in range(4):  # scroll for more pins
        page.evaluate("window.scrollBy(0, 900)")
        page.wait_for_timeout(1000)
    # Extract pins same as search (selector works for boards too)
    pins = page.evaluate("""... (same as search extraction) ...""")
```

**Board access tested:** 19 pins extracted from a public user-created board.
Accessible without login if the board is public.

## Full Pipeline (Two Entry Points)

### Entry 1: User passes a board link (PREFERRED)
```
User: "moodboard: acá está mi board https://pin.it/XXXXX
       para el Provincial Plaza, aplicá la marca"
            │
            ▼
    ┌──────────────────┐
    │  PinterestScraper  │  ← scrapes the board URL
    │  (pinterest.py)    │     pin.it shortlink → full board
    │                    │     scroll 4x, 736x conversion
    └────────┬──────────┘
             │ 15-20 imágenes del board
             ▼
    [rest of pipeline: Curator → VRH → Synthesizer → Brand Merger → SpecBridge → Fal.ai]
```

### Entry 2: Auto-search by concept (when no board)
```
User: "moodboard: hotel lujo selva"
            │
            ▼
    ┌─────────────────┐
    │  Searcher        │  ← genera queries por template
    │  (searcher.py)   │     + scoring + diversidad
    └────────┬────────┘
             │ 4-6 queries
             ▼
    ┌───────────────────┐
    │  PinterestScraper  │  ← Playwright Firefox + xvfb
    └────────┬──────────┘
             │ 50+ imágenes a 736px
             ▼
    [rest of pipeline]
```

### Full Pipeline (shared downstream)

```
    ┌─────────────────┐
    │  Curator         │  ← 1. score por alt text
    │  (curator.py)    │     2. filtrar negativos
    │                   │     3. dedup por alt text
    │                   │     4. hash perceptual
    │                   │     5. top 15 diversas
    └────────┬────────┘
             │ 12-15 imágenes curadas
             ▼
    ┌─────────────────┐     ┌──────────────────────┐
    │  Visual Analyzer │ ──→ │ N × StructuredSpec   │
    │  (VRH)           │     │ (1 por imagen)       │
    └────────┬────────┘     └──────────────────────┘
             │ specs[]
             ▼
    ┌──────────────────┐
    │  Mood Synthesizer │  ← paleta: moda de colores
    │  (synthesizer.py) │  ← mood: mayoría
    │                   │  ← iluminación: consenso
    │                   │  ← composición: frecuencia
    └────────┬─────────┘
             │ mood_spec.json
             ▼
    ┌──────────────────┐
    │  Brand Merger     │  ← MOOD_SPEC + DESIGN.md
    │  (brand_merge.py) │  ← Marca gana en colores/tipografía
    │                   │  ← Referencia gana en composición/luz
    │                   │  ← Fusión: mood + elementos
    └────────┬─────────┘
             │ mood_spec_final.json
             ▼
    ┌────────────────┐
    │  SpecBridge +   │  ← MOOD_SPEC → prompt
    │  Goldilocks     │  + fidelity dinámico
    └────────┬───────┘
             │ prompt
             ▼
    ┌────────────────┐
    │  Fal.ai         │  ← genera imagen final
    │  (DAG)          │
    └────────────────┘
```

## Storage

```
~/.hermesfy/moodboard/<session-id>/
├── images/              ← imágenes descargadas en 736px
├── specs/               ← StructuredSpec por imagen
├── mood_spec.json       ← spec sintetizado final
├── mood_spec.preview.md ← preview legible
└── metadata.json        ← queries usadas + scores + fuentes
```

## Playwright Implementation (Verified Working)

```python
from playwright.sync_api import sync_playwright
from urllib.parse import quote
import re

def to_736x(url: str) -> str:
    """Convert Pinterest URL to highest accessible resolution."""
    return re.sub(r'/\d+x\d*?/', '/736x/', url)

profile_dir = "/home/hermes/.cache/pinterest-profile"

with sync_playwright() as p:
    context = p.firefox.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=False,       # xvfb-run maneja el display
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:128.0)"
    )
    page = context.pages[0] if context.pages else context.new_page()
    
    page.goto(f"https://www.pinterest.com/search/pins/?q={quote(query)}",
              wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)
    
    # Scroll for more results
    for _ in range(4):
        page.evaluate("window.scrollBy(0, 900)")
        page.wait_for_timeout(1200)
    
    # Extract images (no regex, URL.split approach is stable)
    results = page.evaluate("""() => {
        const imgs = document.querySelectorAll('img[src*="pinimg"]');
        const out = [];
        for (const img of imgs) {
            let s = img.src || '';
            if (!s.includes('pinimg')) continue;
            const parts = s.split('/');
            for (let i = 0; i < parts.length; i++) {
                if (/^\\d+x\\d*$/.test(parts[i])) {  // match 236x, 736x, etc
                    parts[i] = '736x';
                    break;
                }
            }
            s = parts.join('/');
            if (!out.find(x => x.url === s)) {
                out.push({ url: s, alt: img.alt || '' });
            }
        }
        return out;
    }""")
```

**Always run with:** `xvfb-run python3 script.py`

## MOOD_SPEC Output

```json
{
  "palette": ["#HEX1", "#HEX2", ...],
  "mood_consensus": "serene|luxurious|dramatic|...",
  "lighting_majority": {"type": "...", "direction": "..."},
  "composition_mode": "rule-of-thirds|center|symmetry",
  "technique": "editorial|product-photo|campaign",
  "sources_count": 12,
  "confidence": 0.85
}
```

## Pilot Results Summary

| Metric | Value |
|--------|-------|
| Queries | 5 (hotel themed) |
| Candidates | 70 (scored > 0) |
| Diverse downloads | 10 |
| Max resolution | 736px |
| Avg size | ~109 KB |
| Time | ~2 min for 5 queries |

## Common Pitfalls

1. **DO NOT try `originals/` URL** — returns 403. Use `736x/` instead.
2. **DO NOT use regex in JS evaluate** — backslash escaping causes `invalid regular expression flag o` errors. Use string split/join approach.
3. **DO filter for diversity** — same alt text = same Pinterest account. Dedup by first 60 chars of alt text.
4. **DO use negative keyword filter** — Pinterest returns lots of wedding, food, fashion content that's not relevant.
5. **DO scroll 3-4 times** — only ~8 results visible without scrolling.
