# AGENTS.md

Verified notes. Trust the code over this file when they disagree; the **why** is in
`MEMORY.md`, here only the **what** and **how**.

## Two apps, one engine

- **Planner** (`main.py`, `graph/`, `agents/`): description -> plan. Implemented.
- **Reviewer** (`review.py`, `review/`): release gate, code-only; lab, probing and
  `frontend` are planned.

The debate is a reusable subgraph (`core/engine.py`); the reviewer is a second
consumer, never a node in the planner graph. Boundary (AST test): `core/`, `sinks/`
and `tools/export.py` never import `agents/`, `graph/`, `review/`.

## Layout

| Path | Responsibility |
| :--- | :--- |
| `main.py` / `review.py` | CLIs: planner (streaming, HITL) and reviewer |
| `graph/`, `agents/` | `pipeline.py` (a node per `DebateConfig`), `state`, `intake`, `generators` |
| `core/` | `engine.py` (`build_debate`), `models`, `llm`, `prompts`, `structured`, `cli/` |
| `prompts/`, `sinks/` | Prompt text; `base`, `markdown`, `obsidian`, `notion`, `registry` |
| `tools/`, `review/` | Export fallback; `models`, `lenses`, `gate`, `runner`, `report`, `cli` |

## Run

```powershell
.\.venv\Scripts\python.exe main.py --describe "Build a chat app in 3 weeks with 2 devs"
.\.venv\Scripts\python.exe review.py --repo . --lens all
```

Planner: `--describe`, `--sink {auto,markdown,notion,obsidian}`, `--output-dir`,
`--thread-id`, `--no-trace`; `auto` = Notion with `NOTION_TOKEN` + `NOTION_PARENT_PAGE_ID`.
Reviewer: `--repo`, `--lens` (repeatable, `all`), `--out` (`review-output/`), `--fail-on`,
`--strict`, `--profile`, `--models`, `--check-models`. No `.env` at import.

## Models

Seats are `provider:model`; names may contain colons.

| Variable | Default |
| :--- | :--- |
| `PLANNER_MODEL_DEBATER` / `_A` / `_B` | `groq:llama-3.1-8b-instant` |
| `PLANNER_MODEL_INTAKE` | `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_JUDGE` | `groq:llama-3.3-70b-versatile` |
| `PLANNER_MODEL_GENERATOR` | `google_genai:gemini-2.5-flash` |
| `REVIEW_MODEL_RED` / `_BLUE` / `_JUDGE` | required by `review.py` |

Registered: `groq`, `google_genai`, `openai` (`@register_provider` in `core/llm.py`);
a seat needs `invoke(prompt)`, else `core/structured.py` parses JSON from the text.

**BYO providers:** one `cli` adapter runs any command-line agent; a new one is config,
not code. `models.toml` (or `$MODELS_TOML`, or `--models`) declares it: `{model}` gets
the name, `default` none, `prompt` `stdin` or `arg`, empty `env` forces a login.
`openai_compatible` covers OpenRouter/Ollama/vLLM; `core.cli.check` probes the seats.

## Debate semantics

- `min_rounds` are guaranteed without the judge; after that it decides and
  `needs_another_round` loops. At `max_rounds` it is forced False (`max_rounds`).
- Statuses: `decided`, `max_rounds`, `fallback` (unparseable judge), `skipped` (cost 0);
  verdicts are Pydantic, scores 0-10; results in `state["debates"][cfg.name]`, no per-debate fields.

## Reviewer

`GO` / `CONDITIONAL` / `NO-GO` + `review.json`, `review.md`, exit `0/1/2/3` (`3` =
usage/config). One `DebateConfig` per lens, red -> blue -> judge, `min_rounds=1`,
`max_rounds=2`; red investigates, blue verifies, **the judge gets no tools**. Lenses:
`general`, `security`, `reliability`, `correctness`, `cost_perf`, `frontend` (`--url`).

- `local` = no lab, no probing, no frontend, max claim `GO (code-only)`; `ci` = all
  three, `GO`; a release check needs `scope=full`, loopback/private target only.
- Code first: cells come from handlers/middleware, only expected-`deny` ones probed.
  `ProbePlan` caps: 1 rps, burst 20, 300 requests, abort on 429 or >5% 5xx.
- Gate: open `critical` blocks; `--fail-on` sets the lowest blocking severity; below
  it only `high`/`medium` downgrade. `winner`, scores and `blocker` are ignored.
- `code-only` is a gap, not a downgrade: a clean review can be GO; `--strict` makes
  an unverified or unprobed lens NO-GO. Capacity is never a `NO-GO`.
- Each lens gets the earlier findings (`ALREADY REPORTED`); the judge dedups in its
  own call and skips another round with an open `critical`/`high`.

## Prompts

All prompt text is Markdown under `prompts/`; `load_prompt` (static) and
`render_prompt` (`str.format`, double braces), never prose in Python.

## Tests

`pytest -q` and `ruff check .` in the venv; `conftest.py` strips credentials and disables
Langfuse, so no `.env` or network. `test_engine`/`test_graph_smoke`/`test_sinks` are the
contracts; `test_review_*` cover the gate matrix, boundary, e2e and reports. CI runs 3.11.

## Rules

- `graph/pipeline.py` builds no module-level graph; `load_models_config()` is entrypoint-only.
- `debate_flow_generator` is deterministic, after the generators.
- `notion.py` imports `mcp` lazily and shells out to `npx`; Langfuse without keys is disabled.
- `MemorySaver` is the checkpointer; a lens is one `Lens` row, a CLI agent one `models.toml` block.
- One function, one job (SRP): the entry point orchestrates, helpers do one thing.
