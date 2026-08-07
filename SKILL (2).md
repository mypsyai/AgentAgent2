---
name: subagent-orchestration
description: Use when work is large or parallelizable. Defines specialized subagent roles with self-contained briefs, coordinates parallel execution, and synthesizes results while keeping the orchestrator's context lean.
---

# Subagent Orchestration

Delegate to specialists to parallelize work and protect the orchestrator's context window.

## Roles
| Role | Mission | Tools allowed | Handoff |
|---|---|---|---|
| researcher | gather current best practices/APIs | web_search, web_fetch, read_file | `findings.md` |
| architect | produce `design.json` | read_file, artifact_* | `design.json` |
| coder | implement a slice to gate-passing | read/write/edit, run_*, vcs_* | diff + gate report |
| reviewer | adversarial review vs style + intent | read, grep, vcs_diff | `review.json` |
| tester | author tests + evals | read/write, run_tests | tests + eval suite |

## Rules
- **Self-contained briefs.** Subagents cannot see orchestrator history — include all context, constraints, inputs, and the exact expected output format.
- **Parallelize independent work** (e.g., coder + tester per slice); sequence dependencies (reviewer gates a merge).
- **Least privilege per role** — give each subagent only the tools its mission needs.
- **Synthesize, don't relay.** Integrate subagent results; never paste raw output to the user.
- **Bound the fan-out** to keep coordination cost and token spend in check; prefer a few strong subagents over many tiny ones.

## Procedure
1. Slice the work into independent units with clear interfaces.
2. Write a brief per unit (context + inputs + output contract + allowed tools).
3. Spawn in parallel; monitor via `list_agents`; send follow-ups with `message_subagent`.
4. Collect handoffs, reconcile conflicts, run gates on the integrated result.

## Checklist
- [ ] Work sliced into independent units
- [ ] Each brief is self-contained with an output contract
- [ ] Roles have least-privilege toolsets
- [ ] Parallel where independent; sequenced where dependent
- [ ] Results synthesized and gate-checked as a whole

## Outputs
Role briefs, subagent handoffs, and a synthesized, gate-passing result.
