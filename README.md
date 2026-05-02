     1|# Hermesfy Studio
     2|
     3|<img width="1344" height="768" alt="Generated Image April 30, 2026 - 2_22AM" src="https://github.com/user-attachments/assets/bd283b8d-611e-4a7e-8025-3748d1b31fec" />
     4|
     5|> **A DAG workflow engine for AI image generation — built for Hermes Agent.**
     6|>
     7|> Define complex multi-step image pipelines as directed acyclic graphs. Execute them topologically via Fal.ai. Let an AI agent plan, generate, evaluate, and refine your images autonomously. All through natural language in your Hermes chat.
     8|
     9|---
    10|
    11|## Why Hermesfy?
    12|
    13|Most AI image generation tools give you a text box and a "generate" button. That works for single images — but what about the 90% of real workflows that aren't that simple?
    14|
    15|- **Batch generation** — create 50 product variants while you sleep
    16|- **Multi-step pipelines** — generate → upscale → remove background → deliver
    17|- **Iterative refinement** — generate, evaluate with vision AI, adjust prompt, regenerate
    18|- **Consistent style** — apply cinematic/anime/photorealistic presets across entire batches
    19|- **Budget control** — hard spending cap per flow ($0.07 default)
    20|- **Seed consistency** — automatic seed inheritance between pipeline steps
    21|
    22|Hermesfy turns these into composable DAG workflows. Each node is a step. Each edge is a data dependency. The engine resolves the graph, executes in parallel where possible, and delivers results when done.
    23|
    24|The key insight: **the LLM becomes the workflow designer**. You describe what you want in plain English. Hermes builds the DAG, executes it, and shows you the results — all without you touching a single node configuration.
    25|
    26|---
    27|
    28|## Quick Start
    29|
    30|```bash
    31|git clone https://github.com/sebaunsa-collab/hermesfy-studio.git
    32|cd hermesfy-studio
    33|bash setup.sh
    34|```
    35|
    36|The `setup.sh` script will:
    37|1. ✅ Create a Python virtual environment
    38|2. ✅ Install hermesfy-studio in editable mode (with all deps)
    39|3. ✅ Create required directories (cache/, output/, logs/)
    40|4. ✅ Create `.env` file (edit with your FAL API key)
    41|5. ✅ Fetch the latest models from FAL.ai (48+ models)
    42|6. ✅ Show dashboard instructions
    43|
    44|Then generate your first image:
    45|```bash
    46|source venv/bin/activate
    47|export FAL_API_KEY=***
    48|python3 -m hermesfy.cli "haceme un ad de Nike con fondo negro"
    49|```
    50|
    51|---
    52|
    53|## What's Inside
    54|
    55|```
    56|hermesfy-studio/
    57|├── src/hermesfy/
    58|│   ├── dag/                  # Core engine
    59|│   │   ├── graph.py          # DAG definition, validation, Kahn's algo
    60|│   │   ├── executor.py       # Topological execution engine
    61|│   │   ├── state.py          # Node state tracking
    62|│   │   └── quality.py        # QA scoring + auto-adjustment
    63|│   ├── providers/
    64|│   │   └── fal.py            # Fal.ai HTTP provider
    65|│   ├── tools/                # 10 Hermes Agent tools
    66|│   ├── styles/               # YAML style presets
    67|│   ├── persistence/          # Workflow save/load (JSON)
    68|│   ├── execution_spec.py     # V4: Formal JSON contract for generation
    69|│   ├── budget_gate.py        # V4: Hard spending cap ($0.07/flow)
    70|│   ├── seed_propagator.py    # V4: Seed inheritance between nodes
    71|│   ├── intermediate_validator.py  # V4: Step-by-step validation
    72|│   └── plugin.py             # Hermes plugin registration
    73|├── dashboard/                # Web dashboard (Antigravity theme)
    74|├── tests/                    # 312 tests, all green
    75|├── setup.sh                  # One-command setup
    76|├── SPEC_V3.md                # V3 Spec (Intent Router, Versions, Edit)
    77|└── SPEC_V4.md                # V4 Spec (Protocol-Driven Execution)
    78|```
    79|
    80|---
    81|
    82|## V4: Protocol-Driven Execution
    83|
    84|The latest version formalizes the contract between the LLM and the backend:
    85|
    86|### ExecutionSpec — JSON Schema
    87|Every generation request is a validated JSON contract. The pipeline rejects anything non-conforming.
    88|
    89|```python
    90|from hermesfy.execution_spec import ExecutionSpec
    91|
    92|# Simple single-step
    93|spec = ExecutionSpec.simple("professional photo of Nike sneaker")
    94|
    95|# Draft → Refine (2-step)
    96|spec = ExecutionSpec.draft_then_refine("luxury skincare bottle")
    97|
    98|# Full control
    99|spec = ExecutionSpec.from_dict({
   100|    "routing_decision": {
   101|        "intent_category": "product",
   102|        "action": "generate",
   103|        "target_model": "fal-ai/flux/dev",
   104|        "budget_estimation": 0.045,
   105|        "priority": "quality"
   106|    },
   107|    "dag_workflow": {
   108|        "steps": [
   109|            {"node_id": 1, "action": "base_generation", "model": "fal-ai/flux/schnell", "params": {"width": 1024, "height": 1024}},
   110|            {"node_id": 2, "action": "latent_refiner", "model": "fal-ai/flux/1.1-pro", "params": {"denoising_strength": 0.35}}
   111|        ]
   112|    },
   113|    "prompt_metadata": {"cleaned_prompt": "luxury skincare bottle on marble"}
   114|})
   115|```
   116|
   117|### Budget Gate — Cost Control
   118|Hard cap per flow. Every FAL.ai call passes through the gate before execution.
   119|
   120|```python
   121|from hermesfy.budget_gate import BudgetGate, BudgetExceeded
   122|
   123|gate = BudgetGate(max_budget=0.07)
   124|if gate.record_and_check("fal-ai/flux/schnell"):  # $0.003
   125|    # ... generate ...
   126|    gate.record_and_check("fal-ai/flux/1.1-pro")  # $0.04
   127|else:
   128|    raise BudgetExceeded(gate.remaining(), 0.07)
   129|```
   130|
   131|### Seed Propagation — Consistency Between Steps
   132|The seed from node 1 is automatically inherited by node 2+. No wasted credits on inconsistent compositions.
   133|
   134|```python
   135|from hermesfy.seed_propagator import SeedPropagator
   136|
   137|prop = SeedPropagator()
   138|seed = prop.resolve_seed(-1)           # auto-generate
   139|params = prop.propagate(seed, {...})   # inject seed into next step
   140|```
   141|
   142|### Intermediate Validation — Validate Between Nodes
   143|After each generation step, validate the image before proceeding. Bad images get caught early.
   144|
   145|```python
   146|from hermesfy.intermediate_validator import IntermediateValidator
   147|
   148|validator = IntermediateValidator(api_key="gemini_key")
   149|result = validator.validate_step(
   150|    step_result={"image_path": "/cache/fal/gen_xxx.png"},
   151|    original_prompt="professional photo of sneaker",
   152|)
   153|if not result.should_continue:
   154|    # Abort — don't waste credits on next step
   155|```
   156|
   157|---
   158|
   159|## Tools
   160|
   161|Hermesfy registers **10 tools** with Hermes Agent:
   162|
   163|| Tool | Description |
   164||------|-------------|
   165|| `hermesfy_define_workflow` | Build a DAG from natural language |
   166|| `hermesfy_execute_workflow` | Execute topologically via Fal.ai |
   167|| `hermesfy_workflow_status` | Node states (○ ⏳ ✅ ❌ 🔄) |
   168|| `hermesfy_edit_node` | Edit a node's config |
   169|| `hermesfy_list_models` | List available Fal.ai models |
   170|| `hermesfy_list_templates` | List workflow templates |
   171|| `hermesfy_save_workflow` | Save workflow to JSON |
   172|| `hermesfy_load_workflow` | Load workflow from JSON |
   173|| `hermesfy_history` | View generation history |
   174|| **`hermesfy_run_agentic_workflow`** | **Full agentic loop: plan → execute → QA → adjust → deliver** |
   175|
   176|---
   177|
   178|## Usage
   179|
   180|### Agentic (recommended)
   181|
   182|Just tell Hermes what you want:
   183|
   184|> *"Generate a photo of a luxury skincare bottle on marble, white background, remove the background when done"*
   185|
   186|Hermes calls `hermesfy_run_agentic_workflow`. It handles everything:
   187|
   188|1. **Plan** — selects the right workflow pattern + model
   189|2. **Execute** — generates the image via Fal.ai
   190|3. **QA** — Gemini Vision analyzes the result
   191|4. **Adjust** — if quality < threshold, rewrites prompt and re-generates
   192|5. **Deliver** — returns the final image + QA history
   193|
   194|### Manual (for power users)
   195|
   196|```python
   197|hermesfy_define_workflow(
   198|    nodes=[
   199|        {"id": "prompt", "type": "text_prompt", "config": {"prompt": "cyberpunk city at night"}},
   200|        {"id": "gen", "type": "image_gen", "config": {"model": "flux-dev", "width": 1024, "height": 1024}},
   201|        {"id": "upscale", "type": "upscale", "config": {"model": "clarity-upscaler", "scale": 2}},
   202|    ],
   203|    edges=[
   204|        {"source": "prompt", "target": "gen"},
   205|        {"source": "gen", "target": "upscale"},
   206|    ]
   207|)
   208|hermesfy_execute_workflow()
   209|```
   210|
   211|---
   212|
   213|## Dashboard
   214|
   215|A web dashboard for visual workflow management:
   216|
   217|```bash
   218|cd dashboard && python3 -m http.server 8090
   219|# Open http://localhost:8090
   220|```
   221|
   222|Dark-mode "Antigravity" theme — deep navy with mint/cyan neon accents, glassmorphism panels, CRT scanline aesthetic.
   223|
   224|---
   225|
   226|## Architecture
   227|
   228|```
   229|┌─────────────────────────────────────────────────────────┐
   230|│                  Hermes Agent (LLM)                      │
   231|│             Interprets natural language                  │
   232|│             Calls tools automatically                    │
   233|└───────────┬─────────────────────┬───────────────────────┘
   234|            │                     │
   235|   ┌────────▼────────┐  ┌────────▼────────────────┐
   236|   │  10 Hermes Tools │  │  Agentic Workflow       │
   237|   │  define/execute/ │  │  plan → execute →       │
   238|   │  status/edit/... │  │  QA → adjust → deliver  │
   239|   └────────┬────────┘  └────────┬────────────────┘
   240|            │                     │
   241|   ┌────────▼─────────────────────▼──────────────┐
   242|   │         ExecutionSpec (V4 JSON Contract)     │
   243|   │   BudgetGate → SeedPropagator → Validator    │
   244|   └────────────────────┬───────────────────────┘
   245|                        │
   246|   ┌────────────────────▼──────────────────────┐
   247|   │           DAG Engine (Kahn's algo)         │
   248|   │     graph.py → executor.py → state.py     │
   249|   └────────────────────┬──────────────────────┘
   250|                        │
   251|   ┌────────────────────▼──────────────────────┐
   252|   │         Fal.ai Provider (HTTP)             │
   253|   │   flux-dev · clarity-upscaler · img2img    │
   254|   └────────────────────────────────────────────┘
   255|```
   256|
   257|---
   258|
   259|## Specs
   260|
   261|| Version | Focus | Status |
   262||---------|-------|--------|
   263|   264|| [SPEC_V4.md](SPEC_V4.md) | ExecutionSpec, Budget Gate, Seed Inheritance, Intermediate Validation | ✅ Implemented |
   265|
   266|---
   267|
   268|## Requirements
   269|
   270|- Python 3.10+
   271|- Hermes Agent (latest)
   272|- Fal.ai API key ([get one here](https://fal.ai))
   273|- Gemini API key (for QA/validation features, optional)
   274|
   275|---
   276|
   277|## Tests
   278|
   279|```bash
   280|python3 -m pytest tests/ -v
   281|# 312 passed
   282|```
   283|
   284|---
   285|
   286|## Built by
   287|
   288|[sebaunsa-collab](https://github.com/sebaunsa-collab) — Hermes Agent ecosystem.
   289|
   290|Part of the [Hermes](https://github.com/sebaunsa-collab/hermes-agent) project.
   291|
   292|---
   293|
   294|## License
   295|
   296|MIT
   297|