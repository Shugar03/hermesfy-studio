---
version: alpha
name: MAISON Apparel
description: Visual identity system for MAISON — avant-garde fashion brand. Editorial, architectural, monochromatic. Generated via Hermesfy Studio.
colors:
  bone: "#F2EDE8"
  stone: "#C4B8A8"
  charcoal: "#3A3A3A"
  ink: "#1C1C1C"
  terracotta: "#C4704B"
  olive: "#6B7B5E"
  cream: "#FAF6F0"
  pure-white: "#FFFFFF"
  black: "#0A0A0A"
typography:
  display:
    fontFamily: Playfair Display
    fontSize: 42px
    fontWeight: 400
    letterSpacing: 0.02em
  body:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: JetBrains Mono
    fontSize: 9px
    fontWeight: 600
    letterSpacing: 0.2em
    textTransform: uppercase
rounded:
  sm: 0px
  md: 2px
  lg: 6px
spacing:
  padding: 32px
  gap: 20px
components:
  lookbook:
    backgroundColor: "{colors.bone}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "{spacing.padding}"
  editorial:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.sm}"
    padding: 40px
  detail-shot:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 24px
  social-square:
    backgroundColor: "{colors.black}"
    textColor: "{colors.bone}"
    rounded: "{rounded.sm}"
    padding: 32px
---

## Overview

MAISON is an avant-garde fashion brand. The visual language is architectural — clean lines, monochromatic palettes, negative space as a design element. Every image should feel like a page from a high-fashion editorial spread.

## Colors

- **Bone (#F2EDE8):** Primary background. Warm neutral, like raw canvas.
- **Stone (#C4B8A8):** Mid-tone. Texture, depth, natural fabrics.
- **Charcoal (#3A3A3A):** Text, shadows, structured elements.
- **Ink (#1C1C1C):** Near-black for high-contrast editorial.
- **Terracotta (#C4704B):** Warm accent. Earth tones, leather, clay.
- **Olive (#6B7B5E):** Cool accent. Nature, sustainability references.
- **Cream (#FAF6F0):** Lighter neutral for layered compositions.

## Shot Types

### Lookbook (studio)
- Bone/cream background
- Garment on invisible mannequin or flat-lay
- Even, diffused lighting (no harsh shadows)
- Architectural composition — garment fills frame with purpose
- Model: flux-dev, 28 steps

### Editorial (lifestyle)
- Natural setting — concrete, stone, raw wood
- Model wearing garment (if applicable)
- High-contrast B&W conversion option
- Cinematic crop — asymmetric framing

### Detail Shot
- Close-up of fabric texture, stitching, hardware
- Macro-style, shallow DOF
- Stone or charcoal background

### Social — Monochrome
- Black background
- Single garment, centered
- Dramatic spotlight from above
- Minimal — the garment IS the design

## Prompts

**Lookbook — Oversized blazer:**
"Oversized charcoal wool blazer, structured shoulders, minimalist design, displayed on invisible mannequin, bone white background, even studio lighting, fashion lookbook photography, architectural composition, high resolution, editorial quality"

**Editorial — Street style:**
"Model wearing oversized charcoal blazer over white t-shirt, walking on raw concrete architecture, golden hour side lighting, editorial fashion photography, cinematic crop, monochromatic palette with terracotta accent"

**Detail — Fabric texture:**
"Macro close-up of premium wool fabric texture, charcoal color, visible weave pattern, dramatic side lighting, shallow depth of field, fashion detail photography"

**Social — Product spotlight:**
"Minimalist folded sweater in olive green, centered on pure black background, single dramatic spotlight from above, high contrast, editorial fashion layout, negative space composition"
