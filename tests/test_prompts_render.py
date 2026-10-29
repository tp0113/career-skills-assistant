from app import prompts
from app.render import render_enroll_question, render_enrolled, render_recommendation
from app.schemas import CourseRec, Recommendation, RoleRec, SkillRec


def test_advise_system_prompt_is_at_most_150_words():
    assert len(prompts.ADVISE_SYSTEM.split()) <= 150


def test_compose_messages_wrap_every_data_block_as_untrusted():
    messages = prompts.compose_messages("q", {"name": "x"}, [{"id": "C03"}], [{"id": "J01"}], [{"id": "S05"}])
    assert messages[0]["role"] == "system" and messages[1]["role"] == "user"
    body = messages[1]["content"]
    for source in ("profile", "courses", "jobs", "candidate_skills"):
        assert f'<untrusted_data source="{source}">' in body


def test_repair_message_lists_each_error():
    message = prompts.repair_message(["Course C99 does not exist.", "Give exactly 3 skills, but there are 2."])
    assert message["role"] == "user"
    assert "- Course C99 does not exist." in message["content"] and "- Give exactly 3 skills" in message["content"]


def test_enroll_messages_number_the_courses():
    messages = prompts.enroll_messages("Enroll me in the second one", [
        {"course_id": "C03", "title": "A"}, {"course_id": "C04", "title": "B"}])
    assert "2. C04: B" in messages[0]["content"]


def test_render_uses_the_data_titles_and_shows_sources():
    rec = Recommendation(
        skills=[SkillRec(skill_id="S05", name="Machine learning", reason="Core skill.", sources=["J01"])],
        courses=[CourseRec(course_id="C04", title="Intro to Machine Learning", reason="Start here.", sources=["C04"])],
        roles=[RoleRec(job_id="J01", title="Machine Learning Engineer", reason="Matches your goal.", sources=["J01", "C04"])],
    )
    text = render_recommendation(rec)
    assert "1. Machine learning: Core skill. (from J01)" in text
    assert "Intro to Machine Learning [C04]" in text
    assert "(from J01, C04)" in text
    assert "Enroll me in the first course" in text


def test_enroll_texts():
    assert "Intro [C04]" in render_enroll_question("C04", "Intro")
    assert "enrolled in Intro" in render_enrolled("C04", "Intro", True)
    assert "already enrolled" in render_enrolled("C04", "Intro", False)
