# AgentAgent2

**AgentAgent2** is a meta-agent that **designs and builds other Claude agents** to a verified quality bar. It is the successor to AgentAgent (v1), which produced only design documents. AgentAgent2 designs **and** builds **and** proves: it emits runnable, tested, linted, typed agent code plus the validated design that justifies it.

## What's in this package
```
AGENTAGENT2.system.md        # operating instructions / system prompt (the core)
config/
  agent.config.json          # models, autonomy, budgets, environment, gates
  mcp.servers.json           # MCP server manifest (safe defaults; secrets by env only)
tools/
  tool_manifest.json         # least-privilege tool suite (19 tools)
skills/                      # 9 model-invoked Agent Skills (playbooks + checklists)
  agent-scaffolding/  tool-design/  prompt-engineering/  eval-harness/
  code-quality-gates/  mcp-integration/  subagent-orchestration/
  context-memory/  safety-guardrails/
style/                       # coding-style engine
  STYLE_CORE.md + python.md typescript.md go.md rust.md bash.md
design/
  phase1_highlevel_plan.json # framework + key decisions
  phase2_design_template.json# skeleton with <FILL> markers
  phase3_detailed_design.json# every detail resolved
  phase4_final_design.json   # reconciliation vs intent + template
  agentagent2.design.json    # AgentAgent2's own design (validates the schema)
  schemas/agent_design.schema.json
templates/
  agent_project_scaffold/    # devcontainer + CI + pre-commit + gate scripts + .env.example
```

## The operating loop
`INTENT → PLAN → DESIGN → SCAFFOLD → IMPLEMENT → VERIFY* → EVALUATE* → DELIVER → DEBRIEF`
(`*` = hard gate). Each phase emits a schema-valid JSON artifact. `VERIFY` runs `format → lint → typecheck → test → coverage → security`; `EVALUATE` runs the produced agent's eval suite. Nothing ships unless gates are green and the eval score ≥ 0.90 (safety = 1.0).

## Why it produces high-quality code
- **Objective definition of done:** the gate chain, not opinion.
- **Best-known practices encoded as skills** (progressive-disclosure playbooks) instead of rediscovered ad hoc.
- **Style enforced by tooling** across 5 languages.
- **Evaluation harness** turns acceptance criteria into measurable scores.
- **Least-privilege tools + MCP + sandbox** keep builds safe and reproducible.
- **Subagents + memory policy** let it tackle large builds within context limits.

## How to deploy
1. Load `AGENTAGENT2.system.md` as the agent's system prompt.
2. Wire the tools in `tools/tool_manifest.json` to your harness (Agent-SDK style).
3. Enable MCP servers from `config/mcp.servers.json` (inject secrets via env).
4. Bind concrete model IDs per the policy in `config/agent.config.json` (FLAG-2).
5. Point new builds at `templates/agent_project_scaffold/` for a gate-ready skeleton.

## Open flags (non-blocking)
- **FLAG-1** MCP credentials/endpoints are deployment-specific (placeholders shipped).
- **FLAG-2** exact model IDs depend on availability (policy shipped; bind at deploy).
- **FLAG-3** container base image is host-specific (devcontainer spec + defaults shipped).
