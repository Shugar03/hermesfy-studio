---
version: alpha
name: LUMIÈRE Skincare
description: Visual identity system for LUMIère — French-inspired luxury skincare. Clean, luminous, editorial. Generated via Hermesfy Studio.
colors:
  pearl: "#F5F0EB"
  ivory: "#FAF7F2"
  champagne: "#E8D5B7"
  gold: "#C9A96E"
  deep-navy: "#1A1A2E"
  soft-sage: "#C5D1C8"
  rose-mist: "#E8C4C4"
  pure-white: "#FFFFFF"
  charcoal: "#2D2D2D"
typography:
  display:
    fontFamily: Cormorant Garamond
    fontSize: 36px
    fontWeight: 300
    letterSpacing: 0.08em
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 300
    lineHeight: 1.7
  accent:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: 500
    letterSpacing: 0.15em
rounded:
  sm: 4px
  md: 8px
  lg: 24px
  full: 9999px
spacing:
  padding: 24px
  gap: 16px
  section-gap: 48px
components:
  product-shot:
    backgroundColor: "{colors.pearl}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.lg}"
    padding: "{spacing.padding}"
  lifestyle-shot:
    backgroundColor: "{colors.ivory}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.md}"
    padding: "{spacing.padding}"
  social-post:
    backgroundColor: "{colors.deep-navy}"
    textColor: "{colors.pearl}"
    rounded: "{rounded.sm}"
    padding: 32px
  ingredient-callout:
    backgroundColor: "{colors.soft-sage}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.full}"
    padding: 12px 24px
---

## Overview

LUMIÈRE is a French-inspired luxury skincare brand. The visual system centers on luminosity — soft, diffused light that flatters skin and product equally. Every image should feel like it was shot in a Parisian atelier at golden hour.

## Colors

- **Pearl (#F5F0EB):** Primary background. Warm off-white with subtle pink undertone.
- **Ivory (#FAF7F2):** Secondary background. Slightly warmer than pearl.
- **Champagne (#E8D5B7):** Accent for lids, text overlays, warm highlights.
- **Gold (#C9A96E):** Premium accent. Logos, borders, call-to-action highlights.
- **Deep Navy (#1A1A2E):** Text, contrast elements, dark-mode social posts.
- **Soft Sage (#C5D1C8):** Ingredient callouts, natural/botanical references.
- **Rose Mist (#E8C4C4):** Blush tones for lifestyle shots, soft gradients.

## Shot Types

### Product Shot (studio)
- Clean pearl/ivory background
- Single product, centered
- Soft shadow (45° from top-left)
- Props: marble slab, linen cloth, dried botanicals
- Model: flux-dev, 28 steps, guidance 3.5

### Lifestyle Shot
- Natural light, warm tones
- Product in context (vanity, bathroom shelf, hand holding)
- Shallow depth of field
- img2img from product shot, strength 0.35

### Social Post
- Deep navy background with gold text overlay
- Product + tagline
- 1:1 for Instagram, 9:16 for Stories
- img2img from product shot, strength 0.4

## Generation Parameters

| Shot Type | Model | Steps | Strength | Notes |
|-----------|-------|-------|----------|-------|
| Studio | flux-dev | 28 | — | Master image |
| Lifestyle | flux-dev | 28 | 0.35 | img2img from studio |
| Social IG | flux-dev | 28 | 0.4 | img2img + overlay |
| Social Stories | flux-dev | 28 | 0.4 | 9:16 aspect |

## Prompts

**Studio master:**
"Luxury skincare jar, frosted glass with gold lid, cream-colored product visible, pearl white background, soft studio lighting from top-left, professional product photography, sharp focus, 8k, minimal composition"

**Lifestyle:**
Same product, marble bathroom counter, morning light through window, eucalyptus sprig nearby, soft focus background

**Social:**
Same product, deep navy background, gold accent line, text area top 30%, editorial layout
