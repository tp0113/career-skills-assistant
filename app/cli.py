"""Command line front door: python -m app.cli --employee E01 "question".

Prints the tool events, the reply, the recommendation as JSON and the time and token counts.
`--stub` uses the fake model, so the whole path can be tried without Ollama.
"""
import argparse
import json
import sys
import time
import uuid

from app.config import load_settings
from app.data import load_catalog
from app.graph import Assistant, TurnResult
from app.llm import get_llm


def _print_result(result: TurnResult, seconds: float) -> None:
    for event in result.events:
        status = "ok" if event["ok"] else f"ERROR {event['error']}"
        print(f"[tool] {event['name']} {json.dumps(event['arguments'])} -> {status}")
    for item in result.flagged:
        print(f"[flagged] {item['id']} {item['title']}: {'; '.join(item['reasons'])}")
    if result.repair_attempts:
        print(f"[repairs] {result.repair_attempts}")
    print("\n" + result.reply)
    if result.recommendation:
        print("\n" + json.dumps(result.recommendation, indent=2))
    usage = result.usage
    print(f"\n[{result.route or '-'} / {result.outcome or '-'}] {seconds:.1f}s, "
          f"{usage.get('model_calls', 0)} model calls, {usage.get('prompt_tokens', 0)} prompt tokens, "
          f"{usage.get('output_tokens', 0)} output tokens, compose prompt {usage.get('compose_prompt_tokens', 0)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask the career skills assistant one question.")
    parser.add_argument("--employee", required=True, help="signed-in employee id, for example E01")
    parser.add_argument("--stub", action="store_true", help="use the fake model (no Ollama needed)")
    parser.add_argument("message")
    args = parser.parse_args(argv)

    settings = load_settings()
    catalog = load_catalog(settings.data_dir)
    if args.stub:
        from evals.stub_llm import StubLLM  # kept out of the app package on purpose

        llm = StubLLM()
    else:
        llm = get_llm(settings)
    assistant = Assistant(settings, catalog, llm)
    conversation = uuid.uuid4().hex[:8]

    started = time.perf_counter()
    result = assistant.ask(args.employee, conversation, args.message)
    _print_result(result, time.perf_counter() - started)
    if result.pending_enrollment and sys.stdin.isatty():
        answer = input("\n> ")
        started = time.perf_counter()
        _print_result(assistant.ask(args.employee, conversation, answer), time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
