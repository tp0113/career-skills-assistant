"""The shape of a recommendation, in two forms.

`ModelRecommendation` is what the model fills: ids, reasons and sources only (F12). Extra fields
such as a made-up `title` are ignored. `Recommendation` is what the rest of the app and the UI
see; code adds the `name` and `title` from the data after validation, so a hallucinated title
cannot appear.
"""
from pydantic import BaseModel

SKILL_COUNT = 3
COURSE_RANGE = (2, 3)
ROLE_RANGE = (1, 2)
MAX_REASON_CHARS = 300


class SkillPick(BaseModel):
    skill_id: str
    reason: str
    sources: list[str]


class CoursePick(BaseModel):
    course_id: str
    reason: str
    sources: list[str]


class RolePick(BaseModel):
    job_id: str
    reason: str
    sources: list[str]


class ModelRecommendation(BaseModel):
    skills: list[SkillPick]
    courses: list[CoursePick]
    roles: list[RolePick]


class SkillRec(SkillPick):
    name: str


class CourseRec(CoursePick):
    title: str


class RoleRec(RolePick):
    title: str


class Recommendation(BaseModel):
    skills: list[SkillRec]
    courses: list[CourseRec]
    roles: list[RoleRec]


def recommendation_json_schema() -> dict:
    """Sent to Ollama as `format`, so decoding is constrained to this shape (F10).

    Counts are not in the schema on purpose: validate.py checks them and gives a readable error.
    """
    return ModelRecommendation.model_json_schema()
