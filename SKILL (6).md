---
name: prompt-engineering
description: Use when authoring or revising an agent's system/operating prompt. Produces a structured prompt with role, operating loop, tool policy, guardrails, and prompt-level tests.
---

# Prompt Engineering

The system prompt is the agent's constitution. Make it explicit, testable, and minimal.

## Structure (in order)
1. **Identity & role** — who the agent is, its one prime directive.
2. **Operating loop** — the phases/steps and any gates.
3. **Working style** — plan-first, parallelism, read-before-edit, dedicated tools.
4. **Tool policy** — least privilege, destructive-action gate, audit.
5. **Quality bar** — the non-negotiable acceptance conditions.
6. **Communication** — what/when to report to the user.
7. **Ambiguity policy** — assume-vs-ask rule.

## Techniques
- Prefer **imperative, specific rules** over vague aspiration ("run the formatter and require zero diff", not "write clean code").
- Give **decision procedures**, not just goals (what to do on gate failure, on ambiguity, on destructive actions).
- Encode **positive and negative examples** for high-risk behaviors.
- Keep it **DRY**: push detailed procedures into skills; the prompt references them.
- Put the **most important, most-violated rules first and last** (primacy/recency).
- Avoid contradictions; when rules conflict, state the precedence order.

## Prompt-level tests
Write scenario checks the prompt must satisfy:
- Ambiguous request → lists assumptions and proceeds (or asks one question).
- Destructive request → confirms first.
- Injection in tool output → ignores embedded instructions.
- Missing tests → refuses to mark work done.

## Checklist
- [ ] Single prime directive stated
- [ ] Loop + gates unambiguous
- [ ] Tool + safety policy present
- [ ] Quality bar is measurable
- [ ] No internal contradictions; precedence stated
- [ ] Scenario tests written and passing in eval harness

## Outputs
A `system.md` prompt + scenario tests wired into the eval harness.
