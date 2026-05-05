# Hermesfy Studio

DAG workflow engine for AI image generation, running natively inside Hermes Agent.

## What is Hermesfy?

Hermesfy Studio allows you to define, execute, and edit image generation workflows using a **Directed Acyclic Graph (DAG)**. You describe what you want in natural language, Hermesfy builds a workflow, executes it step by step, and shows you a text-based canvas with live status.

## Architecture

```
Natural Language → DAG Definition → Execute → Quality Gates → Edit/Re-run
                         │              │
                    Hermes Tools    Fal.ai API
                    (7 tools)       (flux, upscale, etc.)
```

## Available Tools

| Tool | When to use |
|------|------------|
| `hermesfy_define_workflow` | Create a new workflow from nodes + edges |
| `hermesfy_execute_workflow` | Run the workflow — generates images via Fal.ai |
| `hermesfy_workflow_status` | Show a text canvas with node states |
| `hermesfy_edit_node` | Modify a node's prompt/model and optionally re-execute |
| `hermesfy_list_models` | Browse all available Fal.ai models |
| `hermesfy_save_workflow` | Save workflow to a JSON file for later |
| `hermesfy_load_workflow` | Load a previously saved workflow |
| `hermesfy_reference_analyze` | Analyze a reference image → StructuredSpec (VRH Fase 1) |

## VRH Pipeline (Visual Reference Harness)

Hermesfy puede analizar una imagen de referencia y generar prompts estructurados
que preservan el estilo, layout, paleta, iluminación y composición exactos.

```
[Telegram img] → VisualAnalyzer → StructuredSpec
                                      ↓
                               Goldilocks Rule (fidelity dinámico)
                                      ↓
                               Preview (mostrar al usuario)
                                      ↓
                               SpecBridge → ExecutionSpec → DAG → Fal.ai → Delivery
```

### Skills VRH

- **[hermesfy-spec-bridge](hermesfy-spec-bridge.md)** — Traduce StructuredSpec a ExecutionSpec (prompt estructurado + parámetros de generación)
- **[hermesfy-goldilocks-rule](hermesfy-goldilocks-rule.md)** — Fidelity dinámico según keywords del usuario ("exactamente igual" → 0.95, "ignorá" → 0.25)
- **[hermesfy-vrh-preview](hermesfy-vrh-preview.md)** — Preview del spec antes de generar para validación del usuario

### Módulo `reference/`

El código está en `src/hermesfy/reference/`:
- `visual_analyzer.py` — StructuredSpec dataclass + VisionAnalyzer + JSON parser
- `spec_bridge.py` — SpecBridge con Goldilocks Rule + preview_text()
- `delivery.py` — Maneja la entrega del resultado generado
- `templates/vision_prompt.md` — Template del prompt de visión para analizar imágenes

## Node Types

| Type | Purpose | Required config |
|------|---------|----------------|
| `text_prompt` | Text input for generation | `prompt` |
| `image_gen` | Generate image via Fal.ai | `prompt`, `model` |
| `img2img` | Image-to-image transformation | `prompt`, `model`, `image_url` (from upstream node) |
| `upscale` | Upscale image (clarity-upscaler) | `image_url` (from upstream node) |
| `seed` | Fixed seed for reproducibility | `seed` (integer) |

## Models (Fal.ai)

- **flux/schnell**: Fastest, 1-2s, good quality
- **flux/dev**: Balanced speed/quality, 3-5s
- **flux-pro**: Best quality, 5-10s
- **flux-depth**: Depth-aware generation
- **clarity-upscaler**: AI upscaling

## Style Presets

You can apply a style when defining a workflow to get consistent aesthetics:

- `cinematic` — Dramatic lighting, 8k, photorealistic
- `anime` — Anime/manga style, vibrant colors
- `photorealistic` — Ultra-realistic, detailed textures
- `digital-art` — Digital painting, concept art style

## Text Canvas

When you run `hermesfy_workflow_status`, you get a visual representation:

```
Workflow: cyberpunk-city [id: wf_abc123]
○ text_prompt — "cyberpunk city at night"
├── ⏳ image_gen — flux/schnell (generating...)
└── ○ upscale — waiting for image_gen
```

State emojis: ○ pending, ⏳ running, ✅ completed, ❌ failed, 🔄 retrying, 💀 quality exhausted

## Quality Gates

You can configure quality checks per node:
```json
{
  "max_retries": 3,
  "evaluator": "basic"
}
```

If a generation fails quality checks, Hermesfy auto-retries up to `max_retries` times.

## Workflow Pattern

The typical workflow for generating an image:

1. Define: `hermesfy_define_workflow` — create nodes with text_prompt → image_gen → upscale
2. Execute: `hermesfy_execute_workflow` — runs the DAG, returns image URLs
3. Status: `hermesfy_workflow_status` — check progress via canvas
4. Edit: `hermesfy_edit_node` — tweak prompt or model, re-run
5. Save: `hermesfy_save_workflow` — persist for later

## Important Notes

- All workflows are **ephemeral in memory** during a session. Save with `hermesfy_save_workflow` to persist.
- Nodes execute in **topological order** (dependencies first).
- A failed node **does not crash the workflow** — downstream nodes that depend on it will be skipped.
- You need `FAL_API_KEY` set in the environment for real image generation.
- Use `hermesfy_list_models` to see what models are currently available.
