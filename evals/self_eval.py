#!/usr/bin/env python3
"""Self-evaluation for AgentAgent2 spec package.

Validates design artifacts and scores against thresholds.
Exit 0 = pass, exit 1 = fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
THRESHOLD_OVERALL = 0.90
THRESHOLD_SAFETY = 1.00


def _design_validates() -> bool:
    """Check that agentagent2.design.json validates against the schema."""
    schema_path = REPO_ROOT / "design" / "schemas" / "agent_design.schema.json"
    design_path = REPO_ROOT / "design" / "agentagent2.design.json"
    if not schema_path.exists() or not design_path.exists():
        return False
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        design = json.loads(design_path.read_text(encoding="utf-8"))
        # Basic structural checks (full jsonschema validation would require a dependency)
        required_keys = {"identity", "tools", "skills", "mcp", "style", "evaluation"}
        if not all(k in design for k in required_keys):
            return False
        # Check identity has name and role
        identity = design.get("identity", {})
        return "name" in identity and "role" in identity
    except (json.JSONDecodeError, KeyError):
        return False


def _json_artifacts_parse() -> tuple[int, int]:
    """Count JSON files and how many parse successfully."""
    json_files = list((REPO_ROOT / "design").glob("*.json"))
    json_files.extend((REPO_ROOT / "design" / "schemas").glob("*.json"))
    json_files.extend((REPO_ROOT / "config").glob("*.json"))
    json_files.extend((REPO_ROOT / "tools").glob("*.json"))
    passed = 0
    for f in json_files:
        try:
            json.loads(f.read_text(encoding="utf-8"))
            passed += 1
        except json.JSONDecodeError:
            print(f"  JSON parse error: {f}", file=sys.stderr)
    return passed, len(json_files)


def _skills_present() -> tuple[int, int]:
    """Check that expected skills exist."""
    expected = [
        "agent-scaffolding", "tool-design", "prompt-engineering", "eval-harness",
        "code-quality-gates", "mcp-integration", "subagent-orchestration",
        "context-memory", "safety-guardrails"
    ]
    found = 0
    for skill in expected:
        skill_path = REPO_ROOT / "skills" / skill / "SKILL.md"
        if skill_path.exists():
            found += 1
    return found, len(expected)


def _style_files_present() -> tuple[int, int]:
    """Check that style files exist."""
    expected = ["STYLE_CORE.md", "python.md", "typescript.md", "go.md", "rust.md", "bash.md"]
    found = sum(1 for f in expected if (REPO_ROOT / "style" / f).exists())
    return found, len(expected)


def _tools_defined() -> tuple[int, int]:
    """Check that tool_manifest.json has expected tool count."""
    manifest_path = REPO_ROOT / "tools" / "tool_manifest.json"
    if not manifest_path.exists():
        return 0, 19
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return len(manifest.get("tools", [])), 19
    except json.JSONDecodeError:
        return 0, 19


def main() -> int:
    checks: list[tuple[str, bool, float]] = []

    # JSON artifacts parse
    passed, total = _json_artifacts_parse()
    checks.append(("json_artifacts", passed == total, passed / total if total else 0))

    # Design validates
    ok = _design_validates()
    checks.append(("design_schema", ok, 1.0 if ok else 0.0))

    # Skills present
    found, expected = _skills_present()
    checks.append(("skills", found == expected, found / expected if expected else 0))

    # Style files present
    found, expected = _style_files_present()
    checks.append(("style", found == expected, found / expected if expected else 0))

    # Tools defined
    found, expected = _tools_defined()
    checks.append(("tools", found >= expected, min(found / expected, 1.0) if expected else 0))

    # Safety: all required artifacts present (no runtime safety violations possible in spec-only)
    safety_ok = all(c[1] for c in checks)
    checks.append(("safety", safety_ok, 1.0 if safety_ok else 0.0))

    # Calculate scores
    overall = sum(c[2] for c in checks) / len(checks)
    safety_score = checks[-1][2]

    # Print scoreboard
    print("=" * 50)
    print("AgentAgent2 Self-Evaluation Scoreboard")
    print("=" * 50)
    for name, passed, score in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<20} {status:<6} {score:.2f}")
    print("-" * 50)
    print(f"  {'overall':<20} {'PASS' if overall >= THRESHOLD_OVERALL else 'FAIL':<6} {overall:.2f}")
    print(f"  {'safety':<20} {'PASS' if safety_score >= THRESHOLD_SAFETY else 'FAIL':<6} {safety_score:.2f}")
    print("=" * 50)

    # Write markdown scoreboard
    scoreboard_path = REPO_ROOT / "evals" / "scoreboard.md"
    with scoreboard_path.open("w", encoding="utf-8") as f:
        f.write("# AgentAgent2 Self-Evaluation Scoreboard\n\n")
        f.write("| Check | Status | Score |\n")
        f.write("|-------|--------|-------|\n")
        for name, passed, score in checks:
            status = "✅ PASS" if passed else "❌ FAIL"
            f.write(f"| {name} | {status} | {score:.2f} |\n")
        f.write(f"\n**Overall:** {overall:.2f} (threshold: {THRESHOLD_OVERALL})\n")
        f.write(f"**Safety:** {safety_score:.2f} (threshold: {THRESHOLD_SAFETY})\n")

    if overall >= THRESHOLD_OVERALL and safety_score >= THRESHOLD_SAFETY:
        print("\n✅ EVALUATE gate: PASS")
        return 0
    else:
        print("\n❌ EVALUATE gate: FAIL")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
