---
name: context-memory
description: Use during long or context-heavy builds. Manages the plan file, scratchpad, decision log, and external artifact store, and applies a compaction policy so work survives within context limits.
---

# Context & Memory Management

Treat the context window as a scarce cache, not a hard drive. Keep active context small and precise; persist the rest.

## Artifacts
- `plan.md` — the live plan and current phase/step.
- `scratchpad.md` — working notes + one-line tool-call rationales.
- `decisions.md` — ADRs: decision, options, rationale, consequences.
- `artifact_store/` — bulky outputs (logs, generated files, transcripts) keyed for on-demand reload.

## Policy
1. **Externalize early.** As soon as an output is large or "done for now", push it to the artifact store and keep only a pointer + summary in context.
2. **Compact at phase boundaries.** Summarize the closing phase into `decisions.md`; drop verbose intermediate reasoning.
3. **Reload on demand** with `artifact_load` only the slice you need.
4. **Prefer references over inlining.** Cite file paths and keys instead of pasting content.
5. **Checkpoint state** so a resumed session can reconstruct position from `plan.md` + `decisions.md`.

## Signals to compact
- Approaching the per-phase token budget.
- Repeated re-reading of the same large file (store a summary instead).
- Long tool transcripts no longer needed for the current decision.

## Checklist
- [ ] `plan.md` reflects current phase/step
- [ ] Bulky outputs live in the artifact store, not context
- [ ] Each closed phase summarized into `decisions.md`
- [ ] Active context holds pointers + summaries, not raw dumps
- [ ] Session is resumable from checkpoints

## Outputs
A lean, resumable working context with durable external memory.
