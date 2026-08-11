# TypeScript / JavaScript Style

Binds `STYLE_CORE.md` to the TS toolchain. Target: TypeScript 5+, Node 20+ (ESM).

## Toolchain
| Concern | Tool | Command |
|---|---|---|
| Package | **pnpm** | `pnpm install`, `pnpm add <pkg>` |
| Format | **Prettier** | `pnpm prettier -c .` |
| Lint | **ESLint** + typescript-eslint | `pnpm eslint .` |
| Typecheck | **tsc --strict** | `pnpm tsc --noEmit` |
| Test | **Vitest** (or Jest) | `pnpm vitest run --coverage` |
| Security | **npm/pnpm audit** | `pnpm audit --audit-level=high` |

## Conventions
- `camelCase` for variables/functions, `PascalCase` for types/classes, `UPPER_SNAKE` for consts.
- **`strict: true`** in tsconfig; no implicit `any`. Ban `any` — use `unknown` + narrowing.
- Prefer `type`/`interface` models and discriminated unions; make illegal states unrepresentable.
- ESM only; named exports preferred over default exports.
- `async/await` over raw promise chains; always handle rejections; set timeouts on fetch.
- Immutable by default (`const`, `readonly`); avoid mutation of inputs.
- Validate external data at the boundary (e.g., **zod**) before trusting types.

## Layout
```
package.json
pnpm-lock.yaml
tsconfig.json
src/index.ts
src/...
test/ (or *.test.ts co-located)
```

## Anti-patterns
- `any`, non-null `!` assertions to silence the checker, `// @ts-ignore` without reason.
- Default exports for libraries, barrel files that create cycles, `console.log` as logging.

## tsconfig essentials
```json
{ "compilerOptions": {
  "strict": true, "noUncheckedIndexedAccess": true,
  "exactOptionalPropertyTypes": true, "module": "NodeNext",
  "target": "ES2022", "moduleResolution": "NodeNext" } }
```
