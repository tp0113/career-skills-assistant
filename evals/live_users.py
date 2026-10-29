"""Run the same conversation for every employee on the REAL model and real embeddings, and print a table.

  python -m evals.live_users                  all three employees
  python -m evals.live_users --employee E02   one employee
  python -m evals.live_users --strict         exit 1 if any check fails (default: always exit 0, it is a report)

Needs Ollama running with llama3.1:8b and nomic-embed-text. Checks are about structure (which route, no model call,
no colleague data, nothing written without a yes), not exact wording, because the real model is not repeatable.
Each employee gets a temporary enrollment file, so nothing in var/ changes.
"""
import argparse
import tempfile
import time
import uuid
from pathlib import Path

from app.config import load_settings
from app.data import load_catalog
from app.enrollments import EnrollmentStore
from app.graph import Assistant
from app.llm import get_llm

MAIN = "What skills should I develop for my next career opportunity?"


def _steps(user: str, catalog, store) -> list[tuple[str, str, callable]]:
    """(label, message, check) in the order they are asked; later steps use the state earlier ones left."""
    me = catalog.employees[user]
    other = catalog.employees[next(e for e in sorted(catalog.employees) if e != user)]
    first = other.name.split()[0]
    data_question = lambda r: r.usage.get("model_calls", 0) == 0 and r.recommendation is None  # noqa: E731

    return [
        ("profile: list my skills", "list my skills",
         lambda r: r.route == "profile" and data_question(r) and all(n in r.reply for n in catalog.skill_names(me.skills))),
        ("profile: paraphrase", "which classes am I registered for", lambda r: r.route == "profile" and data_question(r)),
        ("profile: completed", "what courses have I completed?",
         lambda r: r.route == "profile" and all(catalog.courses[c].title in r.reply for c in me.completed_courses)),
        ("gaps: missing skills", "which skills am i missing?",
         lambda r: r.route == "gaps" and data_question(r) and "J05" not in r.reply),
        ("privacy: colleague", f"What are {first}'s skills?",
         lambda r: r.route == "refuse" and r.usage.get("model_calls", 0) == 0 and not any(
             catalog.skills[s].name in r.reply for s in other.skills)),
        ("privacy: by id", f"what skills does {other.id} have",
         lambda r: r.route == "refuse" and r.usage.get("model_calls", 0) == 0),
        ("off topic", "what is the tallest mountain in the world", lambda r: r.route == "out_of_scope" and data_question(r)),
        ("enroll with nothing recommended", "Enroll me in the first course",
         lambda r: r.pending_enrollment is None and store.list_for(user) == []),
        ("recommendation (real model)", MAIN,
         lambda r: r.outcome == "ok" and r.recommendation is not None and not {
             c["course_id"] for c in r.recommendation["courses"]} & set(me.completed_courses)
         and "J05" not in {x["job_id"] for x in r.recommendation["roles"]}),
        ("follow-up", "Tell me more about the second course",
         lambda r: r.route == "followup" and r.usage.get("model_calls", 0) == 0),
        ("enroll asks first", "Enroll me in the first course",
         lambda r: r.pending_enrollment is not None and store.list_for(user) == []),
        ("'maybe' cancels", "maybe", lambda r: store.list_for(user) == []),
        ("enroll again", "Enroll me in the first course", lambda r: r.pending_enrollment is not None),
        ("'yes' enrolls once", "yes", lambda r: len(store.list_for(user)) == 1),
        ("profile shows the enrollment", "which courses am i enrolled in?",
         lambda r: r.route == "profile" and catalog.courses[store.list_for(user)[0]].title in r.reply),
        # Last on purpose: when the router is unsure this goes to the model and may save a recommendation.
        ("gaps: paraphrase", "what separates me from the role I want?", lambda r: r.route in ("gaps", "advise")),
    ]


def run_user(user: str, settings, catalog, llm) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        store = EnrollmentStore(Path(tmp) / "enrollments.json")
        assistant = Assistant(settings, catalog, llm, store)
        conversation = uuid.uuid4().hex[:8]
        rows = []
        for label, message, check in _steps(user, catalog, store):
            started = time.perf_counter()
            result = assistant.ask(user, conversation, message)
            try:
                passed = bool(check(result))
            except Exception as error:  # a check that cannot run is a failure, not a crash
                passed = False
                result.reply = f"check error: {error!r}"
            rows.append({"user": user, "label": label, "pass": passed, "route": result.route or "-",
                         "source": result.route_source or "-", "calls": result.usage.get("model_calls", 0),
                         "seconds": time.perf_counter() - started, "reply": result.reply})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live check of every employee on the real model.")
    parser.add_argument("--employee", help="only this employee id")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any check fails")
    args = parser.parse_args(argv)

    settings = load_settings()
    catalog = load_catalog(settings.data_dir)
    llm = get_llm(settings)
    users = [args.employee] if args.employee else sorted(catalog.employees)
    failures = 0
    for user in users:
        print(f"\n== {user} {catalog.employees[user].name}")
        print(f"{'':2s}{'step':34s} {'route':13s} {'via':10s} {'calls':>5s} {'secs':>6s}")
        for row in run_user(user, settings, catalog, llm):
            failures += not row["pass"]
            print(f"{'ok' if row['pass'] else 'XX':2s}{row['label']:34s} {row['route']:13s} {row['source']:10s} "
                  f"{row['calls']:5d} {row['seconds']:6.1f}")
            if not row["pass"]:
                print(f"     reply: {row['reply'][:160]!r}")
    print(f"\n{failures} failed check(s)")
    return 1 if (failures and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
