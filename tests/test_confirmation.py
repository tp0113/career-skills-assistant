import pytest

from app.confirmation import answer_is_yes, is_explicit_yes


@pytest.mark.parametrize("text", ["yes", "Yes", "Y", "yes please", "Yes, please!", "confirm", "  YES enroll me. "])
def test_explicit_yes(text):
    assert is_explicit_yes(text)


@pytest.mark.parametrize("text", ["maybe", "sure but later", "no", "", "yes but not now", "yeah", "ok", "yes yes",
                                  "yes, 但不要报名", "yes?", "yes; no", "yes 🙂", "yés"])
def test_everything_else_is_not_yes(text):
    assert not is_explicit_yes(text)


def test_structured_answers_must_name_the_pending_course():
    assert answer_is_yes({"confirm": True, "course_id": "C03"}, "C03")
    assert not answer_is_yes({"confirm": True, "course_id": "C04"}, "C03")  # a stale button for another course
    assert not answer_is_yes({"confirm": True}, "C03")
    assert not answer_is_yes({"confirm": False, "course_id": "C03"}, "C03")
    assert not answer_is_yes({"confirm": "true", "course_id": "C03"}, "C03")
    assert not answer_is_yes(True, "C03") and not answer_is_yes(None, "C03") and not answer_is_yes({}, "C03")
    assert answer_is_yes("yes", "C03")
