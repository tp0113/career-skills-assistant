"""Semantic routing: pick the route whose example questions are closest in meaning to the message.

How it works, in one breath: every example in `route_examples.py` is turned into a vector once, a
message is turned into a vector, and each route scores as its best cosine similarity. The winner
counts only if it is clearly good (MIN_SCORE) and clearly ahead of the runner-up (MARGIN); otherwise
the caller keeps the keyword rules' answer. A wrong guess is therefore rare, and a failure to embed
(Ollama down) only means the rules decide, as before.

It never chooses `enroll` or `followup`, and it runs after the privacy guard, so it only decides
among the routes that read the signed-in employee's own data or give a canned answer.
"""
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.llm import LLMError
from app.route_examples import EXAMPLES
from app.router import ADVISE, OUT_OF_SCOPE, route_message
from app.schemas import Recommendation

# nomic-embed-text was trained with a task prefix; "classification:" is the one meant for this use.
PREFIX = "classification: "
# Chosen on the dev half of evals/route_cases.json, then checked on the test half (see the README).
MIN_SCORE = 0.75
MARGIN = 0.03

Embedder = Callable[[list[str]], list[list[float]]]


@dataclass(frozen=True)
class Decision:
    route: str
    score: float
    margin: float


def _checked(vectors, count: int, size: int | None = None) -> list[list[float]]:
    """`count` vectors of real numbers, all one length (`size` if given). Anything else is an LLMError, so the
    rules decide instead of a crash or a silently cut comparison (Codex 3 finding 5)."""
    if not isinstance(vectors, list) or len(vectors) != count:
        raise LLMError("embedding: wrong number of vectors")
    for vector in vectors:
        if not isinstance(vector, list) or not vector or not all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in vector):
            raise LLMError("embedding: a vector is not a list of finite numbers")
    size = size or len(vectors[0])
    if any(len(vector) != size for vector in vectors):
        raise LLMError("embedding: vectors of different lengths")
    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class EmbedRouter:
    def __init__(self, embed: Embedder, examples: dict[str, list[str]] = EXAMPLES,
                 min_score: float = MIN_SCORE, margin: float = MARGIN) -> None:
        self._embed = embed
        self._examples = examples
        self.min_score = min_score
        self.margin = margin
        self._vectors: list[tuple[str, list[float]]] | None = None
        self._lock = threading.Lock()

    def _example_vectors(self) -> list[tuple[str, list[float]]]:
        """Embedded on first use, not at start-up, so the app starts without Ollama. A failure is not remembered."""
        with self._lock:
            if self._vectors is None:
                pairs = [(route, text) for route, texts in self._examples.items() for text in texts]
                vectors = _checked(self._embed([PREFIX + text for _, text in pairs]), len(pairs))
                self._vectors = [(route, vector) for (route, _), vector in zip(pairs, vectors)]
            return self._vectors

    def scores(self, message: str) -> dict[str, float]:
        """Best similarity per route. Raises LLMError if the embedding call fails."""
        examples = self._example_vectors()
        vector = _checked(self._embed([PREFIX + message]), 1, len(examples[0][1]))[0]
        best: dict[str, float] = {}
        for route, example in examples:
            best[route] = max(best.get(route, -1.0), _cosine(vector, example))
        return best

    def classify(self, message: str) -> Decision | None:
        """The winning route, or None when it is not clearly better than the rest."""
        ranked = sorted(self.scores(message).items(), key=lambda item: -item[1])
        (route, score), runner_up = ranked[0], ranked[1][1] if len(ranked) > 1 else 0.0
        if score < self.min_score or score - runner_up < self.margin:
            return None
        return Decision(route, round(score, 3), round(score - runner_up, 3))


def pick_route(message: str, recommendation: Recommendation | None, own_names: tuple[str, ...],
               router: "EmbedRouter | None") -> tuple[str, str, float]:
    """(route, source, score). The keyword rules go first; the embeddings are asked only when the rules fell
    through to advise or out_of_scope, the two catch-all routes. enroll, followup, profile and gaps from the
    rules are final. Any embedding failure keeps the rules' answer."""
    rules = route_message(message, recommendation, own_names)
    if router is None or rules not in (ADVISE, OUT_OF_SCOPE):
        return rules, "rules", 0.0
    try:
        decision = router.classify(message)
    except LLMError:
        return rules, "rules", 0.0
    if decision is None:
        return rules, "rules", 0.0
    return decision.route, "embedding", decision.score
