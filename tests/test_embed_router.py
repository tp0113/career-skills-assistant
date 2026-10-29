import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from app.config import load_settings
from app.data import load_catalog
from app.embed_router import MIN_SCORE, PREFIX, EmbedRouter, pick_route
from app.enrollments import EnrollmentStore
from app.graph import Assistant
from app.llm import LLMError, OllamaLLM
from app.route_examples import EXAMPLES
from app.router import route_message
from evals.stub_llm import StubLLM

SETTINGS = load_settings()
CATALOG = load_catalog(SETTINGS.data_dir)

# One axis per route: profile, gaps, advise, out_of_scope. Unknown texts sit between profile and gaps.
SMALL = {"profile": ["show my profile"], "gaps": ["what am I missing"], "advise": ["recommend a course"],
         "out_of_scope": ["tell me a joke"]}
VECTORS = {
    "show my profile": [1, 0, 0, 0], "what am I missing": [0, 1, 0, 0],
    "recommend a course": [0, 0, 1, 0], "tell me a joke": [0, 0, 0, 1],
    "list what I hold": [0.95, 0.1, 0, 0],
    "something odd": [0.7, 0.7, 0, 0],
    "I am hungry": [0.5, 0.4, 0.4, 0.4],  # ahead of the rest by margin, but only a weak match
    "chat about lunch": [0, 0, 0.2, 0.95],
    "tell me about rain": [0.1, 0, 0, 0.9],
}


@pytest.mark.parametrize("bad", [
    [None], [["x", 1.0, 0.0, 0.0]], [[1.0, 0.0]], [[]], [[float("nan"), 0, 0, 0]], [[1.0, 0, 0, 0], [0, 1.0, 0, 0]],
])
def test_a_malformed_query_vector_falls_back_to_the_rules(bad):
    """Codex 3 finding 5: null, text, short or extra vectors crashed the request or were silently truncated."""
    healthy = FakeEmbedder()
    router = EmbedRouter(lambda texts: healthy(texts) if len(texts) > 1 else bad, examples=SMALL)
    assert pick_route("list what I hold", None, (), router) == (route_message("list what I hold"), "rules", 0.0)


def test_malformed_example_vectors_are_not_cached():
    """Codex 3 finding 5: a bad first batch stayed in the cache, so every later request failed too."""
    healthy, calls = FakeEmbedder(), []

    def embed(texts):
        calls.append(len(texts))
        return [[None]] * len(texts) if len(calls) == 1 else healthy(texts)

    router = EmbedRouter(embed, examples=SMALL)
    assert pick_route("list what I hold", None, (), router)[1] == "rules"
    assert pick_route("list what I hold", None, (), router) == ("profile", "embedding", pytest.approx(0.994, abs=0.01))


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]] | None = None) -> None:
        self.vectors = vectors or VECTORS
        self.calls: list[list[str]] = []
        self.fail = False

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail:
            raise LLMError("down")
        return [self.vectors.get(t.removeprefix(PREFIX), [0.0, 0.0, 0.0, 0.0]) for t in texts]


def make_router(embedder: FakeEmbedder, **kwargs) -> EmbedRouter:
    return EmbedRouter(embedder, SMALL, **kwargs)


def test_the_closest_route_wins_when_it_is_clearly_ahead():
    decision = make_router(FakeEmbedder()).classify("list what I hold")
    assert decision.route == "profile" and decision.score > MIN_SCORE


def test_a_tie_between_two_routes_gives_no_answer():
    assert make_router(FakeEmbedder()).classify("something odd") is None


def test_a_weak_best_match_gives_no_answer():
    assert make_router(FakeEmbedder()).classify("I am hungry") is None


def test_examples_are_embedded_once_with_the_prefix():
    embedder = FakeEmbedder()
    router = make_router(embedder)
    router.classify("list what I hold")
    router.classify("tell me about rain")
    assert len(embedder.calls) == 3  # examples once, then one call per message
    assert all(text.startswith(PREFIX) for call in embedder.calls for text in call)


def test_a_failed_start_is_not_remembered():
    embedder = FakeEmbedder()
    router = make_router(embedder)
    embedder.fail = True
    with pytest.raises(LLMError):
        router.classify("list what I hold")
    embedder.fail = False
    assert router.classify("list what I hold").route == "profile"


# ---- how it combines with the keyword rules ----------------------------------------------------

def test_an_enroll_message_never_reaches_the_embedder():
    embedder = FakeEmbedder()
    assert pick_route("Enroll me in the first course", None, (), make_router(embedder)) == ("enroll", "rules", 0.0)
    assert embedder.calls == []


def test_a_clear_rule_match_is_final():
    embedder = FakeEmbedder()
    assert pick_route("list my skills", None, (), make_router(embedder))[0:2] == ("profile", "rules")
    assert embedder.calls == []


def test_embeddings_can_rescue_a_message_the_rules_do_not_know():
    # The rules say out_of_scope for this (no career word); the embedder knows it is a profile question.
    route, source, score = pick_route("list what I hold", None, (), make_router(FakeEmbedder()))
    assert (route, source) == ("profile", "embedding") and score > 0.9


def test_embeddings_can_pull_a_keyword_false_alarm_back_to_out_of_scope():
    embedder = FakeEmbedder({**VECTORS, "tell me about the course rain": [0.1, 0, 0, 0.9]})
    assert pick_route("tell me about the course rain", None, (), make_router(embedder))[0:2] == ("out_of_scope", "embedding")


def test_an_unsure_embedder_keeps_the_rules_answer():
    assert pick_route("something odd", None, (), make_router(FakeEmbedder()))[0:2] == ("out_of_scope", "rules")


def test_an_embedding_failure_keeps_the_rules_answer():
    embedder = FakeEmbedder()
    embedder.fail = True
    assert pick_route("What skills should I develop?", None, (), make_router(embedder))[0:2] == ("advise", "rules")


def test_no_router_means_rules_only():
    assert pick_route("list what I hold", None, (), None) == ("out_of_scope", "rules", 0.0)


def test_the_example_lists_only_name_routes_safe_to_pick_by_similarity():
    assert set(EXAMPLES) == {"profile", "gaps", "advise", "out_of_scope"}
    assert all(len(texts) >= 8 for texts in EXAMPLES.values())


def test_no_labelled_eval_message_is_also_an_example():
    cases = json.loads((Path(__file__).resolve().parent.parent / "evals" / "route_cases.json").read_text())["cases"]
    labelled = {c["message"].lower().strip(" ?.") for c in cases}
    examples = {t.lower().strip(" ?.") for texts in EXAMPLES.values() for t in texts}
    assert labelled.isdisjoint(examples)


# ---- Ollama embedding request ----------------------------------------------------------------

def make_llm(handler) -> tuple[OllamaLLM, list[dict]]:
    sent: list[dict] = []

    def wrapper(request: httpx.Request) -> httpx.Response:
        sent.append({"url": str(request.url), "body": json.loads(request.content)})
        return handler(request)

    return OllamaLLM(SETTINGS, httpx.Client(transport=httpx.MockTransport(wrapper))), sent


def test_embed_request_sends_the_model_and_num_ctx():
    llm, sent = make_llm(lambda r: httpx.Response(200, json={"embeddings": [[1.0], [2.0]]}))
    assert llm.embed(["a", "b"]) == [[1.0], [2.0]]
    assert sent[0]["url"].endswith("/api/embed")
    assert sent[0]["body"]["model"] == SETTINGS.embed_model and sent[0]["body"]["options"]["num_ctx"] == SETTINGS.ollama_num_ctx


@pytest.mark.parametrize("response", [
    httpx.Response(500, text="boom"), httpx.Response(200, text="not json"),
    httpx.Response(200, json={"oops": 1}), httpx.Response(200, json={"embeddings": [[1.0]]}),
])
def test_bad_embedding_responses_become_llm_errors(response):
    llm, _ = make_llm(lambda r: response)
    with pytest.raises(LLMError):
        llm.embed(["a", "b"])


# ---- in the whole graph ----------------------------------------------------------------------

def assistant_with(embedder: FakeEmbedder, tmp_path) -> Assistant:
    settings = replace(SETTINGS, embed_router=True)
    return Assistant(settings, CATALOG, StubLLM(embedder=embedder), EnrollmentStore(tmp_path / "e.json"))


def test_graph_uses_the_embedding_router_and_reports_where_the_route_came_from(tmp_path):
    from app import embed_router

    embedder = FakeEmbedder()
    assistant = assistant_with(embedder, tmp_path)
    # The graph builds its router from the real example list, so give the fake those vectors too.
    for route, axis in zip(("profile", "gaps", "advise", "out_of_scope"), range(4)):
        for text in EXAMPLES[route]:
            embedder.vectors[text] = [1.0 if i == axis else 0.0 for i in range(4)]
    embedder.vectors["list what I hold"] = [0.95, 0.1, 0, 0]
    result = assistant.ask("E01", "c1", "list what I hold")
    assert result.route == "profile" and result.route_source == "embedding" and result.route_score > 0.9
    assert result.usage["model_calls"] == 0 and embed_router.MIN_SCORE < result.route_score


def test_a_refused_message_never_reaches_the_embedder(tmp_path):
    embedder = FakeEmbedder()
    result = assistant_with(embedder, tmp_path).ask("E01", "c1", "What are Marcus's skills?")
    assert result.route == "refuse" and embedder.calls == []


def test_the_graph_still_works_when_embedding_is_down(tmp_path):
    embedder = FakeEmbedder()
    embedder.fail = True
    result = assistant_with(embedder, tmp_path).ask("E01", "c1", "list my skills")
    assert result.route == "profile" and result.route_source == "rules"
