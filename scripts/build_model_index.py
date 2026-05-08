"""Build the FAL model index by scanning genmedia models and schemas."""
import subprocess, json, os, re, sys

GENMEDIA = "/home/hermes/.local/bin/genmedia"
env = {"FAL_KEY": os.environ.get("FAL_API_KEY", ""), "PATH": os.environ.get("PATH", "")}

# Load all models
print("📥 Loading models...", flush=True)
all_models = []
cursor = None
page = 0
while True:
    cmd = [GENMEDIA, "models", "--json"]
    if cursor:
        cmd += ["--cursor", cursor]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env)
    if r.returncode != 0:
        print(f"  Stop: {r.stderr[:100]}")
        break
    d = json.loads(r.stdout)
    batch = d.get("models", [])
    if not batch:
        break
    all_models.extend(batch)
    page += 1
    if not d.get("has_more"):
        break
    cursor = d.get("next_cursor")

print(f"✅ Loaded {len(all_models)} models in {page} pages", flush=True)

if not all_models:
    print("❌ No models loaded. Aborting.")
    sys.exit(1)

# Index models
print("🔍 Extracting schemas...", flush=True)
index = {}
total = len(all_models)

for i, m in enumerate(all_models):
    eid = m.get("endpoint_id", "")
    if not eid:
        continue

    try:
        sr = subprocess.run(
            [GENMEDIA, "schema", eid, "--json"],
            capture_output=True, text=True, timeout=12, env=env,
        )
        if sr.returncode != 0:
            continue
        s = json.loads(sr.stdout)
    except Exception:
        continue

    if s is None:
        continue

    ins = [p.get("name", "") for p in (s.get("input") or [])]
    
    caps = {
        "endpoint_id": eid,
        "name": m.get("name", ""),
        "category": m.get("category", ""),
        "provider": eid.split("/")[0] if "/" in eid else "unknown",
        "tags": m.get("tags", []),
        "supports_image_input": bool(any("image" in n.lower() for n in ins)),
        "supports_mask": bool(any("mask" in n.lower() for n in ins)),
        "supports_prompt": "prompt" in ins,
        "supports_multiple_refs": False,
        "supports_seed": "seed" in ins,
        "supports_thinking": "thinking_level" in ins,
        "supports_strength": "strength" in ins,
        "max_resolution": "1K",
    }

    # Multiple refs
    for p in (s.get("input") or []):
        ptype = str(p.get("type", ""))
        if "array" in ptype and "image" in p.get("name", "").lower():
            caps["supports_multiple_refs"] = True
            break

    # Resolution
    for p in (s.get("input") or []):
        dsc = p.get("description", "")
        if "4K" in dsc or "4k" in dsc:
            caps["max_resolution"] = "4K"
            break
        if "2K" in dsc or "2k" in dsc:
            caps["max_resolution"] = "2K"

    # Max refs
    for p in (s.get("input") or []):
        if "image" in p.get("name", "").lower():
            nums = [int(n) for n in re.findall(r"\b(\d+)\b", p.get("description", "")) if 2 <= int(n) <= 100]
            if nums:
                caps["max_reference_images"] = max(nums)
                break

    index[eid] = caps

    if (i + 1) % 200 == 0:
        print(f"  {i + 1}/{total} ({len(index)} indexed)", flush=True)

print(f"✅ Indexed {len(index)} models", flush=True)

# Save
os.makedirs("src/hermesfy/data", exist_ok=True)
with open("src/hermesfy/data/model_index.json", "w") as f:
    json.dump(index, f, indent=2)
print(f"💾 Saved to src/hermesfy/data/model_index.json", flush=True)
