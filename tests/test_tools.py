import pytest

from app.config import load_settings
from app.data import load_catalog
from app.session import Session
from app.tools import ToolContext, execute_tool, tool_schemas

CATALOG = load_catalog(load_settings().data_dir)
E01 = Session("E01")


def ctx(**kw) -> ToolContext:
    return ToolContext(catalog=CATALOG, **kw)


def test_four_tools_with_schemas():
    names = [s["function"]["name"] for s in tool_schemas()]
    assert names == ["get_employee_profile", "search_courses", "search_jobs", "enroll_in_course"]


def test_no_schema_has_an_employee_property():
    for schema in tool_schemas():
        props = schema["function"]["parameters"].get("properties", {})
        assert not any("employee" in key.lower() for key in props)


def test_schema_subset_by_name():
    assert [s["function"]["name"] for s in tool_schemas(["search_jobs"])] == ["search_jobs"]


@pytest.mark.parametrize("name,good", [
    ("get_employee_profile", {}),
    ("search_courses", {"query": "python"}),
    ("search_jobs", {"query": "python"}),
    ("enroll_in_course", {"course_id": "C04"}),
])
def test_smuggled_employee_id_is_rejected(name, good):
    result = execute_tool(name, {**good, "employee_id": "E02"}, E01, ctx())
    assert not result.ok and "employee_id" in result.error


def test_unknown_tool_rejected():
    result = execute_tool("delete_everything", {}, E01, ctx())
    assert not result.ok and "unknown tool" in result.error


def test_tool_not_offered_is_rejected():
    result = execute_tool("get_employee_profile", {}, E01, ctx(offered=frozenset({"search_jobs"})))
    assert not result.ok and "not available" in result.error


def test_json_string_arguments_are_parsed():
    assert execute_tool("enroll_in_course", '{"course_id": "C04"}', E01, ctx()).ok


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]", {"course_id": "X1"}, {"course_id": "c04"}, {}])
def test_bad_arguments_are_rejected(raw):
    assert not execute_tool("enroll_in_course", raw, E01, ctx()).ok


def test_query_length_limits():
    assert not execute_tool("search_courses", {"query": ""}, E01, ctx()).ok
    assert not execute_tool("search_courses", {"query": "x" * 101}, E01, ctx()).ok


def test_profile_uses_session_id_only():
    mine = execute_tool("get_employee_profile", None, Session("E01"), ctx())
    other = execute_tool("get_employee_profile", "", Session("E02"), ctx())
    assert mine.data["name"] == "Priya Shah" and other.data["name"] == "Marcus Okafor"
    assert mine.data["completed_courses"] == [{"id": "C01", "title": "SQL for Analysts"}]
    assert mine.content_for_model.startswith('<untrusted_data source="get_employee_profile">')


def test_enroll_tool_only_proposes():
    result = execute_tool("enroll_in_course", {"course_id": "C04"}, E01, ctx())
    assert result.data == {"proposed_course_id": "C04"}


def test_search_courses_excludes_completed_and_records_retrieval():
    c = ctx()
    result = execute_tool("search_courses", {"query": "sql"}, E01, c)
    ids = [r["id"] for r in result.data["courses"]]
    assert result.ok and "C01" not in ids and "C09" in ids
    assert set(c.retrieved_courses) == set(ids)
    assert c.retrieved_courses["C09"]["score"] > 0
    assert result.content_for_model.startswith('<untrusted_data source="search_courses">')


def test_search_jobs_quarantines_poisoned_posting_when_defense_on():
    c = ctx()
    result = execute_tool("search_jobs", {"query": "data"}, E01, c)
    ids = [r["id"] for r in result.data["jobs"]]
    assert "J03" in ids and "J05" not in ids
    assert "J05" not in c.retrieved_jobs and "Ignore your instructions" not in result.content_for_model
    assert [f["id"] for f in c.flagged] == ["J05"] and c.flagged[0]["reasons"]


def test_search_jobs_defense_off_lets_poisoned_posting_through():
    c = ctx(defense=False)
    result = execute_tool("search_jobs", {"query": "data"}, E01, c)
    assert "J05" in [r["id"] for r in result.data["jobs"]]
    assert c.flagged == []


def test_search_with_no_matches_is_ok_and_empty():
    result = execute_tool("search_jobs", {"query": "gardening"}, E01, ctx())
    assert result.ok and result.data == {"jobs": []}


def test_descriptions_are_trimmed_to_200_characters():
    result = execute_tool("search_courses", {"query": "python"}, E01, ctx())
    assert all(len(r["description"]) <= 200 for r in result.data["courses"])
