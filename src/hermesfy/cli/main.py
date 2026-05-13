"""Hermesfy CLI — Thin HTTP client for the Hermesfy DAG workflow engine.

Console script 'hermesfy' with subcommands:
    nodes       List nodes in current workflow
    info        Show workflow metadata
    graph       Display DAG graph structure
    context     Show session context
    create      Create a new workflow from JSON
    connect     Connect two nodes with an edge
    set         Set workflow-level config
    run         Run a single node
    run-all     Execute the entire workflow
    save        Save workflow to server
    load        Load workflow from file
    clear       Clear the current session

All commands POST/GET to a FastAPI backend via HermesfyClient.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from hermesfy.cli.client import HermesfyClient, HermesfyClientError

# ── Constants ────────────────────────────────────────────────────────────────

ENV_AUTH_TOKEN = "HERMESFY_AUTH_TOKEN"
ENV_SERVER_URL = "HERMESFY_SERVER_URL"

# ── Command Handlers ─────────────────────────────────────────────────────────


def _resolve_ids(args: argparse.Namespace) -> None:
    """Resolve workflow-id and session-id from args, using client defaults if not set."""
    if hasattr(args, "workflow_id") and args.workflow_id:
        args.client.workflow_id = args.workflow_id
    if hasattr(args, "session_id") and args.session_id:
        args.client.session_id = args.session_id


def cmd_nodes(args: argparse.Namespace) -> int:
    """List nodes in the current workflow."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'nodes' command", file=sys.stderr)
        return 1
    try:
        result = args.client.get_nodes()
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Show workflow metadata."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'info' command", file=sys.stderr)
        return 1
    try:
        result = args.client.get_info()
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_graph(args: argparse.Namespace) -> int:
    """Display DAG graph structure."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'graph' command", file=sys.stderr)
        return 1
    try:
        result = args.client.get_graph()
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_context(args: argparse.Namespace) -> int:
    """Show session context."""
    _resolve_ids(args)
    try:
        result = args.client.get_context()
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new workflow from JSON input."""
    _resolve_ids(args)
    try:
        if args.file:
            data = json.loads(Path(args.file).read_text())
        elif not sys.stdin.isatty():
            data = json.load(sys.stdin)
        else:
            print("Error: provide workflow JSON via --file or stdin", file=sys.stderr)
            return 1

        # Allow name override
        if args.name:
            data["name"] = args.name

        result = args.client.create_workflow(data)
        print(json.dumps(result, indent=2))
        return 0
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return 1
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_connect(args: argparse.Namespace) -> int:
    """Connect two nodes with an edge."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'connect' command", file=sys.stderr)
        return 1
    if not args.source or not args.target:
        print("Error: --source and --target are required for 'connect'", file=sys.stderr)
        return 1
    try:
        result = args.client.connect_nodes(args.source, args.target)
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_set(args: argparse.Namespace) -> int:
    """Set workflow-level config."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'set' command", file=sys.stderr)
        return 1
    try:
        config = {}
        if args.json_config:
            config = json.loads(args.json_config)
        elif args.key:
            # Parse key=value pairs
            for kv in args.key:
                k, _, v = kv.partition("=")
                if not k:
                    continue
                # Try to parse as JSON, fallback to string
                try:
                    config[k] = json.loads(v)
                except json.JSONDecodeError:
                    config[k] = v
        else:
            print("Error: provide --json or --key=value pairs", file=sys.stderr)
            return 1

        result = args.client.set_workflow_config(config)
        print(json.dumps(result, indent=2))
        return 0
    except (json.JSONDecodeError, HermesfyClientError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run a single node."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'run' command", file=sys.stderr)
        return 1
    if not args.node_id:
        print("Error: --node-id is required for 'run' command", file=sys.stderr)
        return 1
    try:
        inputs = {}
        if args.inputs:
            inputs = json.loads(args.inputs)
        result = args.client.run_node(args.node_id, inputs)
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_run_all(args: argparse.Namespace) -> int:
    """Execute the entire workflow."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'run-all' command", file=sys.stderr)
        return 1
    try:
        options = {}
        if args.options:
            options = json.loads(args.options)
        result = args.client.run_all(options)
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_save(args: argparse.Namespace) -> int:
    """Save workflow to server."""
    _resolve_ids(args)
    if not args.client.workflow_id:
        print("Error: --workflow-id is required for 'save' command", file=sys.stderr)
        return 1
    try:
        result = args.client.save_workflow(args.filename)
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_load(args: argparse.Namespace) -> int:
    """Load workflow from file."""
    _resolve_ids(args)
    if not args.filename:
        print("Error: --filename is required for 'load' command", file=sys.stderr)
        return 1
    try:
        result = args.client.load_workflow(args.filename)
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_clear(args: argparse.Namespace) -> int:
    """Clear the current session."""
    _resolve_ids(args)
    try:
        result = args.client.clear_session()
        print(json.dumps(result, indent=2))
        return 0
    except HermesfyClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# ── Argument Parser ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the Hermesfy CLI."""
    parser = argparse.ArgumentParser(
        prog="hermesfy",
        description="Hermesfy CLI — Thin HTTP client for the DAG workflow engine",
    )

    # Global flags
    parser.add_argument(
        "--server-url",
        default=os.environ.get(ENV_SERVER_URL, "http://localhost:8000"),
        help="FastAPI backend URL (default: $HERMESFY_SERVER_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--auth-token",
        default=os.environ.get(ENV_AUTH_TOKEN, ""),
        help="Bearer auth token (default: $HERMESFY_AUTH_TOKEN)",
    )
    parser.add_argument(
        "--workflow-id",
        default=None,
        help="Workflow ID for workflow-scoped commands",
    )
    parser.add_argument(
        "--session-id",
        default="default",
        help="Session ID for session-scoped commands",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # nodes
    subparsers.add_parser("nodes", help="List nodes in current workflow")

    # info
    subparsers.add_parser("info", help="Show workflow metadata")

    # graph
    subparsers.add_parser("graph", help="Display DAG graph structure")

    # context
    subparsers.add_parser("context", help="Show session context")

    # create
    p_create = subparsers.add_parser("create", help="Create a new workflow from JSON")
    p_create.add_argument("--file", help="Path to JSON file with workflow definition")
    p_create.add_argument("--name", help="Override workflow name")

    # connect
    p_connect = subparsers.add_parser("connect", help="Connect two nodes with an edge")
    p_connect.add_argument("--source", required=True, help="Source node ID")
    p_connect.add_argument("--target", required=True, help="Target node ID")

    # set
    p_set = subparsers.add_parser("set", help="Set workflow-level config")
    p_set.add_argument("--json", dest="json_config", help="JSON config string")
    p_set.add_argument("--key", nargs="*", help="key=value pairs (e.g., width=1024 height=768)")

    # run
    p_run = subparsers.add_parser("run", help="Run a single node")
    p_run.add_argument("--node-id", required=True, help="Node ID to run")
    p_run.add_argument("--inputs", help="JSON input overrides for the node")

    # run-all
    p_run_all = subparsers.add_parser("run-all", help="Execute the entire workflow")
    p_run_all.add_argument("--options", help="JSON options dict (budget, validate_steps, etc.)")

    # save
    p_save = subparsers.add_parser("save", help="Save workflow to server")
    p_save.add_argument("--filename", help="Optional filename for the save")

    # load
    p_load = subparsers.add_parser("load", help="Load workflow from file")
    p_load.add_argument("--filename", required=True, help="Filename to load")

    # clear
    subparsers.add_parser("clear", help="Clear the current session")

    return parser


# ── Command Dispatch ─────────────────────────────────────────────────────────

COMMAND_HANDLERS: dict[str, Any] = {
    "nodes": cmd_nodes,
    "info": cmd_info,
    "graph": cmd_graph,
    "context": cmd_context,
    "create": cmd_create,
    "connect": cmd_connect,
    "set": cmd_set,
    "run": cmd_run,
    "run-all": cmd_run_all,
    "save": cmd_save,
    "load": cmd_load,
    "clear": cmd_clear,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point for the 'hermesfy' console script.

    Never uses shell=True — all subprocess calls are avoided.
    All backend communication goes through HTTP via HermesfyClient.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Create the HTTP client
    args.client = HermesfyClient(
        server_url=args.server_url,
        auth_token=args.auth_token,
    )
    args.client.session_id = args.session_id
    if args.workflow_id:
        args.client.workflow_id = args.workflow_id

    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
