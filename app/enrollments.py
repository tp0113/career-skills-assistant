"""Enrollments live in their own JSON file, never in the seed data.

Why a separate file: tests and evals use temp files, and the reset script can clear the demo
state with one delete. The file looks like {"E01": ["C04"]}.
"""
import json
import os
from pathlib import Path


class EnrollmentStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, list[str]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def list_for(self, employee_id: str) -> list[str]:
        return list(self._read().get(employee_id, []))

    def add(self, employee_id: str, course_id: str) -> bool:
        """Enroll once. Returns False (and writes nothing) if already enrolled."""
        data = self._read()
        courses = data.setdefault(employee_id, [])
        if course_id in courses:
            return False
        courses.append(course_id)
        self._write(data)
        return True

    def _write(self, data: dict[str, list[str]]) -> None:
        """Write to a temp file then swap it in, so a crash cannot leave half a file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
