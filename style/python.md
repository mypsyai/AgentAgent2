# Python Style

Binds `STYLE_CORE.md` to the Python toolchain. Target: Python 3.11+.

## Toolchain
| Concern | Tool | Command |
|---|---|---|
| Package/venv | **uv** | `uv sync`, `uv add <pkg>` |
| Format | **ruff format** (Black-compatible) | `uv run ruff format .` |
| Lint | **ruff** | `uv run ruff check .` |
| Typecheck | **mypy --strict** (or pyright) | `uv run mypy --strict .` |
| Test | **pytest** (+pytest-cov) | `uv run pytest --cov --cov-fail-under=85` |
| Security | **pip-audit**, **detect-secrets** | `uv run pip-audit` |

## Conventions
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- **Full type hints** on all public functions; enable `from __future__ import annotations`.
- Prefer `dataclasses`/`pydantic` models over dicts for structured data.
- Use `pathlib.Path`, not string paths. Use `logging`, not `print`.
- Context managers for resources; `with` over manual open/close.
- Prefer comprehensions and generators for clarity; avoid mutable default args.
- Errors: raise specific exceptions; never bare `except:`; chain with `raise ... from e`.

## Layout (src layout)
```
pyproject.toml
uv.lock
src/<package>/__init__.py
src/<package>/...
tests/
```

## Anti-patterns
- `import *`, bare `except`, mutable default arguments, `# type: ignore` without a reason.
- Business logic in `__init__.py`. Global mutable state. `assert` for runtime validation in production paths.

## pyproject essentials
```toml
[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E","F","I","UP","B","SIM","RUF"]
[tool.mypy]
strict = true
warn_unused_ignores = true
```
