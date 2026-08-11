# Bash / Shell Style

Binds `STYLE_CORE.md` to shell scripts. Prefer a real language once a script exceeds ~100 lines or needs data structures.

## Toolchain
| Concern | Tool | Command |
|---|---|---|
| Format | **shfmt** | `shfmt -d -i 2 -ci .` |
| Lint | **shellcheck** | `shellcheck script.sh` |
| Test | **bats** | `bats tests/` |

## Conventions
- Start every script with a strict mode header:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  IFS=$'\n\t'
  ```
- Quote **all** expansions: `"$var"`, `"${arr[@]}"`. Use `[[ ... ]]` over `[ ... ]`.
- `local` for function variables; `readonly` for constants; `lower_snake_case` names.
- Prefer `$(...)` over backticks. Check command existence before use.
- Trap for cleanup: `trap 'rm -rf "$tmp"' EXIT`. Create temp files with `mktemp`.
- Provide `--help`; validate args; exit with meaningful codes. Send errors to stderr.
- Never `eval` untrusted input; never build commands from unsanitized variables.

## Anti-patterns
- Unquoted variables, parsing `ls`, `cd` without error handling, `rm -rf "$var/"` without guarding empty `$var`.
- Silent failures (missing `set -e`), world-writable temp files, secrets in argv (visible in `ps`).
