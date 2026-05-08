---
name: fal-model-prompt-formats
description: >-
  FAL.ai model-specific prompt engineering formats. Each of FAL's 1200+ models
  has its own optimal prompt structure. THIS SKILL ENSURES the correct format
  is used per model instead of one-size-fits-all creative paragraphs.
  Covers: GPT Image 2 Edit (Change/Preserve/Constraints), Seedream (reference
  roles), mask-based editing pipeline, anti-slop rules, and where to find
  official docs for every model.
---

# FAL.ai Model-Specific Prompt Formats

## ⛔ THE CARDINAL RULE

**Never use the same prompt format across different models.**
Each of FAL's 1200+ models has its own optimal structure documented by FAL.
Before generating with ANY model, check its prompt guide.

## GPT Image 2 Edit — Change/Preserve/Constraints

Source: https://fal.ai/learn/tools/prompting-gpt-image-2

```
Change:
[exactly what should change]

Preserve:
[face, identity, pose, lighting, framing, background, geometry, text, layout]

Constraints:
[no extra objects, no redesign, no logo drift, no watermark]
```

**Key rules:**
- Separate change from preserve — NEVER merge them into one paragraph
- Repeat the preserve list each iteration to reduce drift
- Label reference images by role: "Image 1: base scene. Image 2: product reference."
- For masking: pass `mask_image_url` — white regions = edit zone, everything else = pixel-perfect preservation

## GPT Image 2 Generation — Scene/Subject/Details/UseCase/Constraints

```
Scene:
[where this happens, time of day, background, environment]

Subject:
[who or what is the main focus]

Important details:
[materials, clothing, texture, lighting, camera angle, lens feel, composition, mood]

Use case:
[editorial photo / product mockup / poster / UI screen / infographic / concept frame]

Constraints:
[no watermark / no logos / no extra text / preserve face / preserve layout]
```

## Seedream 4.5 — Reference Roles

Source: https://fal.ai/learn/devs/seedream-v4-5-prompt-guide

Seedream supports 4 reference roles. Assign each uploaded image to one:
- **Character reference** — face, hair, body
- **Style reference** — lighting, color treatment, aesthetic
- **Palette reference** — color palette
- **Composition reference** — layout, framing

Example:
```
Use the product from Image 1 (character reference),
the lighting and color from Image 2 (style reference),
the red-burgundy palette from Image 3 (palette reference),
and the centered composition from Image 4 (composition reference).
```

## Nano Banana / Gemini Edit

Source: Google Nano Banana tutorials

Formula: **Action + Subject + Style/Lighting + Scene/Constraints**

```
Change the color of X to Y.
Keep the same lighting, background, composition, and every other detail.
Only modify the specified element.
```

## Anti-Slop Rules (ALL models)

From FAL's official guide:

| ❌ Don't use | ✅ Use instead |
|---|---|
| stunning, incredible, epic, masterpiece | overcast daylight, brushed aluminum, chipped paint |
| premium, gorgeous, insane detail | clean kerning, 50mm feel, soft bounce light |
| more realistic, more stylish | change only X, keep everything else the same |
| one giant paragraph | structured blocks with line breaks |

1. **Visual facts over vague praise** — describe materials, not vibes
2. **In edits, separate change from preserve** — two-column logic
3. **One revision per turn** — "Make the light warmer. Keep everything else the same."
4. **Wrap literal text in quotes or ALL CAPS**
5. **Order matters** — most important elements FIRST

## Mask-Based Editing Pipeline

For surgical edits where precision matters:

```
Step 1: SAM 3 segment the target object
  → genmedia run fal-ai/sam-3/image
  → --prompt "white dropper bottle"  (descriptive text prompt)
  → Returns mask image + bounding boxes

Step 2: Edit with mask
  → genmedia run openai/gpt-image-2/edit
  → --image_urls [layout_ref, subject_ref]
  → --mask_url <mask_from_step_1>
  → --prompt (Change/Preserve/Constraints format)

Step 3: Verify
  → vision_analyze on output
  → Check: background preserved? Product swapped correctly?
```

**IMPORTANT:** GPT Image inpainting with mask does NOT do pixel-level mask replacement
(like DALL-E 2 did). It uses a "soft mask" with total image recreation BUT constrained
to the masked region. The FAL docs say: "white regions of the mask indicate the areas
to edit; everything outside remains pixel-perfect."

## How to Find Prompt Formats for ANY FAL Model

### Method 1: FAL's published guides
```
https://fal.ai/learn/tools/prompting-<model-slug>
https://fal.ai/learn/devs/<model-slug>-prompt-guide
```

### Method 2: Model page on FAL
```
https://fal.ai/models/<endpoint-id>
```
Check for "Prompting Guide" or "Documentation" sections.

### Method 3: Brave Search
```
"<model name> prompt guide" site:fal.ai
"<model name> prompting" site:byteplus.com
```

### Method 4: Check genmedia schema for parameters
```bash
genmedia schema <endpoint-id> --json
```
Parameters reveal what the model accepts — but NOT how to structure prompts.

## Credits

This skill was built after Sherman caught me using creative/verbose prompts across
all models (FLUX, GPT Image 2, Seedream, Nano Banana, Gemini) with identical format.
Each model needs its own format. The difference between failure and success was
using the correct structure per model.
