# Rust Style

Binds `STYLE_CORE.md` to the Rust toolchain. Target: stable Rust, 2021 edition.

## Toolchain
| Concern | Tool | Command |
|---|---|---|
| Build/pkg | **cargo** | `cargo build`, `cargo add <crate>` |
| Format | **rustfmt** | `cargo fmt --check` |
| Lint | **clippy** (deny warnings) | `cargo clippy -- -D warnings` |
| Typecheck | **cargo check** | `cargo check` |
| Test | **cargo test** | `cargo test` |
| Security | **cargo-audit** | `cargo audit` |

## Conventions
- `snake_case` for functions/vars/modules, `PascalCase` for types/traits, `SCREAMING_SNAKE` for consts.
- Prefer `Result<T, E>` + the `?` operator; reserve `panic!`/`unwrap`/`expect` for truly-unreachable states (and justify).
- Model errors with `thiserror` (libraries) / `anyhow` (binaries). Make illegal states unrepresentable with enums.
- Borrow over clone; clone deliberately. Prefer iterators over index loops.
- `#![forbid(unsafe_code)]` unless `unsafe` is essential and documented with safety invariants.
- Derive `Debug`; derive `Clone`/`PartialEq` where it aids testing. Use `#[non_exhaustive]` for public enums that may grow.

## Layout
```
Cargo.toml
Cargo.lock
src/main.rs | src/lib.rs
src/<module>.rs | src/<module>/mod.rs
tests/ (integration)
```

## Anti-patterns
- `unwrap()`/`expect()` on fallible I/O in production paths.
- Unjustified `unsafe`, `.clone()` to dodge the borrow checker, stringly-typed errors.
- Blocking calls inside async contexts.
