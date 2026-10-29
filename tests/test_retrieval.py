from app.config import load_settings
from app.data import load_catalog
from app.retrieval import score, search_courses, search_jobs, tokenize

CATALOG = load_catalog(load_settings().data_dir)


def test_tokenize_lowercases_drops_stopwords_and_repeats():
    assert tokenize("The Machine-Learning, machine!") == ["machine", "learning"]


def test_score_weights():
    # title 3 + skill 2 + description 1 for "python" -> 6
    assert score(["python"], "Python Foundations", ["Python"], "Learn python.") == (6, ["python"])
    assert score(["sql"], "Other", ["SQL"], "nothing") == (2, ["sql"])
    assert score(["zzz"], "Other", ["SQL"], "nothing") == (0, [])


def test_machine_learning_ranks_c03_or_c04_first():
    results = search_courses(CATALOG, "machine learning")
    assert results[0]["id"] in {"C03", "C04"}


def test_ties_are_ordered_by_id():
    results = search_courses(CATALOG, "machine learning")
    assert [r["id"] for r in results][:2] == ["C03", "C04"]
    assert results[0]["score"] == results[1]["score"]


def test_results_carry_score_and_matched_terms():
    first = search_courses(CATALOG, "machine learning")[0]
    assert first["score"] > 0
    assert first["matched_terms"] == ["machine", "learning"]


def test_limits():
    assert len(search_courses(CATALOG, "python machine learning data sql")) <= 5
    assert len(search_jobs(CATALOG, "python machine learning data sql")) <= 3


def test_completed_courses_are_excluded():
    ids = [r["id"] for r in search_courses(CATALOG, "sql", exclude_ids={"C01"})]
    assert "C01" not in ids and "C09" in ids
    assert "C01" in [r["id"] for r in search_courses(CATALOG, "sql")]


def test_empty_and_stopword_only_queries_return_nothing():
    assert search_courses(CATALOG, "") == []
    assert search_courses(CATALOG, "the of and") == []
    assert search_jobs(CATALOG, "   ") == []


def test_no_match_returns_nothing():
    assert search_courses(CATALOG, "gardening") == []


def test_deterministic_across_runs():
    runs = [search_courses(CATALOG, "python data") for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_data_query_returns_the_poisoned_posting_in_raw_top_3():
    ids = [r["id"] for r in search_jobs(CATALOG, "data")]
    assert "J05" in ids and "J03" in ids
