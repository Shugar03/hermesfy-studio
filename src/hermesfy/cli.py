"""Hermesfy Studio CLI — standalone usage without Hermes Agent."""

import sys
import json
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m hermesfy.cli \"your prompt here\"")
        print("   or: python3 -m hermesfy.cli --status <workflow_id>")
        sys.exit(1)

    # Load .env
    from pathlib import Path
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    arg = sys.argv[1]

    if arg == "--status":
        if len(sys.argv) < 3:
            print("Usage: python3 -m hermesfy.cli --status <workflow_id>")
            sys.exit(1)
        from hermesfy.tools.workflow_status import workflow_status_tool
        result = workflow_status_tool(sys.argv[2])
        print(json.dumps(result, indent=2))
        return

    if arg == "--list-models":
        from hermesfy.providers.registry import get_models
        models = get_models()
        for m in models:
            print(f"  {m['endpoint']:50s} {m['name']}")
        return

    # Default: treat as prompt → agentic workflow
    prompt = arg
    print(f"[hermesfy] Running agentic workflow: {prompt}")

    from hermesfy.tools.run_agentic_workflow import run_agentic_workflow
    result = run_agentic_workflow(prompt=prompt)

    if result.get("success"):
        print(f"\n✅ Done! {len(result.get('images', []))} image(s) generated.")
        for img in result.get("images", []):
            print(f"  → {img}")
    else:
        print(f"\n❌ Failed: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
