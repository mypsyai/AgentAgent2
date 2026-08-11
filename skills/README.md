# AgentAgent2 Skills Library

Skills are **model-invoked playbooks**: AgentAgent2 loads a skill when the task matches its `description`. Each skill is a folder containing a `SKILL.md` with YAML front-matter (`name`, `description`) and a body of procedure + checklists. Skills may also ship `scripts/` and `resources/`.

**Progressive disclosure:** only the front-matter is always in context. The body is pulled in when the skill triggers, and heavy resources are loaded on demand — this keeps the context window lean.

| Skill | Triggers when… |
|---|---|
| `agent-scaffolding` | starting a new agent build |
| `tool-design` | defining or refining an agent's tools |
| `prompt-engineering` | writing a system/operating prompt |
| `eval-harness` | you need to measure an agent's quality |
| `code-quality-gates` | before any delivery |
| `mcp-integration` | connecting external capabilities |
| `subagent-orchestration` | work is large or parallelizable |
| `context-memory` | builds are long or context-heavy |
| `safety-guardrails` | any tool/permission/secret handling |

**Authoring rules:** keep `description` specific and trigger-oriented; keep the body actionable (checklists over prose); make scripts idempotent; never hardcode secrets.
