# Hermesfy Studio

> **The AI image workflow engine that turns "I want this" into a finished image — without you touching a single setting.**

Hermesfy Studio lets you describe what you want in plain English. It plans the pipeline, generates it via Fal.ai, validates the output, and delivers. Batch generation, multi-step workflows, iterative refinement — all through a conversation with your AI agent.

<img src="https://github.com/user-attachments/assets/bd283b8d-611e-4a7e-8025-3748d1b31fec" alt="Hermesfy Dashboard" width="100%" />

---

## The Problem

Most AI image tools give you a text box and a "generate" button. That's fine for one image. But real creative work isn't one image — it's:

- 30 product variants for a campaign
- A sequence: generate → refine → upscale → remove background
- "This isn't quite right, adjust the lighting, regenerate"
- Consistent style across an entire brand batch

That's where most tools break down. You end up manually stitching pipelines together, babysitting generations, and burning credits on bad outputs. **Hermesfy solves that.**

---

## What Hermesfy Actually Does

Instead of a generate button, you have a conversation:

> *"Generame un ad de un sneaker Nike con fondo negro, después hazle upscale y sacale el fondo"*

Hermesfy:
1. Plans the optimal pipeline (draft → refine → upscale → remove background)
2. Selects the right model for each step
3. Executes with automatic seed propagation (style consistency)
4. Validates each output before moving to the next step
5. Stops if you're about to hit the budget cap
6. Delivers the final image

You're in control — you just speak English.

---

## Key Features

### Multi-Step Pipelines, Not Single Images
Generate → Upscale → Remove Background → Deliver. Or any combination. Hermesfy resolves the workflow as a directed acyclic graph and executes in parallel where possible.

### Agentic Refinement
Not happy with the output? Say so. Hermes regenerates with adjusted prompts, validates the new result, and only proceeds if it's better. No wasted credits on garbage.

### Batch Generation at Scale
Create 50 variants while you sleep. Same product, different backgrounds, angles, or styles — all from a single natural language request.

### Seed Propagation
The seed from your first generation automatically inherits into subsequent steps. Your sneaker stays your sneaker through every pipeline iteration.

### Hard Budget Control
Every flow has a spending cap (default $0.07). Hermesfy stops before it burns through your credits. No surprises.

### 48+ Fal.ai Models
Access the full Fal.ai model library directly: FLUX, Stable Diffusion, upscalers, background removal, img2img, and more. No model management overhead.

### Workflow Persistence
Save workflows as JSON, reload them, share them. Build a library of proven pipelines for your clients or campaigns.

---

## Quick Start

```bash
git clone https://github.com/sebaunsa-collab/hermesfy-studio.git
cd hermesfy-studio
bash setup.sh
```

The `setup.sh` script handles everything:
- Python virtual environment setup
- Dependencies installation
- Required directories (cache/, output/, logs/)
- `.env` configuration (add your FAL API key)
- FAL.ai model discovery

Then:

```bash
source venv/bin/activate
export FAL_API_KEY=your_key_here
python3 -m hermesfy.cli "generame un ad de Nike con fondo negro"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Hermes Agent (LLM)                     │
│              Natural language → tool calls                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│   Define DAG    │ │   Execute   │ │  Agentic Loop        │
│  workflow from  │ │  topologic  │ │  plan → execute →     │
│  natural lang   │ │  via FAL    │ │  QA → adjust → deliver│
└────────┬────────┘ └──────┬──────┘ └──────────┬───────────┘
         │                 │                   │
         └─────────────────┴───────────────────┘
                           │
              ┌────────────▼────────────┐
              │   ExecutionSpec (V4)    │
              │ BudgetGate · SeedProp   │
              │ IntermediateValidator   │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
  │ Graph Engine│   │  FAL.ai    │   │ Gemini Vision │
  │ (Kahn's)   │   │  HTTP API  │   │  (QA only)   │
  └─────────────┘   └─────────────┘   └──────────────┘
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `dag/graph.py` | DAG definition, validation, Kahn's topological sort |
| `dag/executor.py` | Parallel execution engine with state tracking |
| `execution_spec.py` | V4: Formal JSON contract for generation requests |
| `budget_gate.py` | Hard spending cap per flow |
| `seed_propagator.py` | Seed inheritance across pipeline steps |
| `intermediate_validator.py` | Step-by-step QA with Gemini Vision |
| `providers/fal.py` | Fal.ai HTTP provider wrapper |

---

## Tools

Hermesfy registers **10 tools** with Hermes Agent:

| Tool | Description |
|------|-------------|
| `hermesfy_define_workflow` | Build a DAG from natural language |
| `hermesfy_execute_workflow` | Execute topologically via Fal.ai |
| `hermesfy_workflow_status` | Node states (○ ⏳ ✅ ❌ 🔄) |
| `hermesfy_edit_node` | Edit a node's config on the fly |
| `hermesfy_list_models` | List available Fal.ai models |
| `hermesfy_list_templates` | List workflow templates |
| `hermesfy_save_workflow` | Save workflow to JSON |
| `hermesfy_load_workflow` | Load workflow from JSON |
| `hermesfy_history` | View generation history |
| `hermesfy_run_agentic_workflow` | Full loop: plan → execute → QA → adjust → deliver |

---

## Usage

### Agentic (Recommended)

Tell Hermes what you want:

```
Generame una foto de un skincare bottle en marble blanco, después sacale el fondo
```

Hermes calls `hermesfy_run_agentic_workflow` and handles the rest — pipeline planning, model selection, generation, validation, and delivery.

### Manual (Power Users)

Full control over the DAG:

```python
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
hermesfy_execute_workflow()
```

---

## Dashboard

Visual workflow management with a dark-mode Antigravity theme — deep navy with mint/cyan neon accents, glassmorphism panels, CRT scanline aesthetic.

```bash
cd dashboard && python3 -m http.server 8090
# Open http://localhost:8090
```

---

## Requirements

- Python 3.10+
- Hermes Agent (latest)
- Fal.ai API key — [get one here](https://fal.ai)
- Gemini API key (optional, for QA/validation)

---

## Specifications

| Version | Focus | Status |
|---------|-------|--------|
| `SPEC_V4.md` | ExecutionSpec, Budget Gate, Seed Inheritance, Intermediate Validation | ✅ Implemented |
| `SPEC_V3.md` | Intent Router, Versions, Edit | Legacy |

---

## Built by

[sebaunsa-collab](https://github.com/sebaunsa-collab) — part of the [Hermes](https://github.com/sebaunsa-collab/hermes-agent) ecosystem.

---

## License

MIT
