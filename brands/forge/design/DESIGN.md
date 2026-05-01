---
version: alpha
name: FORGE Fitness
description: Visual identity system for FORGE — industrial-strength fitness brand. Bold, raw, powerful. Generated via Hermesfy Studio.
colors:
  obsidian: "#0D0D0D"
  steel: "#2A2A2A"
  concrete: "#4A4A4A"
  ember: "#FF4500"
  neon-green: "#39FF14"
  chalk: "#E8E8E8"
  rust: "#B7410E"
  pure-white: "#FFFFFF"
typography:
  display:
    fontFamily: Bebas Neue
    fontSize: 48px
    fontWeight: 700
    letterSpacing: 0.05em
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.5
  mono:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: 700
    letterSpacing: 0.1em
rounded:
  sm: 2px
  md: 4px
  lg: 8px
  full: 9999px
spacing:
  padding: 24px
  gap: 12px
components:
  hero-shot:
    backgroundColor: "{colors.obsidian}"
    textColor: "{colors.chalk}"
    rounded: "{rounded.sm}"
    padding: "{spacing.padding}"
  detail-shot:
    backgroundColor: "{colors.steel}"
    textColor: "{colors.chalk}"
    rounded: "{rounded.md}"
    padding: "{spacing.padding}"
  action-shot:
    backgroundColor: "{colors.rust}"
    textColor: "{colors.pure-white}"
    rounded: "{rounded.sm}"
    padding: 32px
  supplement-label:
    backgroundColor: "{colors.concrete}"
    textColor: "{colors.neon-green}"
    rounded: "{rounded.full}"
    padding: 8px 20px
---

## Overview

FORGE is an industrial-strength fitness brand. The visual language is raw power — concrete textures, dramatic shadows, ember accents against obsidian backgrounds. Every image should feel like it was shot in a warehouse gym at dawn.

## Colors

- **Obsidian (#0D0D0D):** Primary. Near-black with warm undertone. Backgrounds.
- **Steel (#2A2A2A):** Elevated surfaces, cards, panels.
- **Concrete (#4A4A4A):** Mid-tone for text and borders.
- **Ember (#FF4500):** Primary accent. Energy, power, CTAs.
- **Neon Green (#39FF14):** Secondary accent. Supplement branding, metrics.
- **Chalk (#E8E8E8):** Text on dark backgrounds. Not pure white.
- **Rust (#B7410E):** Tertiary. Warmth, grit, aged metal.

## Shot Types

### Hero Product Shot
- Obsidian/black background
- Product front and center
- Dramatic rim lighting (ember/green edge glow)
- Dust/particle overlay
- Model: flux-dev, 40 steps (max quality for dark scenes)

### Action Shot
- Dark gym/warehouse environment
- Athlete in motion (blur suggests power)
- Product visible in scene
- High contrast, deep shadows

### Supplement Detail
- Close-up of label/texture
- Macro-style, shallow DOF
- Neon-green accent elements

## Prompts

**Hero — Pre-workout tub:**
"Black matte supplement tub with ember-orange label, dramatic side lighting creating rim glow, dark concrete background, dust particles in air, gym warehouse atmosphere, professional product photography, high contrast, cinematic lighting, 8k"

**Action — Gym scene:**
"Athlete mid-deadlift in dark warehouse gym, dramatic overhead lighting, chalk dust in air, raw concrete walls, intensity and power, cinematic fitness photography, dark moody tones"

**Detail — Label close-up:**
"Macro close-up of supplement label, matte black surface with neon green text, textured finish, dramatic side lighting, shallow depth of field, product detail photography"
