# Adversarial Project Planner

A multi-agent planner built with **LangGraph**. It takes a vague project idea,
runs an adversarial debate to stress-test the technical decision, and writes a
structured project plan. The debate is a reusable subgraph and the export
destination is a pluggable sink, so neither the models nor the target page
(Notion, Markdown, Obsidian) are hardcoded into the pipeline.

## Pipeline

```text
intake_node -> prepare_debates -> debate_tech_stack -> architecture_generator
  -> scope_generator -> plan_generator -> debate_flow_generator -> export_node
```

1. **Intake** extracts goal, timeline, team size and constraints. When
   something essential is missing it pauses with a LangGraph `interrupt()` and
   asks for it.
2. **Adversarial debate** is compiled per config (`core/engine.py`). Agent A
   proposes, Agent B challenges, and a judge either picks a winner or orders
   another round. Two rounds are guaranteed, three at most.
3. **Generators** turn the winning decision and the transcript into Markdown
   documents: architecture, scope, plan and debate flow.
4. **Export** writes the same document tree to any registered sink.

The engine knows nothing about project planning: a `DebateConfig` goes in and a
`DebateResult` comes out in `state["debates"]`.

## Export destinations

| Sink | When it is used | Output |
| :--- | :--- | :--- |
| `auto` (default) | Notion if configured, otherwise Markdown | — |
| `markdown` | Zero configuration | `output/<run>/` with numbered `.md` files and `INDEX.md` |
| `obsidian` | Vault users | Markdown with frontmatter and `[[wikilinks]]` |
| `notion` | `NOTION_TOKEN` + `NOTION_PARENT_PAGE_ID` | Page tree with the same hierarchy |

`auto` falls back to Markdown if a Notion export fails at runtime, so generated
documents are never lost. An explicit `--sink notion` reports the error instead.

Adding a destination means implementing `export()` in `sinks/` and registering
it in `sinks/registry.py`; the pipeline does not change. Importing the package
never imports `mcp` or requires credentials.

## Models

Every seat is configurable with a `provider:model` value:

| Variable | Default |
| :--- | :--- |
| `PLANNER_MODEL_INTAKE` | falls back to `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_DEBATER` | `groq:llama-3.1-8b-instant` |
| `PLANNER_MODEL_DEBATER_A` / `PLANNER_MODEL_DEBATER_B` | `PLANNER_MODEL_DEBATER` |
| `PLANNER_MODEL_JUDGE` | `groq:llama-3.3-70b-versatile` |
| `PLANNER_MODEL_GENERATOR` | `google_genai:gemini-2.5-flash` |

Registered providers: `groq`, `google_genai` and `openai`. A new provider is one
factory function in `core/llm.py`; models are built lazily and cached, so no key
is needed until a model is actually invoked.

## Installation

```bash
git clone <repo>
cd Adversarial_Project_Planner
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Python 3.10+. Only the providers you use need keys:

- `GROQ_API_KEY` for the default debaters and judge.
- `GOOGLE_API_KEY` for the default generators.
- `NOTION_TOKEN` + `NOTION_PARENT_PAGE_ID` only for Notion export.
- `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` only for tracing.

Nothing is validated at import time: `python main.py --help` works with no
`.env` at all.

## Usage

```bash
python main.py --describe "Build a real-time chat app in 3 weeks with 2 devs"
python main.py --sink markdown --output-dir output
python main.py --sink obsidian --output-dir vault
python main.py --no-trace
```

If `--describe` is omitted the CLI prompts for a description. Missing intake
details are asked interactively.

## Observability

Langfuse is optional. With keys present, every run is traced, and after each
debate the judge scores are sent against the **same trace id** the callback
handler exported. `--no-trace` or a missing key disables it without affecting
the run.

## Tests

```bash
pytest -q          # offline: fake models, no credentials, no network
ruff check .
```

The suite covers the engine contract (rounds, max-rounds override, fallback
verdicts, skip), a second `DebateConfig` proving genericity, the sink contract
and its fallback, intake HITL, model configuration and a full graph smoke run
that writes real Markdown to a temporary directory.

## Output

```text
output/<run-id>/
├── INDEX.md
├── 01-architectural-overview.md
├── 02-scope-objectives.md
├── 03-1-full-plan.md
└── 04-debate-flow.md
```

Notion receives the same tree: root page, `1. Architectural Overview`,
`2. Scope & Objectives`, `3. Project Plan` → `3.1 Full Plan`, and
`4. Debate Flow`.
