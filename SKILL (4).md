---
name: code-quality-gates
description: Use before any delivery and after each implementation slice. Runs and enforces the format, lint, typecheck, test, coverage, and security gate chain and reports pass/fail.
---

# Code Quality Gates

The gate chain is the objective definition of "done". Run it per slice, not only at the end.

## The chain (fail-fast, in order)
1. **Format** — formatter must produce **no diff**.
2. **Lint** — **zero errors**; warnings tracked with justification.
3. **Typecheck** — **zero errors in strict mode**.
4. **Test** — **all pass**; unit + focused integration.
5. **Coverage** — **≥ 85%** of changed code; no coverage-only tests (assert behavior).
6. **Security** — dependency audit + static analysis: **no high/critical**; secret scan: **no secrets in tree**.

## Procedure
1. Resolve the concrete commands from `style/<lang>.md`.
2. Run the chain; on first failure, stop, fix root cause (not the symptom), re-run from the top.
3. After ≤3 auto-repair loops without green, escalate model tier or notify with a defect list.
4. Record the passing run in `verify_report.json` with tool versions.

## Per-language commands (defaults)
- **python:** `ruff format --check . && ruff check . && mypy --strict . && pytest --cov --cov-fail-under=85 && pip-audit && detect-secrets scan`
- **typescript:** `prettier -c . && eslint . && tsc --noEmit && vitest run --coverage && npm audit --audit-level=high`
- **go:** `gofmt -l . && golangci-lint run && go vet ./... && go test -cover ./... && govulncheck ./...`
- **rust:** `cargo fmt --check && cargo clippy -- -D warnings && cargo test && cargo audit`
- **bash:** `shfmt -d . && shellcheck **/*.sh && bats tests/`

## Checklist
- [ ] Format: no diff
- [ ] Lint: zero errors
- [ ] Typecheck: zero errors (strict)
- [ ] Tests: all pass
- [ ] Coverage ≥ 85% changed code
- [ ] Security: no high/critical; no secrets
- [ ] `verify_report.json` recorded with tool versions

## Outputs
`verify_report.json`; CI + pre-commit configs that run this chain.
