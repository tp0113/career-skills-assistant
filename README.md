# Career Skills Assistant

A small AI assistant that helps an employee decide which skills to develop next. A signed-in
employee asks "What skills should I develop for my next career opportunity?" and gets
3 skills, 2-3 courses and 1-2 internal roles, each with a reason and the ids of the catalog
or posting items it came from. If the employee says yes, it enrolls them in a course.

It runs locally on a laptop GPU with `llama3.1:8b` through Ollama. All data is synthetic.

> Status: under construction. Run steps, design choices, test results and limitations are
> filled in as each part is built and tested.

## Design at a glance

- **LangGraph agent with real tool calls**: `get_employee_profile`, `search_courses`,
  `search_jobs`, `enroll_in_course`.
- **Privacy in code**: no tool takes an employee id; a guard refuses questions about other
  people before the model is called.
- **Enrollment gate in code**: a LangGraph interrupt plus a flag the enroll step checks.
- **Keyword retrieval with provenance**, **validated structured output**, and a
  **prompt-injection defense** tested against a deliberately poisoned job posting.

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start (development)

```
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

PowerShell helper scripts run with `powershell -ExecutionPolicy Bypass -File scripts/<name>.ps1`.
