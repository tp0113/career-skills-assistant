# Architecture

A signed-in employee asks "What skills should I develop for my next career opportunity?".
The assistant reads that employee's profile, searches a course catalog and internal job
postings, and returns 3 skills, 2-3 courses and 1-2 roles, each with a reason and the ids of
the data items it came from. If the employee says yes, it enrolls them in a course.

All data is synthetic. The default model is a local `llama3.1:8b` served by Ollama.

## The three rules, and where each is enforced

| Rule | Enforced by (code, not the prompt) |
|---|---|
| An employee only ever sees their own data | `app/guard.py` runs before any model call. No tool has an employee-id parameter; `app/tools.py` reads the id from the server-side session. |
| Enrollment only after an explicit yes | `app/graph.py`: the enroll proposal pauses on a LangGraph `interrupt()`. Only the `enroll` node writes, and only if the `enrollment_confirmed` flag (set from the confirmation, not by the model) is true for the same course. |
| Recommendations are real and checked | `app/validate.py`: counts, ids exist, ids were retrieved this turn, completed courses excluded, flagged postings excluded. Titles are filled from the data, not from the model. |

## Request flow (the graph)

```
START -> guard --refuse--> END                     (no model call; polite refusal)
           |
           v
         route --out_of_scope--> END               (canned graceful answer)
           |------followup-----> followup -> END   (resolves "the second course" from state)
           |------enroll-------> enroll_agent -> confirm (interrupt) -> enroll -> END
           |                                          '--declined--> END
           v
         advise_agent <-> run_tools                (loop: one tool call per step)
           |   '--too many failed steps--> tool_fallback -> END
           v
         compose (structured output) -> validate (repair up to 2x) -> respond -> END
```

- **guard** (deterministic): refuses if the message asks about another person: a different
  employee's name (full, first, lowercase, possessive), a possessive capitalized name that is
  not the signed-in employee's and not a known skill/course word ("Daniel's skills"), or
  relationship words ("my manager", "my teammate", "everyone on my team", "other employees").
  The signed-in employee's own name is allowed. Claiming to be someone else is refused.
- **route** (deterministic keyword rules): `enroll` (enroll / sign me up / register),
  `followup` (an ordinal or "tell me more" and a previous recommendation exists),
  `advise` (career, skill, learn, course, role, job, grow...), else `out_of_scope`.
- **advise_agent / run_tools**: the model chooses each tool call and its arguments. The
  graph decides which tools are *offered* at each step: first only `get_employee_profile`,
  then `search_courses` and `search_jobs` until both have been called. Measured reason: when
  all tools were offered at once, `llama3.1:8b` searched before reading the profile, with a
  generic query. If the model answers in prose instead of calling a tool, the graph adds a
  short reminder and asks again. Malformed arguments or unknown tools produce an error tool
  message. A search counts as done only when enough items have been retrieved this turn (2 courses,
  1 job, the minimums the answer needs); otherwise a short user message follows the result with
  the catalog's skill names the employee lacks (keyword search only finds the catalog's own words),
  and the model searches again with words it chooses. After 6 steps without the required calls, `tool_fallback` returns a graceful
  message and no recommendation.
- **compose**: one model call with Ollama's JSON-schema `format`, given the profile, the
  retrieved courses and jobs, and the candidate skills (skills required by retrieved jobs or
  taught by retrieved courses that the employee does not have).
- **validate**: Pydantic parse plus the rule checks above. On failure the errors are sent
  back to the model (at most 2 repair attempts), then a graceful failure message.
- **respond**: the friendly message is rendered in code from the validated object, so no
  free model prose reaches the user on this path.
- **enroll_agent**: the model is offered only `enroll_in_course(course_id)` and the last
  recommended courses, so it resolves "the second one" to an id. Code checks the id exists,
  is not completed and is not already enrolled. **confirm** calls `interrupt()`; the UI's
  Confirm/Decline buttons resume it with `{confirm, course_id}`, and a yes counts only if
  `course_id` is the pending course (a stale click cannot confirm a newer proposal). Free-text
  replies count as yes only if they exactly match a short list (`yes`, `y`, `yes please`,
  `confirm`, `yes enroll me`) after lowercasing and removing only `. , !`. Anything else
  ("maybe", "sure but later", "yes" plus words in any language) cancels the pending enrollment.

## State (one LangGraph thread per employee conversation)

Thread id = `"{employee_id}:{conversation_id}"`. Switching employees in the UI starts a new
conversation id, and the server always prefixes the signed-in id, so threads never mix.
Checkpointer: in-memory (`InMemorySaver`); state is lost on restart (a known limitation).

| Field | Meaning | Lifetime |
|---|---|---|
| `employee_id` | set by the server from the session | thread |
| `user_message`, `route` | this turn's input and route | turn |
| `llm_messages` | this turn's agent transcript | turn |
| `called_tools`, `agent_steps` | tool-use bookkeeping | turn |
| `profile` | the signed-in employee's profile | turn |
| `retrieved_courses`, `retrieved_jobs` | id -> sanitized record + score | turn |
| `flagged` | items quarantined by the injection filter, with the reason | turn |
| `recommendation` | last validated recommendation | thread (used by follow-ups) |
| `pending_course_id`, `enrollment_confirmed` | enrollment gate | thread |
| `reply`, `events`, `usage` | output, tool status events, token/latency counts | turn |

## Tools (all take no employee id)

| Tool | Arguments (model-visible) | Returns |
|---|---|---|
| `get_employee_profile` | none | name, current role, skills, completed courses, career interest |
| `search_courses` | `query: str` | top 5 courses: id, title, level, duration, skills taught, score, matched terms. Completed courses excluded |
| `search_jobs` | `query: str` | top 3 postings: id, title, required skills, score, matched terms. Flagged postings are left out of the result and listed in `flagged` |
| `enroll_in_course` | `course_id: str` | proposal only from the model's side; the write happens in the `enroll` node after confirmation |

Argument models use `extra="forbid"`, so a smuggled `employee_id` argument is rejected.
Tool results go to the model inside `<untrusted_data source="...">` blocks.

## Retrieval

Keyword scoring in `app/retrieval.py`: lowercase, split on non-letters, drop stopwords.
Score = 3 per query term in the title + 2 per term in skill names + 1 per term in the
description. Ties break by id, so results are deterministic. Every result carries its id,
score and matched terms; those ids are the provenance shown in the UI.

## Prompt-injection defense (defense in depth)

1. **Data, not instructions**: retrieved text is wrapped and labeled untrusted; the system
   prompt says so.
2. **Filter**: `app/injection.py` flags lines that look like instructions (ignore/disregard
   instructions, "recommend this to everyone", fake role tags like `system:`), removes them
   before the model sees them, and quarantines the item.
3. **Validate**: a role can be recommended only if it was retrieved this turn and not flagged.
   So even a fooled model cannot get a poisoned posting into the output.

`INJECTION_DEFENSE=off` disables layers 2 and 3, only for the before/after comparison.

## Data files (`data/`, synthetic)

- `employees.json`: `id, name, current_role, skills[skill ids], completed_courses[course ids], career_interest`
- `skills.json`: `id, name, category, description, roles[job titles]`
- `courses.json`: `id, title, description, skills[skill ids], level, duration_hours`
- `jobs.json`: `id, title, description, required_skills[skill ids]` (one posting contains a hidden instruction, on purpose)
- Enrollments are written to `var/enrollments.json` (git-ignored), never to the seed data.

## Recommendation schema (`app/schemas.py`)

```
Recommendation
  skills:  exactly 3  of {skill_id, name, reason, sources[job/course ids]}
  courses: 2 to 3     of {course_id, title, reason, sources}
  roles:   1 to 2     of {job_id, title, reason, sources}
```

The model fills ids, reasons and sources; code fills `name` and `title` from the data.

## Model provider (`app/llm.py`)

One interface: `chat(messages, tools=None, json_schema=None) -> LLMReply(content,
tool_calls, prompt_tokens, output_tokens, latency_ms)`. `LLM_PROVIDER=ollama` (default)
calls the native `/api/chat` endpoint and sends `num_ctx=8192` on every request. The
OpenAI-compatible `/v1` endpoint is not used: it has no per-request `num_ctx`, and a call
to it reloaded the model at the 32K default, which on an 8 GB GPU spills to the CPU.
Tests use a deterministic stub model (`evals/stub_llm.py`), never the real one.

## API (`app/api.py`) and UI (`web/`)

| Route | Body | Returns |
|---|---|---|
| `GET /api/health` | | provider, model |
| `GET /api/employees` | | `[{id, name}]` for the demo sign-in picker |
| `POST /api/chat` | `{employee_id, conversation_id, message}` | `{reply, recommendation, pending_enrollment, events, flagged, metrics}` |
| `POST /api/chat/stream` | same | newline-delimited JSON: tool status events, then the final result |
| `POST /api/confirm` | `{employee_id, conversation_id, confirm: bool, course_id}` | same as `/api/chat` |

The React app (no state library, no CSS framework): `App`, `EmployeePicker`, `ChatLog`,
`MessageInput`, `SuggestedPrompts`, `RecommendationCards`, `EnrollConfirm`, `MetricsLine`.
It is built into `web/dist` and served by FastAPI, so the demo is one command.

Each request appends one line to `logs/requests.jsonl`: request id, time, employee id,
route, latency, model calls, prompt and output tokens, tools called, repair attempts, outcome.
