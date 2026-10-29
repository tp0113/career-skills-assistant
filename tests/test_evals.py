from app.config import load_settings
from evals import checks, run

SETTINGS = load_settings()


def _outcomes():
    question, cases = run.load_cases()
    return run.run_cases(cases, question, SETTINGS, real=False, repeat=1, defense_off=False)


def test_there_are_13_cases_and_only_the_followup_is_expected_to_fail():
    outcomes = _outcomes()
    assert len(outcomes) == 13
    assert {o.case_id: o.status for o in outcomes if o.status != "PASS"} == {"followup_second": "XFAIL"}


def test_every_check_a_case_names_exists():
    _, cases = run.load_cases()
    named = {c for case in cases for c in case["checks"] + case.get("defense_off_checks", [])}
    assert named <= set(checks.CHECKS)


def test_a_failing_check_makes_the_case_fail(monkeypatch):
    monkeypatch.setitem(checks.CHECKS, "route_advise", lambda r: "forced failure")
    statuses = {o.case_id: o.status for o in _outcomes()}
    assert statuses["main_question"] == "FAIL" and statuses["own_name_ok"] == "FAIL"


def test_a_pass_that_was_expected_to_fail_is_flagged(monkeypatch):
    monkeypatch.setitem(checks.CHECKS, "reply_is_about_second_course", lambda r: None)
    outcome = next(o for o in _outcomes() if o.case_id == "followup_second")
    assert outcome.status == "XPASS" and outcome.is_bad


def test_defense_off_shows_the_poisoned_role_getting_through():
    from dataclasses import replace

    question, cases = run.load_cases()
    only = [c for c in cases if c.get("defense_off_checks")]
    outcomes = run.run_cases(only, question, replace(SETTINGS, injection_defense=False), False, 1, True)
    assert [o.status for o in outcomes] == ["PASS"]
