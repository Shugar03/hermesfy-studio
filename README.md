# Hermesfy Studio

<img width="1344" height="768" alt="Generated Image April 30, 2026 - 2_22AM" src="https://github.com/user-attachments/assets/bd283b8d-611e-4a7e-8025-3748d1b31fec" />

> **A DAG workflow engine for AI image generation — built for Hermes Agent.**
>
> Define complex multi-step image pipelines as directed acyclic graphs. Execute them topologically via Fal.ai. Let an AI agent plan, generate, evaluate, and refine your images autonomously. All through natural language in your Hermes chat.

---

## Why Hermesfy?

Most AI image generation tools give you a text box and a "generate" button. That works for single images — but what about the 90% of real workflows that aren't that simple?

- **Batch generation** — create 50 product variants while you sleep
- **Multi-step pipelines** — generate → upscale → remove background → deliver
- **Iterative refinement** — generate, evaluate with vision AI, adjust prompt, regenerate
- **Consistent style** — apply cinematic/anime/photorealistic presets across entire batches

Hermesfy turns these into composable DAG workflows. Each node is a step. Each edge is a data dependency. The engine resolves the graph, executes in parallel where possible, and delivers results when done.

The key insight: **the LLM becomes the workflow designer**. You describe what you want in plain English. Hermes builds the DAG, executes it, and shows you the results — all without you touching a single node configuration.

---

## What's Inside

```
hermesfy-studio/
├── src/hermesfy/
│   ├── dag/              # Core engine
│   │   ├── graph.py      # DAG definition, validation, Kahn's algo
│   │   ├── executor.py   # Topological execution engine
│   │   ├── state.py      # Node state tracking (pending → running → done/error)
│   │   └── quality.py    # QA scoring + auto-adjustment logic
│   ├── providers/
│   │   └── fal.py        # Fal.ai HTTP provider (flux, upscale, img2img)
│   ├── tools/            # 8 Hermes Agent tools
│   ├── styles/           # YAML style presets (cinematic, anime, etc.)
│   ├── persistence/      # Workflow save/load (JSON)
│   └── plugin.py         # Hermes plugin registration
├── tests/                # 144 tests, 100% green
├── DESIGN.md             # UI design system (Antigravity theme)
└── dashboard/            # Web dashboard (server + static)
```

---

## Tools

Hermesfy registers **8 tools** with Hermes Agent. The LLM calls them automatically when you describe what you want.

| Tool | Description |
|------|-------------|
| `hermesfy_define_workflow` | Build a DAG from natural language description |
| `hermesfy_execute_workflow` | Execute the workflow topologically via Fal.ai |
| `hermesfy_workflow_status` | Text canvas with node states (○ ⏳ ✅ ❌ 🔄) |
| `hermesfy_edit_node` | Edit a node's config and optionally re-execute |
| `hermesfy_list_models` | List all available Fal.ai models |
| `hermesfy_save_workflow` | Save workflow to a JSON file |
| `hermesfy_load_workflow` | Load workflow from a JSON file |
| **`hermesfy_run_agentic_workflow`** | **Full agentic loop: plan → execute → QA → adjust → deliver** |

The last one — `run_agentic_workflow` — is the flagship. It takes a plain-English description, builds a workflow from predefined patterns, executes it, runs Gemini vision QA on every output, and automatically adjusts prompts if quality scores drop below threshold. One tool, zero manual steps.

---

## Quick Start

```bash
# Install from GitHub
pip install git+https://github.com/sebaunsa-collab/hermesfy-studio.git

# Set your Fal.ai API key
export FAL_API_KEY=your_key_here

# Verify everything works
python -m pytest tests/ -v
# Expected: 144 passed
```

---

## Usage

### Agentic (recommended)

Just tell Hermes what you want:

> *"Generate a photo of a luxury skincare bottle on marble, white background, remove the background when done"*

Hermes calls `hermesfy_run_agentic_workflow` with the `remove_bg` pattern. It handles everything:

1. **Plan** — selects the right workflow pattern + model
2. **Execute** — generates the image via Fal.ai
3. **QA** — Gemini 2.5 Flash analyzes the result (prompt adherence, quality, commercial viability)
4. **Adjust** — if score < 7/10, rewrites the prompt and re-generates
5. **Deliver** — returns the final image URL + QA history

### Manual (for power users)

Build the DAG yourself:

```python
# Define a workflow
hermesfy_define_workflow(
    nodes=[
        {"id": "prompt", "type": "text_prompt", "config": {"prompt": "cyberpunk city at night"}},
        {"id": "gen", "type": "image_gen", "config": {"model": "flux-dev", "width": 1024, "height": 1024}},
        {"id": "upscale", "type": "upscale", "config": {"model": "clarity-upscaler", "scale": 2}},
    ],
    edges=[
        {"source": "prompt", "target": "gen"},
        {"source": "gen", "target": "upscale"},
    ]
)

# Execute it
hermesfy_execute_workflow()

# Check status
hermesfy_workflow_status()
# ┌─────────────────────────────┐
# │  prompt ✅  →  gen ⏳  →  upscale ○  │
# └─────────────────────────────┘
```

---

## Workflow Patterns

The agentic workflow comes with 4 built-in patterns:

| Pattern | Pipeline | Use Case |
|---------|----------|----------|
| `simple` | text → image_gen | Quick single image |
| `upscale` | text → image_gen → upscale | High-res output |
| `remove_bg` | text → image_gen → remove_bg | E-commerce, product photos |
| `variants` | text → image_gen → img2img (×2) | Style variations from a master |

---

## Node Types

| Type | Purpose |
|------|---------|
| `text_prompt` | Input prompt for generation |
| `image_gen` | Generate image via Fal.ai (flux-dev, flux-schnell, etc.) |
| `img2img` | Image-to-image transformation |
| `upscale` | Upscale via Fal.ai clarity-upscaler |
| `remove_bg` | Background removal via Fal.ai |
| `seed` | Fixed seed for reproducible generation |

---

## QA Engine

Every image goes through automated quality analysis:

- **Vision model**: Gemini 2.5 Flash (or compatible)
- **Scoring**: prompt adherence (1-10), technical quality (1-10), commercial viability (1-10)
- **Threshold**: composite score < 7 triggers auto-adjustment
- **Loop**: max 3 iterations with prompt refinement between each
- **History**: full QA log preserved for each execution

---

## Style Presets

```yaml
# Available: cinematic, anime, photorealistic, digital-art
# Applied automatically or manually:

hermesfy_define_workflow(..., style="cinematic")
```

Each preset injects style-specific prompt modifiers and recommended model parameters.

---

## Dashboard

A web dashboard for visual workflow management:

```bash
cd dashboard/
python server.py
# Opens at http://localhost:8080
```

Dark-mode "Antigravity" theme — deep navy with mint/cyan neon accents, glassmorphism panels, CRT scanline aesthetic.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Hermes Agent (LLM)                  │
│         Interprets natural language              │
│         Calls tools automatically                │
└───────────┬─────────────────────┬───────────────┘
            │                     │
   ┌────────▼────────┐  ┌────────▼────────────┐
   │  8 Hermes Tools  │  │  Agentic Workflow   │
   │  define/execute/ │  │  plan → execute →   │
   │  status/edit/... │  │  QA → adjust →      │
   └────────┬────────┘  │  deliver             │
            │           └────────┬────────────┘
   ┌────────▼────────────────────▼──────────────┐
   │           DAG Engine (Kahn's algo)          │
   │     graph.py → executor.py → state.py      │
   └────────────────────┬──────────────────────┘
                        │
   ┌────────────────────▼──────────────────────┐
   │         Fal.ai Provider (HTTP)             │
   │   flux-dev · clarity-upscaler · img2img    │
   └────────────────────────────────────────────┘
```

---

## Requirements

- Python 3.10+
- Hermes Agent (latest)
- Fal.ai API key ([get one here](https://fal.ai))
- Gemini API key (for QA features, optional)

---

## Quick Start

```bash
git clone https://github.com/sebaunsa-collab/hermesfy-studio.git
cd hermesfy-studio
bash setup.sh
```

The `setup.sh` script will:
1. ✅ Create a Python virtual environment
2. ✅ Install hermesfy-studio in editable mode (with all deps)
3. ✅ Create required directories (cache/, output/, logs/)
4. ✅ Create `.env` file (edit with your FAL API key)
5. ✅ Fetch the latest models from FAL.ai
6. ✅ Show dashboard instructions

Then generate your first image:
```bash
source venv/bin/activate
export FAL_API_KEY=your_key_here
python3 -m hermesfy.cli "haceme un ad de Nike con fondo negro"
```

**Dashboard** (optional):
```bash
cd dashboard && python3 -m http.server 8090
# Open http://localhost:8090
```

---

## Built by

[sebaunsa-collab](https://github.com/sebaunsa-collab) — Hermes Agent ecosystem.

Part of the [Hermes](https://github.com/sebaunsa-collab/hermes-agent) project.

---

## License

MIT
