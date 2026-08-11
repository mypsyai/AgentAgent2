# Style Core — Language-Agnostic Coding Standard

These principles apply to **all** code AgentAgent2 produces. Language files in this directory bind them to concrete tools. Where a tool and this document disagree, fix the tool config deliberately and record why in `decisions.md`.

## 1. Naming
- Intention-revealing names; no cryptic abbreviations.
- Consistent casing per language convention (see language file).
- Booleans read as predicates (`is_ready`, `has_next`). Functions are verbs; values are nouns.

## 2. Structure
- Small functions, single responsibility, shallow nesting (prefer early returns).
- **Pure core, impure edges**: keep I/O and side effects at the boundary; keep logic pure and testable.
- No dead code, no commented-out code, no TODO without an issue reference.
- Module boundaries reflect the domain, not the framework.

## 3. Errors
- Handle errors explicitly; never swallow them silently.
- Fail fast with actionable messages (what failed, why, how to fix).
- Distinguish expected conditions (return typed results) from bugs (raise/panic).
- Never leak secrets or PII in error text or logs.

## 4. Typing
- Strict typing wherever the language allows; no implicit `any`/`interface{}`/untyped escapes without justification.
- Make illegal states unrepresentable; prefer enums/sum types over stringly-typed flags.

## 5. Tests
- Test **behavior**, not implementation details.
- Arrange–Act–Assert; one logical assertion per test where practical.
- Deterministic and fast; no reliance on network/time/order. Inject clocks and randomness.
- Cover happy path, edge cases, and failure modes. Coverage ≥ 85% of changed code — but coverage is a floor, not a goal.

## 6. Documentation
- Docstring/JSDoc every public API: purpose, params, returns, errors.
- `README.md` with exact run/test steps that work from a clean clone.
- ADRs (`decisions.md`) for non-obvious choices: context, options, decision, consequences.

## 7. Security
- Validate and sanitize all external input. Parameterize queries; never string-build SQL/shell.
- Least privilege for every credential and capability.
- No secrets in code/logs/tests; reference env vars. Keep dependencies patched.

## 8. Dependencies
- Minimal, pinned, vetted, license-checked. Prefer the standard library.
- Every dependency must earn its place against a maintenance-cost bar.

## 9. Concurrency & Resources
- Make shared state explicit; prefer immutability and message passing.
- Always release resources (context managers/`defer`/RAII). Set timeouts on all I/O.

## 10. Commits & History
- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- Atomic commits in imperative mood; each commit builds and passes its gate.

## 11. Performance
- Correct first, then measure, then optimize. Optimize with a benchmark, not a hunch.
- Avoid accidental O(n²); mind allocations in hot paths.
