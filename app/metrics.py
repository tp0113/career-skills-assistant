"""One JSON line per request in logs/requests.jsonl: what happened and what it cost, never the message text."""
import json
import time
import uuid
from pathlib import Path

from app.graph import TurnResult


def metrics_of(result: TurnResult, seconds: float) -> dict:
    """The numbers the UI shows under a reply. Same figures as the log line."""
    usage = result.usage
    return {
        "seconds": round(seconds, 1),
        "model_calls": usage.get("model_calls", 0),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "repair_attempts": result.repair_attempts,
        "tools": result.called_tools,
        "route": result.route,
        "route_source": result.route_source,
        "route_score": result.route_score,
        "outcome": result.outcome,
    }


def log_request(path: Path, employee_id: str, metrics: dict) -> None:
    """Append one line. The message and reply text are left out on purpose: they can hold personal data."""
    record = {"request_id": uuid.uuid4().hex[:12], "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "employee_id": employee_id, **metrics}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
