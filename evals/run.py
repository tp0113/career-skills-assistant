"""Run the eval cases and print a pass/fail table.

  python -m evals.run                      stub model, exits 1 on any failure
  python -m evals.run --real --repeat 3    the cases tagged "real" on the configured model, a pass rate per case;
                                           also exits 1 on any failure (add --report-only to always exit 0)
  python -m evals.run --defense off        the injection case with the code layers off (shows what they stop)
  python -m evals.run --real --case poisoned_posting   only the named case(s); results are saved under a "-partial" name

Each run gets its own temporary enrollment file and conversation id, so cases never share state.
A case with "expected_fail" is a known gap: it shows as XFAIL and does not fail the run, but if it
starts passing it shows as XPASS and does, so the marker cannot be forgotten.
"""
import argparse
import json
import statistics
import tempfile
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from app.config import Settings, load_settings
from app.data import load_catalog
from app.enrollments import EnrollmentStore
from app.graph import Assistant
from app.llm import get_llm
from evals.checks import CHECKS, Run
from evals.stub_llm import StubLLM

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def _add_completed_course(valid: dict) -> dict:
    """A model that recommends a course the employee already finished (E02 completed C07)."""
    valid["courses"][0] = {"course_id": "C07", "reason": "x", "sources": ["C06"]}
    return valid


COMPOSE_SCRIPTS = {
    "bad_json_then_valid": ["this is not json", None],
    "recommend_completed_c07": [_add_completed_course, None],
}


@dataclass
class Outcome:
    case_id: str
    employee: str
    runs: int = 0
    passes: int = 0
    seconds: list[float] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    expected_fail: str = ""

    @property
    def status(self) -> str:
        if self.expected_fail:
            return "XPASS" if self.passes == self.runs else "XFAIL"
        return "PASS" if self.passes == self.runs else "FAIL"

    @property
    def is_bad(self) -> bool:
        return self.status in ("FAIL", "XPASS")


def load_cases() -> tuple[str, list[dict]]:
    data = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    return data["main_question"], data["cases"]


def _make_llm(case: dict, real_llm):
    if real_llm is not None:
        return real_llm
    stub = case["stub"]
    return StubLLM(stub["mode"], list(COMPOSE_SCRIPTS.get(stub.get("compose", ""), [])))


def run_once(case: dict, employee: str, main_question: str, settings: Settings, real_llm, check_names: list[str]) -> tuple[list[str], float]:
    """One full run of a case. Returns (failure texts, seconds)."""
    catalog = load_catalog(settings.data_dir)
    llm = _make_llm(case, real_llm)
    with tempfile.TemporaryDirectory() as tmp:
        store = EnrollmentStore(Path(tmp) / "enrollments.json")
        assistant = Assistant(settings, catalog, llm, store)
        run = Run(assistant, llm, store, catalog, employee, uuid.uuid4().hex[:8])
        started = time.perf_counter()
        try:
            last_course = None
            for turn in case["turns"]:
                if "ask" in turn:
                    result = assistant.ask(employee, run.conversation, turn["ask"].replace("$MAIN", main_question))
                else:
                    result = assistant.confirm(employee, run.conversation, turn["confirm"], last_course)
                if result.pending_enrollment:
                    last_course = result.pending_enrollment["course_id"]
                run.turns.append(result)
            seconds = time.perf_counter() - started
            failures = [f"{name}: {text}" for name in check_names if (text := CHECKS[name](run))]
        except Exception as error:  # a crash is a failure of the case, not of the eval script
            return [f"crashed: {type(error).__name__}: {error}"], time.perf_counter() - started
    return failures, seconds


def run_cases(cases: list[dict], main_question: str, settings: Settings, real: bool, repeat: int, defense_off: bool) -> list[Outcome]:
    real_llm = get_llm(settings) if real else None
    outcomes = []
    for case in cases:
        employees = case.get("real", []) if real else [case["employee"]]
        checks = case.get("defense_off_checks", []) if defense_off else case["checks"]
        for employee in employees:
            outcome = Outcome(case["id"], employee, expected_fail=case.get("expected_fail", ""))
            for _ in range(repeat if real else 1):
                failures, seconds = run_once(case, employee, main_question, settings, real_llm, checks)
                outcome.runs += 1
                outcome.passes += not failures
                outcome.seconds.append(seconds)
                outcome.failures += [f for f in failures if f not in outcome.failures]
            outcomes.append(outcome)
            print(f"  {outcome.status:5} {outcome.case_id} ({employee}) {outcome.passes}/{outcome.runs}", flush=True)
    return outcomes


def render_table(outcomes: list[Outcome], real: bool) -> str:
    head = "| Case | Employee | Result | Passed |" + (" Median s |" if real else "") + " Notes |"
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for o in outcomes:
        notes = "; ".join(o.failures) if o.failures else ""
        if o.expected_fail:
            notes = f"expected to fail: {o.expected_fail}" + (f" ({notes})" if notes else "")
        median = f" {statistics.median(o.seconds):.1f} |" if real else ""
        lines.append(f"| {o.case_id} | {o.employee} | {o.status} | {o.passes}/{o.runs} |{median} {notes} |")
    return "\n".join(lines)


def summary_line(outcomes: list[Outcome]) -> str:
    counts = {s: sum(o.status == s for o in outcomes) for s in ("PASS", "FAIL", "XFAIL", "XPASS")}
    text = f"{counts['PASS']}/{len(outcomes)} PASS"
    return text + "".join(f", {n} {s}" for s, n in counts.items() if s != "PASS" and n)


def save(outcomes: list[Outcome], settings: Settings, real: bool, repeat: int, defense_off: bool, partial: bool = False) -> Path:
    kind = ("real" if real else "stub") + ("-defense-off" if defense_off else "")
    kind += "-partial" if partial else ""
    path = RESULTS / f"{kind}-{date.today().isoformat()}.md"
    model = f"{settings.ollama_model}, num_ctx {settings.ollama_num_ctx}, {repeat} runs per case" if real else "deterministic stub model"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"# Eval results ({kind}, {date.today().isoformat()})\n\nModel: {model}.\n\n"
                    f"{render_table(outcomes, real)}\n\n**{summary_line(outcomes)}**\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the eval cases.")
    parser.add_argument("--real", action="store_true", help="run the cases tagged real on the configured model")
    parser.add_argument("--repeat", type=int, default=3, help="runs per case with --real (default 3)")
    parser.add_argument("--defense", choices=["on", "off"], default="on", help="off: injection case only, layers 2-3 off")
    parser.add_argument("--case", action="append", help="run only this case id (repeatable)")
    parser.add_argument("--report-only", action="store_true", help="print and save the results, but always exit 0")
    args = parser.parse_args(argv)

    # The flag decides, not INJECTION_DEFENSE in the environment (Codex checkpoint 2 finding 6).
    defense_off = args.defense == "off"
    settings = replace(load_settings(), injection_defense=not defense_off)
    main_question, cases = load_cases()
    if defense_off:
        cases = [c for c in cases if c.get("defense_off_checks")]
    if args.case:
        unknown = set(args.case) - {c["id"] for c in cases}
        if unknown:
            parser.error(f"unknown case id(s): {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in args.case]
    print(f"Running {'real model ' + settings.ollama_model if args.real else 'stub model'}:")
    outcomes = run_cases(cases, main_question, settings, args.real, args.repeat, defense_off)
    print("\n" + render_table(outcomes, args.real))
    print("\n" + summary_line(outcomes))
    print(f"saved {save(outcomes, settings, args.real, args.repeat, defense_off, bool(args.case))}")
    # Both runs gate (Codex checkpoint 2 finding 5); a measuring run on the flaky real model says --report-only.
    if args.report_only:
        print("report only: exit 0 whatever the results")
        return 0
    return int(any(o.is_bad for o in outcomes))


if __name__ == "__main__":
    raise SystemExit(main())
