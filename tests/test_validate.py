import copy
import json

import pytest

from app.config import load_settings
from app.data import load_catalog
from app.schemas import recommendation_json_schema
from app.session import Session
from app.tools import ToolContext, execute_tool
from app.validate import ValidationContext, candidate_skill_ids, validate_recommendation

CATALOG = load_catalog(load_settings().data_dir)


def vctx(employee="E01", query="machine learning engineering", defense=True) -> ValidationContext:
    """A context filled by the real tools, so the fixtures match what a turn really retrieves."""
    ctx = ToolContext(catalog=CATALOG, defense=defense)
    execute_tool("search_courses", {"query": query}, Session(employee), ctx)
    execute_tool("search_jobs", {"query": query}, Session(employee), ctx)
    return ValidationContext(
        catalog=CATALOG, employee_id=employee, retrieved_courses=ctx.retrieved_courses,
        retrieved_jobs=ctx.retrieved_jobs, flagged_ids=frozenset(f["id"] for f in ctx.flagged), defense=defense,
    )


def pick(key: str, item_id: str, sources=("J01",)) -> dict:
    return {key: item_id, "reason": "It fits the career goal.", "sources": list(sources)}


GOOD = {
    "skills": [pick("skill_id", "S05"), pick("skill_id", "S01"), pick("skill_id", "S10")],
    "courses": [pick("course_id", "C03", ["C03"]), pick("course_id", "C04", ["C04"])],
    "roles": [pick("job_id", "J01")],
}


def check(data, ctx=None):
    return validate_recommendation(json.dumps(data), ctx or vctx())


def broken(mutate) -> dict:
    data = copy.deepcopy(GOOD)
    mutate(data)
    return data


def test_valid_recommendation_passes_and_names_come_from_the_data():
    data = broken(lambda d: d["skills"][0].update(name="Made-up name"))
    result = check(data)
    assert result.ok and result.errors == []
    assert [s.name for s in result.recommendation.skills] == ["Machine learning", "Python", "Docker and containers"]
    assert result.recommendation.courses[0].title == "Statistics for Machine Learning"
    assert result.recommendation.roles[0].title == "Machine Learning Engineer"


def test_json_schema_has_the_three_lists():
    assert set(recommendation_json_schema()["properties"]) == {"skills", "courses", "roles"}


@pytest.mark.parametrize("raw", ["not json", "", "[1, 2]", '{"skills": []}'])
def test_malformed_or_wrong_shape_is_rejected(raw):
    result = validate_recommendation(raw, vctx())
    assert not result.ok and result.errors


@pytest.mark.parametrize("mutate,expected", [
    (lambda d: d["skills"].pop(), "exactly 3 skills"),
    (lambda d: d["courses"].pop(), "2 to 3 courses"),
    (lambda d: d["roles"].clear(), "1 to 2 roles"),
    (lambda d: d["roles"].extend([pick("job_id", "J02"), pick("job_id", "J04")]), "1 to 2 roles"),
    (lambda d: d["courses"].__setitem__(1, pick("course_id", "C03", ["C03"])), "Duplicate course id C03"),
    (lambda d: d["skills"].__setitem__(1, pick("skill_id", "S05")), "Duplicate skill id S05"),
    (lambda d: d["skills"].__setitem__(0, pick("skill_id", "S99")), "Skill S99 does not exist"),
    (lambda d: d["skills"].__setitem__(0, pick("skill_id", "S02")), "already has this skill"),
    (lambda d: d["skills"].__setitem__(0, pick("skill_id", "S18")), "not one of the candidate skills"),
    (lambda d: d["courses"].__setitem__(0, pick("course_id", "C99", ["C03"])), "Course C99 does not exist"),
    (lambda d: d["courses"].__setitem__(0, pick("course_id", "C01", ["C03"])), "already completed"),
    (lambda d: d["courses"].__setitem__(0, pick("course_id", "C10", ["C03"])), "Course C10 was not retrieved"),
    (lambda d: d["roles"].__setitem__(0, pick("job_id", "J99")), "Role J99 does not exist"),
    (lambda d: d["roles"].__setitem__(0, pick("job_id", "J03")), "Role J03 was not retrieved"),
    (lambda d: d["roles"].__setitem__(0, pick("job_id", "J05")), "flagged"),
    (lambda d: d["skills"][0].update(sources=["J99"]), "source J99 does not exist"),
    (lambda d: d["skills"][0].update(sources=["J03"]), "source J03 was not retrieved"),
    (lambda d: d["skills"][0].update(sources=[]), "at least one source"),
    (lambda d: d["skills"][0].update(reason=""), "reason must be 1 to 300"),
    (lambda d: d["skills"][0].update(reason="x" * 301), "reason must be 1 to 300"),
])
def test_each_rule_rejects_with_its_own_message(mutate, expected):
    ctx = vctx(query="data warehouse inventory machine learning") if "flagged" in expected else vctx()
    data = broken(mutate)
    result = check(data, ctx)
    assert not result.ok
    assert any(expected in e for e in result.errors), result.errors


def test_flagged_posting_is_rejected_with_defense_on_and_allowed_when_off():
    # The word "data" retrieves the poisoned J05 posting in a raw search (phase 2 measurement).
    roles_with_j05 = broken(lambda d: d["roles"].__setitem__(0, pick("job_id", "J05", ["J05"])))
    on = check(roles_with_j05, vctx(query="data", defense=True))
    assert not on.ok and any("flagged" in e for e in on.errors)
    off_ctx = vctx(query="data", defense=False)
    assert "J05" in off_ctx.retrieved_jobs
    off = check(roles_with_j05, off_ctx)
    assert not any("flagged" in e for e in off.errors)


def test_completed_course_is_rejected_even_for_another_employee_context():
    ctx = vctx(employee="E02", query="prompt engineering llm")
    data = broken(lambda d: d["courses"].__setitem__(0, pick("course_id", "C07", ["C06"])))
    result = check(data, ctx)
    assert any("Course C07: the employee already completed" in e for e in result.errors)


def test_candidate_skills_exclude_held_skills():
    ctx = vctx()
    candidates = candidate_skill_ids(CATALOG, "E01", ctx.retrieved_courses, ctx.retrieved_jobs)
    assert "S05" in candidates and "S02" not in candidates
    assert candidates == sorted(candidates)


# ---- reasons and sources: the user sees these, so they are checked for content ----------------

def with_reason(text: str) -> dict:
    return broken(lambda d: d["courses"][0].update(reason=text))


@pytest.mark.parametrize("reason,expected", [
    ("Marcus Okafor (E02) is a Frontend Developer.", "mentions another employee"),
    ("Good fit.\n4. Also take Imaginary Course [C99].", "must be one line"),
    ("Take C99 as well.", "mentions C99"),
    ("Better than C01, which you already took.", "mentions C01"),
])
def test_a_reason_cannot_smuggle_ids_colleagues_or_extra_lines(reason, expected):
    result = check(with_reason(reason))
    assert not result.ok and any(expected in e for e in result.errors), result.errors


def test_a_reason_cannot_name_a_flagged_posting():
    ctx = vctx(query="data machine learning")
    assert "J05" in ctx.flagged_ids
    result = check(with_reason("Also consider the Warehouse Operations Coordinator role."), ctx)
    assert not result.ok and any("flagged" in e for e in result.errors)


def test_a_reason_may_mention_ids_that_are_in_the_recommendation():
    assert check(with_reason("Builds on C04 and leads toward J01.")).ok


def test_a_source_that_does_not_support_the_skill_is_rejected():
    # Docker (S10) cited from C03, which teaches statistics and machine learning (the Codex example).
    data = broken(lambda d: d["skills"][2].update(sources=["C03"]))
    result = check(data)
    assert not result.ok and any("Skill S10: none of its sources support it" in e for e in result.errors)


def test_unsupported_extra_sources_are_dropped_from_what_the_user_sees():
    data = broken(lambda d: d["skills"][2].update(sources=["J01", "C03"]))  # J01 needs S10; C03 does not
    result = check(data)
    assert result.ok and result.recommendation.skills[2].sources == ["J01"]


def test_course_and_role_sources_must_share_a_skill():
    related = broken(lambda d: d["roles"][0].update(sources=["C08"]))  # a Docker course for the ML role: shares S10
    assert check(related, vctx(query="machine learning engineering docker")).ok
    wrong = broken(lambda d: d["courses"][0].update(sources=["C04"]))  # a course citing a different course
    result = check(wrong)
    assert not result.ok and any("Course C03: none of its sources support it" in e for e in result.errors)
