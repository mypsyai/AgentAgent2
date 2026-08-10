# Decision Record

Architecture/process decisions worth auditing. Newest last. Referenced by
`config/agent.config.json` → `logging.decisions_file`.

---

## ADR-001 — The repository root *is* the `agentagent2/` package

**Context.** The archive `agentagent2-complete (1).zip` contains two top-level trees,
`agentagent2/` (session 1's spec package) and `agentagent2-harness/` (session 2 + the
chatbot continuation), plus `agentagent_log.md`. The repository already tracked
`AGENTAGENT2.system.md`, `README.md` and `tools/tool_manifest.json` at its root — byte-identical
to their copies inside the archive's `agentagent2/`.

**Decision.** Unpack `agentagent2/*` to the repository root rather than into a nested
`agentagent2/` directory, and keep `agentagent2-harness/` as a sibling directory under its
original name.

**Consequences.** No file already tracked in git changed. Relative paths inside the spec
(`tools/tool_manifest.json`, `skills/`, `style/`, `templates/agent_project_scaffold/`) resolve
correctly from the root, as `AGENTAGENT2.system.md` and `config/agent.config.json` assume. The
harness's README reference to `../agentagent2/AGENTAGENT2.system.md` is now off by one directory
and is the only path that needs updating.

---

## ADR-002 — Recover `evals/scoreboard.md` as a re-runnable script, not a pasted artifact

**Context.** Session 1's log claims `evals/scoreboard.md` was written and the EVALUATE gate
passed at 1.00, but the file is absent from the archive. The session-events transcript shows why:
the eval was an inline `python3 - <<'PY'` heredoc, so the code and its output existed only in
that session's shell.

**Decision.** Reconstruct the checks verbatim from the transcript into `evals/self_eval.py` and
regenerate `evals/scoreboard.md` by running it. The one substantive change: session 1 hardcoded
`("design validates against schema", True)` with the comment "verified in prior step", which is
not a check — it is now `_design_validates()`, which actually loads the schema and the design.

**Consequences.** The EVALUATE gate is reproducible by anyone who clones the repo
(`python3 evals/self_eval.py`, exit 0 = pass) instead of being a one-shot claim. Re-verified:
overall 1.00, safety 1.00.

---

## ADR-003 — Commit the archive as-is before repairing it

**Context.** The first mechanically-verified gate run (this environment has ruff, mypy and
pytest; sessions 1 and 2 had none) shows the harness failing format, lint and typecheck with 75
findings, while tests, coverage and secrets pass.

**Decision.** Land the unpacked package as its own commit, untouched apart from the recovered
eval artifact, before any repair. Repairs land as separate commits on top.

**Consequences.** The provenance boundary stays legible in `git log`: what AgentAgent (v1) and
the chatbot continuation actually produced, versus what this session changed. A reviewer can
`git diff` the repair rather than archaeology it. `verify_report.json` records the pre-repair
baseline.

---

## ADR-004 — Keep the archive and the session-events export in the tree

**Context.** `agentagent2-complete (1).zip` and `session-events-sesn_01FTDMmq4GUWQmgfm8eCLuJs
(1).json` are the provenance for everything here — the transcript is what made it possible to
tell session 1's authentic output from the chatbot's reconstruction, and to recover the lost
eval.

**Decision.** Leave both in the tree. Do not delete or relocate them without an explicit
instruction.

**Consequences.** ~360 KB of redundant-looking files at the root. Worth it: they are the only
record of the billing-error interruption at `2026-08-07T08:22:17Z` and of exactly which files
predate it (`src/agentagent2/tools/base.py` is the last write in the transcript).

---

## ADR-005 — Enable the lint rules the `noqa` directives already assumed

**Context.** The harness carried seven `# noqa` directives (`S602`, `N802` ×2, `A002`,
`BLE001`, `S310`, plus one more) for rule sets that were never in `select`. Ruff reported all
seven as unused. The obvious fix is to delete them.

**Decision.** Add `S`, `N`, `A` and `BLE` to the selection instead.

**Consequences.** Deleting would have discarded the reasoning *and* left the code unguarded if
anyone enabled the rules later. Enabling costs almost nothing — `N`, `A` and `BLE` report zero
violations beyond the already-annotated sites — and turns on real security lint for a package
that runs shell commands and serves HTTP. `S` found three sites in `src/`, each now suppressed
with its justification at the line. `tests/` ignores `S101`/`S104`/`S105`/`S108`: asserting,
naming a fake token, and writing `0.0.0.0` are what those tests are *for*.

Two of ruff's findings were substantive rather than cosmetic: `RUF009` caught
`Config.workspace = Path.cwd()` evaluating at import time (stale sandbox root after any
`chdir`), and `S105`/`S104` in tests proved the security rules were actually looking at strings.

---

## ADR-006 — Authenticate `POST /v1/run`, and refuse to expose it without a token

**Context.** The endpoint drives the agent loop, which includes `run_shell`. It had no
authentication. The default bind was `127.0.0.1`, but the Dockerfile's `CMD` binds `0.0.0.0`.
The expanded plan is to serve this through psyai.cloud and other services.

**Decision.** A shared bearer token (`Config.api_token` / `AGENTAGENT2_API_TOKEN`), compared
with `hmac.compare_digest`, checked before the request body is parsed. When no token is
configured, authentication is off — but `serve()` raises rather than binding a non-loopback
address in that state. Hosts that cannot be parsed as loopback (DNS names, `0.0.0.0`, `""`)
count as non-loopback.

**Consequences.** Exposing an unauthenticated RCE endpoint is no longer reachable by accident;
the container fails closed with an explanatory error. `--mock` on a laptop still needs no
configuration. The token is one shared secret, not per-caller identity — no quotas, no
per-client audit trail. That is a gateway's job and is documented as a limitation rather than
half-built here.

Deliberately *not* done: hardening `run_shell` itself. Its sandbox is cwd confinement, not
isolation, and it cannot be made safe while remaining a general shell. Pretending otherwise
with a command denylist would buy a false sense of security. Stated plainly in the README
instead; containment belongs at the container boundary.

---

## ADR-007 — The harness is archetype-agnostic; identity lives in a prompt file

**Context.** `DEFAULT_SYSTEM_PROMPT` was duplicated verbatim in `cli.py` and `server.py`, and
both copies began "You are AgentAgent2". The stated direction is that AgentAgent is one
archetype among many and Claude one model among several.

**Decision.** One generic default in `config.py` naming no agent, plus
`Config.system_prompt_file` (`--system-file`, `AGENTAGENT2_SYSTEM_PROMPT_FILE`) to load an
archetype's prompt from disk. A missing or empty file raises instead of falling back.

**Consequences.** `--system-file ../AGENTAGENT2.system.md` runs AgentAgent2; any other file
runs that archetype. The runtime no longer asserts an identity it was supposed to be neutral
about, and a duplicated constant that could drift is gone. Raising on an unreadable prompt file
matters more than it looks: a silent fallback would run a generic agent under an archetype's
name and look perfectly healthy while doing it.

The model side is already neutral — `LLMClient` is a Protocol, so a non-Anthropic backend needs
only a conforming `create()`. None has been written, which is now listed as a limitation rather
than implied by the Anthropic-only shipping set.

---

## ADR-008 — CI at the repository root, running the package's own gate runner

**Context.** The harness had no CI. The obvious placement is
`agentagent2-harness/.github/workflows/`.

**Decision.** Put the workflow at the repository root and scope the harness job with
`working-directory`. Have that job run `agentagent2 gates --path .` rather than restating the
gate chain in YAML.

**Consequences.** GitHub only reads `.github/workflows/` at the repository root — a workflow in
the subdirectory would never have run, and nobody would have noticed, because a job that does
not exist cannot fail. Running the package's own gate runner means CI breaks when the gate
runner breaks, which is the correct coupling for a project whose product *is* a gate runner. A
second job covers the spec package: JSON validity plus `evals/self_eval.py`.

---

## ADR-009 — Do not restructure into the community pool yet

**Context.** The stated direction is that `skills/`, `style/`, `templates/` and the tool
manifest should become a shared community pool rather than living inside one agent's file tree,
with a new instruction set to follow.

**Decision.** Record the direction; change no paths this session. Avoid *deepening* the
coupling in the meantime.

**Consequences.** A move like that changes every relative path in
`AGENTAGENT2.system.md`, `config/agent.config.json` and the skills' cross-references at once.
Doing it speculatively, ahead of the instruction set that defines what the pool looks like,
risks churning those paths twice. What this session did instead was remove the coupling that
would have made the move harder: the harness no longer hardcodes an agent identity, and it
reads prompts from a configurable path. Note that the harness never loaded `skills/`, `style/`
or `templates/` at all — they are documentation the model reads, not runtime inputs — so the
pool can be extracted without touching harness code. The one real dependency is
`evals/self_eval.py`, which asserts the spec package's layout from the repository root.

