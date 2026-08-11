"""The nine-phase AgentAgent2 loop: INTENT..DEBRIEF, with VERIFY/EVALUATE as hard, objectively
checked gates and a bounded repair loop back into IMPLEMENT on gate failure.

This mirrors ``AGENTAGENT2.system.md``: INTENT, PLAN, DESIGN, SCAFFOLD, and IMPLEMENT run as
ordinary conversational turns through an :class:`~agentagent2.agent.AgentLoop`. VERIFY runs the
real quality gates (:func:`agentagent2.gates.run_gates`) against the workspace — not a model
self-report. EVALUATE runs a caller-supplied ``evaluate_fn`` (default: an always-pass stub,
since there is no universal eval suite for an arbitrary task). On a gate failure the runner
feeds a defect report back into IMPLEMENT, up to ``max_repair_loops`` times, then escalates
rather than looping forever.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .agent import AgentLoop
from .gates import GateReport, run_gates
from .llm.base import Message
from .logging import AuditLog

DEFAULT_MAX_REPAIR_LOOPS = 3


class Phase(Enum):
    """The nine phases of the AgentAgent2 operating loop, in order."""

    INTENT = "INTENT"
    PLAN = "PLAN"
    DESIGN = "DESIGN"
    SCAFFOLD = "SCAFFOLD"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
    EVALUATE = "EVALUATE"
    DELIVER = "DELIVER"
    DEBRIEF = "DEBRIEF"


class PhaseStatus(Enum):
    """The outcome of a single phase."""

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


_PHASE_PROMPTS: dict[Phase, str] = {
    Phase.INTENT: (
        "Phase INTENT: decompose the task into explicit goals. List ambiguities and resolve "
        "each by ASSUME (record the assumption), since authority is delegated. State concrete "
        "success criteria."
    ),
    Phase.PLAN: (
        "Phase PLAN: choose the framework and key decisions only (no minutiae). Identify which "
        "tools you will use and produce a short risk register."
    ),
    Phase.DESIGN: (
        "Phase DESIGN: fully specify what you will build — structure, interfaces, and behavior "
        "— in enough detail to implement without further open questions."
    ),
    Phase.SCAFFOLD: (
        "Phase SCAFFOLD: create the project layout (directories and any skeleton files) needed "
        "before implementation."
    ),
    Phase.IMPLEMENT: (
        "Phase IMPLEMENT: build the smallest correct, complete slice. Write real, working code "
        "and tests, no placeholders. Then stop."
    ),
    Phase.DELIVER: (
        "Phase DELIVER: summarize what was built and confirm it is in place and ready for the "
        "user."
    ),
    Phase.DEBRIEF: (
        "Phase DEBRIEF: report what was accomplished, note any known limitations, and suggest "
        "reasonable next steps."
    ),
}

#: Phases driven by an ordinary model turn, in run order (VERIFY/EVALUATE are handled separately).
CONVERSATIONAL_PHASES: tuple[Phase, ...] = (
    Phase.INTENT,
    Phase.PLAN,
    Phase.DESIGN,
    Phase.SCAFFOLD,
    Phase.IMPLEMENT,
)


@dataclass(frozen=True)
class PhaseResult:
    """The outcome of one phase."""

    phase: Phase
    status: PhaseStatus
    summary: str
    detail: str = ""


@dataclass
class PhaseRunReport:
    """The full trace of a :meth:`PhaseRunner.run` call."""

    task: str
    results: list[PhaseResult] = field(default_factory=list)
    repair_loops: int = 0
    escalated: bool = False

    @property
    def passed(self) -> bool:
        """True if the run reached DEBRIEF without escalating or a hard-gate failure."""
        return not self.escalated and all(r.status is not PhaseStatus.FAIL for r in self.results)

    def result_for(self, phase: Phase) -> PhaseResult | None:
        """The most recent result recorded for ``phase``, or ``None`` if it never ran."""
        for result in reversed(self.results):
            if result.phase is phase:
                return result
        return None


EvaluateFn = Callable[[Path], PhaseResult]


def default_evaluate(_workspace: Path) -> PhaseResult:
    """The default EVALUATE step: always passes.

    There is no universal eval suite for an arbitrary task, so this is a stub. Pass a real
    ``evaluate_fn`` to :class:`PhaseRunner` (e.g. one that runs a produced agent's eval suite
    and scores it) to make EVALUATE a meaningful gate rather than a formality.
    """
    return PhaseResult(
        phase=Phase.EVALUATE,
        status=PhaseStatus.PASS,
        summary="No eval suite configured; EVALUATE defaults to pass.",
    )


@dataclass
class PhaseRunner:
    """Drives an :class:`AgentLoop` through the nine AgentAgent2 phases for one task.

    Attributes:
        agent: The underlying tool-use loop.
        workspace: Project root that VERIFY's quality gates run against.
        evaluate_fn: Scores the EVALUATE phase; defaults to :func:`default_evaluate`.
        max_repair_loops: Times to retry IMPLEMENT after a VERIFY/EVALUATE failure before
            escalating (matches the "max 3 auto-repair loops" rule in AGENTAGENT2.system.md).
        log: Optional audit log for phase transitions.
    """

    agent: AgentLoop
    workspace: Path
    evaluate_fn: EvaluateFn = default_evaluate
    max_repair_loops: int = DEFAULT_MAX_REPAIR_LOOPS
    log: AuditLog | None = None

    def run(self, task: str) -> PhaseRunReport:
        """Run all nine phases for ``task`` and return the full trace.

        Forward-only except the bounded VERIFY/EVALUATE -> IMPLEMENT repair loop. Stops early
        (without running VERIFY/DELIVER/DEBRIEF) if a conversational phase itself fails by
        exhausting its step budget.
        """
        report = PhaseRunReport(task=task)
        messages: list[Message] | None = None

        for phase in CONVERSATIONAL_PHASES:
            instruction = f"{_PHASE_PROMPTS[phase]}\n\nTask: {task}"
            result, messages = self._run_conversational(phase, instruction, messages)
            report.results.append(result)
            if result.status is PhaseStatus.FAIL:
                self._log(f"phase {phase.value} failed (step limit); stopping before gates.")
                return report

        messages = self._gate_loop(report, task, messages)
        if report.escalated:
            return report

        for phase in (Phase.DELIVER, Phase.DEBRIEF):
            instruction = f"{_PHASE_PROMPTS[phase]}\n\nTask: {task}"
            result, messages = self._run_conversational(phase, instruction, messages)
            report.results.append(result)

        return report

    def _gate_loop(
        self, report: PhaseRunReport, task: str, messages: list[Message] | None
    ) -> list[Message] | None:
        """Run VERIFY/EVALUATE, repairing via IMPLEMENT on failure, up to ``max_repair_loops``."""
        for attempt in range(self.max_repair_loops + 1):
            verify_result = self._verify()
            if verify_result.status is PhaseStatus.PASS:
                evaluate_result = self.evaluate_fn(self.workspace)
            else:
                evaluate_result = PhaseResult(
                    phase=Phase.EVALUATE, status=PhaseStatus.SKIPPED, summary="Skipped: VERIFY failed."
                )

            if verify_result.status is PhaseStatus.PASS and evaluate_result.status is PhaseStatus.PASS:
                report.results.extend([verify_result, evaluate_result])
                return messages

            if attempt >= self.max_repair_loops:
                report.results.extend([verify_result, evaluate_result])
                report.escalated = True
                self._log(f"gates failed after {attempt} repair loop(s); escalating to the user.")
                return messages

            report.repair_loops += 1
            defect_report = _defect_report(verify_result, evaluate_result)
            self._log(f"repair loop {report.repair_loops}: retrying IMPLEMENT.")
            instruction = (
                f"{_PHASE_PROMPTS[Phase.IMPLEMENT]}\n\n"
                f"The VERIFY/EVALUATE gates just failed. Fix the defects below, then stop.\n\n"
                f"Task: {task}\n\n{defect_report}"
            )
            repair_result, messages = self._run_conversational(Phase.IMPLEMENT, instruction, messages)
            report.results.append(repair_result)
            if repair_result.status is PhaseStatus.FAIL:
                report.escalated = True
                self._log("repair attempt hit its step limit; escalating to the user.")
                return messages

        return messages  # pragma: no cover - loop always returns within max_repair_loops + 1 iterations

    def _run_conversational(
        self, phase: Phase, instruction: str, messages: list[Message] | None
    ) -> tuple[PhaseResult, list[Message]]:
        agent_result = self.agent.run(instruction, messages=messages)
        self._log(
            f"phase {phase.value}: {agent_result.step_count} step(s), stop={agent_result.stop_reason}"
        )
        status = PhaseStatus.FAIL if agent_result.hit_step_limit else PhaseStatus.PASS
        summary = agent_result.final_text or "(no text response)"
        return PhaseResult(phase=phase, status=status, summary=summary), agent_result.messages

    def _verify(self) -> PhaseResult:
        gate_report: GateReport = run_gates(self.workspace)
        status = PhaseStatus.PASS if gate_report.passed else PhaseStatus.FAIL
        return PhaseResult(
            phase=Phase.VERIFY, status=status, summary=gate_report.summary(), detail=gate_report.detail()
        )

    def _log(self, message: str) -> None:
        if self.log is not None:
            self.log.event("phase", message)


def _defect_report(verify: PhaseResult, evaluate: PhaseResult) -> str:
    parts: list[str] = []
    if verify.status is PhaseStatus.FAIL:
        parts.append(f"VERIFY failures:\n{verify.detail or verify.summary}")
    if evaluate.status is PhaseStatus.FAIL:
        parts.append(f"EVALUATE failures:\n{evaluate.detail or evaluate.summary}")
    return "\n\n".join(parts) if parts else "Gate failed with no further detail available."
