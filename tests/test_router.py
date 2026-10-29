import pytest

from app.router import ADVISE, ENROLL, FOLLOWUP, OUT_OF_SCOPE, route_message
from app.schemas import CourseRec, Recommendation, RoleRec, SkillRec

REC = Recommendation(
    skills=[SkillRec(skill_id="S05", name="Machine learning", reason="r", sources=["C04"])],
    courses=[CourseRec(course_id="C04", title="Intro to Machine Learning", reason="r", sources=["C04"])],
    roles=[RoleRec(job_id="J01", title="Machine Learning Engineer", reason="r", sources=["J01"])],
)


@pytest.mark.parametrize("message,expected", [
    ("What skills should I develop for my next career opportunity?", ADVISE),
    ("How can I grow into a new role?", ADVISE),
    ("Any course I should take to improve?", ADVISE),
    ("Is there a promotion path for me?", ADVISE),
    ("What's the weather in Paris?", OUT_OF_SCOPE),
    ("Tell me a joke", OUT_OF_SCOPE),
    ("", OUT_OF_SCOPE),
    ("Enroll me in the first course", ENROLL),
    ("please enrol me", ENROLL),
    ("Sign me up for that one", ENROLL),
    ("register me for the second course", ENROLL),
    ("I want to sign up for a course", ENROLL),
])
def test_routes_without_a_previous_recommendation(message, expected):
    assert route_message(message) == expected


@pytest.mark.parametrize("message", [
    "Tell me more about the second course",
    "What about the first role?",
    "more about that one",
    "Explain the third skill",
    "Tell me about Intro to Machine Learning",
])
def test_followups_need_a_previous_recommendation(message):
    assert route_message(message, REC) == FOLLOWUP
    assert route_message(message) != FOLLOWUP


def test_enroll_wins_over_followup_and_advise():
    assert route_message("Enroll me in the first course", REC) == ENROLL


def test_a_fresh_career_question_stays_advise_after_a_recommendation():
    assert route_message("What skills should I develop for my next career opportunity?", REC) == ADVISE
