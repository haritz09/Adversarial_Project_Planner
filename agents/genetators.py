# agents/generators.py
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import DebateState
from dotenv import load_dotenv

load_dotenv()

def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash")

llm_generator = get_llm()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _project_block(ctx: dict) -> str:
    constraints = ", ".join(ctx.get("constraints", [])) or "none"
    return (
        f"Goal: {ctx.get('goal', 'n/a')} | "
        f"Timeline: {ctx.get('timeline', 'n/a')} | "
        f"Team: {ctx.get('team_size', 'n/a')} devs | "
        f"Constraints: {constraints}"
    )


def _debate_block(arguments: list[dict]) -> str:
    """Summarise debate history as a compact string."""
    if not arguments:
        return "No debate arguments available."
    lines = []
    for a in arguments:
        lines.append(f"[Round {a['round']} - Agent {a['agent']}]: {a['argument']}")
    return "\n".join(lines)


def _invoke(prompt: str) -> str:
    response = llm_generator.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


# ── Prompts ───────────────────────────────────────────────────────────────────

ARCHITECTURE_PROMPT = """You are a senior software architect. Write a concise architectural overview.

PROJECT: {project_block}

DEBATE SUMMARY:
{debate_block}

CHOSEN STACK: {decision}
JUDGE RATIONALE: {rationale}

Write in Markdown with these sections:
## Chosen Stack
List the technologies and why each was chosen.

## System Components
List the main components/services and their responsibilities (max 6).

## Key Architectural Decisions
List 3-5 decisions made and the reasoning behind each.

## Risks & Mitigations
List the top 3 technical risks and how to mitigate them.

Be specific and concise. No generic advice.
"""

SCOPE_PROMPT = """You are a senior product manager. Define the project scope concisely.

PROJECT: {project_block}
ARCHITECTURE SUMMARY: {architecture_summary}

Write in Markdown with these sections:
## Objectives
3-5 clear, measurable objectives.

## MVP Definition
Core features included in the MVP. Be specific about what ships first.

## Out of Scope
What will NOT be built in this version (prevents scope creep).

## Success Criteria
3-5 measurable criteria for project success.

Be concise. Avoid generic statements.
"""

PLAN_PROMPT = """You are a senior project manager. Create a realistic project plan.

PROJECT: {project_block}
STACK: {decision}
SCOPE SUMMARY: {scope_summary}

Write in Markdown with these sections:
## Phases
3-5 phases. For each: name, duration range (e.g. "3-5 days"), main tasks, deliverable.

## Milestones
| Milestone | Target Date | Description |
Calculate dates from today ({today}).

## Time Estimates
| Task | Phase | Effort Range |
Use ranges like "2-4h" or "1-2 days". Never fixed numbers.

## Risks
| Risk | Probability | Impact | Mitigation |
Probability/Impact: Low / Medium / High. Top 3-5 risks only.

Be realistic. If timeline is tight, say so and adjust scope accordingly.
"""


# ── Helpers for prompt truncation ─────────────────────────────────────────────

def _summarise(text: str, max_chars: int = 800) -> str:
    """Truncate long generated docs to avoid bloating downstream prompts."""
    if not text or len(text) <= max_chars:
        return text or "not available"
    return text[:max_chars] + "\n... [truncated for brevity]"


# ── Nodes ─────────────────────────────────────────────────────────────────────

def architecture_generator(state: DebateState) -> dict:
    """
    Generates architecture_doc.
    Input: project_context + debate1 arguments + judge decision.
    """
    ctx = state["project_context"]

    prompt = ARCHITECTURE_PROMPT.format(
        project_block=_project_block(ctx),
        debate_block=_debate_block(state.get("debate1_arguments", [])),
        decision=state.get("debate1_decision", "not specified"),
        rationale=state.get("debate1_judge_rationale", "not specified"),
    )

    return {
        "architecture_doc": _invoke(prompt),
        "current_node": "architecture_generator",
    }


def scope_generator(state: DebateState) -> dict:
    ctx = state["project_context"]

    prompt = SCOPE_PROMPT.format(
        project_block=_project_block(ctx),
        architecture_summary=_summarise(state.get("architecture_doc", ""), max_chars=600),
    )

    return {
        "scope_doc": _invoke(prompt),
        "current_node": "scope_generator",
    }


def plan_generator(state: DebateState) -> dict:
    """
    Generates project_plan_doc (MVP single-page output).
    Input: project_context + debate1 decision + scope_doc (summarised).
    """
    from datetime import date
    ctx = state["project_context"]

    prompt = PLAN_PROMPT.format(
        project_block=_project_block(ctx),
        decision=state.get("debate1_decision", "not specified"),
        scope_summary=_summarise(state.get("scope_doc", ""), max_chars=600),
        today=date.today().strftime("%Y-%m-%d"),
    )

    return {
        "project_plan_doc": _invoke(prompt),
        "current_node": "plan_generator",
    }