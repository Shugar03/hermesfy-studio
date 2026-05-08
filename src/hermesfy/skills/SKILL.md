---
name: hermesfy-studio
description: >-
  Hermesfy Studio V4 — DAG workflow engine for AI image generation via Fal.ai.
  Plugin registered via entry_points, auto-detected by Hermes Agent.
  Source: /opt/hermesfy-studio/ (active), GitHub: sebaunsa-collab/hermesfy-studio.
tags:
  - hermesfy
  - image-generation
  - fal-ai
  - dag-workflows
  - plugin
required_environment_variables:
  - FAL_API_KEY
optional_environment_variables:
  - GOOGLE_API_KEY
required_commands: []
setup_needed: false
---

# Hermesfy Studio V4 — Complete Guide

## Quick Reference

- **Active install:** `/opt/hermesfy-studio/` (pip installed in hermes-agent venv)
- **GitHub:** `sebaunsa-collab/hermesfy-studio` (master, private)
- **Plugin:** registered via entry_points → `hermesfy.plugin:register`
- **Config:** `plugins.enabled: [hermesfy-studio]` in `~/.hermes/config.yaml`
- **Tests:** 341 passing (includes 27 genmedia provider tests)

## Dependencies

- **genmedia CLI** (required, replaces FalProvider)
  ```bash
  curl https://genmedia.sh/install -fsS | bash
  ```
- **FAL_KEY** or **FAL_API_KEY** environment variable
- Python 3.10+

## After Repo Changes

```bash
cd /opt/hermesfy-studio && git pull origin master
/home/hermes/hermes-agent/venv/bin/python3 -m pip install -e .
```

## Architecture

```
/opt/hermesfy-studio/
├── src/hermesfy/
│   ├── dag/                  # Core engine
│   │   ├── graph.py          # DAG definition, validation, Kahn's algo
│   │   ├── executor.py       # Topological execution (V4: all modules wired)
│   │   ├── state.py          # Node state tracking
│   │   └── quality.py        # QA scoring + auto-adjustment
│   ├── providers/
│   │   ├── genmedia.py      # genmedia CLI provider (NEW — replaces fal.py)
│   │   └── fal.py            # Legacy Fal.ai HTTP provider (deprecated)
│   ├── model_query_engine.py # V5: Dynamic model selection (1333 models indexed)
│   ├── model_selector.py     # V4: Auto-select model by AdType×QualityLevel + V5: select_dynamic()
│   ├── intent_router.py      # V4: Parse intent → structured routing
│   ├── tools/                # 10 Hermes Agent tools
│   ├── reference/            # VRH pipeline
│   │   ├── visual_analyzer.py
│   │   ├── spec_bridge.py
│   │   └── delivery.py
│   ├── skills/               # Skills symlinked to Hermes Agent
│   │   ├── hermesfy-vrh-workflow.md  # VRH gatekeeper + anti-bypass
│   │   ├── fal-model-taxonomy.md     # 12 families, 780 models, prompt patterns
│   │   ├── hermesfy-goldilocks-rule.md
│   │   └── hermesfy-spec-bridge.md
│   ├── data/                 # Cached model index
│   │   └── model_index.json  # 1333 models with capabilities
│   ├── styles/               # YAML style presets
│   ├── composition/          # Text layers, canvas, color grading
│   ├── persistence/          # Workflow save/load (JSON)
│   ├── rendering/canvas.py   # Text canvas visualization
│   ├── execution_spec.py     # V4: Formal JSON contract for generation
│   ├── budget_gate.py        # V4: Hard spending cap ($0.07/flow)
│   ├── seed_propagator.py    # V4: Seed inheritance between nodes
│   ├── intermediate_validator.py  # V4: Step-by-step validation
│   ├── model_selector.py     # V4: Auto-select model by AdType×QualityLevel
│   ├── intent_router.py      # V4: Parse intent → structured routing
│   ├── plugin.py             # Hermes plugin registration (entry_point)
│   └── cli.py                # Standalone CLI (python3 -m hermesfy.cli)
├── dashboard/                # Web dashboard (Antigravity theme)
├── tests/                    # 312 tests
├── setup.sh                  # One-command setup
└── SPEC_V4.md                # V4 Spec
```

## Plugin System

Registered via pip entry_points — Hermes auto-detects on startup:

```yaml
# plugin.yaml
name: hermesfy-studio
version: 0.1.0
entry_point: hermesfy.plugin:register
```

`register(ctx)` registers: 10 tools + 1 skill (hermesfy-guide) + 1 hook (on_session_start).

## CLI

```bash
PYTHONPATH=src python3 -m hermesfy.cli "your prompt"
PYTHONPATH=src python3 -m hermesfy.cli --list-models
PYTHONPATH=src python3 -m hermesfy.cli --status <workflow_id>
```

## Tools (registered with Hermes)

| Tool | Description |
|------|-------------|
| `hermesfy_define_workflow` | Build a DAG from natural language |
| `hermesfy_execute_workflow` | Execute topologically via Fal.ai |
| `hermesfy_workflow_status` | Node states (○ ⏳ ✅ ❌ 🔄) |
| `hermesfy_edit_node` | Edit a node's config |
| `hermesfy_list_models` | List available Fal.ai models |
| `hermesfy_list_templates` | Browse workflow templates |
| `hermesfy_save_workflow` | Save workflow to JSON |
| `hermesfy_load_workflow` | Load workflow from JSON |
| `hermesfy_history` | View generation history |
| `hermesfy_run_agentic_workflow` | Full agentic loop: plan→execute→QA→adjust→deliver |
| `hermesfy_reference_analyze` | **VRH:** Analyze reference image → structured visual spec |

### Registering a new tool (pattern)

```python
# In plugin.py:

# 1. Import
from hermesfy.tools.my_tool import my_tool_handler, MY_TOOL_SCHEMA

# 2. Register
ctx.register_tool(
    name="hermesfy_my_tool",
    toolset="hermesfy",
    description="What it does",
    schema=MY_TOOL_SCHEMA,
    handler=my_tool_handler,
)

# 3. Update the tool count in logger.info()
# 4. Update _on_session_start() tool list string
```

### IMPORTANT: After ANY change to plugin.py or new tools

```bash
cd /opt/hermesfy-studio
/home/hermes/hermes-agent/venv/bin/python3 -m pip install -e .
```

This re-registers the entry_points so Hermes Agent discovers the plugin on next startup.

## V4 Modules (wired into executor.py)

- **ExecutionSpec** — JSON schema contract for every generation request
- **BudgetGate** — Hard cap $0.07/flow, blocks overages
- **SeedPropagator** — Seed inheritance for consistency between steps
- **IntermediateValidator** — Gemini Vision validates between nodes
- **ModelSelector** — Auto-selects model by AdType×QualityLevel
- **IntentRouter** — Parses natural language → structured intent

## FAL Provider (genmedia CLI)

Hermesfy now uses `genmedia` CLI (FAL's official agent tool) instead of direct HTTP calls.

**Provider chain:**
```
GenmediaProvider (genmedia CLI) → FalProvider (legacy HTTP) → MockProvider (dry-run)
```

**Benefits:**
- 1,200+ models auto-discovered (`genmedia models --json`)
- No HTTP handling code (auth, retry, polling, errors)
- 98% less provider code (3,342 → ~400 LOC)

**genmedia commands used:**
- `genmedia run <endpoint> --json --prompt "..." --<param> <value>`
- `genmedia upload <image_path>` — for img2img/inpaint
- `genmedia pricing <endpoint>` — for budget gate
- `genmedia schema <endpoint>` — for model discovery

**Backward compatibility:**
- `FAL_API_KEY` is still supported (mapped to `FAL_KEY`)
- Fallback to legacy `FalProvider` if genmedia not installed
- `execute_workflow` auto-selects best available provider

## V5: Model Intelligence Layer (NEW)

### ModelQueryEngine Scoring Calibration (v1 → v2)

**V1 Pitfall:** Capability-weighted scoring (`supports_mask` = +0.35, `supports_image_input` = +0.25) caused cheap inpainting utilities to outrank quality models. `z-image/turbo/inpaint` ($0.01) ranked #1 for composite tasks over GPT Image 2.

**V2 Fix:** Three-component scoring model found in `model_query_engine.py._score()`:
```
Score = QUALITY(0.40) + TASK_FIT(0.35) + COST(0.15) + SPEED(0.10)
```

| Component | What It Measures | Source |
|-----------|-----------------|--------|
| **QUALITY** | Provider reputation + editorial curation + tags (realism, typography) | Module-level `_CURATED_MODELS`, `_PROVIDER_BONUS` |
| **TASK_FIT** | Category match, capability requirements (hard fail if lacking), content affinity | `_CONTENT_AFFINITY`, `_UTILITY_PATTERNS` |
| **COST** | Non-linear tiers ($0.01=0.95, $0.03=0.85, $0.05=0.70, $0.08=0.50) | `_ESTIMATED_COSTS` |
| **SPEED** | Thinking penalty (-0.7), simple text-to-image bonus (+0.9) | Schema `thinking_level`, `num_input_params` |

**Anti-bonus:** `_UTILITY_PATTERNS` = `["tiling", "material", "character", "lora", "inpaint", ...]` — models matching these get -0.10 QUALITY, hard floor at 0.05 (filtered out).

**Calibration methodology:** Write the expected ranking for 3 test queries, run engine, compare actual vs expected, adjust weights until ranking matches. SDD (SPEC → Implement → Test → Iterate).

```python
from hermesfy.model_query_engine import ModelQueryEngine, TaskSpec

engine = ModelQueryEngine()  # reads model_index.json
results = engine.query(TaskSpec(
    action="edit",          # generate | edit | composite
    reference_count=2,      # 0, 1, 2+
    needs_mask=True,        # for surgical edits
    max_budget=0.10,        # USD
))
# → [RankedModel(score=0.92, reason="Mask-capable, multi-ref(16)..."), ...]
```

**How it works:**
1. **Filters** 1333 models by real capabilities (category, mask, multi-ref, budget, resolution)
2. **Scores** using weighted metrics per task type (context preservation, fidelity, text, cost, speed)
3. **Returns top 5** with scores, estimated costs, and reasons

**Build the index:**
```bash
cd /opt/hermesfy-studio
export FAL_KEY="$FAL_API_KEY"
python3 scripts/build_model_index.py  # ~25 min for 1333 schemas (67 pages + 1319 schema calls)
```

**Index build pitfalls:**
- `s.get("input") or []` NOT `s.get("input", [])` — genmedia schemas can have `"input": null` (returns None, default only fires on missing key)
- Background processes lose PATH — pass full binary path: `GENMEDIA=$(which genmedia)` in shell, then `'${GENMEDIA}'` expands before Python sees it
- FAL rate limits: schema extraction at ~1-2s per model is safe. Don't parallelize without backoff.

### fal-model-taxonomy

Complete taxonomy of 780+ FAL models grouped into 12 families with documented prompting patterns. See `fal-model-taxonomy` skill (symlinked from `src/hermesfy/skills/`).

**Key families:**
| Family | Best For | Prompt Pattern |
|--------|----------|---------------|
| **GPT Image** | Surgical edits, precise instructions | `Change:` / `Preserve:` / `Constraints:` |
| **Seedream** | Multi-image compositing | 4 reference roles (scene, product, style, composition) |
| **Nano Banana** | Semantic editing, thinking modes | `Action + Subject + Style + Constraints` |
| **FLUX** | Generation, high quality | Subject-first hierarchy, HEX codes |
| **SAM 3** | Segmentation → masks | Text-to-mask, bounding boxes |

### VRH Gatekeeper (Anti-Bypass)

The `hermesfy-vrh-workflow` skill now has an **ANTI-BYPASS** checklist that blocks direct genmedia calls when reference images are present:

```
□ FASE 1: ¿Analicé CADA imagen con vision_analyze?
□ FASE 2: ¿Mostré el preview al usuario y esperé su confirmación?
□ ModelSelection: ¿Consulté fal-model-taxonomy?
□ PromptFormat: ¿Usé el formato de la familia del modelo?
□ FASE 3: ¿Planifiqué un DAG multi-step?
```

**CRITICAL DISTINCTION — Generative vs Edit models:**
| Category | What They Do | Examples |
|----------|-------------|----------|
| **GENERATIVE** | Create from scratch. DON'T preserve original. | `flux/schnell`, `flux/dev`, `gpt-image-2` (text-to-image) |
| **EDIT** | Take input image + make PUNTUAL changes. Preserve rest. | `seedream/v4.5/edit`, `gemini-3-pro/edit`, `gpt-image-2/edit`, `nano-banana-pro/edit` |

**Golden Rule:** "Reemplazar X por Y manteniendo todo lo demás" → EDIT models, NEVER generative.

## Model Selection Guide (critical for product fidelity)

**Golden Rule:** FLUX models CANNOT faithfully reproduce specific branded products from text alone — they have no visual reference. When the output MUST look 1:1 like a reference image (logo, specific design, branding), use an EDIT model with the product photo as input, not a text description.

| Model | Product Fidelity | Best For |
|---|---|---|
| `fal-ai/flux/schnell` | ❌ Invents generic versions | Fast text→image, no brand fidelity needed |
| `fal-ai/bytedance/seedream/v4.5/edit` | ✅ **Best for compositing** | Product swap: layout ref + product ref → composite |
| `openai/gpt-image-2/edit` | ✅ **Surgical edits** | Change/Preserve/Constraints format, mask-capable |
| `fal-ai/gemini-3-pro-image-preview/edit` | ⚠️ Good context, adapts colors | Preserves scene, may recolor product |

**Prompt formats that work (from FAL official docs):**
- **GPT Image 2 Edit:** `Change:` / `Preserve:` / `Constraints:`
- **Seedream 4.5:** `Image 1: scene` / `Image 2: product` / `Instruction:`
- **Nano Banana:** `Action + Subject + Style + Constraints`

**Anti-slop rules:**
1. Visual facts > vague adjectives (❌ "stunning masterpiece" → ✅ "overcast daylight, brushed aluminum")
2. One revision per turn
3. Separate change from preserve
4. Wrap literal text in quotes

## Tests

```bash
cd /opt/hermesfy-studio
python3 -m pytest tests/ -v  # 341 passed (27 genmedia + 314 original)
```

## GenmediaProvider End-to-End Test Pattern

To verify genmedia + GenmediaProvider works with real generations:

```bash
cd /opt/hermesfy-studio && export FAL_KEY="$FAL_API_KEY"
/home/hermes/hermes-agent/venv/bin/python3 -c "
import asyncio, sys; sys.path.insert(0, 'src')
from hermesfy.providers.genmedia import GenmediaProvider

async def main():
    p = GenmediaProvider()
    result = await p.generate('image_gen', {
        'prompt': 'test prompt',
        'width': 1024, 'height': 768,
    })
    print(f'URL: {result.url}')
    print(f'Dims: {result.width}x{result.height}')

asyncio.run(main())
"
```

The `generate()` method is **async** — uses `asyncio.create_subprocess_exec` under the hood. Always wrap calls in `asyncio.run()`.

## Pitfalls

### 🚨 ANTI-BYPASS: Always use Hermesfy DAG, NEVER genmedia run directly

When working with FAL image generation/editing, **always route through Hermesfy's DAG executor**, not ad-hoc `genmedia run` CLI calls. The genmedia CLI has no persistence, no audit trail, no workflow history — everything done there is invisible. Hermesfy's `execute()` function + GenmediaProvider gives you all of that for free.

**The DAG has all needed node types already:**
- `reference_image` → `img2img` → `upscale` (or any chain)
- All node types (img2img, upscale, inpaint, outpainting, remove_bg, etc.) work via GenmediaProvider
- Reference resolution (`{{node_id}}`) connects nodes automatically

**BudgetGate default ($0.07) is too low for expensive models.** GPT Image 2 Edit costs $0.12/minimum — always pass `options={"budget": 0.25}` or higher when using premium edit models. The executor blocks nodes that exceed the budget gate silently.

### `num_inference_steps` cap per model

| Model | Max `num_inference_steps` |
|-------|--------------------------|
| `fal-ai/flux/schnell` | **12** |
| `fal-ai/flux/dev` | 50 |
| `fal-ai/nano-banana-2` | varies |

**Error:** `Validation error — num_inference_steps: Input should be less than or equal to 12`

**Fix:** Remove `num_inference_steps` from config for schnell, or set ≤12. Default (omitted) is 4 for schnell — produces high quality regardless. Only use higher steps for dev/kontext models.

### Multi-product compositions with FLUX schnell

FLUX schnell can merge/confuse multiple distinct products in a single prompt (e.g., "Vichy bottle + Quencher tumbler" → hybrid object). For complex multi-object scenes:
- Prefer `fal-ai/flux/dev` or `fal-ai/nano-banana-pro` (better prompt adherence)
- Or break into separate generations + composition step
- Keep prompt focused — fewer competing details = better cohesion

### Test count is 341, not 312

The skill originally listed 312. Actual count: 341 (314 original + 27 genmedia provider tests).

### ANTI-PATTERN: Never bypass Hermesfy with direct genmedia calls

**The mistake:** Using `genmedia run <model> --prompt "..."` directly to test/edit images instead of building a Hermesfy DAG workflow.

**Why it's wrong:**
- Zero persistence — no workflow JSON saved, no history.jsonl entry, no audit trail
- No DAG — can't chain multiple edits, no node state tracking
- User expectation: Hermesfy was built for this. Using genmedia directly makes the plugin dead weight.

**The right way:**
1. Upload image: `genmedia upload <path>` → get CDN URL
2. Build DAG via Hermesfy: `reference_image` → `img2img` → `upscale` → ...
3. Execute via `hermesfy_execute_workflow` or `PYTHONPATH=src python3 -m hermesfy.cli`
4. Workflow auto-saved to `~/.hermes/hermesfy/workflows/<id>.json`

**Recovery when you already ran genmedia directly:** The results exist on FAL CDN but have no Hermesfy trace. Re-upload the output to FAL and feed it as a `reference_image` node in a new DAG.

### Hermesfy node types are model-agnostic

The `img2img`, `upscale`, `inpaint`, and `image_gen` node types accept **any** FAL model in their `model` config field — not just the defaults listed in `_NODE_DEFAULT_MODELS`.

| Node Type | Default Model | Also Works With |
|-----------|--------------|-----------------|
| `img2img` | `fal-ai/flux/dev/image-to-image` | `openai/gpt-image-2/edit`, `fal-ai/ideogram/v3/edit`, `fal-ai/bytedance/seedream/v4.5/edit`, `fal-ai/hunyuan-image/v3/instruct/edit`, `fal-ai/ideogram/v3/remix`, etc. |
| `upscale` | `fal-ai/clarity-upscaler` | `fal-ai/topaz/upscale/image`, `fal-ai/ideogram/upscale`, `fal-ai/real-esrgan` |
| `inpaint` | `fal-ai/flux/inpainting` | `fal-ai/ideogram/v3/edit` (with mask_url) |
| `image_gen` | `fal-ai/flux/schnell` | `openai/gpt-image-2`, `fal-ai/flux-pro/kontext`, `fal-ai/ideogram/v3`, etc. |

The genmedia provider calls `genmedia run <model>` — it passes the model string verbatim. Any model that `genmedia run` supports works in Hermesfy.

### Ideogram V3 Layerize Text does NOT fit image→image DAGs

`fal-ai/ideogram/v3/layerize-text` outputs:
- `image` — background with text **removed** (not improved)
- `text_containers` — hierarchical JSON of text elements
- `text_html` — overlay HTML for recompositing

It separates text from image for external editing — it does NOT produce an image with improved text. Cannot be used as a final node in an image→image pipeline. For text improvement in a DAG, use `fal-ai/ideogram/v3/remix` or `fal-ai/ideogram/v3/edit` with a text mask instead.

### Model-specific genmedia quirks

- **FLUX Kontext:** expects `image_url` (singular), NOT `image_urls`. Most other edit models use `image_urls` (plural/array).
- **Seedream 4.5 Edit:** has minimum resolution 1920×1920. Smaller inputs get upscaled, losing original aspect ratio. Set `image_size` explicitly to preserve proportions.
- **GPT Image 2 Edit:** supports `Change:` / `Preserve:` / `Constraints:` prompt format. Brand names may trigger content policy filters. **Known to be slow (60-180s) — needs timeout ≥360s.**
- **Ideogram V3 Edit:** requires `mask_url` with identical dimensions to `image_url` — it's inpainting-only, not prompt-guided edit.

### GenmediaProvider Critical Fixes (May 2026)

These fixes are in `src/hermesfy/providers/genmedia.py` and MUST be preserved across updates:

**1. `image_urls` vs `image_url` auto-detection:**
Different FAL models expect different parameter names for image input. The provider now auto-detects based on model family:

```python
_IMAGE_URL_SINGULAR_FAMILIES = [
    "fal-ai/flux-pro/kontext",
    "fal-ai/flux/redux",
    "fal-ai/ideogram/",
    "fal-ai/flux/dev/image-to-image",
    "fal-ai/topaz/",
    "fal-ai/clarity-upscaler",
]

def _model_uses_image_url_singular(model: str) -> bool:
    for family in _IMAGE_URL_SINGULAR_FAMILIES:
        if model.startswith(family):
            return True
    return False
```

In `_build_args()`, the image input line uses this check:
```python
if _model_uses_image_url_singular(model):
    args.extend(["--image_url", image_url])
else:
    args.extend(["--image_urls", json.dumps([image_url])])
```

**Without this fix:** GPT Image 2 Edit, Seedream, Hunyuan, Nano Banana all fail with `Validation error — image_urls: Field required` because they expect plural. FLUX Kontext, Ideogram, and Topaz use singular. The auto-detection handles both.

**2. Timeout for slow models:**
`DEFAULT_TIMEOUT` was increased from 180s to **360s**. GPT Image 2 Edit needs 60-180s and was being killed prematurely. Fast models (Seedream, Hunyuan, FLUX) complete in 10-30s regardless.

**3. Speed benchmark (verified May 2026):**
| Method | Topaz Upscale Time | Overhead |
|--------|-------------------|----------|
| `genmedia run` direct | 14.1s | 0% |
| Hermesfy Provider (warm) | ~14.2s | ~100ms |
| Hermesfy Provider (cold import) | 18.5s | +4.4s (Python startup) |

The genmedia binary is identical — overhead is negligible subprocess spawn + JSON parse (~100ms). No structural slowdown. The cold-start Python import is one-time per session.
