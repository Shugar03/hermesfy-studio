#!/usr/bin/env python3
"""Test end-to-end del moodboard con el board de Sherman."""
import json, sys, os
sys.path.insert(0, "/opt/hermesfy-studio/src")

from hermesfy.moodboard.database import MoodboardDB
from hermesfy.moodboard.searcher import search_moodboard_sources
from hermesfy.moodboard.curator import curate_images
from hermesfy.moodboard.synthesizer import Synthesizer
from hermesfy.moodboard.brand_merge import merge_with_brand, load_design_md

BOARD_URL = "https://pin.it/6tbRV9DTE"
OUTPUT_DIR = "/home/hermes/.hermesfy/moodboard/images/mb_test_e2e"
CONCEPT = "provincial plaza hotel publicidad"

print("=" * 60)
print("🧪 TEST E2E: Moodboard Pipeline")
print("=" * 60)

# 1. SEARCHER: scrap board
print("\n[1/5] Scraping board...")
candidates = search_moodboard_sources(
    concept=CONCEPT,
    source="pinterest_board",
    source_url=BOARD_URL,
    max_images=30,
)
print(f"  → {len(candidates)} candidatos")
if candidates:
    print(f"  Top: [{candidates[0]['score']}] {candidates[0]['alt'][:60]}")

# 2. CURATOR: download + filter
print("\n[2/5] Curating images...")
curated = curate_images(
    candidates=candidates,
    output_dir=OUTPUT_DIR,
    concept=CONCEPT,
    max_images=12,
)
print(f"  → {len(curated)} imágenes curadas")
for c in curated:
    print(f"    ✓ {c['fname']} — {c['size_kb']}KB ({c.get('width',0)}x{c.get('height',0)}) score={c.get('score',0)}")

# 3. SYNTHESIZER (mock specs since no VRH)
print("\n[3/5] Synthesizing mood spec...")
synth = Synthesizer()
# Mock specs basadas en scores de alt text
mock_specs = []
for c in curated:
    score = c.get("score", 0)
    mock_specs.append({
        "palette": {"colors": ["#8B7355", "#2F4F4F", "#D4AF37"]},
        "composition": {"mood": "premium" if score > 15 else "elegant", "rule": "center"},
        "lighting": {"direction": "golden hour", "type": "warm"},
        "semantic": {"technique": "editorial photography"},
    })

mood_spec = synth.synthesize(mock_specs, session_id="mb_test_e2e", concept=CONCEPT)
print(f"  → MoodSpec generado:")
print(f"    Paleta: {' '.join(mood_spec.dominant_palette)}")
print(f"    Mood: {mood_spec.mood_majority}")
print(f"    Luz: {mood_spec.lighting_consensus}")
print(f"    Composición: {mood_spec.composition_mode}")
print(f"    Técnica: {mood_spec.technique_majority}")
print(f"    Confianza: {mood_spec.confidence:.0%}")

# 4. BRAND MERGER
print("\n[4/5] Testing brand merge (creando brand demo)...")
brand_dir = os.path.expanduser("~/.hermesfy/brands/provincial-plaza")
os.makedirs(brand_dir, exist_ok=True)
brand_yaml = """brand: Provincial Plaza Hotel
colors:
  primary: '#8B7355'
  secondary: '#2F4F4F'
  accent: '#D4AF37'
  background: '#F5F0E8'
typography:
  headings: Cormorant Garamond
  body: Montserrat
tone: 'Elegante, cálido, regional salteño'
elements:
  - Arquitectura colonial salteña
  - Paisajes de los Valles Calchaquíes
formats:
  instagram_post: '4:5'
  story: '9:16'
"""
with open(f"{brand_dir}/design.yaml", "w") as f:
    f.write(brand_yaml)

merged = merge_with_brand(mood_spec.to_dict(), "provincial-plaza")
print(f"  → Brand '{merged.get('brand_name', '—')}' applied: {merged.get('brand_applied')}")
print(f"    Palette (brand): {' '.join(merged.get('dominant_palette', []))}")
print(f"    Brand tone: {merged.get('brand_tone', '—')}")
print(f"    Brand elements: {merged.get('brand_elements', [])}")

# 5. Preview
print("\n[5/5] Preview:")
print(mood_spec.to_preview_md())

print("\n" + "=" * 60)
print("✅ E2E TEST COMPLETED")
print(f"   Imágenes: {OUTPUT_DIR}/")
print(f"   Brand: {brand_dir}/")
print("=" * 60)
