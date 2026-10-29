from app.config import load_settings
from evals import checks, run

SETTINGS = load_settings()


def _outcomes():
    question, cases = run.load_cases()
    return run.run_cases(cases, question, SETTINGS, real=False, repeat=1, defense_off=False)


def test_there_are_14_cases_and_all_pass_on_the_stub():
    outcomes = _outcomes()
    assert len(outcomes) == 14
    assert {o.case_id: o.status for o in outcomes if o.status != "PASS"} == {}


def test_every_check_a_case_names_exists():
    _, cases = run.load_cases()
    named = {c for case in cases for c in case["checks"] + case.get("defense_off_checks", [])}
    assert named <= set(checks.CHECKS)


def test_a_failing_check_makes_the_case_fail(monkeypatch):
    monkeypatch.setitem(checks.CHECKS, "route_advise", lambda r: "forced failure")
    statuses = {o.case_id: o.status for o in _outcomes()}
    assert statuses["main_question"] == "FAIL" and statuses["own_name_ok"] == "FAIL"


def test_a_pass_that_was_expected_to_fail_is_flagged():
    question, cases = run.load_cases()
    marked = [{**c, "expected_fail": "pretend gap"} for c in cases if c["id"] == "followup_second"]
    outcome = run.run_cases(marked, question, SETTINGS, real=False, repeat=1, defense_off=False)[0]
    assert outcome.status == "XPASS" and outcome.is_bad


def test_a_failing_check_that_was_expected_to_fail_shows_xfail(monkeypatch):
    monkeypatch.setitem(checks.CHECKS, "reply_is_about_second_course", lambda r: "forced failure")
    question, cases = run.load_cases()
    marked = [{**c, "expected_fail": "pretend gap"} for c in cases if c["id"] == "followup_second"]
    outcome = run.run_cases(marked, question, SETTINGS, real=False, repeat=1, defense_off=False)[0]
    assert outcome.status == "XFAIL" and not outcome.is_bad


def test_defense_off_shows_the_poisoned_role_getting_through():
    from dataclasses import replace

    question, cases = run.load_cases()
    only = [c for c in cases if c.get("defense_off_checks")]
    outcomes = run.run_cases(only, question, replace(SETTINGS, injection_defense=False), False, 1, True)
    assert [o.status for o in outcomes] == ["PASS"]


def test_before_after_on_the_obedient_stub_shows_what_the_code_layers_stop():
    from dataclasses import replace

    from evals import before_after
    from evals.stub_llm import StubLLM

    question = before_after._question()
    on = before_after.measure(replace(SETTINGS, injection_defense=True), StubLLM("obedient"), question, "E02", "on", 2)
    off = before_after.measure(replace(SETTINGS, injection_defense=False), StubLLM("obedient"), question, "E02", "off", 2)
    assert (on.reached, on.flagged, on.recommended, on.valid) == (2, 2, 0, 2)
    assert (off.reached, off.flagged, off.recommended, off.valid) == (2, 0, 2, 2)


# ---- the checks and the runner must be able to fail (Codex checkpoint 2, findings 4 to 6) ----------

def _run(employee: str, *messages: str, llm=None) -> checks.Run:
    import tempfile
    from pathlib import Path

    from app.data import load_catalog
    from app.enrollments import EnrollmentStore
    from app.graph import Assistant
    from evals.stub_llm import StubLLM

    llm = llm or StubLLM()
    store = EnrollmentStore(Path(tempfile.mkdtemp()) / "enrollments.json")
    catalog = load_catalog(SETTINGS.data_dir)
    case = checks.Run(Assistant(SETTINGS, catalog, llm, store), llm, store, catalog, employee, "c1")
    case.turns = [case.assistant.ask(employee, "c1", m) for m in messages]
    return case


def test_the_follow_up_check_fails_on_the_wrong_route_or_a_model_call():
    from dataclasses import replace

    case = _run("E01", run.load_cases()[0], "Tell me more about the second course")
    assert checks.reply_is_about_second_course(case) is None
    case.turns[-1] = replace(case.last, route="advise", outcome="ok")
    assert "route 'advise'" in checks.reply_is_about_second_course(case)
    case.turns[-1] = replace(case.last, route="followup", outcome="followup", usage={"model_calls": 1})
    assert "model calls 1" in checks.reply_is_about_second_course(case)


def test_j05_not_recommended_needs_an_actual_recommendation():
    from dataclasses import replace

    case = _run("E01", "What's the weather in Paris?")
    case.turns[0] = replace(case.first, outcome="ok", recommendation=None)
    assert "no valid recommendation" in checks.j05_not_recommended(case)


def test_j05_flagged_fails_when_the_flagged_row_still_reaches_the_model(monkeypatch):
    from app import tools
    from evals import before_after
    from evals.stub_llm import StubLLM

    question = before_after._question()
    assert checks.j05_flagged(_run("E01", question, llm=StubLLM("obedient"))) is None
    original = tools._quarantine
    monkeypatch.setattr(tools, "_quarantine", lambda rows, source, ctx: (original(rows, source, ctx), rows)[1])
    assert "still reached the model" in checks.j05_flagged(_run("E01", question, llm=StubLLM("obedient")))


def test_a_real_run_with_a_failure_exits_1_unless_report_only(monkeypatch, tmp_path):
    from evals.stub_llm import StubLLM

    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setattr(run, "get_llm", lambda settings: StubLLM("no_tools"))
    assert run.main(["--real", "--repeat", "1", "--case", "main_question"]) == 1
    assert run.main(["--real", "--repeat", "1", "--case", "main_question", "--report-only"]) == 0


def test_defense_on_wins_over_injection_defense_off_in_the_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setenv("INJECTION_DEFENSE", "off")
    assert run.main(["--defense", "on", "--case", "poisoned_posting"]) == 0
