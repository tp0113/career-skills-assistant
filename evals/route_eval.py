"""Measure the router on labelled messages: keyword rules alone vs rules plus embeddings.

  python -m evals.route_eval                  needs Ollama and `ollama pull nomic-embed-text`
  python -m evals.route_eval --scores         also print every route's similarity per message
  python -m evals.route_eval --min 0.55 --margin 0.02    try other thresholds

Thresholds are chosen on "dev" only. "test" was looked at while fixing the examples. "holdout" was written
afterwards and run once with the settings already fixed: it is the honest number.
Every wrong answer is listed, because a misroute count alone hides which kind of mistake it is.
"""
import argparse
import json
import time
from pathlib import Path

from app.config import load_settings
from app.embed_router import MARGIN, MIN_SCORE, EmbedRouter, pick_route
from app.llm import get_llm
from app.router import route_message

CASES = Path(__file__).resolve().parent / "route_cases.json"


def _accuracy(rows: list[dict], key: str) -> str:
    right = sum(row[key] == row["route"] for row in rows)
    return f"{right}/{len(rows)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Router accuracy: rules only vs rules + embeddings.")
    parser.add_argument("--min", type=float, default=MIN_SCORE, dest="min_score")
    parser.add_argument("--margin", type=float, default=MARGIN)
    parser.add_argument("--scores", action="store_true")
    args = parser.parse_args(argv)

    settings = load_settings()
    router = EmbedRouter(get_llm(settings).embed, min_score=args.min_score, margin=args.margin)
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    rows, millis = [], []
    for case in cases:
        started = time.perf_counter()
        route, source, score = pick_route(case["message"], None, (), router)
        millis.append((time.perf_counter() - started) * 1000)
        rows.append({**case, "rules": route_message(case["message"]), "both": route, "source": source, "score": score,
                     "scores": router.scores(case["message"]) if args.scores else None})

    print(f"thresholds: min {args.min_score}, margin {args.margin}")
    for split in ("dev", "test", "holdout"):
        part = [r for r in rows if r["split"] == split]
        print(f"{split:5s} rules only {_accuracy(part, 'rules')}   rules + embeddings {_accuracy(part, 'both')}")
    print(f"all   rules only {_accuracy(rows, 'rules')}   rules + embeddings {_accuracy(rows, 'both')}")
    print(f"time per message (first one includes embedding the examples): median {sorted(millis)[len(millis) // 2]:.0f} ms, "
          f"first {millis[0]:.0f} ms")
    for r in rows:
        if r["both"] != r["route"] or r["rules"] != r["route"] or args.scores:
            mark = "OK " if r["both"] == r["route"] else "BAD"
            extra = ""
            if r["scores"]:
                extra = "  " + " ".join(f"{k}={v:.2f}" for k, v in sorted(r["scores"].items(), key=lambda kv: -kv[1]))
            print(f"{mark} [{r['split']}] want {r['route']:12s} rules {r['rules']:12s} both {r['both']:12s} "
                  f"({r['source']} {r['score']}) {r['message']}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
