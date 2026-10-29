# Conventions for coding agents and contributors

A small employee skills assistant: a LangGraph agent with four tools, keyword retrieval,
validated structured output, a privacy guard, an enrollment gate and an eval script.
Design: `docs/ARCHITECTURE.md`.

## Layout

```
app/        Python package: config, data, guard, retrieval, tools, llm, graph, api
data/       synthetic JSON (employees, skills, courses, jobs). Read-only at runtime
evals/      cases.json + run.py (pass/fail table) + the deterministic stub model
tests/      pytest unit tests
web/        React (Vite) chat UI, built into web/dist and served by FastAPI
scripts/    PowerShell helpers (run with: powershell -ExecutionPolicy Bypass -File <script>)
var/, logs/ runtime output (enrollments, request log). Git-ignored
```

## Commands

```
python -m venv .venv && .venv\Scripts\activate      (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m pytest -q                                  unit tests, stub model, no Ollama needed
python -m evals.run                                  eval cases on the stub model
python -m evals.run --real                           eval cases on the configured real model
uvicorn app.api:app --port 8000                      API + built UI
```

## Rules that must not be broken

1. No tool takes an employee id from the model. The server injects the signed-in id.
2. The privacy guard runs before any model call. A refused message never reaches the model.
3. `enroll_in_course` writes only from the enroll node, after an explicit confirmation.
4. Every recommendation is validated in code: counts, ids exist, ids were retrieved this turn,
   completed courses excluded, flagged postings excluded.
5. Retrieved text is untrusted data: delimited, labeled, instruction-like lines removed.
6. Every Ollama request sends `num_ctx` explicitly.
7. Tests and the default eval run use the stub model. Never fake tool calls on the real path.

## Code style

- Small files, named functions, type hints, docstrings that say why.
- Boring over clever. If a function needs a paragraph to explain, split it.
- Pin every dependency version. Never commit `.env` or keys.
- Commit messages: one short imperative subject (max 50 chars, no period), no trailers.
