---
name: tool-design
description: Use when defining or refining the tools an agent can call. Produces least-privilege tool definitions with strict input schemas, clear usage boundaries, and safety classifications.
---

# Tool Design

A tool is an API the model calls. Good tools are unambiguous, hard to misuse, and least-privileged.

## Principles
- **One clear job per tool.** If a description needs "and", consider splitting.
- **Strict input schemas.** Type every field; mark optionals; reject unknown fields.
- **Name for intent**, not implementation (`run_tests`, not `pytest_wrapper`).
- **Least privilege.** Grant the narrowest permission class that works: `read < write < exec < network-read < network-write < orchestrate`.
- **Guidance in the tool.** Include `when_to_use` and `when_not_to_use` so the model routes correctly.
- **Safe by default.** Classify `safe | guarded | privileged`; gate destructive/irreversible variants behind confirmation.
- **Deterministic, structured output.** Return machine-parseable results with explicit error fields.

## Procedure
1. Enumerate the capabilities the agent actually needs (from acceptance tests) — nothing speculative.
2. For each, write a manifest entry: `name, purpose, input_schema, output, permissions, safety, when_to_use, when_not_to_use`.
3. Collapse overlaps; prefer a small, orthogonal set.
4. Add validation + actionable error messages for every failure mode.
5. Write a smoke test per tool (happy path + one malformed input).

## Checklist
- [ ] Every tool maps to a real requirement
- [ ] Input schemas strict; unknown fields rejected
- [ ] Permission is the minimum that works
- [ ] Safety class set; destructive variants gated
- [ ] `when_to_use` / `when_not_to_use` present
- [ ] Errors are structured and actionable
- [ ] Smoke tests exist and pass

## Outputs
`tool_manifest.json` entries + per-tool smoke tests.
