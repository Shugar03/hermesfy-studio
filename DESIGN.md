---
version: alpha
name: Hermesfy Studio
description: DAG workflow engine for AI image generation. Dark-mode antigravity aesthetic with mint/cyan accents on deep navy.
colors:
  primary: "#0A0E14"
  secondary: "#0D1117"
  tertiary: "#00FFC6"
  neutral: "#E6FFF9"
  accent-mint: "#A8E6CF"
  accent-cyan: "#00E5FF"
  error: "#FF6464"
  warning: "#f59e0b"
  dim: "#1a2a3a"
  muted: "#3a4a5a"
typography:
  display:
    fontFamily: Instrument Serif
    fontSize: 26px
    fontWeight: 400
    letterSpacing: -0.02em
  body:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: 400
  label:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: 700
    letterSpacing: 0.06em
rounded:
  sm: 6px
  md: 10px
  lg: 14px
spacing:
  sidebar-width: 280px
  header-padding: 16px 28px
  main-padding: 28px 36px
  node-padding: 16px 18px
  card-gap: 52px
components:
  header:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.neutral}"
    typography: "{typography.body}"
  sidebar:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.neutral}"
    typography: "{typography.body}"
  node-card:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.neutral}"
    typography: "{typography.mono}"
    rounded: "{rounded.md}"
    padding: "{spacing.node-padding}"
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
  badge-completed:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.primary}"
    rounded: 9999px
  badge-failed:
    backgroundColor: "{colors.error}"
    textColor: "{colors.primary}"
    rounded: 9999px
---

## Overview

Hermesfy Studio is a DAG workflow engine for AI image generation via Fal.ai. The design follows an "Antigravity" aesthetic — dark-mode cockpit with mint/cyan neon accents, CRT scanlines, and glassmorphism panels. Inspired by sci-fi control interfaces.

## Colors

- **Primary (#0A0E14):** Deep navy foundation. Near-black with blue undertone. Used for backgrounds and dark surfaces.
- **Secondary (#0D1117):** Slightly lighter navy for cards, panels, and elevated surfaces.
- **Tertiary (#00FFC6):** Electric mint — primary accent for CTAs, active states, completed indicators. The signature color.
- **Neutral (#E6FFF9):** Mint-white text. High contrast on dark backgrounds. Used for all readable text.
- **Accent Mint (#A8E6CF):** Softer mint for borders, subtle highlights, sidebar labels.
- **Accent Cyan (#00E5FF):** Glitch cyan for running states and pulse animations.
- **Error (#FF6464):** Red for failed nodes, error messages, warnings.
- **Warning (#f59e0b):** Amber for upscale badges, caution indicators.
- **Dim (#1a2a3a):** Dark muted for subtle borders and dividers.
- **Muted (#3a4a5a):** Medium muted for placeholder text and metadata.

## Typography

- **Display:** Instrument Serif 26px — header branding only. Gradient text effect (mint to cyan).
- **Body:** Space Grotesk 16px — all body text, UI labels, descriptions.
- **Mono:** JetBrains Mono 11px — config values, JSON inspector, node metadata.
- **Label:** JetBrains Mono 10px/700 — section headers, badges, small caps.

## Components

- **header:** Glassmorphism bar with electric-mint gradient underline. Brand title + workflow count badge.
- **sidebar:** Glassmorphism panel with workflow list, colored state dots, file upload button.
- **node-card:** Individual DAG node with state-colored border (mint=completed, cyan=running, red=failed), glow effects, arrow connectors.
- **button-primary:** Electric mint CTA (#00FFC6 on #0A0E14) for "Load JSON" and primary actions.
- **badge-completed:** Electric mint pill for completed workflow state.
- **badge-failed:** Red pill for failed workflow state.

## Do's and Don'ts

- **Do** use electric mint (#00FFC6) for success/completed states
- **Do** use CRT scanlines sparingly (opacity 0.04) for texture
- **Do** use glassmorphism (backdrop-filter: blur) for panels
- **Don't** use pure white (#FFFFFF) — always use neutral (#E6FFF9)
- **Don't** use bold fonts — weight 400-500 throughout
- **Don't** animate more than one element per component
- **Don't** use rgba() in color tokens — use #hex only
