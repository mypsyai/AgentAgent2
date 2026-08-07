---
name: eval-harness
description: Use when you need to measure a produced agent's quality. Generates a task-based eval suite scoring success, tool-call correctness, code quality, safety, robustness, and cost, with a scoreboard.
---

# Eval Harness

If it isn't evaluated, it isn't done. Build evals from the acceptance tests defined in INTENT.

## Dimensions
| Dimension | Measures | Method |
|---|---|---|
| task_success | acceptance tests pass | run tasks, assert outputs |
| tool_call_correctness | right tool, args, ordering; no hallucinated tools | trace assertions on tool calls |
| code_quality | gates pass + reviewer score | run gates + rubric |
| safety | refuses unsafe, no secret leak, injection-resistant | red-team prompts |
| robustness | handles malformed input / tool errors | fault-injection cases |
| cost | tokens + tool calls within budget | meter the run |

## Procedure
1. Convert each acceptance test into ≥1 eval case with a deterministic checker.
2. Add adversarial cases: prompt injection, destructive request, ambiguous request, tool failure.
3. Implement checkers (assertions), not LLM-graded vibes, wherever possible; use an LLM judge only for open-ended quality with a rubric + tie-break to conservative.
4. Run the suite; emit `eval_report.json` and a human-readable `scoreboard.md`.
5. Gate: overall ≥ 0.90 and safety = 1.0, else diagnose the weakest dimension, patch, re-verify, re-evaluate.

## Checklist
- [ ] Every acceptance test has an eval case
- [ ] Adversarial + robustness cases included
- [ ] Deterministic checkers preferred over LLM grading
- [ ] Cost metered against budget
- [ ] Scoreboard produced; thresholds enforced

## Outputs
`evals/` suite, `eval_report.json`, `scoreboard.md`.
