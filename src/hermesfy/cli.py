"""Hermesfy Studio CLI — standalone usage without Hermes Agent."""

import sys
import json
import os

USAGE = """Usage: python3 -m hermesfy.cli [OPTIONS] "your prompt here"

Options:
  --help          Show this help message
  --list-models   List available Fal.ai models
  --status ID     Show workflow status by ID
"""

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(USAGE)
        sys.exit(0)

    arg = sys.argv[1]

    if arg == "--status":
        if len(sys.argv) < 3:
            sys.exit(1)
        from hermesfy.tools.workflow_status import workflow_status
        print(workflow_status(sys.argv[2]))
        return

    if arg == "--list-models":
        from hermesfy.providers.registry import get_models
        for m in get_models():
            print(f"  {m['endpoint']:50s} {m['name']}")
        return

    # Default: agentic workflow
    from hermesfy.tools.run_agentic_workflow import run_agentic_workflow
    print(run_agentic_workflow(description=arg))

if __name__ == "__main__":
    main()
