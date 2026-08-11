"""Command-line interface: run, serve, gates, version."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import AgentLoop
from .config import load_config
from .gates import run_gates
from .llm import build_llm
from .logging import AuditLog
from .tools import default_registry
from .version import __version__

DEFAULT_SYSTEM_PROMPT = (
    "You are AgentAgent2, a careful coding assistant. Use the available tools to complete the "
    "user's task. When you are done, reply with plain text and no further tool calls."
)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``agentagent2`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1
    try:
        return int(args.func(args))
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentagent2", description="AgentAgent2 harness CLI.")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the agent loop against a task.")
    run_p.add_argument("task", help="The task to give the agent.")
    run_p.add_argument("--workspace", default=".", help="Sandbox root for tool use (default: cwd).")
    run_p.add_argument("--mock", action="store_true", help="Use the offline mock LLM instead of the API.")
    run_p.add_argument("--model", default=None, help="Override the model id.")
    run_p.add_argument("--max-steps", type=int, default=None, help="Override the step limit.")
    run_p.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT, help="Override the system prompt.")
    run_p.add_argument("--json", action="store_true", help="Print the result as JSON.")
    run_p.set_defaults(func=_cmd_run)

    serve_p = sub.add_parser("serve", help="Start the HTTP API server.")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8420)
    serve_p.add_argument("--workspace", default=".", help="Sandbox root for tool use (default: cwd).")
    serve_p.add_argument("--mock", action="store_true", help="Use the offline mock LLM instead of the API.")
    serve_p.set_defaults(func=_cmd_serve)

    gates_p = sub.add_parser("gates", help="Run the quality gates against a project.")
    gates_p.add_argument("--path", default=".", help="Project root (default: cwd).")
    gates_p.add_argument("--fix", action="store_true", help="Auto-fix formatting/lint where possible.")
    gates_p.set_defaults(func=_cmd_gates)

    version_p = sub.add_parser("version", help="Print the package version.")
    version_p.set_defaults(func=_cmd_version)

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    cfg = load_config(
        model=args.model, max_steps=args.max_steps, mock=args.mock, workspace=workspace
    )

    log = AuditLog(workspace / "agentagent2_run.log")
    loop = AgentLoop(
        llm=build_llm(cfg),
        tools=default_registry(workspace),
        system=args.system,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        max_steps=cfg.max_steps,
        log=log,
    )
    result = loop.run(args.task)

    if args.json:
        payload = {
            "final_text": result.final_text,
            "stop_reason": result.stop_reason,
            "steps": result.step_count,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(result.final_text)
        print(f"\n[stop_reason={result.stop_reason} steps={result.step_count}]", file=sys.stderr)

    return 2 if result.hit_step_limit else 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve  # local import: keeps `run --mock` free of http.server startup cost

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    cfg = load_config(mock=args.mock, workspace=workspace)
    serve(host=args.host, port=args.port, config=cfg)
    return 0


def _cmd_gates(args: argparse.Namespace) -> int:
    report = run_gates(Path(args.path).resolve(), fix=args.fix)
    for outcome in report.outcomes:
        print(f"{outcome.name:<10} {outcome.status}")
    if not report.passed:
        detail = report.detail()
        if detail:
            print()
            print(detail)
    return 0 if report.passed else 1


def _cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
