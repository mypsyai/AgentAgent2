"""Objective quality gates: format, lint, strict type-check, tests, coverage, and a secrets scan.

Each gate shells out to the corresponding tool. A missing tool is its own status
(``"missing_tool"``) rather than being silently skipped or conflated with a real failure, so
callers can tell "not installed" apart from "ran and found problems".

Coverage does not depend on the third-party ``coverage`` package: it is measured by re-running
the test suite under the standard library's :mod:`trace` module in an isolated subprocess, then
comparing hit lines against a token-based estimate of executable lines in ``src/``. This is a
statement-coverage approximation, not a drop-in replacement for ``coverage.py`` — see
``_measure_coverage`` — but it requires nothing beyond the standard library, matching this
harness's zero-required-dependency design.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT_S = 300
COVERAGE_THRESHOLD = 0.85
MAX_OUTPUT_CHARS = 8_000

_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "private key block"),
    (r"(?i)\b(api|secret)[_-]?key\b\s*[:=]\s*['\"][A-Za-z0-9/+_-]{20,}['\"]", "hardcoded key literal"),
    (r"(?i)\bpassword\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]", "hardcoded password literal"),
)
_SECRET_SCAN_EXCLUDE_DIRS = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "node_modules", ".venv"}
)


@dataclass(frozen=True)
class GateOutcome:
    """The result of one gate.

    Attributes:
        name: Short gate identifier, e.g. ``"format"``.
        status: One of ``"pass"``, ``"fail"``, ``"missing_tool"``, or ``"error"``.
        detail: Diagnostic text (tool output, an error message); empty on a clean pass.
    """

    name: str
    status: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "pass"


@dataclass
class GateReport:
    """The aggregate result of running all configured gates, in order."""

    outcomes: list[GateOutcome] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.outcomes) and all(o.ok for o in self.outcomes)

    def summary(self) -> str:
        """A one-line ``name: status`` summary for every gate."""
        return "; ".join(f"{o.name}: {o.status}" for o in self.outcomes)

    def detail(self) -> str:
        """Full diagnostic detail for every gate that did not pass; empty string if all passed."""
        failing = [o for o in self.outcomes if not o.ok]
        if not failing:
            return ""
        return "\n\n".join(f"--- {o.name} ({o.status}) ---\n{o.detail}" for o in failing)


def run_gates(
    root: Path,
    *,
    fix: bool = False,
    coverage_threshold: float = COVERAGE_THRESHOLD,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> GateReport:
    """Run format, lint, typecheck, tests, coverage, and a secrets scan against ``root``.

    Args:
        root: Project root; expected to contain ``pyproject.toml``, ``src/``, and ``tests/``.
        fix: When true, let ``ruff`` auto-fix formatting and safe lint issues before checking.
        coverage_threshold: Minimum fraction of executed statements in ``src/`` to pass coverage.
        timeout_s: Per-subprocess timeout, in seconds.

    Returns:
        A :class:`GateReport` with one :class:`GateOutcome` per gate.
    """
    report = GateReport()
    report.outcomes.append(_run_ruff_format(root, fix=fix, timeout_s=timeout_s))
    report.outcomes.append(_run_ruff_check(root, fix=fix, timeout_s=timeout_s))
    report.outcomes.append(_run_mypy(root, timeout_s=timeout_s))
    report.outcomes.append(_run_tests(root, timeout_s=timeout_s))
    report.outcomes.append(_run_coverage(root, coverage_threshold, timeout_s=timeout_s))
    report.outcomes.append(_run_secrets_scan(root))
    return report


def _run(
    cmd: list[str], *, cwd: Path, timeout_s: int, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Run ``cmd`` and return its result, or ``None`` if the executable is not on PATH.

    A timeout or launch failure is reported as a synthetic :class:`~subprocess.CompletedProcess`
    with a non-zero return code rather than raised, so every gate has exactly one failure path
    (inspect ``returncode``) instead of also needing to catch exceptions.
    """
    if shutil.which(cmd[0]) is None:
        return None
    env = None
    if extra_env:
        env = {**os.environ, **extra_env}
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s, check=False, env=env
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, stdout="", stderr=f"Timed out after {timeout_s}s.")
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=f"Failed to launch: {exc}")


def _src_on_pythonpath(root: Path) -> dict[str, str]:
    """PYTHONPATH override so a subprocess can ``import agentagent2`` without an editable install.

    Mirrors what pytest gets for free from this project's ``[tool.pytest.ini_options] pythonpath
    = ["src"]`` — the stdlib-only fallback paths (unittest discovery, the trace coverage runner)
    need the same thing done explicitly since they do not read pyproject.toml.
    """
    src = str((root / "src").resolve())
    existing = os.environ.get("PYTHONPATH", "")
    return {"PYTHONPATH": f"{src}{os.pathsep}{existing}" if existing else src}


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated, {len(text) - limit} more characters]"


def _run_ruff_format(root: Path, *, fix: bool, timeout_s: int) -> GateOutcome:
    cmd = ["ruff", "format", *([] if fix else ["--check"]), "."]
    result = _run(cmd, cwd=root, timeout_s=timeout_s)
    if result is None:
        return GateOutcome("format", "missing_tool", "ruff is not installed (pip install 'agentagent2[dev]').")
    if result.returncode == 0:
        return GateOutcome("format", "pass")
    return GateOutcome("format", "fail", _truncate(result.stdout + result.stderr))


def _run_ruff_check(root: Path, *, fix: bool, timeout_s: int) -> GateOutcome:
    cmd = ["ruff", "check", *(["--fix"] if fix else []), "."]
    result = _run(cmd, cwd=root, timeout_s=timeout_s)
    if result is None:
        return GateOutcome("lint", "missing_tool", "ruff is not installed (pip install 'agentagent2[dev]').")
    if result.returncode == 0:
        return GateOutcome("lint", "pass")
    return GateOutcome("lint", "fail", _truncate(result.stdout + result.stderr))


def _run_mypy(root: Path, *, timeout_s: int) -> GateOutcome:
    result = _run(["mypy", "--strict", "src"], cwd=root, timeout_s=timeout_s)
    if result is None:
        return GateOutcome("typecheck", "missing_tool", "mypy is not installed (pip install 'agentagent2[dev]').")
    if result.returncode == 0:
        return GateOutcome("typecheck", "pass")
    return GateOutcome("typecheck", "fail", _truncate(result.stdout + result.stderr))


def _run_tests(root: Path, *, timeout_s: int) -> GateOutcome:
    if shutil.which("pytest") is not None:
        # Belt-and-suspenders: this harness's own pyproject.toml sets `pythonpath = ["src"]`,
        # but run_gates() is meant to work against *any* src/+tests/ project, including ones
        # without that ini option, so PYTHONPATH is injected explicitly here too.
        result = _run(["pytest"], cwd=root, timeout_s=timeout_s, extra_env=_src_on_pythonpath(root))
        if result is not None:
            status = "pass" if result.returncode == 0 else "fail"
            return GateOutcome("tests", status, _truncate(result.stdout + result.stderr))

    # Fallback: the standard library's unittest runner. Tests are written as unittest.TestCase
    # subclasses specifically so they are discoverable both by pytest and by this fallback.
    result = _run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=root,
        timeout_s=timeout_s,
        extra_env=_src_on_pythonpath(root),
    )
    if result is None:
        return GateOutcome("tests", "missing_tool", "Neither pytest nor a usable python3 were found.")
    status = "pass" if result.returncode == 0 else "fail"
    return GateOutcome("tests", status, _truncate(result.stdout + result.stderr))


def _run_coverage(root: Path, threshold: float, *, timeout_s: int) -> GateOutcome:
    src, tests = root / "src", root / "tests"
    if not src.is_dir() or not tests.is_dir():
        return GateOutcome("coverage", "error", "Expected 'src' and 'tests' directories under root.")

    runner_path = root / "_agentagent2_trace_runner.py"
    runner_path.write_text(_TRACE_RUNNER_SOURCE, encoding="utf-8")
    try:
        result = _run(
            [sys.executable, runner_path.name],
            cwd=root,
            timeout_s=timeout_s,
            extra_env=_src_on_pythonpath(root),
        )
    finally:
        runner_path.unlink(missing_ok=True)

    if result is None:
        return GateOutcome("coverage", "missing_tool", "No usable python3 interpreter was found.")
    if result.returncode not in (0, 1):
        return GateOutcome("coverage", "error", _truncate(result.stdout + result.stderr))

    fraction: float | None = None
    for line in result.stdout.splitlines():
        if line.startswith("COVERAGE_FRACTION:"):
            try:
                fraction = float(line.split(":", 1)[1])
            except ValueError:
                fraction = None

    if fraction is None:
        return GateOutcome("coverage", "error", "Coverage runner produced no measurement.\n" + _truncate(result.stdout + result.stderr))

    detail = f"{fraction:.1%} of executable statements in src/ were exercised by tests (threshold {threshold:.0%})."
    if fraction >= threshold:
        return GateOutcome("coverage", "pass", detail)
    return GateOutcome("coverage", "fail", detail)


def _run_secrets_scan(root: Path) -> GateOutcome:
    """A best-effort, dependency-free scan for obviously hardcoded credentials.

    This is a pattern match, not a real secret-scanning tool (trufflehog, gitleaks, etc.) — it
    catches egregious cases (AWS-style keys, PEM blocks, ``password = "..."`` literals) and
    nothing subtler. Treat a pass here as a floor, not a guarantee.

    ``tests/`` and ``test/`` are excluded by convention: fixtures for a secrets scanner's own
    test suite necessarily contain fake credentials shaped like real ones (this project's own
    tests are an example), and scanning them would make the gate permanently unpassable for any
    project that tests its own scanner. Real leaked credentials are far more likely to show up
    in application or config code than in deliberately-fake test fixtures.
    """
    compiled = [(re.compile(pattern), label) for pattern, label in _SECRET_PATTERNS]
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(
            part in _SECRET_SCAN_EXCLUDE_DIRS | {"tests", "test"} for part in path.parts
        ):
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in compiled:
            match = pattern.search(text)
            if match:
                lineno = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(root)}:{lineno}: possible {label}")

    if not findings:
        return GateOutcome("secrets", "pass")
    return GateOutcome("secrets", "fail", "\n".join(findings))


_TRACE_RUNNER_SOURCE = '''\
"""Standalone coverage runner (stdlib only): trace tests/, report src/ statement coverage.

Written to a temp file and run as a subprocess so a gate run never mutates the calling
process's import state (sys.modules, etc.). Deleted immediately after it runs.

Three easy-to-miss details this accounts for:

1. Discovery must be *inside* the traced region, not before it. unittest.TestLoader.discover()
   imports every test module (and transitively, the src modules under test), which executes
   each module's def/class/decorator lines exactly once. If that import happens before the
   tracer starts, those lines never register as "hit" even though they plainly ran — only the
   actual test-time *calls* into function bodies would be counted, undercounting coverage on
   every file (worst on files with many small definitions, e.g. several dataclasses).

2. trace.Trace installs its hook with sys.settrace(), which is thread-local. A test that spins
   up a background thread (e.g. this project's own HTTP server tests) would silently get zero
   coverage credit for code that only runs on that thread. threading.settrace() with the same
   trace function fixes this for threads started during the traced call.

3. "Executable line" means the first physical line of a logical statement, not every physical
   line with a token on it. A multi-line import or list literal is one statement — trace.Trace
   attributes at most one hit to it — so counting every continuation line as separately
   executable manufactures coverage gaps that could never close (this hit files with multi-line
   `__all__` lists especially hard before the fix).
"""
from __future__ import annotations

import threading
import tokenize
import trace
import unittest
from pathlib import Path


def executable_lines(path: Path) -> set[int]:
    """Line numbers where a new logical statement begins (see point 3 above)."""
    ignore = {
        tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
        tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER,
    }
    lines: set[int] = set()
    start_of_statement = True
    try:
        with tokenize.open(path) as handle:
            for tok in tokenize.generate_tokens(handle.readline):
                if tok.type == tokenize.NEWLINE:
                    start_of_statement = True
                    continue
                if tok.type in ignore or not tok.string.strip():
                    continue
                if start_of_statement:
                    lines.add(tok.start[0])
                    start_of_statement = False
    except (SyntaxError, OSError, tokenize.TokenError):
        return set()
    return lines


def discover_and_run() -> unittest.TestResult:
    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    return unittest.TextTestRunner(verbosity=0).run(suite)


def main() -> int:
    tracer = trace.Trace(count=True, trace=False)
    threading.settrace(tracer.globaltrace)  # cover background threads too (see module docstring)
    try:
        result = tracer.runfunc(discover_and_run)
    finally:
        threading.settrace(None)  # type: ignore[arg-type]
    counts = tracer.results().counts

    hit_by_file: dict[str, set[int]] = {}
    for filename, lineno in counts:
        resolved = str(Path(filename).resolve())
        hit_by_file.setdefault(resolved, set()).add(lineno)

    total_executable = 0
    total_hit = 0
    for py_file in Path("src").rglob("*.py"):
        resolved = str(py_file.resolve())
        executable = executable_lines(py_file)
        hit = hit_by_file.get(resolved, set()) & executable
        total_executable += len(executable)
        total_hit += len(hit)

    print("TESTS_OK" if result.wasSuccessful() else "TESTS_FAIL")
    if total_executable:
        print(f"COVERAGE_FRACTION:{total_hit / total_executable:.4f}")
    else:
        print("COVERAGE_FRACTION:0.0")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''
