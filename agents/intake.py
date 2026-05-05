# agents/intake.py
import json
import re
import os
from langchain_groq import ChatGroq
from langgraph.types import interrupt
from graph.state import DebateState
from dotenv import load_dotenv

load_dotenv()

# We initialize the LLM. 
# In production it uses environmental variables, in tests it is patched.
def get_llm():
    return ChatGroq(model="llama-3.1-8b-instant")

REQUIRED_FIELDS = ["goal", "timeline", "team_size"]

FIELD_DEFAULTS = {
    "team_size": 1,
    "timeline": "undefined",
    "goal": "undefined project",
}

EXTRACT_PROMPT = """
Extract the following fields from the project description as a JSON object.
If a field is not mentioned, set it to null.

Fields:
- goal: what the project builds (string)
- timeline: how long it takes (string, e.g. "3 weeks", "2 months")
- team_size: number of developers (integer or null)
- constraints: list of explicit constraints mentioned (list of strings, empty list if none)
- stack: technology stack if explicitly mentioned (string or null)
- methodology: delivery approach if explicitly mentioned, e.g. "scrum", "kanban" (string or null)

Example output:
{{"goal": "real-time chat app", "timeline": "3 weeks", "team_size": 2, "constraints": ["must use existing auth system"], "stack": "Firebase", "methodology": null}}

Project description:
{raw_input}

Return ONLY the JSON object. No explanation, no markdown, no code fences.
"""

MAX_INTERRUPT_ATTEMPTS = 3


def _parse_json(text: str) -> dict | None:
    """Try to parse JSON from LLM response, with tolerant fallback."""
    if not isinstance(text, str):
        text = str(text)

    # Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract first JSON object found in the text
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    return None


def _normalize(context: dict) -> dict:
    """Ensure all expected keys exist and types are correct."""
    context.setdefault("goal", None)
    context.setdefault("timeline", None)
    context.setdefault("team_size", None)
    context.setdefault("constraints", [])
    context.setdefault("stack", None)
    context.setdefault("methodology", None)

    # Normalize constraints: always a list
    if context["constraints"] is None:
        context["constraints"] = []

    # Normalize team_size: must be int or None
    if context["team_size"] is not None:
        try:
            context["team_size"] = int(context["team_size"])
        except (ValueError, TypeError):
            context["team_size"] = None

    # Normalize empty strings to None
    for key in ["goal", "timeline", "stack", "methodology"]:
        if context.get(key) == "":
            context[key] = None

    return context


def extract_context(raw_input: str) -> dict:
    """Call the LLM to extract structured project context from free text."""
    llmInst = get_llm()
    response = llmInst.invoke(EXTRACT_PROMPT.format(raw_input=raw_input))

    # Normalize LLM response to string
    text = response.content if hasattr(response, "content") else str(response)
    if isinstance(text, list):
        first = text[0]
        text = first.get("text", str(first)) if isinstance(first, dict) else str(first)

    result = _parse_json(text)
    if result is None:
        result = {}

    return _normalize(result)


def check_missing(context: dict) -> list[str]:
    """Return list of required fields that are missing or null."""
    return [
        f for f in REQUIRED_FIELDS
        if context.get(f) is None or context.get(f) == ""
    ]


def apply_defaults(context: dict, missing: list[str]) -> dict:
    """Apply safe defaults for fields that are still missing after max interrupts."""
    for field in missing:
        context[field] = FIELD_DEFAULTS.get(field, "undefined")
    return context


def detect_user_provided(context: dict) -> dict:
    """Track which fields were explicitly provided by the user."""
    def provided(k: str) -> bool:
        v = context.get(k)
        return v is not None and v != "" and v != "undefined" and v != "undefined project"

    return {
        "goal": provided("goal"),
        "timeline": provided("timeline"),
        "team_size": provided("team_size"),
        "stack": provided("stack"),
        "methodology": provided("methodology"),
    }


def _build_interrupt_message(missing: list[str], attempt: int) -> str:
    """Build a user-friendly clarification message."""
    field_questions = {
        "goal": "What does the project build? (e.g. 'a real-time chat app', 'an e-commerce platform')",
        "timeline": "What is the expected timeline? (e.g. '3 weeks', '2 months')",
        "team_size": "How many developers will work on this? (e.g. '1', '2', 'solo')",
    }

    if attempt == 1:
        header = "I need a bit more context before we start:\n"
    else:
        header = f"I still need the following information (attempt {attempt}/{MAX_INTERRUPT_ATTEMPTS}):\n"

    questions = "\n".join(f"- {field_questions.get(f, f)}" for f in missing)
    return header + questions


def intake_node(state: DebateState) -> dict:
    """
    First node in the pipeline.
    - Extracts structured project_context from raw_input.
    - Interrupts to ask the user for missing required fields (up to MAX_INTERRUPT_ATTEMPTS).
    - Applies safe defaults if fields are still missing after max attempts.
    - Detects which fields were user-provided vs inferred.
    """
    accumulated_input = state["raw_input"]
    context = extract_context(accumulated_input)

    for attempt in range(1, MAX_INTERRUPT_ATTEMPTS + 1):
        missing = check_missing(context)

        if not missing:
            break

        if attempt == MAX_INTERRUPT_ATTEMPTS:
            # Last attempt: apply defaults and continue rather than interrupting again
            context = apply_defaults(context, missing)
            break

        # Interrupt and wait for user response
        answer = interrupt(_build_interrupt_message(missing, attempt))

        # Accumulate all context so the LLM has the full picture on re-extraction
        accumulated_input = accumulated_input + "\n" + answer
        context = extract_context(accumulated_input)

    return {
        "project_context": context,
        "user_provided_fields": detect_user_provided(context),
    }