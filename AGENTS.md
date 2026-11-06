# AGENTS.md

Verified notes for OpenCode sessions. Trust the code over this file when they
disagree, and update this file when you change the architecture.

## What this repo is

A LangGraph pipeline that turns a vague project description into a Markdown or
Notion project plan. The adversarial debate is a **reusable subgraph**; the
planning domain (tech stack, architecture, scope, plan) lives outside it.

```text
intake_node -> prepare_debates -> debate_tech_stack (subgraph) ->
architecture_generator -> scope_generator -> plan_generator ->
debate_flow_generator -> export_node -> END
```

`debate_tech_stack` is the compiled subgraph:

```text
[skip]  (only when the config defines skip_when)
debater_a -> debater_b -> judge -> debater_a (another round)
                               \-> END
```

The parent graph is linear. The loop lives inside the subgraph.

## Layout

| Path | Responsibility |
| :--- | :--- |
| `main.py` | CLI: streaming with `subgraphs=True`, HITL resume, result printing |
| `graph/pipeline.py` | Graph assembly; each `DebateConfig` becomes a node |
| `graph/state.py` | `PlannerState`: `debate_inputs`, `debates`, `docs`, `export_config` |
| `graph/document.py` | Maps `docs` to the sink-neutral `ProjectDocument` tree |
| `agents/intake.py` | Extraction + `interrupt()` clarifications |
| `agents/stack_debate.py` | The tech-stack `DebateConfig` (prompts, verdict, brief) |
| `agents/generators.py` | Node factories for architecture/scope/plan and the debate-flow renderer |
| `agents/generator_prompts.py` | Builders that fill the generator prompt templates |
| `core/prompt_loader.py` | Loads/adds values to prompt files under `prompts/` |
| `prompts/` | All prompt text: `debate/`, `tech_stack/`, `generators/`, `intake/` |
| `core/engine.py` | `build_debate(cfg)` — the reusable debate subgraph |
| `core/models.py` | `DebateConfig`, `BaseVerdict`, `DebateResult`, `RoleSpec` |
| `core/llm.py` | `ModelSpec` (`provider:model`), provider registry, resolver |
| `core/prompts.py`, `core/structured.py`, `core/usage.py`, `core/render.py` | Prompts, verdict parsing, token/cost, debate rendering |
| `sinks/` | `base` contract, `markdown`, `obsidian`, `notion`, lazy `registry` |
| `tools/export.py` | Export node + automatic Markdown fallback |
| `observability.py` | Optional Langfuse trace and scores |

`core/`, `sinks/` and `tools/export.py` must not import `agents/` or planning
concepts. Keep that boundary: it is what makes the engine reusable.

## Setup and run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --describe "Build a chat app in 3 weeks with 2 devs"
```

No `.env` is required at import time: Notion and Langfuse are configured lazily.
A missing provider key fails only when that model is actually invoked.

CLI flags: `--describe`, `--sink {auto,markdown,notion,obsidian}`,
`--output-dir`, `--thread-id`, `--no-trace`.

`auto` resolves to Notion when `NOTION_TOKEN`/`NOTION_CONNECTION_TOKEN` **and**
`NOTION_PARENT_PAGE_ID` are set, otherwise Markdown. If an `auto` Notion export
fails at runtime, the node logs and falls back to Markdown; an explicit
`--sink notion` propagates the error.

## Models

Seats are `provider:model` strings, overridable from the environment:

| Variable | Default |
| :--- | :--- |
| `PLANNER_MODEL_INTAKE` | `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_DEBATER` | `groq:llama-3.1-8b-instant` |
| `PLANNER_MODEL_DEBATER_A` / `_B` | `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_JUDGE` | `groq:llama-3.3-70b-versatile` |
| `PLANNER_MODEL_GENERATOR` | `google_genai:gemini-2.5-flash` |

Registered providers: `groq`, `google_genai`, `openai`. Add one with
`@register_provider("name")` in `core/llm.py`; nothing else changes. Model
names may contain colons (`openrouter:meta-llama/llama-3:free` parses correctly).

## Debate semantics

- `min_rounds` rounds are guaranteed **without calling the judge**: the judge
  node short-circuits and orders another round.
- From `min_rounds` on, the judge decides. `needs_another_round=True` loops.
- At `max_rounds` the engine overrides `needs_another_round` and sets
  `status="max_rounds"`.
- Statuses: `decided`, `max_rounds`, `fallback` (unparseable judge output),
  `skipped` (`skip_when` true, no model calls, `cost_usd=0`).
- Verdicts are validated with Pydantic; scores are clamped to 0–10 and prose
  or ```json fences around the object are tolerated.
- Each debate writes `state["debates"][cfg.name]`; the subgraph shares the key
  with the parent. Never re-introduce per-debate fields such as `debate1_*`.

## Adding things

**A new debate** (e.g. build-vs-buy):

1. Create `agents/<name>_debate.py` exporting a `DebateConfig` with a unique
   `name`, role prompts, judge rubric, `verdict_model` (subclass `BaseVerdict`)
   and a `brief` callable.
2. Optionally set `prepare_input` to publish domain data into
   `state["debate_inputs"][name]`, and `evidence` for deterministic facts.
3. Add it to `default_debates()` in `graph/pipeline.py` (or pass `configs=` in
   tests). No new state fields, nodes or edges are needed.

**A new sink** (e.g. Jira): implement `export(document, run_id) -> ExportResult`
in `sinks/<name>.py`, then add the dotted path to `_FACTORIES` in
`sinks/registry.py`. Do not import it from the pipeline.

**A new document**: produce it into `state["docs"][slug]` and add the title in
`graph/document.py`. Sinks render whatever hierarchy they receive.

## Prompts

All prompt text lives in `prompts/` as Markdown: `debate/` for engine
scaffolding, `tech_stack/` for this domain's roles and briefs, `generators/`
for document generation, `intake/` for extraction. Python loads and fills them
through `core/prompt_loader.py`:

- `load_prompt("tech_stack/agent_b.md")` for static text.
- `render_prompt("generators/plan.md", **values)` for templates.
- `str.format` placeholders; literal braces must be doubled (`{{`).
- Never inline prompt prose in a Python file. Add a new file under the matching
  `prompts/` folder instead.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q    
.\.venv\Scripts\python.exe -m ruff check .
```

- `tests/conftest.py` strips provider credentials and disables Langfuse, so the
  suite needs no `.env`, network or `npx`.
- Fake models come from `tests/helpers.py` (`GenericFakeChatModel` with a
  scripted response list). Running out of responses raises by design.
- `tests/test_engine.py` is the engine contract; `tests/test_graph_smoke.py`
  proves a second `DebateConfig` needs zero engine/graph changes;
  `tests/test_sinks.py` covers the destination contract.
- Tests marked `live` would call real providers and are deselected by
  `pyproject.toml`; none are currently marked.
- `pyproject.toml` owns pytest and ruff config. CI runs both on Python 3.11.

## Rules

- `debate_flow_generator` is deterministic and runs **after** the generators;
  it has no model call, so it cannot fail on missing credentials.
- `graph/pipeline.py` must not build a module-level `graph = build_graph()`;
  importing the module must stay credential-free.
- Importing `sinks/notion.py` is safe; importing `mcp` happens inside export.
  Notion export still shells out to `npx -y @notionhq/notion-mcp-server`.
- Notion markdown conversion lives in `sinks/notion.py::markdown_to_blocks`.
  Extend that parser instead of post-processing documents in agents.
- Langfuse scores must reference the trace id created by `create_trace_id()`
  and shared with `CallbackHandler(trace_context=...)`. Without keys the
  session is disabled and the pipeline runs normally.
- The `LangChainPendingDeprecationWarning` from
  `langgraph.checkpoint.serde.encrypted` is a known upstream warning.
- The CLI checkpointer is `MemorySaver`; `--thread-id` groups a run and names
  the export folder. Interrupts are resumed with `Command(resume=answer)`.

