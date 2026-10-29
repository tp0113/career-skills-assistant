import json

from app.enrollments import EnrollmentStore


def test_empty_when_no_file(tmp_path):
    assert EnrollmentStore(tmp_path / "e.json").list_for("E01") == []


def test_add_is_idempotent(tmp_path):
    store = EnrollmentStore(tmp_path / "e.json")
    assert store.add("E01", "C04") is True
    assert store.add("E01", "C04") is False
    assert store.list_for("E01") == ["C04"]


def test_employees_are_separate(tmp_path):
    store = EnrollmentStore(tmp_path / "e.json")
    store.add("E01", "C04")
    store.add("E02", "C06")
    assert store.list_for("E01") == ["C04"]
    assert store.list_for("E02") == ["C06"]


def test_creates_missing_folder_and_persists(tmp_path):
    path = tmp_path / "var" / "e.json"
    EnrollmentStore(path).add("E03", "C09")
    assert json.loads(path.read_text(encoding="utf-8")) == {"E03": ["C09"]}
    assert EnrollmentStore(path).list_for("E03") == ["C09"]
    assert not path.with_suffix(".tmp").exists()
