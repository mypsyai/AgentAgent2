#!/usr/bin/env bash
# Run the full quality-gate chain. Auto-detects the project language(s).
set -euo pipefail
IFS=$'\n\t'

fail() { echo "GATE FAILED: $1" >&2; exit 1; }

echo "== AgentAgent2 quality gates =="

if [[ -f pyproject.toml ]]; then
  echo "-- python --"
  uv run ruff format --check .            || fail "python format"
  uv run ruff check .                     || fail "python lint"
  uv run mypy --strict .                  || fail "python typecheck"
  uv run pytest --cov --cov-fail-under=85 || fail "python test/coverage"
  uv run pip-audit                        || echo "warn: pip-audit findings"
fi

if [[ -f package.json ]]; then
  echo "-- typescript --"
  pnpm prettier -c .            || fail "ts format"
  pnpm eslint .                 || fail "ts lint"
  pnpm tsc --noEmit             || fail "ts typecheck"
  pnpm vitest run --coverage    || fail "ts test/coverage"
  pnpm audit --audit-level=high || echo "warn: pnpm audit findings"
fi

if [[ -f go.mod ]]; then
  echo "-- go --"
  [[ -z "$(gofmt -l .)" ]]   || fail "go format"
  go vet ./...               || fail "go vet"
  go test -race -cover ./... || fail "go test"
fi

if [[ -f Cargo.toml ]]; then
  echo "-- rust --"
  cargo fmt --check           || fail "rust format"
  cargo clippy -- -D warnings || fail "rust lint"
  cargo test                  || fail "rust test"
fi

echo "== all gates passed =="
