# AGENTS.md

Verified notes. Trust the code over this file when they disagree, and update it
when you change the architecture. The **why** behind each choice lives in
`MEMORY.md`; this file is only the **what** and **how**.

## Two apps, one engine

- **Planner** (`main.py`, `graph/`, `agents/`) — description -> plan. Implemented.
- **Reviewer** (`review.py`, `review/`) — release gate over a repo, its container
  and a running app. **Planned, not implemented.**

The adversarial debate is a reusable subgraph (`core/engine.py`). The reviewer is
a second consumer of it, never a node inside the planner graph.

```text
intake -> prepare_debates -> debate_tech_stack -> architecture -> scope -> plan
       -> debate_flow -> export
debate_tech_stack: [skip] debater_a -> debater_b -> judge -> debater_a | END
```

Boundary (enforce with an AST import test): `core/`, `sinks/` and
`tools/export.py` never import `agents/`, `graph/` or `review/`; `review/`
imports `core/` and `sinks/` only.

## Layout

| Path | Responsibility |
| :--- | :--- |
| `main.py` | CLI, streaming with `subgraphs=True`, HITL resume |
| `graph/` | `pipeline.py` (assembly, one node per `DebateConfig`), `state.py`, `document.py` |
| `agents/` | `intake.py`, `stack_debate.py`, `generators.py`, `generator_prompts.py` |
| `core/engine.py` | `build_debate(cfg)` — the reusable subgraph |
| `core/models.py` | `DebateConfig`, `BaseVerdict`, `DebateResult`, `RoleSpec` |
| `core/llm.py` | `ModelSpec` (`provider:model`), provider registry, resolver |
| `core/` (rest) | `prompts`, `structured` (verdict parsing), `usage` (cost), `render`, `prompt_loader` |
| `prompts/` | All prompt text; no prose in Python |
| `sinks/` | `base` contract, `markdown`, `obsidian`, `notion`, lazy `registry` |
| `tools/export.py` | Export node + automatic Markdown fallback |
| `observability.py` | Optional Langfuse |
| `review/` *(planned)* | `cli`, `profile`, `models`, `lenses`, `gate`, `report`, `cache`, `brief/`, `probe/`, `lab/`, `frontend/` |
| `core/cli/` | `provider.py` (the single CLI adapter), `config.py` (`models.toml` -> registry), `process.py` (timeout + tree kill), `check.py` (seat probe) |

## Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --describe "Build a chat app in 3 weeks with 2 devs"
```

Flags: `--describe`, `--sink {auto,markdown,notion,obsidian}`, `--output-dir`,
`--thread-id`, `--no-trace`. `auto` = Notion when `NOTION_TOKEN` (or
`NOTION_CONNECTION_TOKEN`) and `NOTION_PARENT_PAGE_ID` are set, else Markdown; an
`auto` failure falls back to Markdown, an explicit `--sink notion` raises.
Nothing needs `.env` at import time; a missing key fails only when used.

## Models

Seats are `provider:model`; model names may contain colons.

| Variable | Default |
| :--- | :--- |
| `PLANNER_MODEL_INTAKE` | `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_DEBATER` | `groq:llama-3.1-8b-instant` |
| `PLANNER_MODEL_DEBATER_A` / `_B` | `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_JUDGE` | `groq:llama-3.3-70b-versatile` |
| `PLANNER_MODEL_GENERATOR` | `google_genai:gemini-2.5-flash` |

Registered: `groq`, `google_genai`, `openai`. Add one with
`@register_provider("name")` in `core/llm.py`.

A seat needs `invoke(prompt) -> message(content, usage_metadata)`. Optional:
`with_structured_output`; without it `core/structured.py` parses text as JSON.
Nothing else — no function calling, no assumed context, no model name in prompts.

**BYO providers (implemented):** one `cli` adapter runs *any* command-line
agent; new agents are config, not code. `models.toml` (or `$MODELS_TOML`, or
`--models`) declares providers; seats stay `provider:model`. `{model}` in `args`
receives the model name, and the model `default` passes none. `prompt = "stdin"`
(default) or `"arg"`; an empty `env` value removes a variable, which forces a
subscription login even when an API key is exported. `openai_compatible` covers
OpenRouter/Ollama/vLLM with no config at all (`OPENAI_BASE_URL` +
`OPENAI_API_KEY`).

The adapter reads plain stdout: no vendor JSON envelopes, so there is nothing to
parse per vendor. `python -m core.cli.check` probes every seat and prints the
configured `login` hint on failure. Subscription logins still do not survive
headless CI except a long-lived token (`CLAUDE_CODE_OAUTH_TOKEN`).

## Debate semantics

- `min_rounds` are guaranteed without calling the judge; from then on the judge
  decides and `needs_another_round` loops.
- At `max_rounds` the engine forces `needs_another_round=False` and
  `status="max_rounds"`.
- Statuses: `decided`, `max_rounds`, `fallback` (unparseable judge), `skipped`
  (`skip_when` true, no calls, cost 0).
- Verdicts are Pydantic, scores clamped 0-10, prose and fences tolerated.
- Results land in `state["debates"][cfg.name]`; never add per-debate fields.

## Reviewer (planned)

Release gate: `GO` / `CONDITIONAL` / `NO-GO` + `review.json`, `review.md`, exit
`0/1/2/3`. One `DebateConfig` per lens, red -> blue -> judge, `min_rounds=1`,
`max_rounds=2`; red investigates with tools, blue verifies, **the judge gets no
tools**. Lenses: `security`, `reliability`, `correctness`, `cost_perf`, `general`,
plus `frontend` only with `--url`.

| Profile | Lab | Probing | Frontend | Max claim |
| :--- | :--- | :--- | :--- | :--- |
| `local` | no | refused | no | `GO (code-only)` |
| `ci` | yes | yes | yes | `GO` |

- Lab and active probing run **only** on an ephemeral Actions runner; the gate
  carries `scope`, and a release check requires `full`.
- Code first: authorization cells come from handlers/middleware, and only those
  expected to `deny` are probed. No seeded tenants, no IDOR claim.
- The model proposes a validated `ProbePlan`; a deterministic runner executes it
  with caps (1 rps, burst 20, 300 requests, abort on 429 or >5% 5xx).
- No production target: loopback/private only, else the run refuses.
- Capacity is not measurable in the lab (`needs staging`, never a `NO-GO`).
- The gate is deterministic; no model decides it.

## Prompts

All prompt text is Markdown under `prompts/` (`debate/`, `tech_stack/`,
`generators/`, `intake/`, planned `review/`). `load_prompt(name)` for static text,
`render_prompt(name, **values)` for `str.format` templates (double literal
braces). Never inline prompt prose in Python.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

`conftest.py` strips provider credentials and disables Langfuse, so the suite
needs no `.env` or network. Fakes come from `tests/helpers.py`
(`GenericFakeChatModel`; running out of scripted responses raises by design).
`test_engine.py` is the engine contract, `test_graph_smoke.py` proves a new
`DebateConfig` needs no engine change, `test_sinks.py` the sink contract. `live`
tests are deselected; `pyproject.toml` owns pytest/ruff config; CI runs 3.11.
The reviewer has **no tests yet** — treat it as unverified.

## Rules

- `graph/pipeline.py` must not build a module-level graph; importing it stays
  credential-free.
- `debate_flow_generator` is deterministic and runs after the generators.
- `sinks/notion.py` imports `mcp` lazily and shells out to
  `npx -y @notionhq/notion-mcp-server`; markdown conversion lives in
  `markdown_to_blocks`.
- Langfuse scores reference the trace id from `create_trace_id()`; no keys means
  a disabled session, not a failure.
- `MemorySaver` is the CLI checkpointer; `--thread-id` groups a run and names the
  export folder; resumes use `Command(resume=answer)`.
- Adding a lens = a `DebateConfig` in `review/lenses.py` + a prompt file. No
  engine change.
- One adapter for all command-line agents. A new agent is a `models.toml` block,
  never a Python class or a vendor branch in `core/cli/provider.py`.
- `load_models_config()` runs in entrypoints only, never at import time.
