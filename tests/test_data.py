import json
import shutil

import pytest

from app.config import load_settings
from app.data import DataError, load_catalog


@pytest.fixture
def catalog():
    return load_catalog(load_settings().data_dir)


def test_counts(catalog):
    assert len(catalog.employees) == 3
    assert len(catalog.skills) == 18
    assert len(catalog.courses) == 10
    assert len(catalog.jobs) == 5


def test_lookup_and_skill_names(catalog):
    assert catalog.employees["E01"].name == "Priya Shah"
    assert catalog.skill_names(["S01", "S02"]) == ["Python", "SQL"]


def test_files_are_labeled_synthetic():
    for name in ("employees", "skills", "courses", "jobs"):
        raw = json.loads((load_settings().data_dir / f"{name}.json").read_text(encoding="utf-8"))
        assert "Synthetic" in raw["_note"]


def test_skill_roles_match_job_titles(catalog):
    titles = {job.title for job in catalog.jobs.values()}
    for skill in catalog.skills.values():
        assert set(skill.roles) <= titles
        needed_by = {j.title for j in catalog.jobs.values() if skill.id in j.required_skills}
        assert set(skill.roles) == needed_by


def _copy_data(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(load_settings().data_dir, target)
    return target


def test_dangling_skill_id_is_rejected(tmp_path):
    target = _copy_data(tmp_path)
    path = target / "employees.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["items"][0]["skills"].append("S99")
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DataError, match="S99"):
        load_catalog(target)


def test_dangling_course_id_is_rejected(tmp_path):
    target = _copy_data(tmp_path)
    path = target / "employees.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["items"][1]["completed_courses"] = ["C99"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DataError, match="C99"):
        load_catalog(target)


def test_duplicate_id_is_rejected(tmp_path):
    target = _copy_data(tmp_path)
    path = target / "jobs.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["items"].append(raw["items"][0])
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DataError, match="duplicate"):
        load_catalog(target)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(DataError, match="cannot read"):
        load_catalog(tmp_path)
