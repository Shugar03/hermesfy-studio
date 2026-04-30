# Hermesfy Studio

<img width="1248" height="832" alt="Generated Image April 30, 2026 - 2_18AM" src="https://github.com/user-attachments/assets/a8300294-4a49-4e8b-a055-0ede3c3415f4" />

> **Lite DAG workflow engine for Hermes Agent.** Define image generation workflows, execute them topologically via Fal.ai, edit nodes on the fly — all through natural language in your Hermes chat.

## Quick Install

```bash
pip install git+https://github.com/<your-username>/hermesfy-studio.git
```

Or clone and install locally:

```bash
git clone https://github.com/<your-username>/hermesfy-studio.git
cd hermesfy-studio
pip install -e .
```

## Configure

```bash
export FAL_API_KEY=your-fal-ai-key
```

Get one at [fal.ai](https://fal.ai).

## Verify

```bash
cd hermesfy-studio
python -m pytest tests/ -v
```

Expected: **140 tests passing**.

## Usage in Hermes

Once installed, Hermes auto-discovers the plugin. Available tools:

| Tool | What it does |
|------|-------------|
| `hermesfy_define_workflow` | Define a DAG workflow from nodes and edges |
| `hermesfy_execute_workflow` | Execute the workflow topologically via Fal.ai |
| `hermesfy_workflow_status` | Show a text canvas with node states (○ ⏳ ✅ ❌ 🔄) |
| `hermesfy_edit_node` | Edit a node's config and optionally re-execute |
| `hermesfy_list_models` | List all available Fal.ai models |
| `hermesfy_save_workflow` | Save workflow to a JSON file |
| `hermesfy_load_workflow` | Load workflow from a JSON file |

### Natural Language Example

> "Create a workflow with a text prompt 'cyberpunk city at night' using flux-schnell, then upscale the result"

The LLM will use `hermesfy_define_workflow` to build the DAG, then `hermesfy_execute_workflow` to run it.

## Architecture

```
┌─────────────────────────────────┐
│       Hermesfy Studio            │
│  ┌─────────────────────────────┐ │
│  │  DAG Engine (Kahn's algo)   │ │
│  │  graph.py → executor.py     │ │
│  ├─────────────────────────────┤ │
│  │  Provider (Fal.ai HTTP)     │ │
│  │  flux, upscale, img2img     │ │
│  ├─────────────────────────────┤ │
│  │  7 Hermes Tools             │ │
│  │  define / execute / status  │ │
│  │  edit / list / save / load  │ │
│  ├─────────────────────────────┤ │
│  │  Text Canvas + Styles       │ │
│  │  4 presets (YAML)           │ │
│  └─────────────────────────────┘ │
└─────────────────────────────────┘
```

## Node Types

| Type | Purpose |
|------|---------|
| `text_prompt` | Input prompt for generation |
| `image_gen` | Generate image via Fal.ai (flux, etc.) |
| `img2img` | Image-to-image transformation |
| `upscale` | Upscale image via Fal.ai clarity-upscaler |
| `seed` | Fixed seed for reproducible generation |

## Style Presets

```yaml
# cinematic, anime, photorealistic, digital-art
# Load: hermesfy_define_workflow(..., style="cinematic")
```

## Requirements

- Python 3.10+
- Hermes Agent (latest)
- Fal.ai API key

## License

MIT
