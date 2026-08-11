# AgentAgent2 Harness

A standalone, deployable Python implementation of **AgentAgent2** — the meta-agent
specified in `../agentagent2/AGENTAGENT2.system.md` (designed in the first half of this
build session). Where that spec is a prompt-and-manifest design for an agent, this
package is a runnable one: point it at a task and it will call Claude, execute tool
calls in a sandboxed workspace, and loop until the model is done.

## Why zero dependencies

Core has **no required third-party packages** — the Anthropic API client is built on
`urllib`, the HTTP server on `http.server`, the coverage gate on `trace`. That's a
deliberate design choice, not a limitation worked around: it means `pip install
agentagent2` (or just copying `src/agentagent2/` somewhere with Python 3.11+) is enough
to run it anywhere, including offline via `--mock` mode, with no dependency resolution
or supply-chain surface beyond the standard library.

```bash
pip install -e .            # editable install, zero required deps
pip install -e ".[dev]"     # + ruff, mypy, pytest for local development
```

## CLI

```bash
# Run a task against the real API (needs ANTHROPIC_API_KEY)
agentagent2 run "list the files in this directory and summarize the project" --workspace .

# Same, but fully offline — demonstrates the real tool-use loop with no network or API key
agentagent2 run "look around" --workspace . --mock

# Start the HTTP API server
agentagent2 serve --port 8420 --workspace . --mock

# Run this project's own quality gates against any project
agentagent2 gates --path . [--fix]

agentagent2 version
```

Configuration resolves in this order (later wins): built-in defaults → `--config`
JSON file → environment variables (`ANTHROPIC_API_KEY`, `AGENTAGENT2_MODEL`,
`AGENTAGENT2_MAX_STEPS`, `AGENTAGENT2_TEMPERATURE`, `AGENTAGENT2_MOCK`, ...) → explicit
CLI flags.

## HTTP API

```
GET  /healthz          -> {"status": "ok", "version": "1.0.0"}
POST /v1/run            body: {"task": str, "system": str?}
                         -> {"final_text": str, "stop_reason": str, "steps": int}
```

```bash
curl -X POST http://127.0.0.1:8420/v1/run \
  -H 'content-type: application/json' \
  -d '{"task": "list files in the workspace"}'
```

## Docker

```bash
docker build -t agentagent2 .
docker run --rm -e ANTHROPIC_API_KEY -p 8420:8420 agentagent2 serve --host 0.0.0.0
```

## Architecture

```
src/agentagent2/
  config.py        Config dataclass + layered load_config() (defaults/file/env/flags)
  logging.py        AuditLog: append-only, timestamped event log (file + stream)
  llm/               Model backend abstraction
    base.py            LLMClient protocol, Message/ContentBlock types, response parsing
    anthropic.py        Real client: stdlib urllib, injectable transport for testing
    mock.py             Offline client: scripted responses or a callback
  tools/             Sandboxed tool suite the agent can call
    base.py            Tool ABC, resolve_within() sandbox guard, argument helpers
    filesystem.py       read_file / write_file / edit_file / list_dir
    shell.py             run_shell (timeout + cwd-guarded)
    search.py            grep_search / glob_search
    registry.py          ToolRegistry: spec generation + dispatch
  agent.py            AgentLoop: the create -> tool_use -> tool_result cycle
  phases.py           PhaseRunner: the 9-phase INTENT..DEBRIEF loop, VERIFY/EVALUATE as
                       real hard gates, bounded repair loop back into IMPLEMENT
  gates.py            run_gates(): format/lint/typecheck/tests/coverage/secrets, each
                       gate independently reporting pass/fail/missing_tool/error
  cli.py              run / serve / gates / version
  server.py           stdlib http.server API
```

`AgentLoop` is the primitive everything else is built on. `PhaseRunner` wraps it with
AgentAgent2's own operating loop and points VERIFY at real, objectively-checked gates
rather than a model self-report — the same discipline the harness was built under
(`agentagent_log.md` in the parent directory is the append-only record of that).

## Quality gates without third-party tools

`gates.py` runs six checks — format, lint, typecheck, tests, coverage, secrets — each
shelling out to the standard tool (`ruff`, `mypy`, `pytest`) when installed. If a tool
isn't installed, that gate reports `missing_tool` (never silently "pass"). Two gates
work with **zero** extra dependencies even when the dev tools aren't installed:

- **tests** falls back to `python -m unittest discover`. Every test in `tests/` is
  written as a `unittest.TestCase` specifically so it's runnable both ways — `pytest`
  when available, stdlib `unittest` when it isn't.
- **coverage** doesn't depend on the third-party `coverage` package at all. It re-runs
  the test suite under the standard library's `trace` module in an isolated subprocess
  and compares hit lines against a token-based estimate of executable statements in
  `src/`. This is a **statement-coverage approximation**, not a drop-in replacement for
  `coverage.py` — see the module docstring in `gates.py` for the specific measurement
  details it accounts for (tracing must wrap test *discovery*, not just the test run;
  `threading.settrace()` is needed to credit code that only runs on a background
  thread; a multi-line statement counts as one executable line, not one per physical
  line). Running `agentagent2 gates` against this project's own `src/` is itself the
  regression test for that logic.
- **secrets** is a pattern match for obviously hardcoded credentials (AWS-style keys,
  PEM blocks, `password = "..."` literals) — a floor, not a real scanner. `tests/` is
  excluded from the scan by convention, since a secrets scanner's own test fixtures
  necessarily contain fake credentials shaped like real ones.

`format`/`lint`/`typecheck` need `ruff`/`mypy` installed (`pip install -e ".[dev]"`);
there's no stdlib fallback for those, and `gates.py` says so plainly rather than
skipping them silently.

## Known limitations

- EVALUATE in `PhaseRunner` defaults to an always-pass stub (`default_evaluate`) — there
  is no universal eval suite for an arbitrary task. Pass a real `evaluate_fn` to make it
  a meaningful gate for a specific produced-agent's eval suite.
- The secrets gate is intentionally simple (see above); don't rely on it in place of a
  real scanner (trufflehog, gitleaks) for anything that matters.
- `format`/`lint`/`typecheck` need `ruff`/`mypy` installed and were **not** mechanically
  verified during this build — the sandbox this harness was built in doesn't have them
  installed either (no network to fetch them). The code was hand-written to strict-mypy
  and ruff conventions (`from __future__ import annotations`, no bare `except:`, no
  unused imports, etc.) but that's a claim about intent, not a passing gate run. First
  thing to do after cloning with `ruff`/`mypy` available: `pip install -e ".[dev]"` then
  `agentagent2 gates --path .` and fix whatever it finds.
