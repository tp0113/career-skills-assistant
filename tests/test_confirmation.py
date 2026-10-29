import pytest

from app.confirmation import answer_is_yes, is_explicit_yes


@pytest.mark.parametrize("text", ["yes", "Yes", "Y", "yes please", "Yes, please!", "confirm", "  YES enroll me. "])
def test_explicit_yes(text):
    assert is_explicit_yes(text)


@pytest.mark.parametrize("text", ["maybe", "sure but later", "no", "", "yes but not now", "yeah", "ok", "yes yes"])
def test_everything_else_is_not_yes(text):
    assert not is_explicit_yes(text)


def test_structured_answers():
    assert answer_is_yes({"confirm": True})
    assert not answer_is_yes({"confirm": False})
    assert not answer_is_yes({"confirm": "true"})
    assert not answer_is_yes(True) and not answer_is_yes(None) and not answer_is_yes({})
    assert answer_is_yes("yes")
