"""HTTP front door: JSON routes under /api, and the built React UI at /.

The browser never sends an employee id to a tool; it only names who is signed in (a demo picker).
The graph still takes the id from the request here and keeps one thread per employee (F19).
"""
import json
import queue
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool

from app.config import Settings, load_settings
from app.data import load_catalog
from app.graph import Assistant, TurnResult, UnknownEmployee
from app.llm import get_llm
from app.metrics import log_request, metrics_of
from app.profile import profile_card

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
MAX_MESSAGE_CHARS = 1000


class ChatRequest(BaseModel):
    employee_id: str
    conversation_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ConfirmRequest(BaseModel):
    employee_id: str
    conversation_id: str = Field(min_length=1, max_length=64)
    # Strict: plain bool would turn "on" or 1 into True, a yes the gate never saw (Codex 3 finding 1).
    confirm: StrictBool
    course_id: str


def _payload(result: TurnResult, metrics: dict) -> dict:
    return {"reply": result.reply, "recommendation": result.recommendation,
            "pending_enrollment": result.pending_enrollment, "events": result.events,
            "flagged": result.flagged, "metrics": metrics}


def create_app(settings: Settings, assistant: Assistant) -> FastAPI:
    app = FastAPI(title="Career skills assistant")

    @app.middleware("http")
    async def page_not_cached(request, call_next):
        """The page names the current hashed bundle, so a cached copy after a rebuild runs old code."""
        response = await call_next(request)
        if not request.url.path.startswith(("/api/", "/assets/")):
            response.headers["Cache-Control"] = "no-cache"
        return response

    def run_turn(employee_id: str, turn: Callable[[], TurnResult]) -> dict:
        """Time a turn, log one line, shape the response. An unknown employee is a 404; any other failure is
        logged as outcome "error" and answered with a fixed text, so no internal detail reaches the browser."""
        started = time.perf_counter()
        try:
            result = turn()
        except UnknownEmployee as error:
            raise HTTPException(status_code=404, detail="unknown employee") from error
        except Exception as error:
            log_request(settings.request_log_path, employee_id,
                        {"seconds": round(time.perf_counter() - started, 1), "outcome": "error"})
            raise HTTPException(status_code=500, detail="internal error") from error
        metrics = metrics_of(result, time.perf_counter() - started)
        log_request(settings.request_log_path, employee_id, metrics)
        return _payload(result, metrics)

    @app.get("/api/health")
    def health() -> dict:
        return {"provider": settings.llm_provider, "model": settings.ollama_model}

    @app.get("/api/employees")
    def employees() -> list[dict]:
        return [{"id": e.id, "name": e.name} for e in assistant.catalog.employees.values()]

    @app.get("/api/profile/{employee_id}")
    def profile(employee_id: str) -> dict:
        """The sidebar card for the signed-in employee (the picker, as for /api/chat). Not a turn, so not logged."""
        if employee_id not in assistant.catalog.employees:
            raise HTTPException(status_code=404, detail="unknown employee")
        return profile_card(employee_id, assistant.catalog, assistant.store.list_for(employee_id))

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> dict:
        return run_turn(request.employee_id, lambda: assistant.ask(
            request.employee_id, request.conversation_id, request.message))

    @app.post("/api/confirm")
    def confirm(request: ConfirmRequest) -> dict:
        return run_turn(request.employee_id, lambda: assistant.confirm(
            request.employee_id, request.conversation_id, request.confirm, request.course_id))

    @app.post("/api/chat/stream")
    def chat_stream(request: ChatRequest) -> StreamingResponse:
        """Newline-delimited JSON: {"type":"status","tool":...} lines while it works, then one {"type":"result",...}."""
        lines: queue.Queue = queue.Queue()

        def work() -> None:
            try:
                data = run_turn(request.employee_id, lambda: assistant.ask(
                    request.employee_id, request.conversation_id, request.message,
                    on_call=lambda name: lines.put({"type": "status", "tool": name})))
                lines.put({"type": "result", **data})
            except HTTPException as error:
                lines.put({"type": "error", "status": error.status_code, "detail": error.detail})
            except Exception:  # the stream must always end, or the browser waits forever
                lines.put({"type": "error", "status": 500, "detail": "internal error"})
            lines.put(None)

        def stream() -> Iterator[str]:
            threading.Thread(target=work, daemon=True).start()
            while (line := lines.get()) is not None:
                yield json.dumps(line) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    if WEB_DIST.is_dir():  # mounted last so it never shadows /api
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


def _default_app() -> FastAPI:
    settings = load_settings()
    catalog = load_catalog(settings.data_dir)
    return create_app(settings, Assistant(settings, catalog, get_llm(settings)))


app = _default_app()
