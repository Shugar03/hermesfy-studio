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
- **Budget control** — hard spending cap per flow ($0.07 default)
- **Seed consistency** — automatic seed inheritance between pipeline steps

Hermesfy turns these into composable DAG workflows. Each node is a step. Each edge is a data dependency. The engine resolves the graph, executes in parallel where possible, and delivers results when done.

The key insight: **the LLM becomes the workflow designer**. You describe what you want in plain English. Hermes builds the DAG, executes it, and shows you the results — all without you touching a single node configuration.

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
5. ✅ Fetch the latest models from FAL.ai (48+ models)
6. ✅ Show dashboard instructions

Then generate your first image:
```bash
source venv/bin/activate
export FAL_API_KEY=your_key_here
python3 -m hermesfy.cli "haceme un ad de Nike con fondo negro"
```

---

## What's Inside

```
hermesfy-studio/
├── src/hermesfy/
│   ├── dag/                  # Core engine
│   │   ├── graph.py          # DAG definition, validation, Kahn's algo
│   │   ├── executor.py       # Topological execution engine
│   │   ├── state.py          # Node state tracking
│   │   └── quality.py        # QA scoring + auto-adjustment
│   ├── providers/
│   │   └── fal.py            # Fal.ai HTTP provider
│   ├── tools/                # 10 Hermes Agent tools
│   ├── styles/               # YAML style presets
│   ├── persistence/          # Workflow save/load (JSON)
│   ├── execution_spec.py     # V4: Formal JSON contract for generation
│   ├── budget_gate.py        # V4: Hard spending cap ($0.07/flow)
│   ├── seed_propagator.py    # V4: Seed inheritance between nodes
│   ├── intermediate_validator.py  # V4: Step-by-step validation
│   └── plugin.py             # Hermes plugin registration
├── dashboard/                # Web dashboard (Antigravity theme)
├── tests/                    # 312 tests, all green
├── setup.sh                  # One-command setup
├── SPEC_V3.md                # V3 Spec (Intent Router, Versions, Edit)
└── SPEC_V4.md                # V4 Spec (Protocol-Driven Execution)
```

---

## V4: Protocol-Driven Execution

The latest version formalizes the contract between the LLM and the backend:

### ExecutionSpec — JSON Schema
Every generation request is a validated JSON contract. The pipeline rejects anything non-conforming.

```python
from engine.execution_spec import ExecutionSpec

# Simple single-step
spec = ExecutionSpec.simple("professional photo of Nike sneaker")

# Draft → Refine (2-step)
spec = ExecutionSpec.draft_then_refine("luxury skincare bottle")

# Full control
spec = ExecutionSpec.from_dict({
    "routing_decision": {
        "intent_category": "product",
        "action": "generate",
        "target_model": "fal-ai/flux/dev",
        "budget_estimation": 0.045,
        "priority": "quality"
    },
    "dag_workflow": {
        "steps": [
            {"node_id": 1, "action": "base_generation", "model": "fal-ai/flux/schnell", "params": {"width": 1024, "height": 1024}},
            {"node_id": 2, "action": "latent_refiner", "model": "fal-ai/flux/1.1-pro", "params": {"denoising_strength": 0.35}}
        ]
    },
    "prompt_metadata": {"cleaned_prompt": "luxury skincare bottle on marble"}
})
```

### Budget Gate — Cost Control
Hard cap per flow. Every FAL.ai call passes through the gate before execution.

```python
from engine.budget_gate import BudgetGate, BudgetExceeded

gate = BudgetGate(max_budget=0.07)
if gate.record_and_check("fal-ai/flux/schnell"):  # $0.003
    # ... generate ...
    gate.record_and_check("fal-ai/flux/1.1-pro")  # $0.04
else:
    raise BudgetExceeded(gate.remaining(), cost)
```

### Seed Propagation — Consistency Between Steps
The seed from node 1 is automatically inherited by node 2+. No wasted credits on inconsistent compositions.

```python
from engine.seed_propagator import SeedPropagator

prop = SeedPropagator()
seed = prop.resolve_seed(-1)           # auto-generate
params = prop.propagate(seed, {...})   # inject seed into next step
```

### Intermediate Validation — Validate Between Nodes
After each generation step, validate the image before proceeding. Bad images get caught early.

```python
from engine.intermediate_validator import IntermediateValidator

validator = IntermediateValidator(api_key="gemini_key")
result = validator.validate_step(
    step_result={"image_path": "/cache/fal/gen_xxx.png"},
    original_prompt="professional photo of sneaker",
)
if not result.should_continue:
    # Abort — don't waste credits on next step
```

---

## Tools

Hermesfy registers **10 tools** with Hermes Agent:

| Tool | Description |
|------|-------------|
| `hermesfy_define_workflow` | Build a DAG from natural language |
| `hermesfy_execute_workflow` | Execute topologically via Fal.ai |
| `hermesfy_workflow_status` | Node states (○ ⏳ ✅ ❌ 🔄) |
| `hermesfy_edit_node` | Edit a node's config |
| `hermesfy_list_models` | List available Fal.ai models |
| `hermesfy_list_templates` | List workflow templates |
| `hermesfy_save_workflow` | Save workflow to JSON |
| `hermesfy_load_workflow` | Load workflow from JSON |
| `hermesfy_history` | View generation history |
| **`hermesfy_run_agentic_workflow`** | **Full agentic loop: plan → execute → QA → adjust → deliver** |

---

## Usage

### Agentic (recommended)

Just tell Hermes what you want:

> *"Generate a photo of a luxury skincare bottle on marble, white background, remove the background when done"*

Hermes calls `hermesfy_run_agentic_workflow`. It handles everything:

1. **Plan** — selects the right workflow pattern + model
2. **Execute** — generates the image via Fal.ai
3. **QA** — Gemini Vision analyzes the result
4. **Adjust** — if quality < threshold, rewrites prompt and re-generates
5. **Deliver** — returns the final image + QA history

### Manual (for power users)

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

A web dashboard for visual workflow management:

```bash
cd dashboard && python3 -m http.server 8090
# Open http://localhost:8090
```

Dark-mode "Antigravity" theme — deep navy with mint/cyan neon accents, glassmorphism panels, CRT scanline aesthetic.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Hermes Agent (LLM)                      │
│             Interprets natural language                  │
│             Calls tools automatically                    │
└───────────┬─────────────────────┬───────────────────────┘
            │                     │
   ┌────────▼────────┐  ┌────────▼────────────────┐
   │  10 Hermes Tools │  │  Agentic Workflow       │
   │  define/execute/ │  │  plan → execute →       │
   │  status/edit/... │  │  QA → adjust → deliver  │
   └────────┬────────┘  └────────┬────────────────┘
            │                     │
   ┌────────▼─────────────────────▼──────────────┐
   │         ExecutionSpec (V4 JSON Contract)     │
   │   BudgetGate → SeedPropagator → Validator    │
   └────────────────────┬───────────────────────┘
                        │
   ┌────────────────────▼──────────────────────┐
   │           DAG Engine (Kahn's algo)         │
   │     graph.py → executor.py → state.py     │
   └────────────────────┬──────────────────────┘
                        │
   ┌────────────────────▼──────────────────────┐
   │         Fal.ai Provider (HTTP)             │
   │   flux-dev · clarity-upscaler · img2img    │
   └────────────────────────────────────────────┘
```

---

## Specs

| Version | Focus | Status |
|---------|-------|--------|
| [SPEC_V3.md](SPEC_V3.md) | Intent Router, Version History, Edit Preservation | ✅ Implemented |
| [SPEC_V4.md](SPEC_V4.md) | ExecutionSpec, Budget Gate, Seed Inheritance, Intermediate Validation | ✅ Implemented |

---

## Requirements

- Python 3.10+
- Hermes Agent (latest)
- Fal.ai API key ([get one here](https://fal.ai))
- Gemini API key (for QA/validation features, optional)

---

## Tests

```bash
python3 -m pytest tests/ -v
# 312 passed
```

---

## Built by

[sebaunsa-collab](https://github.com/sebaunsa-collab) — Hermes Agent ecosystem.

Part of the [Hermes](https://github.com/sebaunsa-collab/hermes-agent) project.

---

## License

MIT
