# Go Style

Binds `STYLE_CORE.md` to the Go toolchain. Target: Go 1.22+.

## Toolchain
| Concern | Tool | Command |
|---|---|---|
| Modules | **go mod** | `go mod tidy` |
| Format | **gofmt / goimports** | `gofmt -l .` |
| Lint | **golangci-lint** | `golangci-lint run` |
| Vet | **go vet** | `go vet ./...` |
| Test | **go test** (+ `-race`, `-cover`) | `go test -race -cover ./...` |
| Security | **govulncheck** | `govulncheck ./...` |

## Conventions
- Follow **Effective Go** and the standard style. `gofmt` is law — no manual formatting debates.
- `MixedCaps`; exported identifiers start uppercase. Short names for short scopes (`i`, `r`), descriptive for wide scopes.
- **Errors are values**: return `error`, wrap with `fmt.Errorf("...: %w", err)`; check every error; no `_ =` discards of errors.
- Accept interfaces, return concrete types. Keep interfaces small (1–3 methods).
- Use `context.Context` as the first param for I/O; honor cancellation and set timeouts.
- Concurrency: goroutines owned by a clear lifecycle; guard shared state; run tests with `-race`.
- `defer` for cleanup. Avoid `panic` for ordinary errors.

## Layout
```
go.mod
go.sum
cmd/<app>/main.go
internal/<pkg>/...
pkg/<lib>/...   (only if truly public)
```

## Anti-patterns
- Ignoring errors, empty `catch`-style `if err != nil {}`, naked returns in long funcs.
- Overusing `interface{}`/`any`, package-level mutable state, giant packages.
