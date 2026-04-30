# Hermesfy Studio — Dashboard Design Spec

> Workflow audit dashboard for Hermes Agent. Read-only viewer for saved workflows, execution history, and node states.

## Design Dials

```
DESIGN_VARIANCE: 5    (Offset — left-aligned data, asymmetric spacing)
MOTION_INTENSITY: 2   (Static — CSS transitions only, no Framer Motion)
VISUAL_DENSITY: 8     (Cockpit Mode — packed data, monospace numbers, 1px dividers)
```

**Rationale:** Audit/operations dashboard. Dense data with zero decorative motion. Every pixel earns its place. Reuses Clawfy Studio's "Antigravity" identity — mint tones, CRT atmosphere, glassmorphism panels.

---

## Color Palette (Clawfy Studio Antigravity — Dark Mode)

| Token | HEX | Usage |
|-------|-----|-------|
| `--background` | `#0A0E14` | Page background |
| `--foreground` | `#E6FFF9` | Primary text |
| `--mint-base` | `#A8E6CF` | Structural highlights, hover states, subtle borders |
| `--mint-deep` | `#7FDBCA` | Links, active borders, branding |
| `--electric-mint` | `#00FFC6` | CTA buttons, critical actions (execute, re-run) |
| `--glitch-cyan` | `#00E5FF` | Text-shadow distortion, animation overlays |
| `--node-fill` | `#0D1117` | Node card backgrounds, input fields |
| `--glass-bg` | `rgba(13, 17, 23, 0.6)` | Glassmorphism panels (backdrop-blur) |
| `--glass-border` | `rgba(127, 219, 202, 0.2)` | Glassmorphism borders (mint-deep at 20%) |

**State Colors (mapped from Clawfy tokens):**

| State | Background | Border | Text |
|-------|-----------|--------|------|
| pending | `--node-fill` | `rgba(168, 230, 207, 0.15)` | `--foreground` at 50% |
| running | `rgba(0, 229, 255, 0.1)` | `--glitch-cyan` | `--glitch-cyan` |
| completed | `rgba(0, 255, 198, 0.1)` | `--electric-mint` | `--electric-mint` |
| failed | `rgba(255, 100, 100, 0.1)` | `#FF6464` | `#FF6464` |
| retrying | `rgba(0, 229, 255, 0.1)` | `--glitch-cyan` | `--glitch-cyan` |
| quality_exhausted | `rgba(255, 100, 100, 0.1)` | `#FF6464` | `#FF6464` |

---

## Typography (The Triptych)

| Role | Font | Fallback | Usage |
|------|------|----------|-------|
| **Display** | Instrument Serif | Georgia, serif | Page title "Hermesfy Studio" — authority, agency feel |
| **Body** | Space Grotesk | system-ui, sans-serif | Labels, descriptions, buttons, workflow names |
| **Mono** | JetBrains Mono | monospace | ALL numbers, IDs, timestamps, JSON, node configs, badges |

**Type Scale:**

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Page title | Serif | 24px | 400 | `--foreground` |
| Section header | Sans | 13px | 600 | `--mint-deep` |
| Workflow name (sidebar) | Sans | 13px | 500 | `--foreground` |
| Node label | Mono | 11px | 600 | state color |
| Body / description | Sans | 13px | 400 | `--foreground` at 70% |
| Timestamp / ID | Mono | 11px | 400 | `--foreground` at 40% |
| Status badge | Mono | 10px | 700 | state color |
| JSON values | Mono | 11px | 400 | `--mint-base` |
| Event log row | Mono | 11px | 400 | `--foreground` at 60% |

**Tracking:** `-0.01em` on all sans headings. Mono values get `letter-spacing: 0.02em`.

---

## CRT Overlay Effect

Applied as a `::after` pseudo-element on `body`:

```css
body::after {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 0, 0, 0.03) 0px,
    rgba(0, 0, 0, 0.03) 1px,
    transparent 1px,
    transparent 2px
  );
  opacity: 0.04;
}
```

Ultra-subtle scanlines. Forces the user to perceive the app in the programmatic automation universe. Never above 0.04 opacity.

---

## Glassmorphism Panels

Used for: sidebar, inspector panel, modal overlays.

```css
.glass {
  background: rgba(13, 17, 23, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(127, 219, 202, 0.2);
  border-radius: 12px;
}
```

Inner refraction: add `box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05)` for physical edge simulation.

---

## Layout Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  HEADER: "Hermesfy Studio" (Instrument Serif)    [Refresh]  │
│  Subtitle: "Workflow Audit Dashboard" (Space Grotesk muted) │
├────────────┬─────────────────────────────────────────────────┤
│            │                                                 │
│  SIDEBAR   │  MAIN PANEL                                     │
│  260px     │                                                 │
│  (glass)   │  ┌─ WORKFLOW HEADER ──────────────────────────┐ │
│            │  │ name · node count · status badge            │ │
│  ┌──────┐  │  │ created: Apr 30, 03:14 · id: 0750548a...   │ │
│  │ ▌    │  │  └────────────────────────────────────────────┘ │
│  │ name │  │                                                 │
│  └──────┘  │  ┌─ DAG CANVAS ───────────────────────────────┐ │
│  ┌──────┐  │  │                                             │ │
│  │      │  │  │  [TEXT] prompt1 ──────► [GEN] gen1           │ │
│  │ name │  │  │       ○                    ⏳                │ │
│  └──────┘  │  │                                             │ │
│            │  └─────────────────────────────────────────────┘ │
│            │                                                 │
│            │  ── Event Log (border-top divider) ─────────── │
│            │  TIMESTAMP      NODE    EVENT       DETAIL      │
│            │  12:03:01.234   gen1    ERROR       Expecting.. │
│            │  12:03:00.892   prompt1 COMPLETE    {prompt:..} │
│            │                                                 │
│            │  ── Node Inspector (border-top divider) ────── │
│            │  { JSON viewer, monospace }                      │
│            │                                                 │
└────────────┴─────────────────────────────────────────────────┘
```

**Sidebar:** Fixed 260px. Glassmorphism background. Scrollable workflow list.

**Main Panel:** Fluid. Sections separated by `border-top: 1px solid rgba(168, 230, 207, 0.1)`. No card boxes — data breathes via spacing.

---

## Components

### 1. Workflow List Item (Sidebar)

```
┌─ selected ─────────────────────┐
│ ▌ cyberpunk-night               │  ← 3px left border: --electric-mint
│   ○ 2 nodes · pending           │
│   Apr 30, 03:14                 │  ← mono, muted
└────────────────────────────────┘

┌─ hover ────────────────────────┐
│   dragon-castle                 │  ← bg: rgba(168, 230, 207, 0.05)
│   ✅ 3 nodes · completed        │
│   Apr 30, 02:58                 │
└────────────────────────────────┘
```

- Background: transparent → `rgba(168, 230, 207, 0.05)` on hover
- Border-left: 3px `--electric-mint` when selected, transparent otherwise
- Padding: `12px 14px`
- Transition: `all 0.15s ease`
- Active: `transform: translateX(2px)` on `:active`

### 2. DAG Canvas

Node graph with positioned divs and SVG edges.

**Node Card:**
```
┌────────────────────────────────┐
│ ✅ TEXT  prompt1                │  ← state emoji + type badge (mono 600) + id
│ prompt="a majestic red..."     │  ← config summary, truncated
│ 12:03:01.234                   │  ← mono, muted
└────────────────────────────────┘
```

- Background: `--node-fill` (#0D1117)
- Border: 1px solid, colored by state (see State Colors table)
- Border-radius: 8px
- Padding: 10px 14px
- Min-width: 220px
- Glassmorphism: add `backdrop-filter: blur(4px)` and `border-color: rgba(state-color, 0.3)`

**Edge Lines (SVG):**
- Default: `stroke: rgba(168, 230, 207, 0.2)` (mint-base at 20%)
- Running: `stroke: --glitch-cyan` + `stroke-dasharray: 5 3` + CSS animation
- Completed: `stroke: --electric-mint` at 30% opacity
- Failed: `stroke: #FF6464` at 30% opacity

### 3. Event Log

Table with `border-top` dividers.

```
 TIMESTAMP          NODE      EVENT          DETAIL
 ──────────────────────────────────────────────────────────
 12:03:01.234       gen1      node_error     Expecting value: line 1...
 12:03:01.100       gen1      node_start     model=flux-schnell
 12:03:00.892       prompt1   node_complete  output={prompt: "a red..."}
 12:03:00.800       prompt1   node_start     type=text_prompt
```

- All monospace
- Row hover: `rgba(168, 230, 207, 0.03)`
- Event coloring:
  - `node_start`: `--foreground` at 50%
  - `node_complete`: `--electric-mint`
  - `node_error`: `#FF6464`
  - `workflow_done`: `--glitch-cyan`

### 4. Node Inspector

Raw JSON viewer for selected node.

```json
{
  "id": "gen1",
  "type": "image_gen",
  "config": {
    "model": "flux-schnell",
    "prompt": "{{prompt1}}",
    "width": 1024
  },
  "state": "completed"
}
```

- Background: `--node-fill`
- Border: 1px solid `rgba(168, 230, 207, 0.1)`
- Border-radius: 8px
- Font: JetBrains Mono, 11px
- Syntax: keys `--mint-deep`, strings `--electric-mint`, numbers `--glitch-cyan`, errors `#FF6464`

### 5. Status Badges

Pill-shaped inline badges.

| State | BG | Text | Border |
|-------|----|------|--------|
| pending | `--node-fill` | `--foreground` at 40% | `--foreground` at 10% |
| running | `rgba(0, 229, 255, 0.1)` | `--glitch-cyan` | `--glitch-cyan` at 30% |
| completed | `rgba(0, 255, 198, 0.1)` | `--electric-mint` | `--electric-mint` at 30% |
| failed | `rgba(255, 100, 100, 0.1)` | `#FF6464` | `#FF6464` at 30% |

- Border-radius: 9999px
- Padding: `2px 8px`
- Font: JetBrains Mono, 10px, weight 700
- Uppercase, letter-spacing 0.05em

### 6. CTA Button (Execute/Refresh)

```css
.btn-cta {
  background: var(--electric-mint);
  color: var(--background);
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-cta:hover {
  box-shadow: 0 0 12px rgba(0, 255, 198, 0.3);
}
.btn-cta:active {
  transform: translateY(1px);
}
```

---

## Interaction States

### Hover
- Sidebar item: `background: rgba(168, 230, 207, 0.05)`
- Node card: border opacity increases to 50%
- Event row: `background: rgba(168, 230, 207, 0.03)`

### Active/Pressed
- Sidebar item: `transform: translateX(2px)`
- Buttons: `transform: translateY(1px)`

### Selected (Workflow)
- Sidebar: left border `--electric-mint` 3px
- Main panel: populated

### Selected (Node)
- Node card: `box-shadow: 0 0 0 2px rgba(0, 255, 198, 0.3)` (mint ring)
- Inspector: populated with node JSON

### Empty State
- Center of main panel
- Text: "Select a workflow to inspect"
- Font: Space Grotesk, 14px, `--foreground` at 30%
- No illustration

### Loading
- Skeleton rows: `--node-fill` bars with subtle `background: linear-gradient(90deg, --node-fill 25%, rgba(168,230,207,0.05) 50%, --node-fill 75%)` shimmer animation

### Error
- Red inline banner: `background: rgba(255, 100, 100, 0.08); border: 1px solid rgba(255, 100, 100, 0.2)`
- Message in mono, `#FF6464`

---

## Responsive

- **< 768px:** Sidebar collapses to 48px icon rail. Node cards stack vertically.
- **768-1024px:** Sidebar 200px. DAG canvas horizontal scroll.
- **> 1024px:** Full layout as specified.

---

## Anti-Patterns

- No purple/AI glow effects
- No emojis in UI chrome (only in node state indicators as functional symbols)
- No Inter font
- No center-aligned hero sections
- No card boxes for data grouping — use `border-top` dividers
- No `h-screen` — use `min-h-dvh`
- No pure `#000` — use `#0A0E14`
- No neon outer shadows — use `box-shadow: 0 0 Npx rgba(color, 0.2)` only for CTAs
- No generic SVG avatars or "egg" icons

---

## Data Source

Dashboard reads JSON files from `~/.hermes/hermesfy/workflows/`. Pure client-side via `<input type="file">` or served via `python3 -m http.server`.

**Required JSON format:**
```json
{
  "id": "uuid",
  "name": "workflow-name",
  "nodes": [{"id": "...", "type": "...", "config": {...}}],
  "edges": [{"source": "...", "target": "..."}],
  "execution": {
    "node_states": {"node_id": "completed"},
    "node_errors": {"node_id": "error msg"},
    "events": [{"event_type": "...", "node_id": "...", "data": {...}}]
  }
}
```

**Note:** The `execution` key must be added to `save_workflow.py` to persist runtime state alongside the static definition.

---

## File Structure

```
hermesfy-dashboard/
└── index.html    ← Single self-contained HTML (CSS + JS inline)
```

**Constraints:**
- Zero dependencies (no React, no Tailwind CDN, no build tools)
- Single HTML file, copy-pasteable
- Vanilla JS + CSS custom properties
- Works from `file://` protocol
- Instrument Serif loaded via Google Fonts CDN (single external dependency for typography)
