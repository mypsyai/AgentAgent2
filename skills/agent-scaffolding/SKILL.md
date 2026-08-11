---
name: agent-scaffolding
description: Use when starting a new agent build to generate a reproducible project layout — repo tree, dependency lockfiles, devcontainer, CI, and pre-commit hooks — before any feature code is written.
---

# Agent Scaffolding

Establish a reproducible, gate-ready project skeleton so that every later slice can be verified the moment it is written.

## Procedure
1. **Pick the stack** from `design.json` (language, package manager, test framework) and the matching `style/<lang>.md`.
2. **Generate the tree** from `templates/agent_project_scaffold/`. Standard layout:
   - `src/` (or `pkg/`), `tests/`, `evals/`, `config/`, `skills/`, `prompts/`, `scripts/`, `docs/`.
3. **Initialize VCS** and add a sensible `.gitignore`; create the first commit `chore: scaffold`.
4. **Pin dependencies** and commit lockfiles (`uv.lock`, `pnpm-lock.yaml`, `go.sum`, `Cargo.lock`).
5. **Add the devcontainer** (`.devcontainer/devcontainer.json`) with the pinned toolchain.
6. **Wire quality gates** as the CI workflow and a pre-commit config: format → lint → typecheck → test → coverage → security.
7. **Add project docs**: `README.md` (run steps), `decisions.md` (ADR log), `CONTRIBUTING.md`.
8. **Prove the skeleton**: run the gates on the empty project — they must pass green before any feature work.

## Checklist
- [ ] Layout matches design and language conventions
- [ ] Lockfiles committed; build is deterministic
- [ ] Devcontainer reproduces the toolchain
- [ ] CI + pre-commit run the full gate set
- [ ] Empty-project gate run is green
- [ ] Secrets excluded via `.gitignore`; `.env.example` provided

## Outputs
A committed, CI-green project skeleton ready for test-first implementation.
